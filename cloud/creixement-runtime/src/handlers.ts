import { createHash } from "node:crypto";
import type { SupabaseHttp } from "./supabase.js";
import type { JobDefinitionRow } from "./scheduler.js";

export interface JobExecutionRow {
  id: string;
  job_definition_id: string;
  correlation_id: string;
  idempotency_key: string;
  input: Record<string, unknown>;
  attempt: number;
}

export interface HandlerContext {
  db: SupabaseHttp;
  definition: JobDefinitionRow;
  execution: JobExecutionRow;
  runtimeId: string;
}

export interface HandlerResult {
  status: "succeeded" | "blocked";
  output: Record<string, unknown>;
  receipt?: Record<string, unknown>;
}

const digest = (value: unknown): string => createHash("sha256").update(JSON.stringify(value)).digest("hex");

async function chiefPriorities(ctx: HandlerContext): Promise<HandlerResult> {
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    "v_goal_queue_v4?select=goal_key,title,status,execution_mode,blocker_type,priority_score,runnable,blocker&order=priority_score.desc&limit=25",
  );
  return { status: "succeeded", output: { priorities: rows, observedAt: new Date().toISOString() } };
}

async function connectorHealth(ctx: HandlerContext): Promise<HandlerResult> {
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    "v_connector_health?select=slug,name,state,runtime_connection,effective_health,last_sync_attempt_at,last_sync_status,last_error&order=slug.asc",
  );
  const summary = rows.reduce<Record<string, number>>((acc, row) => {
    const key = String(row.effective_health ?? "unknown");
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  return { status: "succeeded", output: { connectors: rows, summary, observedAt: new Date().toISOString() } };
}

async function opportunityRadar(ctx: HandlerContext): Promise<HandlerResult> {
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    "v_opportunity_radar?select=*&actionable=eq.true&order=opportunity_score.desc.nullslast&limit=50",
  );
  return { status: "succeeded", output: { actionable: rows, count: rows.length } };
}

async function evolutionNiches(ctx: HandlerContext): Promise<HandlerResult> {
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    "v_evolution_dashboard?select=*&order=niche.asc,fitness.desc.nullslast",
  );
  return { status: "succeeded", output: { genomes: rows, count: rows.length } };
}

async function counterpartyFreshness(ctx: HandlerContext): Promise<HandlerResult> {
  const staleBefore = new Date(Date.now() - 30 * 86_400_000).toISOString();
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    `counterparties?select=id,entity_key,display_name,status,freshness_at,next_useful_action&or=(freshness_at.is.null,freshness_at.lt.${encodeURIComponent(staleBefore)})&limit=100`,
  );
  return { status: "succeeded", output: { staleCounterparties: rows, count: rows.length, staleBefore } };
}

async function deadLetterTriage(ctx: HandlerContext): Promise<HandlerResult> {
  const [events, jobs] = await Promise.all([
    ctx.db.select<Array<Record<string, unknown>>>(
      "dead_letter_events?select=id,event_key,topic,attempts,final_error,dead_lettered_at,resolution_status&resolution_status=eq.open&order=dead_lettered_at.asc&limit=100",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "job_dead_letters_v5?select=id,job_key,attempts,final_error,dead_lettered_at,resolution_status&resolution_status=eq.open&order=dead_lettered_at.asc&limit=100",
    ),
  ]);
  return {
    status: "succeeded",
    output: { openEventDeadLetters: events, openJobDeadLetters: jobs, count: events.length + jobs.length },
  };
}

async function runtimeReconcile(ctx: HandlerContext): Promise<HandlerResult> {
  const findings = await ctx.db.rpc<Array<Record<string, unknown>>>("creixement_reconcile_runtime_v5", {});
  const readiness = await ctx.db.select<Array<Record<string, unknown>>>("v_runtime_readiness_v5?select=*&limit=1");
  return {
    status: "succeeded",
    output: {
      findings,
      findingCount: findings.length,
      readiness: readiness.at(0) ?? null,
      observedAt: new Date().toISOString(),
    },
  };
}

function numeric(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

async function kaironControlCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const startedAt = new Date().toISOString();
  const selfHeal: Array<Record<string, unknown>> = [];

  try {
    const recovered = await ctx.db.rpc<Array<Record<string, unknown>>>("creixement_reap_expired_leases_v6", {});
    selfHeal.push({ action: "reap_expired_leases", ok: true, result: recovered.at(0) ?? null });
  } catch (error) {
    selfHeal.push({ action: "reap_expired_leases", ok: false, error: error instanceof Error ? error.message : String(error) });
  }

  let reconcile: Array<Record<string, unknown>> = [];
  try {
    reconcile = await ctx.db.rpc<Array<Record<string, unknown>>>("creixement_reconcile_runtime_v5", {});
    selfHeal.push({ action: "reconcile_runtime", ok: true, findings: reconcile.length });
  } catch (error) {
    selfHeal.push({ action: "reconcile_runtime", ok: false, error: error instanceof Error ? error.message : String(error) });
  }

  const [goals, opportunities, healthRows, schedulerRows, providerRows] = await Promise.all([
    ctx.db.select<Array<Record<string, unknown>>>(
      "v_goal_queue_v4?select=goal_key,title,status,execution_mode,blocker_type,priority_score,runnable,blocker&order=priority_score.desc&limit=50",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "v_opportunity_radar?select=*&actionable=eq.true&order=opportunity_score.desc.nullslast&limit=50",
    ),
    ctx.db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
    ctx.db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
    ctx.db.select<Array<Record<string, unknown>>>(
      "v_provider_readiness_v6?select=provider_key,runtime_state,authorized,runtime_ready,operational,last_verified_at&order=provider_key.asc",
    ),
  ]);

  const health = healthRows.at(0) ?? {};
  const scheduler = schedulerRows.at(0) ?? {};
  const autonomousGoals = goals.filter((row) => row.runnable === true && row.execution_mode === "autonomous");
  const ownerEscalations = goals.filter((row) => row.execution_mode === "owner" || row.blocker_type === "owner_policy");
  const externalBlockers = goals.filter((row) => row.blocker_type === "external_account" || row.blocker_type === "connector");
  const operationalProviders = providerRows.filter((row) => row.operational === true);
  const opportunityFocus = opportunities.slice(0, 10).map((row) => ({
    id: row.id ?? row.opportunity_id ?? null,
    title: row.title ?? row.name ?? row.opportunity_key ?? "opportunity",
    score: numeric(row.opportunity_score ?? row.score),
    mode: row.decision_mode ?? null,
  }));
  const goalFocus = autonomousGoals.slice(0, 10).map((row) => ({
    goalKey: row.goal_key,
    title: row.title,
    priority: numeric(row.priority_score),
  }));

  if (numeric(health.open_job_dead_letters) + numeric(health.open_outbox_dead_letters) > 0) {
    selfHeal.push({ action: "triage_dead_letters", ok: true, queuedByExistingJob: true });
  }
  if (numeric(health.enabled_job_connector_blockers) > 0) {
    selfHeal.push({ action: "block_connector_dependent_jobs", ok: true, blockers: numeric(health.enabled_job_connector_blockers) });
  }

  const safetyClean = numeric(health.critical_drift) === 0
    && numeric(health.critical_incidents) === 0
    && numeric(health.open_job_dead_letters) === 0
    && numeric(health.open_outbox_dead_letters) === 0
    && numeric(health.open_handler_circuits) === 0;
  const schedulerReady = scheduler.high_frequency_ready === true;
  const cycleStatus = safetyClean && schedulerReady ? "healthy" : "degraded";

  const cyclePayload = {
    goals: { total: goals.length, autonomousRunnable: autonomousGoals.length, ownerEscalations: ownerEscalations.length, externalBlockers: externalBlockers.length },
    opportunities: { actionable: opportunities.length, top: opportunityFocus },
    providers: { total: providerRows.length, operational: operationalProviders.length },
    runtime: health,
    scheduler,
    reconcileFindings: reconcile.length,
  };

  const inserted = await ctx.db.insert<Array<{ id: string }>>("kairon_control_cycles_v7", {
    correlation_id: ctx.execution.correlation_id,
    idempotency_key: `${ctx.execution.idempotency_key}:kairon-cycle`,
    runtime_id: ctx.runtimeId,
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    status: cycleStatus,
    sensed: cyclePayload,
    priorities: [...goalFocus, ...opportunityFocus].slice(0, 15),
    automatic_actions: selfHeal,
    escalations: ownerEscalations.slice(0, 25),
    self_heal: selfHeal,
    outcome: { safetyClean, schedulerReady, operationalProviders: operationalProviders.length },
  }, "idempotency_key");

  const cycleId = inserted.at(0)?.id ?? null;
  const blockers = [
    ...externalBlockers.slice(0, 20),
    ...(schedulerReady ? [] : [{ blocker: "high_frequency_scheduler_not_verified" }]),
    ...(safetyClean ? [] : [{ blocker: "runtime_safety_not_clean" }]),
  ];

  await ctx.db.patch("kairon_state_v7?singleton=eq.true", {
    mode: cycleStatus === "healthy" ? "autonomous" : "degraded",
    last_cycle_at: new Date().toISOString(),
    last_cycle_status: cycleStatus,
    last_cycle_id: cycleId,
    current_focus: [...goalFocus, ...opportunityFocus].slice(0, 15),
    current_blockers: blockers,
    control_snapshot: cyclePayload,
  });

  return {
    status: "succeeded",
    output: {
      operator: "Kairon",
      cycleId,
      cycleStatus,
      autonomyCeiling: "L2",
      automaticActions: selfHeal,
      ownerEscalations: ownerEscalations.slice(0, 25),
      currentFocus: [...goalFocus, ...opportunityFocus].slice(0, 15),
      blockers,
      sensed: cyclePayload,
    },
    receipt: { operator: "Kairon", runtimeId: ctx.runtimeId, cycleId, status: cycleStatus },
  };
}

const handlers: Record<string, (ctx: HandlerContext) => Promise<HandlerResult>> = {
  "chief.compile_priorities": chiefPriorities,
  "automation.connector_health": connectorHealth,
  "opportunity.refresh_radar": opportunityRadar,
  "evolution.evaluate_niches": evolutionNiches,
  "counterparty.refresh_staleness": counterpartyFreshness,
  "automation.dead_letter_triage": deadLetterTriage,
  "automation.runtime_reconcile": runtimeReconcile,
  "kairon.control_cycle": kaironControlCycle,
};

export async function runHandler(ctx: HandlerContext): Promise<HandlerResult> {
  const handler = handlers[ctx.definition.handler_key];
  if (!handler) {
    return {
      status: "blocked",
      output: {
        reason: "Handler is not implemented in the safe internal runtime. Connector-dependent or consequential execution remains disabled.",
        handlerKey: ctx.definition.handler_key,
      },
    };
  }
  return handler(ctx);
}

export async function writeJobReceipt(ctx: HandlerContext, result: HandlerResult): Promise<string | null> {
  const inputDigest = digest(ctx.execution.input);
  const outputDigest = digest(result.output);
  const receiptKey = `${ctx.execution.idempotency_key}:receipt`;
  const inserted = await ctx.db.insert<Array<{ id: string }>>("execution_receipts", {
    correlation_id: ctx.execution.correlation_id,
    idempotency_key: receiptKey,
    actor_agent: ctx.definition.owner_agent_slug,
    action_class: `job:${ctx.definition.handler_key}`,
    connector_slug: null,
    policy_version: ctx.definition.policy_key ?? "internal-runtime-v7",
    policy_decision: result.status === "succeeded" ? "authorized_internal" : "blocked_unimplemented",
    input_digest: inputDigest,
    output_digest: outputDigest,
    connector_receipt: result.receipt ?? { runtimeId: ctx.runtimeId, jobExecutionId: ctx.execution.id },
    status: result.status === "succeeded" ? "succeeded" : "blocked",
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  }, "idempotency_key");
  return inserted.at(0)?.id ?? null;
}
