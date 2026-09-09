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
  const rows = await ctx.db.select<Array<Record<string, unknown>>>(
    "dead_letter_events?select=id,event_key,topic,attempts,final_error,dead_lettered_at,resolution_status&resolution_status=eq.open&order=dead_lettered_at.asc&limit=100",
  );
  return { status: "succeeded", output: { openDeadLetters: rows, count: rows.length } };
}

const handlers: Record<string, (ctx: HandlerContext) => Promise<HandlerResult>> = {
  "chief.compile_priorities": chiefPriorities,
  "automation.connector_health": connectorHealth,
  "opportunity.refresh_radar": opportunityRadar,
  "evolution.evaluate_niches": evolutionNiches,
  "counterparty.refresh_staleness": counterpartyFreshness,
  "automation.dead_letter_triage": deadLetterTriage,
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
    policy_version: ctx.definition.policy_key ?? "internal-runtime-v4",
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
