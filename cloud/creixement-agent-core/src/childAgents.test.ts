import test from "node:test";
import assert from "node:assert/strict";
import { authorizeSpawn, canPromoteChild, ensureNoForbiddenAction, type ChildAgentTemplate } from "./childAgents.js";

const template: ChildAgentTemplate = {
  templateKey: "research-swarm",
  parentAllowlist: ["chief-orchestrator", "research"],
  maxAutonomy: "L2",
  allowedCapabilities: ["public_research", "evidence_collection"],
  forbiddenActions: ["external_send", "payment", "rights_bypass"],
  connectorAllowlist: ["market-data", "google-drive"],
  maxRuntimeSeconds: 900,
  maxParallel: 4,
  maxChildDepth: 0,
  minVerifiedSuccessesForPromotion: 3,
  enabled: true,
};

const valid = {
  parentAgent: "chief-orchestrator",
  templateKey: "research-swarm",
  objective: "Verify one market-size claim from approved sources",
  requestedAutonomy: "L2" as const,
  requestedCapabilities: ["public_research", "evidence_collection"],
  requestedConnectors: ["market-data"],
  requestedRuntimeSeconds: 600,
  currentDepth: 0,
  currentlyRunningForTemplate: 0,
};

test("bounded specialist spawn is authorized", () => {
  assert.equal(authorizeSpawn(valid, template).allowed, true);
});

test("unauthorized parent cannot spawn", () => {
  assert.equal(authorizeSpawn({ ...valid, parentAgent: "marketing" }, template).allowed, false);
});

test("capability escalation is rejected", () => {
  assert.equal(authorizeSpawn({ ...valid, requestedCapabilities: ["public_research", "payment"] }, template).allowed, false);
});

test("connector escalation is rejected", () => {
  assert.equal(authorizeSpawn({ ...valid, requestedConnectors: ["gmail"] }, template).allowed, false);
});

test("nested spawning is rejected when depth ceiling is zero", () => {
  assert.equal(authorizeSpawn({ ...valid, currentDepth: 1 }, template).allowed, false);
});

test("persistent promotion requires repeated verified QA-passed success", () => {
  assert.equal(canPromoteChild({ verifiedSuccesses: 2, totalRuns: 4, paidSuccesses: 1, qaPasses: 4, severeFailures: 0, template }).allowed, false);
  assert.equal(canPromoteChild({ verifiedSuccesses: 3, totalRuns: 4, paidSuccesses: 1, qaPasses: 3, severeFailures: 0, template }).allowed, true);
});

test("forbidden child action throws", () => {
  assert.throws(() => ensureNoForbiddenAction("external_send", template));
});
