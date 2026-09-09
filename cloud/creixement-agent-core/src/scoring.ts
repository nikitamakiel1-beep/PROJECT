import type { FitnessObservation, Opportunity, OpportunityDecision } from "./types.js";

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

export function scoreOpportunity(opportunity: Opportunity): number {
  const m = opportunity.metrics;
  const score =
    (m.expectedContributionMarginPct ?? 0) * 0.01 +
    clamp01(m.paidDemandEvidence) * 1.4 +
    clamp01(m.qualifiedDemandEvidence) * 0.8 +
    clamp01(m.automationPotential) * 0.5 +
    clamp01(m.recurringPotential) * 0.8 +
    clamp01(m.strategicFit) * 0.5 +
    clamp01(m.reversibility) * 0.4 +
    clamp01(m.evidenceQuality) * 0.9 -
    Math.min(Math.max(m.deliveryEffortHours, 0) / 40, 1) * 0.5 -
    Math.min(Math.max(m.timeToCashDays, 0) / 90, 1) * 0.4 -
    clamp01(m.uncertainty) * 0.8 -
    clamp01(m.rightsLegalComplexity) * 1.2 -
    clamp01(m.downsideRisk) * 1.2;

  return Number(score.toFixed(6));
}

export function chooseDecisionMode(opportunity: Opportunity): OpportunityDecision {
  const score = scoreOpportunity(opportunity);
  const m = opportunity.metrics;
  const rationale: string[] = [];

  if (m.rightsLegalComplexity >= 0.8 || m.downsideRisk >= 0.8) {
    return {
      mode: "ABSTAIN",
      score,
      rationale: ["Rights/legal complexity or downside risk exceeds the default autonomous threshold."],
    };
  }

  if (m.evidenceQuality < 0.35 || m.uncertainty > 0.75) {
    return {
      mode: "ABSTAIN",
      score,
      rationale: ["Evidence is too weak for execution; gather evidence before committing resources."],
    };
  }

  if (opportunity.productCode && m.automationPotential >= 0.45) {
    rationale.push("A matching existing product/capability is available.");
    if (score >= 0.8) return { mode: "USE", score, rationale };
  }

  if (m.recurringPotential >= 0.65 && m.strategicFit >= 0.6 && score >= 0.6) {
    rationale.push("Recurring potential and strategic fit justify a reusable capability or product variant.");
    return { mode: opportunity.productCode ? "COMBINE" : "BUILD", score, rationale };
  }

  if (score >= 0.35) {
    rationale.push("Opportunity is plausible but should be tested reversibly before broader commitment.");
    return { mode: opportunity.productCode ? "USE" : "BUILD", score, rationale };
  }

  return {
    mode: "ABSTAIN",
    score,
    rationale: ["Expected value is currently too weak relative to effort, risk or uncertainty."],
  };
}

export interface FitnessSummary {
  fitness: number;
  confidence: number;
  verifiedObservations: number;
  verifiedSuccesses: number;
  paidSuccesses: number;
  verifiedRevenue: number;
  verifiedContributionMargin: number;
}

export function summarizeFitness(observations: FitnessObservation[]): FitnessSummary {
  const verified = observations.filter((o) => o.verified);
  const paid = verified.filter((o) => o.paid);
  const positive = verified.filter((o) => (o.outcomeScore ?? 0) > 0);

  const revenue = paid.reduce((sum, o) => sum + (o.revenue ?? 0), 0);
  const contribution = paid.reduce(
    (sum, o) => sum + (o.contributionMargin ?? ((o.revenue ?? 0) - (o.directCost ?? 0))),
    0,
  );
  const avgOutcome = verified.length
    ? verified.reduce((sum, o) => sum + clamp01(o.outcomeScore ?? 0), 0) / verified.length
    : 0;

  // Paid outcomes dominate; verified non-paid observations contribute weaker evidence.
  const paidSignal = Math.min(paid.length / 3, 1);
  const repeatSignal = Math.min(Math.max(paid.length - 1, 0) / 3, 1);
  const marginSignal = revenue > 0 ? clamp01(contribution / Math.max(revenue, 1)) : 0;
  const evidenceSignal = Math.min(verified.length / 5, 1);

  const fitness =
    paidSignal * 0.35 +
    repeatSignal * 0.20 +
    marginSignal * 0.20 +
    avgOutcome * 0.15 +
    evidenceSignal * 0.10;

  const confidence = clamp01(verified.length / 8 + paid.length / 8);

  return {
    fitness: Number(fitness.toFixed(6)),
    confidence: Number(confidence.toFixed(6)),
    verifiedObservations: verified.length,
    verifiedSuccesses: positive.length,
    paidSuccesses: paid.length,
    verifiedRevenue: Number(revenue.toFixed(2)),
    verifiedContributionMargin: Number(contribution.toFixed(2)),
  };
}
