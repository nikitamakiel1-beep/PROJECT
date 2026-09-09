import type { RuntimeEnv } from "./env.js";
import type { SupabaseHttp } from "./supabase.js";
import { JOB_DEFINITION_SELECT, type JobDefinitionRow } from "./scheduler.js";

export interface OutboxEventRow {
  id: string;
  correlation_id: string;
  event_key: string;
  topic: string;
  payload: Record<string, unknown>;
  attempts: number;
}

function safeError(error: unknown): Record<string, unknown> {
  const message = error instanceof Error ? error.message : String(error);
  return { code: "outbox_route_failed", message: message.slice(0, 1000) };
}

export async function routeClaimedOutboxEvents(
  db: SupabaseHttp,
  env: RuntimeEnv,
  batchSize = 20,
): Promise<{ claimed: number; routed: number; enqueued: number; failed: number }> {
  const events = await db.rpc<OutboxEventRow[]>("creixement_claim_outbox", {
    worker: env.runtimeId,
    batch_size: Math.max(1, Math.min(batchSize, 50)),
    lease_for_seconds: 120,
  });

  let routed = 0;
  let enqueued = 0;
  let failed = 0;

  for (const event of events) {
    try {
      const definitions = await db.select<JobDefinitionRow[]>(
        `job_definitions?enabled=eq.true&trigger_type=eq.event&event_topic=eq.${encodeURIComponent(event.topic)}&select=${JOB_DEFINITION_SELECT}`,
      );

      for (const definition of definitions) {
        const idempotencyKey = `event:${definition.job_key}:${event.event_key}`;
        const inserted = await db.insert<Array<{ id: string }>>("job_executions", {
          job_definition_id: definition.id,
          correlation_id: event.correlation_id,
          idempotency_key: idempotencyKey,
          trigger_ref: `event:${event.event_key}`,
          scheduled_for: new Date().toISOString(),
          status: "queued",
          input: {
            source: "event_outbox",
            eventId: event.id,
            eventKey: event.event_key,
            topic: event.topic,
            payload: event.payload,
          },
        }, "idempotency_key");
        if (inserted.length > 0) enqueued += 1;
      }

      await db.rpc("creixement_finish_outbox", {
        p_event_id: event.id,
        p_worker: env.runtimeId,
        p_success: true,
        p_error: null,
      });
      routed += 1;
    } catch (error) {
      failed += 1;
      await db.rpc("creixement_finish_outbox", {
        p_event_id: event.id,
        p_worker: env.runtimeId,
        p_success: false,
        p_error: safeError(error),
      });
    }
  }

  return { claimed: events.length, routed, enqueued, failed };
}
