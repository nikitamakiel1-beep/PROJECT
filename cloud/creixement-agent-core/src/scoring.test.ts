import test from "node:test";
import assert from "node:assert/strict";
import { chooseDecisionMode, scoreOpportunity, summarizeFitness } from "./scoring.js";
import type { Opportunity } from "./types.js";

const strong: Opportunity = {
  id: "opp-1",
  niche: "international-growth",
  productCode: "IVA",
  title: "Qualified SME needs international visibility audit",
  evidence: [],
  status: "detected",
  metrics: {
    expectedContributionMarginPct: 90,
    paidDemandEvidence: 0.6,
    qualifiedDemandEvidence: 0.9,
    automationPotential: 0.8,
    recurringPotential: 0.6,
    strategicFit: 0.9,
    reversibility: 0.9,
    evidenceQuality: 0.9,
    deliveryEffortHours: 2.5,
    timeToCashDays: 7,
    uncertainty: 0.2,
    rightsLegalComplexity: 0.1,
    downsideRisk: 0.1,
  },
};

test("strong existing-product opportunity selects USE", () => {
  const score = scoreOpportunity(strong);
  assert.ok(score > 0.8);
  assert.equal(chooseDecisionMode(strong).mode, "USE");
});

test("high rights risk forces abstention", () => {
  const risky: Opportunity = {
    ...strong,
    id: "opp-2",
    metrics: { ...strong.metrics, rightsLegalComplexity: 0.95 },
  };
  assert.equal(chooseDecisionMode(risky).mode, "ABSTAIN");
});

test("paid verified observations dominate fitness", () => {
  const summary = summarizeFitness([
    { id: "o1", genomeId: "g1", kind: "sale", verified: true, paid: true, revenue: 149, directCost: 5, outcomeScore: 1 },
    { id: "o2", genomeId: "g1", kind: "repeat", verified: true, paid: true, revenue: 149, directCost: 5, outcomeScore: 1 },
    { id: "o3", genomeId: "g1", kind: "reply", verified: true, paid: false, outcomeScore: 0.5 },
  ]);
  assert.equal(summary.paidSuccesses, 2);
  assert.equal(summary.verifiedRevenue, 298);
  assert.ok(summary.fitness > 0.5);
});
