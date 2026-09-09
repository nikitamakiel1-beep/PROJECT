import test from "node:test";
import assert from "node:assert/strict";
import { checkBudget, consumeBudget, zeroBudgetUsage, type ResourceBudget } from "./budgets.js";

const limit: ResourceBudget = {
  attentionUnits: 100,
  agentRuns: 250,
  experimentSlots: 20,
  enrichmentRecords: 100,
  externalApiCostEur: 0,
  externalMessages: 0,
  publications: 0,
};

test("internal usage inside envelope is allowed", () => {
  const decision = checkBudget(limit, zeroBudgetUsage(), { attentionUnits: 10, agentRuns: 3 });
  assert.equal(decision.allowed, true);
  assert.equal(decision.remaining.attentionUnits, 90);
});

test("default budget blocks external spend and messages", () => {
  const decision = checkBudget(limit, zeroBudgetUsage(), { externalApiCostEur: 0.01, externalMessages: 1 });
  assert.equal(decision.allowed, false);
  assert.deepEqual(new Set(decision.exceeded), new Set(["externalApiCostEur", "externalMessages"]));
});

test("consume throws on overrun", () => {
  assert.throws(() => consumeBudget(limit, zeroBudgetUsage(), { publications: 1 }));
});
