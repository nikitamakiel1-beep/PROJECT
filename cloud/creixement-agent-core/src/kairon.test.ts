import test from "node:test";
import assert from "node:assert/strict";
import { allocateAttention, compileSelfHealPlan, decideKaironAction } from "./kairon.js";

const budget = {
  remainingExternalCostEur: 0,
  remainingAgentRuns: 100,
  remainingExperiments: 10,
  remainingEnrichments: 50,
};

const base = {
  id: "x",
  actionClass: "internal_reversible_crm_write",
  requestedAutonomy: "L2" as const,
  reversible: true,
  externalEffect: false,
  connectorReady: true,
  rightsPermitted: true,
  receiptCapable: true,
  estimatedExternalCostEur: 0,
  expectedValue: 100,
  confidence: 0.8,
  strategicFit: 0.9,
  risk: 0.2,
  uncertainty: 0.2,
};

test("Kairon operates bounded reversible L2 actions", () => {
  assert.equal(decideKaironAction(base, budget).decision, "operate");
});

test("Kairon escalates constitutionally owner-only actions", () => {
  const result = decideKaironAction({ ...base, actionClass: "property_offers_or_purchases" }, budget);
  assert.equal(result.decision, "escalate");
  assert.equal(result.requiresOwner, true);
});

test("Kairon abstains when rights are blocked", () => {
  assert.equal(decideKaironAction({ ...base, rightsPermitted: false }, budget).decision, "abstain");
});

test("Kairon does not auto-run unreceipted L2 actions", () => {
  assert.equal(decideKaironAction({ ...base, receiptCapable: false }, budget).decision, "abstain");
});

test("attention keeps exploration alive while prioritising exploit", () => {
  const selected = allocateAttention([
    { id: "e1", lane: "exploit", score: 9 },
    { id: "e2", lane: "exploit", score: 8 },
    { id: "e3", lane: "exploit", score: 7 },
    { id: "e4", lane: "exploit", score: 6 },
    { id: "e5", lane: "exploit", score: 5 },
    { id: "e6", lane: "exploit", score: 4 },
    { id: "e7", lane: "exploit", score: 3 },
    { id: "a1", lane: "adjacency", score: 9 },
    { id: "a2", lane: "adjacency", score: 8 },
    { id: "x1", lane: "exploration", score: 10 },
  ], 10);
  assert.equal(selected.length, 10);
  assert.equal(selected.some((x) => x.id === "x1"), true);
});

test("self-heal plan reacts to stale runtime and blockers", () => {
  const plan = compileSelfHealPlan({
    staleHeartbeat: true,
    criticalDrift: 0,
    criticalIncidents: 0,
    openDeadLetters: 2,
    openCircuits: 1,
    connectorBlockers: 3,
  });
  assert.equal(plan.includes("degrade_readiness"), true);
  assert.equal(plan.includes("triage_dead_letters"), true);
  assert.equal(plan.includes("block_connector_jobs"), true);
});
