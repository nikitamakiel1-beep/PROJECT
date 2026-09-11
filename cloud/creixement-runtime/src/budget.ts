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

function zonedParts(date: Date, timeZone: string): Record<string, number> {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  return Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, Number(part.value)]));
}

function offsetMs(date: Date, timeZone: string): number {
  const p = zonedParts(date, timeZone);
  const representedUtc = Date.UTC(p.year!, p.month! - 1, p.day!, p.hour!, p.minute!, p.second!);
  const epochSecond = Math.floor(date.getTime() / 1000) * 1000;
  return representedUtc - epochSecond;
}

export function startOfDayInTimeZone(now: Date, timeZone = "Europe/Madrid"): Date {
  const p = zonedParts(now, timeZone);
  const target = Date.UTC(p.year!, p.month! - 1, p.day!, 0, 0, 0);
  let guess = target;
  for (let i = 0; i < 4; i += 1) {
    const next = target - offsetMs(new Date(guess), timeZone);
    if (Math.abs(next - guess) < 1000) return new Date(next);
    guess = next;
  }
  return new Date(guess);
}

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

  const start = startOfDayInTimeZone(new Date(), "Europe/Madrid");
  const usage = await db.select<BudgetUsageRow[]>(
    `budget_usage_events?budget_id=eq.${encodeURIComponent(budget.id)}&occurred_at=gte.${encodeURIComponent(start.toISOString())}&select=attention_units,agent_runs,experiment_slots,enrichment_records,external_api_cost_eur,external_messages,publications`,
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
    metadata: { runtime: "creixement-cloud-runtime-v6.1", operatingTimeZone: "Europe/Madrid" },
  }, "idempotency_key");

  return { allowed: true, reason: "Global daily agent-run budget reserved.", budgetId: budget.id };
}
