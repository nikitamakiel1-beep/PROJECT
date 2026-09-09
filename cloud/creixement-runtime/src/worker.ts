import type { RuntimeEnv } from "./env.js";
import type { SupabaseHttp } from "./supabase.js";
import { JOB_DEFINITION_SELECT, type JobDefinitionRow } from "./scheduler.js";
import { authorizeAgentRunBudget } from "./budget.js";
import { runHandler, writeJobReceipt, type JobExecutionRow } from "./handlers.js";

interface RuntimeControlDecision {
  allowed: boolean;
  reason: string;
}

interface CircuitDecision {
  allowed: boolean;
  state: string;
  reason: string;
}

async function recordHandlerResult(db: SupabaseHttp, handler: string, success: boolean, error: Record<string, unknown> | null): Promise<void> {
  try {
    await db.rpc("creixement_record_handler_result_v6", {
      p_handler: handler,
      p_success: success,
      p_error: error,
    });
  } catch {
    // Do not mask the primary job outcome if circuit telemetry itself is unavailable.
  }
}

export async function processClaimedJobs(db: SupabaseHttp, env: RuntimeEnv, batchSize = 8): Promise<{
  claimed: number;
  succeeded: number;
  blocked: number;
  failed: number;
}> {
  const claimed = await db.rpc<JobExecutionRow[]>("creixement_claim_jobs", {
    worker: env.runtimeId,
    batch_size: Math.max(1, Math.min(batchSize, 25)),
    lease_for_seconds: 240,
  });
  let succeeded = 0;
  let blocked = 0;
  let failed = 0;

  for (const execution of claimed) {
    const definitions = await db.select<JobDefinitionRow[]>(
      `job_definitions?id=eq.${encodeURIComponent(execution.job_definition_id)}&select=${JOB_DEFINITION_SELECT}&limit=1`,
    );
    const definition = definitions.at(0);
    if (!definition) {
      failed += 1;
      await db.rpc("creixement_finish_job", {
        p_job_id: execution.id,
        p_worker: env.runtimeId,
        p_status: "failed",
        p_output: null,
        p_error: { code: "definition_missing" },
        p_receipt_ref: null,
      });
      continue;
    }

    try {
      const controls = await db.rpc<RuntimeControlDecision[]>("creixement_runtime_control_decision", {
        p_action_class: `job:${definition.handler_key}`,
        p_connector: null,
        p_agent: definition.owner_agent_slug,
      });
      const control = controls.at(0);
      if (!control?.allowed) {
        blocked += 1;
        await db.rpc("creixement_finish_job", {
          p_job_id: execution.id,
          p_worker: env.runtimeId,
          p_status: "blocked",
          p_output: { reason: control?.reason ?? "runtime control denied execution" },
          p_error: null,
          p_receipt_ref: null,
        });
        continue;
      }

      const circuits = await db.rpc<CircuitDecision[]>("creixement_handler_circuit_decision_v6", {
        p_handler: definition.handler_key,
      });
      const circuit = circuits.at(0);
      if (!circuit?.allowed) {
        blocked += 1;
        await db.rpc("creixement_finish_job", {
          p_job_id: execution.id,
          p_worker: env.runtimeId,
          p_status: "blocked",
          p_output: { reason: circuit?.reason ?? "handler circuit denied execution", circuitState: circuit?.state ?? "unknown" },
          p_error: null,
          p_receipt_ref: null,
        });
        continue;
      }

      const budget = await authorizeAgentRunBudget(db, {
        correlationId: execution.correlation_id,
        idempotencyKey: execution.idempotency_key,
        actionClass: `job:${definition.handler_key}`,
        actorAgent: definition.owner_agent_slug,
      });
      if (!budget.allowed) {
        blocked += 1;
        await db.rpc("creixement_finish_job", {
          p_job_id: execution.id,
          p_worker: env.runtimeId,
          p_status: "blocked",
          p_output: { reason: budget.reason },
          p_error: null,
          p_receipt_ref: null,
        });
        continue;
      }

      if (definition.required_connectors.length > 0) {
        const connectorList = definition.required_connectors.map((value) => `"${String(value).replace(/"/g, "")}"`).join(",");
        const rows = await db.select<Array<{ slug: string; effective_health: string }>>(
          `v_connector_health?slug=in.(${encodeURIComponent(connectorList)})&select=slug,effective_health`,
        );
        const ready = new Set(rows.filter((row) => row.effective_health === "runtime_ready").map((row) => row.slug));
        const missing = definition.required_connectors.filter((slug) => !ready.has(slug));
        if (missing.length > 0) {
          blocked += 1;
          await db.rpc("creixement_finish_job", {
            p_job_id: execution.id,
            p_worker: env.runtimeId,
            p_status: "blocked",
            p_output: { reason: "required connectors not runtime-ready", missing },
            p_error: null,
            p_receipt_ref: null,
          });
          continue;
        }
      }

      const result = await runHandler({ db, definition, execution, runtimeId: env.runtimeId });
      const receiptId = await writeJobReceipt({ db, definition, execution, runtimeId: env.runtimeId }, result);
      await db.rpc("creixement_finish_job", {
        p_job_id: execution.id,
        p_worker: env.runtimeId,
        p_status: result.status,
        p_output: result.output,
        p_error: null,
        p_receipt_ref: receiptId,
      });
      if (result.status === "succeeded") {
        succeeded += 1;
        await recordHandlerResult(db, definition.handler_key, true, null);
      } else {
        blocked += 1;
      }
    } catch (error) {
      failed += 1;
      const message = error instanceof Error ? error.message : String(error);
      const failure = { code: "runtime_exception", message: message.slice(0, 1000) };
      await recordHandlerResult(db, definition.handler_key, false, failure);
      await db.rpc("creixement_finish_job", {
        p_job_id: execution.id,
        p_worker: env.runtimeId,
        p_status: "failed",
        p_output: null,
        p_error: failure,
        p_receipt_ref: null,
      });
    }
  }

  return { claimed: claimed.length, succeeded, blocked, failed };
}
