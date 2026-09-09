import test from "node:test";
import assert from "node:assert/strict";
import { assertAcyclicGoals, deriveGoalState, ownerGoals, rankRunnableGoals, type Goal } from "./goals.js";

const base: Goal = {
  id: "g1",
  title: "Sell IVA",
  objective: "Validate paid demand",
  successCondition: "One verified paid external sale",
  status: "proposed",
  dependencies: [],
  ownerAgent: "commercial",
  expectedEconomicValue: 149,
  strategicValue: 0.8,
  urgency: 0.8,
  confidence: 0.7,
  reversibility: 0.9,
  risk: 0.1,
};

test("goal DAG rejects cycles", () => {
  assert.throws(() =>
    assertAcyclicGoals([
      { ...base, id: "a", dependencies: ["b"] },
      { ...base, id: "b", dependencies: ["a"] },
    ]),
  );
});

test("dependency blocks child until succeeded", () => {
  const dependency = { ...base, id: "research", status: "active" as const };
  const child = { ...base, id: "outreach", dependencies: ["research"] };
  assert.equal(deriveGoalState(child, [dependency, child]), "blocked");
  const completed = { ...dependency, status: "succeeded" as const };
  assert.equal(deriveGoalState(child, [completed, child]), "ready");
});

test("explicit blocker keeps a goal out of autonomous runnable queue", () => {
  const blocked = { ...base, id: "credits", status: "blocked" as const, blockerType: "external_account" as const };
  assert.equal(rankRunnableGoals([blocked]).length, 0);
  assert.equal(deriveGoalState(blocked, [blocked]), "blocked");
});

test("owner goals are surfaced separately and never silently auto-run", () => {
  const owner = { ...base, id: "policy", executionMode: "owner" as const };
  assert.equal(rankRunnableGoals([owner]).length, 0);
  assert.equal(ownerGoals([owner])[0]?.id, "policy");
});

test("ranking favors stronger runnable economics without ignoring risk", () => {
  const safe = { ...base, id: "safe", expectedEconomicValue: 500, risk: 0.1 };
  const risky = { ...base, id: "risky", expectedEconomicValue: 550, risk: 0.95 };
  const ranked = rankRunnableGoals([safe, risky]);
  assert.equal(ranked[0]?.goal.id, "safe");
});
