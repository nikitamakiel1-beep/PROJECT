import test from "node:test";
import assert from "node:assert/strict";
import { compileKaironSupervisorCycle, type KaironSupervisorInput } from "./kaironSupervisor.js";

const baseWorkItem = {
  id: "economic-1",
  actionClass: "internal_reversible_crm_write",
  requestedAutonomy: "L2" as const,
  reversible: true,
  externalEffect: false,
  connectorReady: true,
  rightsPermitted: true,
  receiptCapable: true,
  estimatedExternalCostEur: 0,
  expectedValue: 500,
  confidence: 0.9,
  strategicFit: 0.9,
  risk: 0.2,
  uncertainty: 0.2,
};

const organism = {
  id: "kairon-supervisor",
  niche: "runtime",
  generation: 9,
  telomere: 0.8,
  energy: 0.8,
  fitness: 0.8,
  confidence: 0.9,
  novelty: 0.7,
  stress: 0.25,
  dormancy: 0,
  traits: {},
  parentIds: [],
  status: "active" as const,
};

const authorityGraph = [
  { key: "internal", actionClass: "internal_reversible_write", maxAutonomy: "L2" as const, forbidden: false, next: [] },
  { key: "external", actionClass: "external_boundary", maxAutonomy: "L1" as const, forbidden: false, next: ["payment"] },
  { key: "payment", actionClass: "payment_authority", maxAutonomy: "L3" as const, forbidden: true, next: [] },
];

const healthyCanaries = Array.from({ length: 5 }, (_, index) => ({
  id: `canary-${index}`,
  passed: true,
  receipted: true,
  deterministicReplay: true,
  digestMatch: true,
}));

function input(overrides: Partial<KaironSupervisorInput> = {}): KaironSupervisorInput {
  return {
    candidates: [{
      workItem: baseWorkItem,
      domain: "economic",
      lane: "exploit",
      authorityNodeKey: "internal",
      routeKey: "crm",
      evidence: [
        { key: "e1", source: "crm", truthLevel: "governed_source_evidence", confidence: 0.95, support: 0.9, independent: true },
        { key: "e2", source: "runtime", truthLevel: "executed_connector_receipt", confidence: 0.95, support: 0.9, independent: true },
      ],
      quorumRequired: true,
      immuneSignature: null,
    }],
    budget: { remainingExternalCostEur: 0, remainingAgentRuns: 100, remainingExperiments: 20, remainingEnrichments: 100 },
    authorityGraph,
    routes: [{ key: "crm", nutrient: 0.9, pheromone: 0.8, friction: 0.1, risk: 0.1, capacity: 1 }],
    organism,
    environment: { demand: 0.8, competition: 0.4, volatility: 0.3, evidenceScarcity: 0.2, resourceScarcity: 0.2, failurePressure: 0.1 },
    immunePatterns: [],
    runtimeHealth: { staleHeartbeat: false, criticalDrift: 0, criticalIncidents: 0, openDeadLetters: 0, openCircuits: 0, connectorBlockers: 0, failedJobs: 0 },
    resourceDemand: { available: 100, maintenanceDemand: 10, executionDemand: 50, explorationDemand: 20 },
    canaries: healthyCanaries,
    priorEconomicL2State: { state: "on", consecutiveAbove: 2, consecutiveBelow: 0 },
    economicEvidenceReady: true,
    ...overrides,
  };
}

test("Kairon supervisor can operate bounded economic L2 only when all gates hold", () => {
  const result = compileKaironSupervisorCycle(input());
  assert.equal(result.economicL2.enabled, true);
  assert.equal(result.decisions[0]?.decision, "operate");
  assert.equal(result.decisions[0]?.authoritySafe, true);
  assert.equal(result.decisions[0]?.quorumReached, true);
  assert.equal(result.proofDigest.length, 64);
});

test("truth floor downgrades L2 operation instead of inventing confidence", () => {
  const base = input();
  base.candidates[0]!.evidence = [
    { key: "h", source: "model", truthLevel: "hypothesis", confidence: 0.99, support: 0.99, independent: true },
    { key: "n", source: "narrative", truthLevel: "generated_narrative", confidence: 0.99, support: 0.99, independent: true },
  ];
  const result = compileKaironSupervisorCycle(base);
  assert.equal(result.decisions[0]?.decision, "recommend");
  assert.match(result.decisions[0]?.reasons.join(" ") ?? "", /Truth floor/);
});

test("forbidden authority traversal dominates economic value", () => {
  const base = input();
  base.candidates[0]!.authorityNodeKey = "external";
  base.candidates[0]!.workItem = { ...baseWorkItem, id: "external-1", externalEffect: true };
  const result = compileKaironSupervisorCycle(base);
  assert.equal(result.decisions[0]?.decision, "escalate");
  assert.equal(result.decisions[0]?.requiresOwner, true);
  assert.equal(result.decisions[0]?.authoritySafe, false);
});

test("immune memory block forces abstention", () => {
  const base = input({
    immunePatterns: [{ signature: "repeat-failure", observations: 5, failures: 4, severity: 0.95 }],
  });
  base.candidates[0]!.immuneSignature = "repeat-failure";
  const result = compileKaironSupervisorCycle(base);
  assert.equal(result.decisions[0]?.decision, "abstain");
  assert.equal(result.decisions[0]?.immuneDisposition, "block");
});

test("failed deterministic canary evidence closes economic L2", () => {
  const badCanaries = healthyCanaries.map((canary, index) => index === 0 ? { ...canary, digestMatch: false } : canary);
  const result = compileKaironSupervisorCycle(input({ canaries: badCanaries }));
  assert.equal(result.economicL2.enabled, false);
  assert.equal(result.decisions[0]?.decision, "recommend");
});

test("runtime injury raises wound-healing priority and preserves recovery actions", () => {
  const result = compileKaironSupervisorCycle(input({
    runtimeHealth: {
      staleHeartbeat: true,
      criticalDrift: 2,
      criticalIncidents: 1,
      openDeadLetters: 4,
      openCircuits: 2,
      connectorBlockers: 1,
      failedJobs: 5,
    },
  }));
  assert.ok(result.ecology.woundHealingPriority >= 0.8);
  assert.equal(result.recoveryPlan.includes("degrade_readiness"), true);
  assert.equal(result.recoveryPlan.includes("triage_dead_letters"), true);
  assert.equal(result.economicL2.enabled, false);
});

test("supervisory proof digest is deterministic for the same stable input", () => {
  const first = compileKaironSupervisorCycle(input());
  const second = compileKaironSupervisorCycle(input());
  assert.equal(first.proofDigest, second.proofDigest);
});
