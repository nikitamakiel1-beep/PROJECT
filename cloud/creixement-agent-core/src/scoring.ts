import type { FitnessObservation, Opportunity, OpportunityDecision } from "./types.js";

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

function normalizedMargin(value?: number): number {
  if (value === undefined || !Number.isFinite(value)) return 0;
  return clamp01(value > 1 ? value / 100 : value);
}

function midpoint(low?: number, high?: number): number {
  const l = Math.max(0, low ?? 0);
  const h = Math.max(0, high ?? l);
  if (l === 0 && h === 0) return 0;
  return (l + Math.max(l, h)) / 2;
}

export interface EconomicSignals {
  revenueMidpointEur: number;
  expectedContributionEur: number;
  revenueSignal: number;
  valueDensitySignal: number;
}

export function economicSignals(opportunity: Opportunity): EconomicSignals {
  const m = opportunity.metrics;
  const revenueMidpointEur = midpoint(m.expectedRevenueLow, m.expectedRevenueHigh);
  const expectedContributionEur = revenueMidpointEur * normalizedMargin(m.expectedContributionMarginPct);
  // Log scaling prevents speculative large ticket estimates from dominating the score.
  const revenueSignal = revenueMidpointEur > 0
    ? clamp01(Math.log1p(revenueMidpointEur) / Math.log1p(10_000)) * clamp01(m.evidenceQuality) * (1 - clamp01(m.uncertainty))
    : 0;
  const contributionPerHour = expectedContributionEur / Math.max(1, m.deliveryEffortHours);
  const valueDensitySignal = clamp01(contributionPerHour / 250) * clamp01(m.evidenceQuality) * (1 - clamp01(m.uncertainty));
  return {
    revenueMidpointEur: Number(revenueMidpointEur.toFixed(2)),
    expectedContributionEur: Number(expectedContributionEur.toFixed(2)),
    revenueSignal: Number(revenueSignal.toFixed(6)),
    valueDensitySignal: Number(valueDensitySignal.toFixed(6)),
  };
}

export function scoreOpportunity(opportunity: Opportunity): number {
  const m = opportunity.metrics;
  const economics = economicSignals(opportunity);
  const score =
    normalizedMargin(m.expectedContributionMarginPct) * 1.0 +
    economics.revenueSignal * 0.35 +
    economics.valueDensitySignal * 0.35 +
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
  const economics = economicSignals(opportunity);
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

  if (economics.expectedContributionEur > 0) {
    rationale.push(`Risk-adjusted economics include an estimated €${economics.expectedContributionEur.toFixed(0)} midpoint contribution before execution costs.`);
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
  const paidSuccessful = paid.filter((o) => (o.revenue ?? 0) > 0 && (o.outcomeScore ?? 0) > 0);

  const revenue = paid.reduce((sum, o) => sum + (o.revenue ?? 0), 0);
  const contribution = paid.reduce(
    (sum, o) => sum + (o.contributionMargin ?? ((o.revenue ?? 0) - (o.directCost ?? 0))),
    0,
  );
  const avgOutcome = verified.length
    ? verified.reduce((sum, o) => sum + clamp01(o.outcomeScore ?? 0), 0) / verified.length
    : 0;

  // Paid successful outcomes dominate; paid failures remain in revenue/cost truth but do not count as success.
  const paidSignal = Math.min(paidSuccessful.length / 3, 1);
  const repeatSignal = Math.min(Math.max(paidSuccessful.length - 1, 0) / 3, 1);
  const marginSignal = revenue > 0 ? clamp01(contribution / Math.max(revenue, 1)) : 0;
  const evidenceSignal = Math.min(verified.length / 5, 1);

  const fitness =
    paidSignal * 0.35 +
    repeatSignal * 0.20 +
    marginSignal * 0.20 +
    avgOutcome * 0.15 +
    evidenceSignal * 0.10;

  const confidence = clamp01(verified.length / 8 + paidSuccessful.length / 8);

  return {
    fitness: Number(fitness.toFixed(6)),
    confidence: Number(confidence.toFixed(6)),
    verifiedObservations: verified.length,
    verifiedSuccesses: positive.length,
    paidSuccesses: paidSuccessful.length,
    verifiedRevenue: Number(revenue.toFixed(2)),
    verifiedContributionMargin: Number(contribution.toFixed(2)),
  };
}
