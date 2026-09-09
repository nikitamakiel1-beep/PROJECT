import type { SupabaseHttp } from "./supabase.js";

interface BudgetEnvelopeRow {
  id: string;
  budget_key: string;
  attention_units: number;
  agent_runs: number;
  experiment_slots: number;
  enrichment_records: number;
  external_api_cost_eur: number;
  external_messages: number;
  publications: number;
}

interface BudgetUsageRow {
  attention_units: number;
  agent_runs: number;
  experiment_slots: number;
  enrichment_records: number;
  external_api_cost_eur: number;
  external_messages: number;
  publications: number;
}

const zero = (): BudgetUsageRow => ({
  attention_units: 0, agent_runs: 0, experiment_slots: 0, enrichment_records: 0,
  external_api_cost_eur: 0, external_messages: 0, publications: 0,
});

export async function authorizeAgentRunBudget(db: SupabaseHttp, input: {
  correlationId: string;
  idempotencyKey: string;
  actionClass: string;
  actorAgent: string;
}): Promise<{ allowed: boolean; reason: string; budgetId?: string }> {
  const budgets = await db.select<BudgetEnvelopeRow[]>(
    "budget_envelopes?scope_type=eq.global&scope_key=eq.creixement&period=eq.day&enabled=eq.true&select=id,budget_key,attention_units,agent_runs,experiment_slots,enrichment_records,external_api_cost_eur,external_messages,publications&limit=1",
  );
  const budget = budgets.at(0);
  if (!budget) return { allowed: false, reason: "No active global daily budget envelope exists." };

  const startUtc = new Date();
  startUtc.setUTCHours(0, 0, 0, 0);
  const usage = await db.select<BudgetUsageRow[]>(
    `budget_usage_events?budget_id=eq.${encodeURIComponent(budget.id)}&occurred_at=gte.${encodeURIComponent(startUtc.toISOString())}&select=attention_units,agent_runs,experiment_slots,enrichment_records,external_api_cost_eur,external_messages,publications`,
  );
  const used = usage.reduce<BudgetUsageRow>((acc, row) => ({
    attention_units: acc.attention_units + Number(row.attention_units ?? 0),
    agent_runs: acc.agent_runs + Number(row.agent_runs ?? 0),
    experiment_slots: acc.experiment_slots + Number(row.experiment_slots ?? 0),
    enrichment_records: acc.enrichment_records + Number(row.enrichment_records ?? 0),
    external_api_cost_eur: acc.external_api_cost_eur + Number(row.external_api_cost_eur ?? 0),
    external_messages: acc.external_messages + Number(row.external_messages ?? 0),
    publications: acc.publications + Number(row.publications ?? 0),
  }), zero());

  if (used.agent_runs + 1 > budget.agent_runs) {
    return { allowed: false, reason: "Global daily agent-run budget exhausted.", budgetId: budget.id };
  }

  await db.insert("budget_usage_events", {
    budget_id: budget.id,
    correlation_id: input.correlationId,
    idempotency_key: `budget:${input.idempotencyKey}`,
    action_class: input.actionClass,
    actor_agent: input.actorAgent,
    agent_runs: 1,
    metadata: { runtime: "creixement-cloud-runtime-v4" },
  }, "idempotency_key");

  return { allowed: true, reason: "Global daily agent-run budget reserved.", budgetId: budget.id };
}
