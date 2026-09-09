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
    outbox: TickPhase;
    scheduling: TickPhase;
    reconciliation: TickPhase;
    execution: TickPhase;
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
  try {
    await heartbeat(db, env, "healthy", { phase: "tick_started", startedAt });
  } catch {
    // Heartbeat storage failure is reflected by readiness; execution may still produce useful receipts.
  }

  const outbox = await phase(async () => {
    const result = await routeClaimedOutboxEvents(db, env, options.outboxBatchSize ?? 20);
    return { ...result };
  });

  const scheduling = await phase(async () => {
    const result = await enqueueDueCronJobs(db, started, options.lookbackMinutes ?? 10);
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
  const ok = outbox.ok && scheduling.ok && reconciliation.ok && execution.ok && workerFailures === 0 && outboxFailures === 0;
  const completed = new Date();

  try {
    await heartbeat(db, env, ok ? "healthy" : "degraded", {
      phase: "tick_completed",
      completedAt: completed.toISOString(),
      phases: { outbox, scheduling, reconciliation, execution },
    });
  } catch {
    // The readiness endpoint independently exposes heartbeat staleness.
  }

  return {
    ok,
    runtimeId: env.runtimeId,
    version: env.runtimeVersion,
    commitSha: env.commitSha,
    startedAt,
    completedAt: completed.toISOString(),
    elapsedMs: completed.getTime() - started.getTime(),
    phases: { outbox, scheduling, reconciliation, execution },
  };
}
