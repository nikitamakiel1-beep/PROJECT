import type { RuntimeEnv } from "./env.js";
import type { SupabaseHttp } from "./supabase.js";
import { routeClaimedOutboxEvents } from "./outbox.js";
import { enqueueDueCronJobs } from "./scheduler.js";
import { processClaimedJobs } from "./worker.js";

export interface TickResult {
  ok: boolean;
  runtimeId: string;
  startedAt: string;
  completedAt: string;
  events: {
    ok: boolean;
    claimed?: number;
    routed?: number;
    enqueued?: number;
    failed?: number;
    error?: string;
  };
  scheduling: {
    ok: boolean;
    examined?: number;
    due?: number;
    enqueued?: number;
    invalidSchedules?: string[];
    error?: string;
  };
  execution: {
    ok: boolean;
    claimed?: number;
    succeeded?: number;
    blocked?: number;
    failed?: number;
    error?: string;
  };
}

function safeError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message.slice(0, 1000);
}

export async function runRuntimeTick(
  db: SupabaseHttp,
  env: RuntimeEnv,
  options: { lookbackMinutes?: number; batchSize?: number; outboxBatchSize?: number; now?: Date } = {},
): Promise<TickResult> {
  const startedAt = new Date().toISOString();
  const now = options.now ?? new Date();
  const lookbackMinutes = Math.max(1, Math.min(options.lookbackMinutes ?? 65, 180));
  const batchSize = Math.max(1, Math.min(options.batchSize ?? 8, 25));
  const outboxBatchSize = Math.max(1, Math.min(options.outboxBatchSize ?? 20, 50));

  let events: TickResult["events"];
  try {
    events = { ok: true, ...(await routeClaimedOutboxEvents(db, env, outboxBatchSize)) };
  } catch (error) {
    events = { ok: false, error: safeError(error) };
  }

  let scheduling: TickResult["scheduling"];
  try {
    scheduling = { ok: true, ...(await enqueueDueCronJobs(db, now, lookbackMinutes)) };
  } catch (error) {
    scheduling = { ok: false, error: safeError(error) };
  }

  let execution: TickResult["execution"];
  try {
    execution = { ok: true, ...(await processClaimedJobs(db, env, batchSize)) };
  } catch (error) {
    execution = { ok: false, error: safeError(error) };
  }

  return {
    ok: events.ok && scheduling.ok && execution.ok,
    runtimeId: env.runtimeId,
    startedAt,
    completedAt: new Date().toISOString(),
    events,
    scheduling,
    execution,
  };
}
