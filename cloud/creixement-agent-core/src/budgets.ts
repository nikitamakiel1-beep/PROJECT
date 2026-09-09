export interface ResourceBudget {
  attentionUnits: number;
  agentRuns: number;
  experimentSlots: number;
  enrichmentRecords: number;
  externalApiCostEur: number;
  externalMessages: number;
  publications: number;
}

export type BudgetKey = keyof ResourceBudget;

export interface BudgetDecision {
  allowed: boolean;
  exceeded: BudgetKey[];
  remaining: ResourceBudget;
}

export const zeroBudgetUsage = (): ResourceBudget => ({
  attentionUnits: 0,
  agentRuns: 0,
  experimentSlots: 0,
  enrichmentRecords: 0,
  externalApiCostEur: 0,
  externalMessages: 0,
  publications: 0,
});

export function addUsage(a: ResourceBudget, b: Partial<ResourceBudget>): ResourceBudget {
  return {
    attentionUnits: a.attentionUnits + (b.attentionUnits ?? 0),
    agentRuns: a.agentRuns + (b.agentRuns ?? 0),
    experimentSlots: a.experimentSlots + (b.experimentSlots ?? 0),
    enrichmentRecords: a.enrichmentRecords + (b.enrichmentRecords ?? 0),
    externalApiCostEur: a.externalApiCostEur + (b.externalApiCostEur ?? 0),
    externalMessages: a.externalMessages + (b.externalMessages ?? 0),
    publications: a.publications + (b.publications ?? 0),
  };
}

export function checkBudget(
  limit: ResourceBudget,
  used: ResourceBudget,
  requested: Partial<ResourceBudget>,
): BudgetDecision {
  const projected = addUsage(used, requested);
  const keys = Object.keys(limit) as BudgetKey[];
  const exceeded = keys.filter((key) => projected[key] > limit[key] + Number.EPSILON);
  const remaining = keys.reduce<ResourceBudget>((acc, key) => {
    acc[key] = Math.max(limit[key] - projected[key], 0);
    return acc;
  }, zeroBudgetUsage());

  return { allowed: exceeded.length === 0, exceeded, remaining };
}

export function consumeBudget(
  limit: ResourceBudget,
  used: ResourceBudget,
  requested: Partial<ResourceBudget>,
): ResourceBudget {
  const decision = checkBudget(limit, used, requested);
  if (!decision.allowed) throw new Error(`Budget exceeded: ${decision.exceeded.join(", ")}`);
  return addUsage(used, requested);
}
