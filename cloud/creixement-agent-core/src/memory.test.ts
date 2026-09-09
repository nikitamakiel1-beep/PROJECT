import test from "node:test";
import assert from "node:assert/strict";
import { maySupersede, resolvePreferredKnowledge, type KnowledgeItem } from "./memory.js";

const verified: KnowledgeItem = {
  id: "k1",
  namespace: "crm",
  subject: "deal:1",
  predicate: "revenue",
  object: 149,
  truthLevel: "verified_external_outcome",
  sourceRefs: ["receipt:1"],
  observedAt: "2026-09-09T10:00:00Z",
  authority: 1,
  freshness: 1,
  confidence: 1,
  sensitivity: "internal",
  rightsStatus: "permitted",
};

const narrative: KnowledgeItem = {
  ...verified,
  id: "k2",
  object: 999,
  truthLevel: "generated_narrative",
  sourceRefs: [],
  observedAt: "2026-09-09T11:00:00Z",
};

test("higher truth beats newer generated narrative", () => {
  const preferred = resolvePreferredKnowledge([narrative, verified], new Date("2026-09-09T12:00:00Z"));
  assert.equal(preferred?.id, "k1");
  assert.equal(maySupersede(narrative, verified), false);
});

test("blocked-rights knowledge is excluded", () => {
  const blocked = { ...verified, id: "k3", rightsStatus: "blocked" as const };
  const preferred = resolvePreferredKnowledge([blocked], new Date("2026-09-09T12:00:00Z"));
  assert.equal(preferred, null);
});
