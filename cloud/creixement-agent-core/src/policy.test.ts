import test from "node:test";
import assert from "node:assert/strict";
import { decidePolicy, safeDefaultEnvelopes } from "./policy.js";
import type { PolicyEnvelope, ProposedAction } from "./types.js";

const base: ProposedAction = {
  id: "a1",
  actionClass: "public_research",
  actorAgent: "opportunity_hunter",
  autonomyLevel: "L2",
  reversible: true,
  hasReceiptAdapter: true,
  rightsSatisfied: true,
  consentSatisfied: true,
  externalEffect: "internal",
  payload: { query: "test" },
};

test("bounded research is authorized by the default constitution", () => {
  const decision = decidePolicy(base, safeDefaultEnvelopes());
  assert.equal(decision.allowed, true);
  assert.equal(decision.requiresHumanApproval, false);
});

test("unreceipted capability is unavailable instead of fabricated", () => {
  const decision = decidePolicy({ ...base, hasReceiptAdapter: false }, safeDefaultEnvelopes());
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, false);
});

test("rights bypass is a hard denial and cannot be approval-routed", () => {
  const decision = decidePolicy(
    { ...base, actionClass: "rights_or_consent_bypass", autonomyLevel: "L3" },
    safeDefaultEnvelopes(),
  );
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, false);
});

test("property purchase remains non-delegable", () => {
  const decision = decidePolicy(
    { ...base, actionClass: "property_purchase", autonomyLevel: "L3" },
    safeDefaultEnvelopes(),
  );
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, true);
});

test("external effects require explicit enabling even inside an envelope", () => {
  const decision = decidePolicy({ ...base, externalEffect: "external" }, safeDefaultEnvelopes());
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, true);
});

test("spend is rejected when it exceeds the envelope", () => {
  const envelope: PolicyEnvelope = {
    version: "2.1.0",
    actionClass: "bounded_vendor_call",
    maxAutonomy: "L2",
    enabled: true,
    limits: { maxEstimatedExternalCostEur: 5, maxExternalSpendPerDayEur: 10 },
  };
  const action: ProposedAction = {
    ...base,
    actionClass: "bounded_vendor_call",
    estimatedExternalCostEur: 6,
  };
  const decision = decidePolicy(action, [envelope]);
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, true);
});

test("expired actions must be replanned from fresh evidence", () => {
  const decision = decidePolicy(
    { ...base, expiresAt: "2026-09-09T09:00:00.000Z" },
    safeDefaultEnvelopes(),
    { now: new Date("2026-09-09T10:00:00.000Z") },
  );
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, false);
});
