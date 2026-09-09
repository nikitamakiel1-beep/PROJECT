export type AttentionBucket = "exploit" | "adjacency" | "exploration";

export interface PortfolioCandidate {
  id: string;
  bucket: AttentionBucket;
  opportunityScore: number;
  confidence: number;
  evidenceQuality: number;
  expectedContributionEur?: number;
  timeToCashDays?: number;
  blocked: boolean;
  expired: boolean;
}

export interface AttentionPolicy {
  exploit: number;
  adjacency: number;
  exploration: number;
  maxCandidateShare: number;
}

export interface AttentionAllocation {
  id: string;
  bucket: AttentionBucket;
  weight: number;
  priorityScore: number;
  rationale: string;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function validatePolicy(policy: AttentionPolicy): void {
  const total = policy.exploit + policy.adjacency + policy.exploration;
  if (Math.abs(total - 1) > 0.000001) throw new Error("Attention policy must sum to 1");
  if ([policy.exploit, policy.adjacency, policy.exploration, policy.maxCandidateShare].some((v) => v < 0 || v > 1)) {
    throw new Error("Attention policy values must be within 0..1");
  }
}

export function portfolioPriority(candidate: PortfolioCandidate): number {
  if (candidate.blocked || candidate.expired) return 0;
  const evidence = clamp01(candidate.evidenceQuality);
  const confidence = clamp01(candidate.confidence);
  const scoreSignal = Math.max(0, candidate.opportunityScore);
  const contribution = Math.max(0, candidate.expectedContributionEur ?? 0);
  const contributionSignal = contribution > 0 ? Math.min(1, Math.log1p(contribution) / Math.log1p(10_000)) : 0;
  const timeSignal = 1 - Math.min(1, Math.max(0, candidate.timeToCashDays ?? 90) / 180);
  return Number((scoreSignal * (0.55 + 0.45 * evidence) * (0.55 + 0.45 * confidence) + contributionSignal * 0.25 + timeSignal * 0.15).toFixed(6));
}

export function allocateAttention(candidates: PortfolioCandidate[], policy: AttentionPolicy): AttentionAllocation[] {
  validatePolicy(policy);
  const bucketBudget: Record<AttentionBucket, number> = {
    exploit: policy.exploit,
    adjacency: policy.adjacency,
    exploration: policy.exploration,
  };
  const allocations: AttentionAllocation[] = [];

  for (const bucket of ["exploit", "adjacency", "exploration"] as const) {
    const eligible = candidates
      .filter((candidate) => candidate.bucket === bucket && !candidate.blocked && !candidate.expired)
      .map((candidate) => ({ candidate, priority: portfolioPriority(candidate) }))
      .filter((item) => item.priority > 0)
      .sort((a, b) => b.priority - a.priority || a.candidate.id.localeCompare(b.candidate.id));

    if (eligible.length === 0) continue;
    const totalPriority = eligible.reduce((sum, item) => sum + item.priority, 0);
    let remaining = bucketBudget[bucket];

    // First pass caps concentration so one speculative item cannot absorb the bucket.
    const provisional = eligible.map((item) => ({
      ...item,
      rawWeight: bucketBudget[bucket] * (item.priority / totalPriority),
    }));
    for (const item of provisional) {
      const weight = Math.min(item.rawWeight, policy.maxCandidateShare, remaining);
      if (weight <= 0) continue;
      remaining -= weight;
      allocations.push({
        id: item.candidate.id,
        bucket,
        weight,
        priorityScore: item.priority,
        rationale: `${bucket} allocation from evidence/confidence-adjusted opportunity value`,
      });
    }

    // Redistribute any cap-created remainder over candidates with spare capacity.
    let guard = 0;
    while (remaining > 1e-9 && guard < 100) {
      guard += 1;
      const spare = allocations.filter((a) => a.bucket === bucket && a.weight < policy.maxCandidateShare - 1e-9);
      if (spare.length === 0) break;
      const add = remaining / spare.length;
      let used = 0;
      for (const item of spare) {
        const delta = Math.min(add, policy.maxCandidateShare - item.weight);
        item.weight += delta;
        used += delta;
      }
      if (used <= 1e-12) break;
      remaining -= used;
    }
  }

  return allocations
    .map((item) => ({ ...item, weight: Number(item.weight.toFixed(6)) }))
    .sort((a, b) => b.weight - a.weight || b.priorityScore - a.priorityScore);
}

export const DEFAULT_ATTENTION_POLICY: AttentionPolicy = {
  exploit: 0.70,
  adjacency: 0.20,
  exploration: 0.10,
  maxCandidateShare: 0.40,
};
