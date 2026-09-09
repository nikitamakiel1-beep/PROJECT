import test from "node:test";
import assert from "node:assert/strict";
import { decidePolicy, safeDefaultEnvelopes } from "./policy.js";
import type { ProposedAction } from "./types.js";

const base: ProposedAction = {
  id: "a1",
  actionClass: "public_research",
  actorAgent: "opportunity_hunter",
  autonomyLevel: "L2",
  reversible: true,
  hasReceiptAdapter: true,
  rightsSatisfied: true,
  consentSatisfied: true,
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

test("property purchase remains non-delegable", () => {
  const decision = decidePolicy(
    { ...base, actionClass: "property_purchase", autonomyLevel: "L3" },
    safeDefaultEnvelopes(),
  );
  assert.equal(decision.allowed, false);
  assert.equal(decision.requiresHumanApproval, true);
});
