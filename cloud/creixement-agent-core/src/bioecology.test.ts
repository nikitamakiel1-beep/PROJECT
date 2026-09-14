import assert from "node:assert/strict";
import test from "node:test";
import {
  apoptosisArchive,
  asexualBud,
  dormancyDecision,
  homeostasisAdjustment,
  immuneDecision,
  metabolicBudget,
  migrationScore,
  nicheDistance,
  redQueenPressure,
  reinforcePheromone,
  sexualRecombine,
  shouldSpeciate,
  slimeMoldAllocate,
  swarmQuorum,
  symbiosisScore,
  updateSenescence,
  woundHealingPriority,
  type OrganismState,
} from "./bioecology.js";

const organism = (id: string, niche = "market-intelligence"): OrganismState => ({
  id,
  niche,
  generation: 2,
  telomere: 0.7,
  energy: 0.7,
  fitness: 0.6,
  confidence: 0.6,
  novelty: 0.4,
  stress: 0.3,
  dormancy: 0,
  traits: { speed: 0.6, depth: 0.7, channel: "web" },
  parentIds: [],
  status: "active",
});

test("slime mold allocation conserves attention", () => {
  const routes = slimeMoldAllocate([
    { key: "a", nutrient: 0.8, pheromone: 0.5, friction: 0.1, risk: 0.1, capacity: 1 },
    { key: "b", nutrient: 0.4, pheromone: 0.5, friction: 0.2, risk: 0.3, capacity: 1 },
  ]);
  assert.equal(routes.length, 2);
  assert.ok(Math.abs(routes.reduce((sum, route) => sum + route.allocation, 0) - 1) < 1e-9);
  assert.ok(routes[0]!.allocation > routes[1]!.allocation);
});

test("pheromone reinforcement only rewards verified outcomes", () => {
  assert.ok(reinforcePheromone(0.5, { verified: true, success: true, paid: true }) > 0.5);
  assert.ok(reinforcePheromone(0.5, { verified: true, success: false }) < 0.5);
  assert.ok(reinforcePheromone(0.5, { verified: false, success: true, paid: true }) < 0.5);
});

test("swarm quorum requires evidence independence", () => {
  const no = swarmQuorum([
    { source: "a", support: 1, confidence: 0.9, independentEvidence: false },
    { source: "b", support: 1, confidence: 0.9, independentEvidence: true },
  ]);
  assert.equal(no.reached, false);
  const yes = swarmQuorum([
    { source: "a", support: 0.9, confidence: 0.9, independentEvidence: true },
    { source: "b", support: 0.8, confidence: 0.8, independentEvidence: true },
  ]);
  assert.equal(yes.reached, true);
});

test("reproduction preserves niche guard and resets confidence", () => {
  const a = organism("a");
  const b = { ...organism("b"), traits: { speed: 0.9, depth: 0.4, channel: "partners" } };
  const child = sexualRecombine({ parentA: a, parentB: b, traitKeysFromB: ["speed"], childId: "c" });
  assert.equal(child.parentIds.length, 2);
  assert.equal(child.confidence, 0);
  assert.equal(child.status, "experimental");
  const bud = asexualBud(a, "d", { depth: 0.8 });
  assert.deepEqual(bud.parentIds, ["a"]);
  assert.equal(bud.status, "experimental");
  assert.throws(() => sexualRecombine({ parentA: a, parentB: organism("x", "funding"), traitKeysFromB: ["speed"], childId: "z" }));
});

test("red queen and homeostasis respond to pressure", () => {
  const base = organism("a");
  const pressure = redQueenPressure(base, { demand: 0.8, competition: 0.9, volatility: 0.8, evidenceScarcity: 0.5, resourceScarcity: 0.4, failurePressure: 0.7 });
  assert.ok(pressure > 0.5);
  const adjustment = homeostasisAdjustment({ ...base, energy: 0.25, stress: 0.8 }, { demand: 0.8, competition: 0.4, volatility: 0.5, evidenceScarcity: 0.4, resourceScarcity: 0.8, failurePressure: 0.4 });
  assert.ok(adjustment.explorationMultiplier < 1);
  assert.ok(adjustment.recoveryPriority > 0);
});

test("immune memory blocks recurrent high-severity signatures", () => {
  const decision = immuneDecision({ signature: "bad", observations: 6, failures: 5, severity: 0.95 });
  assert.equal(decision.action, "block");
});

test("senescence, dormancy and archive are bounded", () => {
  const senescent = updateSenescence({ ...organism("a"), telomere: 0.08 }, { success: false });
  assert.equal(senescent.status, "senescent");
  const dormancy = dormancyDecision({ ...organism("b"), stress: 0.9, fitness: 0.1, energy: 0.2 }, { demand: 0.1, competition: 0.8, volatility: 0.4, evidenceScarcity: 0.7, resourceScarcity: 0.95, failurePressure: 0.8 });
  assert.equal(dormancy.hibernate, true);
  const archived = apoptosisArchive({ ...organism("c"), telomere: 0.01, fitness: 0.1, confidence: 0.8 }, 5);
  assert.equal(archived.status, "archived");
});

test("speciation and symbiosis use trait distance", () => {
  const a = organism("a");
  const b = { ...organism("b", "funding"), traits: { speed: 0.1, depth: 0.2, channel: "events" } };
  assert.ok(nicheDistance(a, b) > 0.5);
  assert.equal(shouldSpeciate(a, b, 0.5), true);
  assert.ok(symbiosisScore(a, b) >= 0 && symbiosisScore(a, b) <= 1);
});

test("migration, metabolism and wound healing remain bounded", () => {
  const score = migrationScore(
    organism("a"),
    { demand: 0.2, competition: 0.8, volatility: 0.4, evidenceScarcity: 0.5, resourceScarcity: 0.8, failurePressure: 0.6 },
    { demand: 0.9, competition: 0.2, volatility: 0.3, evidenceScarcity: 0.2, resourceScarcity: 0.2, failurePressure: 0.2 },
  );
  assert.ok(score > 0.5);
  const budget = metabolicBudget({ available: 100, maintenanceDemand: 30, executionDemand: 60, explorationDemand: 40 });
  assert.deepEqual(budget, { maintenance: 30, execution: 60, exploration: 10, reserve: 0 });
  const healing = woundHealingPriority({ failedJobs: 4, deadLetters: 2, openCircuits: 1, criticalDrift: 1, staleHeartbeat: true });
  assert.ok(healing > 0.7 && healing <= 1);
});
