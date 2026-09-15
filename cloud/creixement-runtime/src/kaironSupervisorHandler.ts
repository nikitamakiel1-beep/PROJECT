import { createHash } from "node:crypto";
import { runHandler as runLegacyHandler, type HandlerContext, type HandlerResult } from "./handlers.js";

function numeric(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, child]) => `${JSON.stringify(key)}:${canonical(child)}`)
    .join(",")}}`;
}

function digest(value: unknown): string {
  return createHash("sha256").update(canonical(value)).digest("hex");
}

export interface KaironRuntimeSupervisorInput {
  legacy: Record<string, unknown>;
  proof: Record<string, unknown>;
  ecology: Record<string, unknown>;
  courts: Record<string, unknown>;
  health: Record<string, unknown>;
}

export interface KaironRuntimeSupervisorSnapshot {
  version: "9.3";
  autonomyCeiling: "L2";
  truth: {
    schedulerExecutionProved: boolean;
    runtimeSafetyClean: boolean;
    configurationCountsAsExecution: false;
  };
  authority: {
    legacyEconomicL2Allowed: boolean;
    supervisedEconomicL2Open: boolean;
    courtEvidenceReady: boolean;
    consequentialBoundary: "L3-owner-only";
  };
  adaptation: {
    mode: "recovery" | "challenge" | "balanced";
    redQueenPressure: number;
    woundHealingPriority: number;
    activePopulation: number;
    activeNiches: number;
    meanFitness: number;
    meanTelomere: number;
    verifiedCanaries: number;
    failedCourts: number;
  };
  invariants: readonly string[];
  proofDigest: string;
}

export function compileSupervisorySnapshot(input: KaironRuntimeSupervisorInput): KaironRuntimeSupervisorSnapshot {
  const schedulerExecutionProved = input.proof.cloudflare_scheduler_verified === true;
  const runtimeSafetyClean = input.legacy.safetyClean === true
    || (input.legacy.sensed as Record<string, unknown> | undefined)?.preflight != null
      && ((input.legacy.sensed as Record<string, unknown>).preflight as Record<string, unknown>).safety_clean === true;
  const legacyEconomicL2Allowed = input.legacy.economicL2Allowed === true;
  const totalCourts = numeric(input.courts.total_courts);
  const failedCourts = numeric(input.courts.failed_courts);
  const verifiedCanaries = numeric(input.courts.verified_canaries);
  const courtEvidenceReady = totalCourts > 0 && failedCourts === 0;

  const openDeadLetters = numeric(input.health.open_job_dead_letters) + numeric(input.health.open_outbox_dead_letters);
  const openCircuits = numeric(input.health.open_handler_circuits);
  const criticalDrift = numeric(input.health.critical_drift);
  const healthyRuntimes = numeric(input.health.healthy_runtime_instances);
  const woundHealingPriority = clamp(
    0.16 * Math.min(openDeadLetters, 4)
      + 0.2 * Math.min(openCircuits, 3)
      + 0.25 * Math.min(criticalDrift, 2)
      + (healthyRuntimes > 0 ? 0 : 0.35),
  );

  const redQueenPressure = clamp(numeric(input.ecology.recent_red_queen_pressure));
  const supervisedEconomicL2Open = legacyEconomicL2Allowed
    && schedulerExecutionProved
    && runtimeSafetyClean
    && courtEvidenceReady
    && woundHealingPriority < 0.8;
  const mode = woundHealingPriority >= 0.5 ? "recovery" : redQueenPressure >= 0.65 ? "challenge" : "balanced";

  const stable = {
    version: "9.3",
    autonomyCeiling: "L2",
    truth: { schedulerExecutionProved, runtimeSafetyClean, configurationCountsAsExecution: false },
    authority: {
      legacyEconomicL2Allowed,
      supervisedEconomicL2Open,
      courtEvidenceReady,
      consequentialBoundary: "L3-owner-only",
    },
    adaptation: {
      mode,
      redQueenPressure,
      woundHealingPriority,
      activePopulation: numeric(input.ecology.active_population),
      activeNiches: numeric(input.ecology.active_niches),
      meanFitness: clamp(numeric(input.ecology.mean_fitness)),
      meanTelomere: clamp(numeric(input.ecology.mean_telomere)),
      verifiedCanaries,
      failedCourts,
    },
    invariants: [
      "truth hierarchy is monotonic",
      "configuration is not execution proof",
      "external/consequential authority remains L3 owner-only",
      "evolution cannot mutate rights, consent, secrets, payment, contract, property or irreversible deletion authority",
      "archive lineage and evidence; never silently erase it",
    ],
  } as const;

  return { ...stable, proofDigest: digest(stable) };
}

export async function kaironSupervisedControlCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const legacy = await runLegacyHandler(ctx);

  let proof: Record<string, unknown> = {};
  let ecology: Record<string, unknown> = {};
  let courts: Record<string, unknown> = {};
  let health: Record<string, unknown> = {};
  try {
    const [proofRows, ecologyRows, courtRows, healthRows] = await Promise.all([
      ctx.db.select<Array<Record<string, unknown>>>("v_runtime_proof_summary_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_bioecology_dashboard_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_conway_court_status_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
    ]);
    proof = proofRows.at(0) ?? {};
    ecology = ecologyRows.at(0) ?? {};
    courts = courtRows.at(0) ?? {};
    health = healthRows.at(0) ?? {};
  } catch (error) {
    const unavailable = {
      version: "9.3",
      autonomyCeiling: "L2",
      status: "supervisory-evidence-unavailable",
      reason: error instanceof Error ? error.message : String(error),
      failClosed: true,
    };
    return {
      status: legacy.status,
      output: { ...legacy.output, supervisor: unavailable },
      receipt: { ...(legacy.receipt ?? {}), supervisor: unavailable },
    };
  }

  const supervisor = compileSupervisorySnapshot({ legacy: legacy.output, proof, ecology, courts, health });

  try {
    await ctx.db.insert("kairon_learning_events_v7", {
      event_key: `${ctx.execution.idempotency_key}:supervisor-v9.3`,
      niche: "runtime",
      subject_ref: `job_execution:${ctx.execution.id}`,
      truth_level: "governed_source_evidence",
      signal: supervisor.authority.supervisedEconomicL2Open ? 1 : 0,
      observation: supervisor,
      evidence_refs: [
        `job_execution:${ctx.execution.id}`,
        "view:v_runtime_proof_summary_v9",
        "view:v_bioecology_dashboard_v9",
        "view:v_conway_court_status_v9",
        "view:v_operating_health_v6",
      ],
    }, "event_key");

    await ctx.db.patch("kairon_state_v7?singleton=eq.true", {
      control_snapshot: {
        legacy: legacy.output.sensed ?? legacy.output,
        supervisor,
      },
    });
  } catch {
    // Supervisory persistence must never turn an otherwise safe maintenance cycle
    // into an unsafe retry loop. The receipt still carries the computed snapshot.
  }

  return {
    status: legacy.status,
    output: {
      ...legacy.output,
      supervisor,
    },
    receipt: {
      ...(legacy.receipt ?? {}),
      supervisorDigest: supervisor.proofDigest,
      supervisedEconomicL2Open: supervisor.authority.supervisedEconomicL2Open,
      adaptationMode: supervisor.adaptation.mode,
    },
  };
}
