import type { RuntimeEnv } from "./env.js";
import type { SupabaseHttp } from "./supabase.js";
import type { JobDefinitionRow } from "./scheduler.js";
import { authorizeAgentRunBudget } from "./budget.js";
import { runHandler, writeJobReceipt, type JobExecutionRow } from "./handlers.js";

interface RuntimeControlDecision {
  allowed: boolean;
  reason: string;
}

export async function processClaimedJobs(db: SupabaseHttp, env: RuntimeEnv, batchSize = 8): Promise<{
  claimed: number;
  succeeded: number;
  blocked: number;
  failed: number;
}> {
  const claimed = await db.rpc<JobExecutionRow[]>("creixement_claim_jobs", {
    worker: env.runtimeId,
    batch_size: batchSize,
    lease_for_seconds: 240,
  });
  let succeeded = 0;
  let blocked = 0;
  let failed = 0;

  for (const execution of claimed) {
    const definitions = await db.select<JobDefinitionRow[]>(
      `job_definitions?id=eq.${encodeURIComponent(execution.job_definition_id)}&select=id,job_key,trigger_type,schedule_expr,timezone,handler_key,owner_agent_slug,autonomy_level,policy_key,required_connectors,enabled,max_attempts&limit=1`,
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
      if (result.status === "succeeded") succeeded += 1;
      else blocked += 1;
    } catch (error) {
      failed += 1;
      const message = error instanceof Error ? error.message : String(error);
      await db.rpc("creixement_finish_job", {
        p_job_id: execution.id,
        p_worker: env.runtimeId,
        p_status: "failed",
        p_output: null,
        p_error: { code: "runtime_exception", message: message.slice(0, 1000) },
        p_receipt_ref: null,
      });
    }
  }

  return { claimed: claimed.length, succeeded, blocked, failed };
}
