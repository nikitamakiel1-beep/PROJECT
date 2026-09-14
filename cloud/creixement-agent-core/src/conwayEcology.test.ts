import assert from "node:assert/strict";
import test from "node:test";
import {
  auditorOfAuditors,
  canaryPromotion,
  deterministicAuthorityTraversal,
  deterministicSkillIdentity,
  hardVetoSelection,
  sanitizePublicProjection,
  updateHysteresis,
  type HysteresisState,
} from "./conwayEcology.js";

test("authority traversal deterministically exposes forbidden paths", () => {
  const nodes = [
    { key: "start", actionClass: "research", maxAutonomy: "L1" as const, forbidden: false, next: ["safe", "pay"] },
    { key: "safe", actionClass: "draft", maxAutonomy: "L2" as const, forbidden: false, next: [] },
    { key: "pay", actionClass: "payment", maxAutonomy: "L3" as const, forbidden: false, next: [] },
  ];
  const first = deterministicAuthorityTraversal(nodes, "start");
  const second = deterministicAuthorityTraversal(nodes, "start");
  assert.equal(first.digest, second.digest);
  assert.equal(first.forbiddenPaths.length, 1);
  assert.equal(first.safePaths.length, 1);
});

test("hard veto dominates seductive expected value", () => {
  const result = hardVetoSelection([
    { key: "unsafe", expectedValue: 1000000, confidence: 1, strategicFit: 1, risk: 0.1, hardVeto: true, vetoReasons: ["payment authority"] },
    { key: "safe", expectedValue: 100, confidence: 0.8, strategicFit: 0.9, risk: 0.1, hardVeto: false, vetoReasons: [] },
  ]);
  assert.equal(result.selected?.key, "safe");
  assert.equal(result.vetoed[0]?.key, "unsafe");
});

test("hysteresis requires dwell and avoids flapping", () => {
  const config = { enterThreshold: 0.7, exitThreshold: 0.4, dwellEnter: 2, dwellExit: 2 };
  let state: HysteresisState = { state: "off", consecutiveAbove: 0, consecutiveBelow: 0 };
  state = updateHysteresis(state, 0.8, config);
  assert.equal(state.state, "candidate");
  state = updateHysteresis(state, 0.82, config);
  assert.equal(state.state, "on");
  state = updateHysteresis(state, 0.35, config);
  assert.equal(state.state, "degrading");
  state = updateHysteresis(state, 0.7, config);
  assert.equal(state.state, "on");
});

test("capability promotion requires fully verified canaries", () => {
  const good = Array.from({ length: 5 }, (_, index) => ({ id: String(index), passed: true, receipted: true, deterministicReplay: true, digestMatch: true }));
  assert.equal(canaryPromotion(good).promotable, true);
  const bad = [...good.slice(0, 4), { id: "bad", passed: true, receipted: false, deterministicReplay: true, digestMatch: true }];
  assert.equal(canaryPromotion(bad).promotable, false);
});

test("auditor-of-auditors and public projection are stable", () => {
  const projection = sanitizePublicProjection({ skill: "x", timestamp: "volatile", nested: { latencyMs: 42, stable: true } });
  assert.deepEqual(projection, { nested: { stable: true }, skill: "x" });
  const a = auditorOfAuditors({ a: 1, b: 2 }, { b: 2, a: 1 });
  assert.equal(a.match, true);
  const id1 = deterministicSkillIdentity({ skillKey: "tectum", version: "1", contract: { b: 2, a: 1 } });
  const id2 = deterministicSkillIdentity({ skillKey: "tectum", version: "1", contract: { a: 1, b: 2, timestamp: "ignored" } });
  assert.equal(id1.digest, id2.digest);
});
