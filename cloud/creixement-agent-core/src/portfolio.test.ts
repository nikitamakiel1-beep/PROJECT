import test from "node:test";
import assert from "node:assert/strict";
import { allocateAttention, DEFAULT_ATTENTION_POLICY, portfolioPriority } from "./portfolio.js";

const candidates = [
  { id: "e1", bucket: "exploit" as const, opportunityScore: 2, confidence: 0.9, evidenceQuality: 0.9, expectedContributionEur: 500, timeToCashDays: 7, blocked: false, expired: false },
  { id: "e2", bucket: "exploit" as const, opportunityScore: 1.5, confidence: 0.8, evidenceQuality: 0.8, expectedContributionEur: 300, timeToCashDays: 14, blocked: false, expired: false },
  { id: "a1", bucket: "adjacency" as const, opportunityScore: 1, confidence: 0.6, evidenceQuality: 0.7, expectedContributionEur: 800, timeToCashDays: 30, blocked: false, expired: false },
  { id: "x1", bucket: "exploration" as const, opportunityScore: 0.8, confidence: 0.4, evidenceQuality: 0.5, expectedContributionEur: 1500, timeToCashDays: 60, blocked: false, expired: false },
];

test("blocked opportunity receives zero priority", () => {
  assert.equal(portfolioPriority({ ...candidates[0]!, blocked: true }), 0);
});

test("attention allocation preserves bucket budgets when enough candidates exist", () => {
  const result = allocateAttention(candidates, DEFAULT_ATTENTION_POLICY);
  const exploit = result.filter((x) => x.bucket === "exploit").reduce((s, x) => s + x.weight, 0);
  const adjacency = result.filter((x) => x.bucket === "adjacency").reduce((s, x) => s + x.weight, 0);
  const exploration = result.filter((x) => x.bucket === "exploration").reduce((s, x) => s + x.weight, 0);
  assert.ok(Math.abs(exploit - 0.7) < 0.00001);
  assert.ok(Math.abs(adjacency - 0.2) < 0.00001);
  assert.ok(Math.abs(exploration - 0.1) < 0.00001);
});

test("no single candidate breaches the concentration cap", () => {
  const result = allocateAttention(candidates, DEFAULT_ATTENTION_POLICY);
  assert.equal(result.every((x) => x.weight <= 0.4 + 1e-9), true);
});

test("invalid policy totals are rejected", () => {
  assert.throws(() => allocateAttention(candidates, { exploit: 0.8, adjacency: 0.2, exploration: 0.2, maxCandidateShare: 0.5 }));
});
