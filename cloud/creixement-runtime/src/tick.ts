import type { RuntimeEnv } from "./env.js";
import type { SupabaseHttp } from "./supabase.js";
import { routeClaimedOutboxEvents } from "./outbox.js";
import { enqueueDueCronJobs } from "./scheduler.js";
import { processClaimedJobs } from "./worker.js";

export interface TickPhase {
  ok: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export interface RuntimeTickResult {
  ok: boolean;
  runtimeId: string;
  version: string;
  commitSha: string | null;
  startedAt: string;
  completedAt: string;
  elapsedMs: number;
  phases: {
    heartbeatStart: TickPhase;
    maintenance: TickPhase;
    outbox: TickPhase;
    scheduling: TickPhase;
    reconciliation: TickPhase;
    execution: TickPhase;
    heartbeatEnd: TickPhase;
  };
}

function safeError(error: unknown): string {
  return (error instanceof Error ? error.message : String(error)).slice(0, 1000);
}

async function heartbeat(
  db: SupabaseHttp,
  env: RuntimeEnv,
  status: "healthy" | "degraded",
  metadata: Record<string, unknown>,
): Promise<void> {
  await db.rpc("creixement_record_heartbeat_v5", {
    p_runtime_id: env.runtimeId,
    p_version: env.runtimeVersion,
    p_commit_sha: env.commitSha,
    p_status: status,
    p_metadata: { ...metadata, environment: env.environment },
  });
}

async function heartbeatPhase(
  db: SupabaseHttp,
  env: RuntimeEnv,
  stage: "start" | "end",
  status: "healthy" | "degraded",
  metadata: Record<string, unknown>,
): Promise<TickPhase> {
  try {
    await heartbeat(db, env, status, metadata);
    return { ok: true, data: { stage, persisted: true } };
  } catch (error) {
    const message = safeError(error);
    console.error(JSON.stringify({
      event: "creixement.runtime.heartbeat_failure",
      stage,
      runtimeId: env.runtimeId,
      version: env.runtimeVersion,
      commitSha: env.commitSha,
      message,
      observedAt: new Date().toISOString(),
    }));
    return { ok: false, error: message };
  }
}

async function phase(fn: () => Promise<Record<string, unknown>>): Promise<TickPhase> {
  try {
    return { ok: true, data: await fn() };
  } catch (error) {
    return { ok: false, error: safeError(error) };
  }
}

export async function runRuntimeTick(
  db: SupabaseHttp,
  env: RuntimeEnv,
  options: { now?: Date; lookbackMinutes?: number; jobBatchSize?: number; outboxBatchSize?: number } = {},
): Promise<RuntimeTickResult> {
  const started = options.now ?? new Date();
  const startedAt = started.toISOString();
  const heartbeatStart = await heartbeatPhase(db, env, "start", "healthy", { phase: "tick_started", startedAt });

  const maintenance = await phase(async () => {
    const rows = await db.rpc<Array<Record<string, unknown>>>("creixement_reap_expired_leases_v6", {});
    return rows.at(0) ?? { job_requeued: 0, job_dead_lettered: 0, outbox_requeued: 0, outbox_dead_lettered: 0 };
  });

  const outbox = await phase(async () => {
    const result = await routeClaimedOutboxEvents(db, env, options.outboxBatchSize ?? 20);
    return { ...result };
  });

  const scheduling = await phase(async () => {
    const result = await enqueueDueCronJobs(db, started, options.lookbackMinutes ?? 1500);
    return { ...result };
  });

  const reconciliation = await phase(async () => {
    const findings = await db.rpc<Array<Record<string, unknown>>>("creixement_reconcile_runtime_v5", {});
    return { findings: findings.length, details: findings.slice(0, 50) };
  });

  const execution = await phase(async () => {
    const result = await processClaimedJobs(db, env, options.jobBatchSize ?? 8);
    return { ...result };
  });

  const workerFailures = Number(execution.data?.failed ?? 0);
  const outboxFailures = Number(outbox.data?.failed ?? 0);
  const baseOk = heartbeatStart.ok && maintenance.ok && outbox.ok && scheduling.ok && reconciliation.ok && execution.ok
    && workerFailures === 0 && outboxFailures === 0;
  const completed = new Date();

  const heartbeatEnd = await heartbeatPhase(db, env, "end", baseOk ? "healthy" : "degraded", {
    phase: "tick_completed",
    completedAt: completed.toISOString(),
    phases: { heartbeatStart, maintenance, outbox, scheduling, reconciliation, execution },
  });
  const ok = baseOk && heartbeatEnd.ok;

  return {
    ok,
    runtimeId: env.runtimeId,
    version: env.runtimeVersion,
    commitSha: env.commitSha,
    startedAt,
    completedAt: completed.toISOString(),
    elapsedMs: completed.getTime() - started.getTime(),
    phases: { heartbeatStart, maintenance, outbox, scheduling, reconciliation, execution, heartbeatEnd },
  };
}
