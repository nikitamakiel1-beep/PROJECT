import { CronExpressionParser } from "cron-parser";
import type { SupabaseHttp } from "./supabase.js";

export interface JobDefinitionRow {
  id: string;
  job_key: string;
  trigger_type: "cron" | "event" | "manual" | "condition";
  schedule_expr: string | null;
  timezone: string;
  handler_key: string;
  owner_agent_slug: string;
  autonomy_level: "L0" | "L1" | "L2" | "L3";
  policy_key: string | null;
  required_connectors: string[];
  enabled: boolean;
  max_attempts: number;
}

function lastCronOccurrence(expression: string, timezone: string, now: Date): Date | null {
  try {
    const interval = CronExpressionParser.parse(expression, { currentDate: now, tz: timezone });
    return interval.prev().toDate();
  } catch {
    return null;
  }
}

export async function enqueueDueCronJobs(db: SupabaseHttp, now = new Date(), lookbackMinutes = 6): Promise<{
  examined: number;
  due: number;
  enqueued: number;
  invalidSchedules: string[];
}> {
  const definitions = await db.select<JobDefinitionRow[]>(
    "job_definitions?enabled=eq.true&trigger_type=eq.cron&select=id,job_key,trigger_type,schedule_expr,timezone,handler_key,owner_agent_slug,autonomy_level,policy_key,required_connectors,enabled,max_attempts",
  );
  const floor = now.getTime() - lookbackMinutes * 60_000;
  let due = 0;
  let enqueued = 0;
  const invalidSchedules: string[] = [];

  for (const definition of definitions) {
    if (!definition.schedule_expr) continue;
    const occurrence = lastCronOccurrence(definition.schedule_expr, definition.timezone, now);
    if (!occurrence) {
      invalidSchedules.push(definition.job_key);
      continue;
    }
    if (occurrence.getTime() < floor || occurrence.getTime() > now.getTime()) continue;
    due += 1;
    const bucket = occurrence.toISOString().slice(0, 16);
    const idempotencyKey = `cron:${definition.job_key}:${bucket}`;
    const inserted = await db.insert<Array<{ id: string }>>("job_executions", {
      job_definition_id: definition.id,
      idempotency_key: idempotencyKey,
      trigger_ref: `cron:${definition.schedule_expr}`,
      scheduled_for: occurrence.toISOString(),
      status: "queued",
      input: { source: "vercel-cron-tick", occurrence: occurrence.toISOString() },
    }, "idempotency_key");
    if (inserted.length > 0) enqueued += 1;
  }

  return { examined: definitions.length, due, enqueued, invalidSchedules };
}
