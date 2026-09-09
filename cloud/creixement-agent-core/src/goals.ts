export type GoalStatus =
  | "proposed"
  | "ready"
  | "active"
  | "blocked"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "expired";

export interface GoalBudget {
  attentionUnits?: number;
  agentRuns?: number;
  enrichmentRecords?: number;
  externalApiCostEur?: number;
  externalMessages?: number;
  publications?: number;
}

export interface Goal {
  id: string;
  title: string;
  objective: string;
  successCondition: string;
  status: GoalStatus;
  parentGoalId?: string;
  dependencies: string[];
  ownerAgent: string;
  expectedEconomicValue: number;
  strategicValue: number;
  urgency: number;
  confidence: number;
  reversibility: number;
  risk: number;
  blocker?: string;
  expiresAt?: string;
  budget?: GoalBudget;
}

export interface GoalPriorityWeights {
  expectedEconomicValue: number;
  strategicValue: number;
  urgency: number;
  confidence: number;
  reversibility: number;
  risk: number;
  blockedDependencyPenalty: number;
}

export const defaultGoalPriorityWeights: GoalPriorityWeights = {
  expectedEconomicValue: 1,
  strategicValue: 0.6,
  urgency: 0.5,
  confidence: 0.7,
  reversibility: 0.3,
  risk: -0.8,
  blockedDependencyPenalty: -2,
};

const clamp01 = (n: number): number => Math.max(0, Math.min(1, n));

export function assertAcyclicGoals(goals: Goal[]): void {
  const byId = new Map(goals.map((goal) => [goal.id, goal]));
  const visiting = new Set<string>();
  const visited = new Set<string>();

  const visit = (id: string): void => {
    if (visited.has(id)) return;
    if (visiting.has(id)) throw new Error(`Goal dependency cycle detected at ${id}`);
    const goal = byId.get(id);
    if (!goal) return;
    visiting.add(id);
    for (const dependency of goal.dependencies) {
      if (!byId.has(dependency)) throw new Error(`Unknown goal dependency: ${dependency}`);
      visit(dependency);
    }
    visiting.delete(id);
    visited.add(id);
  };

  for (const goal of goals) visit(goal.id);
}

export function isGoalRunnable(goal: Goal, goals: Goal[], now = new Date()): boolean {
  if (!(goal.status === "proposed" || goal.status === "ready" || goal.status === "blocked")) return false;
  if (goal.expiresAt && new Date(goal.expiresAt).getTime() <= now.getTime()) return false;
  const byId = new Map(goals.map((candidate) => [candidate.id, candidate]));
  return goal.dependencies.every((dependencyId) => byId.get(dependencyId)?.status === "succeeded");
}

export function scoreGoal(
  goal: Goal,
  goals: Goal[],
  weights: GoalPriorityWeights = defaultGoalPriorityWeights,
): number {
  const blockedDependencies = goal.dependencies.filter(
    (dependencyId) => goals.find((candidate) => candidate.id === dependencyId)?.status !== "succeeded",
  ).length;

  const normalizedEconomicValue = Math.tanh(Math.max(goal.expectedEconomicValue, 0) / 1000);
  const score =
    normalizedEconomicValue * weights.expectedEconomicValue +
    clamp01(goal.strategicValue) * weights.strategicValue +
    clamp01(goal.urgency) * weights.urgency +
    clamp01(goal.confidence) * weights.confidence +
    clamp01(goal.reversibility) * weights.reversibility +
    clamp01(goal.risk) * weights.risk +
    blockedDependencies * weights.blockedDependencyPenalty;

  return Number(score.toFixed(6));
}

export function rankRunnableGoals(
  goals: Goal[],
  weights: GoalPriorityWeights = defaultGoalPriorityWeights,
  now = new Date(),
): Array<{ goal: Goal; score: number }> {
  assertAcyclicGoals(goals);
  return goals
    .filter((goal) => isGoalRunnable(goal, goals, now))
    .map((goal) => ({ goal, score: scoreGoal(goal, goals, weights) }))
    .sort((a, b) => b.score - a.score || a.goal.id.localeCompare(b.goal.id));
}

export function deriveGoalState(goal: Goal, goals: Goal[], now = new Date()): GoalStatus {
  if (["succeeded", "failed", "cancelled", "expired"].includes(goal.status)) return goal.status;
  if (goal.expiresAt && new Date(goal.expiresAt).getTime() <= now.getTime()) return "expired";
  if (isGoalRunnable(goal, goals, now)) return goal.status === "active" ? "active" : "ready";
  return "blocked";
}
