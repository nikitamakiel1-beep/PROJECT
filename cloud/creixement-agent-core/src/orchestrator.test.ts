import test from "node:test";
import assert from "node:assert/strict";
import { AutonomousEconomicLoop } from "./orchestrator.js";
import { safeDefaultEnvelopes } from "./policy.js";
import type { ExecutionReceipt, Opportunity, OpportunitySignal, ProposedAction } from "./types.js";

const signal: OpportunitySignal = {
  id: "sig-1",
  sourceType: "test",
  signalType: "qualified_need",
  title: "Need",
  rightsStatus: "permitted",
  observedAt: "2026-09-09T10:00:00.000Z",
  evidence: [],
  payload: {},
};

const opportunity: Opportunity = {
  id: "opp-1",
  niche: "international-growth",
  productCode: "IVA",
  title: "Visibility need",
  status: "detected",
  evidence: [],
  metrics: {
    expectedRevenueLow: 149,
    expectedRevenueHigh: 149,
    expectedContributionMarginPct: 90,
    paidDemandEvidence: 0.6,
    qualifiedDemandEvidence: 0.8,
    automationPotential: 0.8,
    recurringPotential: 0.4,
    strategicFit: 0.9,
    reversibility: 0.9,
    evidenceQuality: 0.9,
    deliveryEffortHours: 2,
    timeToCashDays: 5,
    uncertainty: 0.2,
    rightsLegalComplexity: 0.1,
    downsideRisk: 0.1,
  },
};

const research: ProposedAction = {
  id: "a1",
  actionClass: "public_research",
  actorAgent: "opportunity_hunter",
  autonomyLevel: "L2",
  reversible: true,
  hasReceiptAdapter: true,
  rightsSatisfied: true,
  consentSatisfied: true,
  externalEffect: "internal",
  payload: { q: "acme" },
};

function deps(action: ProposedAction, existing: ExecutionReceipt | null = null) {
  const saved: ExecutionReceipt[] = [];
  const approvals: unknown[] = [];
  let executeCount = 0;
  return {
    saved,
    approvals,
    get executeCount() { return executeCount; },
    value: {
      verifier: { verify: async () => ({ accepted: true, signal }) },
      compiler: { compile: async () => ({ ...opportunity, metrics: { ...opportunity.metrics } }) },
      opportunities: { save: async () => undefined },
      planner: { plan: async () => [action] },
      executor: {
        execute: async () => {
          executeCount += 1;
          return { status: "succeeded" as const, output: { ok: true }, connectorReceipt: { provider: "test" } };
        },
      },
      receipts: {
        save: async (r: ExecutionReceipt) => { saved.push(r); },
        getByIdempotencyKey: async () => existing,
      },
      approvals: { queue: async (x: unknown) => { approvals.push(x); } },
      resultVerifier: {
        verify: async () => ({ verified: false, reason: "Connector execution is not yet a business outcome", truthLevel: "executed_connector_receipt" as const }),
      },
      policyEnvelopes: safeDefaultEnvelopes(),
    },
  };
}

test("authorized action executes once and receipt does not claim business-outcome verification", async () => {
  const d = deps(research);
  const loop = new AutonomousEconomicLoop(d.value);
  const result = await loop.processSignal(signal);
  assert.equal(d.executeCount, 1);
  assert.equal(result.receipts.length, 1);
  assert.equal(result.receipts[0]?.status, "succeeded");
  assert.equal(result.receipts[0]?.verified, false);
});

test("existing terminal receipt deduplicates external effect", async () => {
  const existing: ExecutionReceipt = {
    correlationId: "old",
    idempotencyKey: "existing",
    actorAgent: "opportunity_hunter",
    actionClass: "public_research",
    policyVersion: "2.1.0",
    policyDecision: "authorized",
    inputDigest: "x",
    status: "succeeded",
    startedAt: "2026-09-09T09:00:00.000Z",
    completedAt: "2026-09-09T09:00:01.000Z",
  };
  const d = deps(research, existing);
  const loop = new AutonomousEconomicLoop(d.value);
  const result = await loop.processSignal(signal);
  assert.equal(d.executeCount, 0);
  assert.equal(result.receipts[0], existing);
});

test("human-gated action is queued and never executed", async () => {
  const purchase: ProposedAction = { ...research, actionClass: "property_purchase", autonomyLevel: "L3", externalEffect: "external" };
  const d = deps(purchase);
  const loop = new AutonomousEconomicLoop(d.value);
  const result = await loop.processSignal(signal);
  assert.equal(d.executeCount, 0);
  assert.equal(result.receipts[0]?.status, "queued");
  assert.equal(d.approvals.length, 1);
});
