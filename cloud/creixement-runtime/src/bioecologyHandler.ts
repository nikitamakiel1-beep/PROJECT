import type { HandlerContext, HandlerResult } from "./handlers.js";

function numeric(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function avg(values: number[]): number {
  return values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;
}

export async function bioecologyCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const startedAt = new Date().toISOString();
  const syncRows = await ctx.db.rpc<Array<Record<string, unknown>>>("creixement_sync_commercial_genomes_v9", {});
  const sync = syncRows.at(0) ?? {};
  const [genomes, organisms, niches, trails, immune, healthRows, preflightRows] = await Promise.all([
    ctx.db.select<Array<Record<string, unknown>>>(
      "commercial_genomes?select=id,niche,generation,telomere,fitness,confidence,status,verified_observations,verified_successes,paid_successes&limit=500",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "ecology_organisms_v9?select=organism_key,niche_key,generation,telomere,energy,fitness,confidence,novelty,stress,dormancy,status&limit=1000",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "ecology_niches_v9?select=niche_key,state,resource_level,demand,competition,volatility,evidence_scarcity,failure_pressure,selection_pressure&limit=100",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "ecology_trails_v9?select=trail_key,from_ref,to_ref,niche_key,nutrient,pheromone,friction,risk,capacity,verified_reinforcements,verified_failures&limit=250",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "ecology_immune_memory_v9?select=signature,observations,failures,severity,disposition,last_seen_at&limit=250",
    ),
    ctx.db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
    ctx.db.rpc<Array<Record<string, unknown>>>("creixement_kairon_preflight_v8", {}),
  ]);

  const health = healthRows.at(0) ?? {};
  const preflight = preflightRows.at(0) ?? {};
  const telomeres = organisms.map((row) => numeric(row.telomere));
  const energies = organisms.map((row) => numeric(row.energy));
  const fitness = organisms.map((row) => numeric(row.fitness));
  const activeNiches = niches.filter((row) => row.state !== "retired");
  const redQueenByNiche = activeNiches.map((row) => {
    const competition = clamp(numeric(row.competition));
    const volatility = clamp(numeric(row.volatility));
    const failures = clamp(numeric(row.failure_pressure));
    const scarcity = clamp(numeric(row.evidence_scarcity));
    const pressure = clamp(0.35 * competition + 0.25 * volatility + 0.25 * failures + 0.15 * scarcity);
    return { niche: row.niche_key, pressure };
  });

  const routed = trails.map((row) => {
    const nutrient = Math.max(0.0001, numeric(row.nutrient));
    const pheromone = Math.max(0.0001, numeric(row.pheromone));
    const friction = 1 + Math.max(0, numeric(row.friction));
    const risk = 1 + 2 * clamp(numeric(row.risk));
    const capacity = Math.max(0.0001, numeric(row.capacity));
    const desirability = (Math.pow(nutrient, 1.35) * Math.pow(pheromone, 0.8) * Math.sqrt(capacity)) / (friction * risk);
    return { trailKey: row.trail_key, to: row.to_ref, niche: row.niche_key, desirability };
  });
  const routeTotal = routed.reduce((sum, route) => sum + route.desirability, 0);
  const routing = routed
    .map((route) => ({ ...route, allocation: routeTotal > 0 ? route.desirability / routeTotal : 0 }))
    .sort((a, b) => b.allocation - a.allocation)
    .slice(0, 25);

  const openDeadLetters = numeric(health.open_job_dead_letters) + numeric(health.open_outbox_dead_letters);
  const woundHealingPriority = clamp(
    0.16 * Math.min(openDeadLetters, 4)
      + 0.2 * Math.min(numeric(health.open_handler_circuits), 3)
      + 0.25 * Math.min(numeric(health.critical_drift), 2)
      + (numeric(health.healthy_runtime_instances) > 0 ? 0 : 0.35),
  );

  const archiveCandidates = genomes
    .filter((row) => row.status !== "champion" && row.status !== "archived" && numeric(row.verified_observations) >= 3)
    .filter((row) => numeric(row.telomere) <= 0.05 || (numeric(row.fitness) <= 0.12 && numeric(row.confidence) >= 0.5))
    .slice(0, 25)
    .map((row) => ({ genomeId: row.id, niche: row.niche, reason: "senescence_or_persistently_low_verified_fitness" }));

  const mutationCandidates = genomes
    .filter((row) => row.status === "active" || row.status === "experimental")
    .map((row) => {
      const nichePressure = redQueenByNiche.find((entry) => entry.niche === row.niche)?.pressure ?? 0;
      const noveltyDeficit = clamp(1 - Math.min(1, numeric(row.generation) / 12));
      const pressure = clamp(0.75 * nichePressure + 0.25 * noveltyDeficit);
      return { genomeId: row.id, niche: row.niche, pressure };
    })
    .filter((row) => row.pressure >= 0.55)
    .sort((a, b) => b.pressure - a.pressure)
    .slice(0, 25);

  const immuneState = {
    blocked: immune.filter((row) => row.disposition === "block").length,
    challenged: immune.filter((row) => row.disposition === "challenge").length,
    allowed: immune.filter((row) => row.disposition === "allow").length,
  };

  const actions = [
    ...(archiveCandidates.length > 0 ? [{ action: "archive_candidates", mode: "recommend_only", candidates: archiveCandidates }] : []),
    ...(mutationCandidates.length > 0 ? [{ action: "mutation_candidates", mode: "experiment_only", candidates: mutationCandidates }] : []),
    ...(woundHealingPriority >= 0.5 ? [{ action: "runtime_wound_healing", mode: "delegate_existing_safe_handlers", priority: woundHealingPriority }] : []),
  ];

  const status = preflight.maintenance_allowed === true ? (woundHealingPriority >= 0.8 ? "degraded" : "healthy") : "blocked";
  const cycleKey = `${ctx.execution.idempotency_key}:bioecology`;
  const inserted = await ctx.db.insert<Array<{ id: string }>>("ecology_cycles_v9", {
    cycle_key: cycleKey,
    correlation_id: ctx.execution.correlation_id,
    runtime_id: ctx.runtimeId,
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    status,
    population_count: organisms.length,
    active_niches: activeNiches.length,
    senescent_count: organisms.filter((row) => row.status === "senescent").length,
    hibernating_count: organisms.filter((row) => row.status === "hibernating").length,
    archived_count: organisms.filter((row) => row.status === "archived").length,
    champion_count: organisms.filter((row) => row.status === "champion").length,
    mean_telomere: avg(telomeres),
    mean_energy: avg(energies),
    mean_fitness: avg(fitness),
    red_queen_pressure: avg(redQueenByNiche.map((entry) => entry.pressure)),
    wound_healing_priority: woundHealingPriority,
    homeostasis: {
      maintenanceAllowed: preflight.maintenance_allowed === true,
      economicL2Allowed: preflight.economic_l2_allowed === true,
      safetyClean: preflight.safety_clean === true,
      schedulerReady: preflight.scheduler_ready === true,
      populationSync: sync,
    },
    routing,
    quorum: { mode: "evidence_independence_required", threshold: 0.67, minIndependentSources: 2 },
    immune_state: immuneState,
    actions,
    evidence_refs: [`job_execution:${ctx.execution.id}`, `runtime:${ctx.runtimeId}`],
  }, "cycle_key");

  return {
    status: status === "blocked" ? "blocked" : "succeeded",
    output: {
      mechanism: "conway-inspired-bioecology-v9",
      cycleId: inserted.at(0)?.id ?? null,
      status,
      population: organisms.length,
      populationSync: sync,
      activeNiches: activeNiches.length,
      meanTelomere: avg(telomeres),
      meanEnergy: avg(energies),
      meanFitness: avg(fitness),
      redQueenPressure: avg(redQueenByNiche.map((entry) => entry.pressure)),
      woundHealingPriority,
      routing,
      immuneState,
      actions,
      constitutionalBoundary: "rights, consent, secrets, payment, contract, property commitment and irreversible-action authority are not evolvable",
    },
    receipt: {
      runtimeId: ctx.runtimeId,
      cycleKey,
      mechanism: "bioecology-v9",
      policy: "internal-runtime-v9",
    },
  };
}
