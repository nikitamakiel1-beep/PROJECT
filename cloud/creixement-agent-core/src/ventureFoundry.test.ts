import test from "node:test";
import assert from "node:assert/strict";
import {
  compileVentureCandidate,
  mayAutoPromoteToOperating,
  selectVentureCandidates,
  ventureOpportunityScore,
  type VentureOpportunity,
} from "./ventureFoundry.js";

const base: VentureOpportunity = {
  id: "9bf4c0d0-3fca-4a23-b1bb-a9d8f5cc8d77",
  title: "Evidence-backed workflow product",
  niche: "operations-intelligence",
  productCode: "OPS-X",
  status: "qualified",
  truthLevel: "governed_source_evidence",
  evidenceRefs: ["source:1", "source:2"],
  evidenceQuality: 0.82,
  confidence: 0.74,
  strategicFit: 0.8,
  automationPotential: 0.75,
  recurringPotential: 0.65,
  reversibility: 0.9,
  rightsLegalComplexity: 0.2,
  downsideRisk: 0.25,
  uncertainty: 0.3,
  expectedRevenueLowEur: 1200,
  expectedRevenueHighEur: 3500,
  deliveryEffortHours: 18,
  timeToCashDays: 28,
};

const openContext = {
  economicL2Open: true,
  experimentSlotsRemaining: 4,
  projectSlotsRemaining: 2,
  now: "2026-09-16T08:00:00.000Z",
};

test("governed evidence can reach reversible incubation only with supervised L2 open", () => {
  const result = compileVentureCandidate(base, openContext);
  assert.equal(result.decision, "incubate");
  assert.equal(result.stage, "incubating");
  assert.equal(result.autonomy, "L2");
  assert.equal(result.requiresOwner, false);
  assert.equal(result.gates.evidenceGoverned, true);
});

test("closed economic gate prevents incubation without deleting the hypothesis", () => {
  const result = compileVentureCandidate(base, { ...openContext, economicL2Open: false });
  assert.equal(result.decision, "experiment");
  assert.equal(result.stage, "experiment");
  assert.equal(result.gates.economicL2Open, false);
});

test("low-authority hypothesis cannot be incubated even at high confidence", () => {
  const result = compileVentureCandidate({
    ...base,
    truthLevel: "hypothesis",
    evidenceQuality: 0.99,
    confidence: 0.99,
  }, openContext);
  assert.notEqual(result.decision, "incubate");
  assert.equal(result.gates.evidenceGoverned, false);
});

test("no evidence references means Kairon does not create a candidate", () => {
  const result = compileVentureCandidate({ ...base, evidenceRefs: [] }, openContext);
  assert.equal(result.decision, "ignore");
});

test("expired or blocked source fails closed", () => {
  assert.equal(compileVentureCandidate({ ...base, blocker: "rights unresolved" }, openContext).decision, "ignore");
  assert.equal(compileVentureCandidate({ ...base, expiresAt: "2026-09-15T00:00:00.000Z" }, openContext).decision, "ignore");
});

test("selection is deterministic and prioritises stronger decisions", () => {
  const results = selectVentureCandidates([
    { ...base, id: "aaaaaaaa-1111-1111-1111-111111111111", title: "A", evidenceQuality: 0.7 },
    { ...base, id: "bbbbbbbb-1111-1111-1111-111111111111", title: "B", truthLevel: "evidence_backed_inference", evidenceQuality: 0.5, confidence: 0.5 },
  ], openContext);
  assert.equal(results.length, 2);
  assert.equal(results[0]?.decision, "incubate");
  assert.equal(results[1]?.decision, "experiment");
});

test("venture score penalises risk and rights complexity", () => {
  const strong = ventureOpportunityScore(base);
  const risky = ventureOpportunityScore({ ...base, downsideRisk: 1, rightsLegalComplexity: 1, uncertainty: 1 });
  assert.ok(strong > risky);
});

test("foundry cannot self-declare an operating business from forecasts alone", () => {
  assert.equal(mayAutoPromoteToOperating({ verifiedExternalOutcomes: 0, executedReceipts: 10, ownerApproved: true }), false);
  assert.equal(mayAutoPromoteToOperating({ verifiedExternalOutcomes: 1, executedReceipts: 1, ownerApproved: false }), false);
  assert.equal(mayAutoPromoteToOperating({ verifiedExternalOutcomes: 1, executedReceipts: 1, ownerApproved: true }), true);
});
