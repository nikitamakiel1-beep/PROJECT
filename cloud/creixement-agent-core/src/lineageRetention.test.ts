import test from "node:test";
import assert from "node:assert/strict";
import { sha256, validateLineage } from "./lineage.js";
import { decideRetention } from "./retention.js";

test("lineage validates an acyclic evidence chain", () => {
  const nodes = [
    { id: "s", kind: "source" as const, contentDigest: sha256("source"), createdAt: "2026-09-09T00:00:00Z" },
    { id: "a", kind: "analysis" as const, contentDigest: sha256("analysis"), createdAt: "2026-09-09T00:01:00Z" },
    { id: "r", kind: "receipt" as const, contentDigest: sha256("receipt"), createdAt: "2026-09-09T00:02:00Z" },
  ];
  const result = validateLineage(nodes, [
    { parentId: "s", childId: "a", relation: "derived_from" },
    { parentId: "a", childId: "r", relation: "verified_by" },
  ]);
  assert.equal(result.valid, true);
});

test("lineage cycle is rejected", () => {
  const nodes = [
    { id: "a", kind: "source" as const, contentDigest: sha256("a"), createdAt: "2026-09-09T00:00:00Z" },
    { id: "b", kind: "analysis" as const, contentDigest: sha256("b"), createdAt: "2026-09-09T00:01:00Z" },
  ];
  assert.equal(validateLineage(nodes, [
    { parentId: "a", childId: "b", relation: "derived_from" },
    { parentId: "b", childId: "a", relation: "derived_from" },
  ]).valid, false);
});

test("retention never silently deletes governed evidence", () => {
  const decision = decideRetention({
    id: "e1", classification: "evidence", createdAt: "2020-01-01T00:00:00Z", legalHold: false, governedEvidence: true,
  }, {
    classification: "evidence", retainDays: 365, deleteAllowed: false, requireApprovalForDeletion: true,
  }, new Date("2026-09-09T00:00:00Z"));
  assert.equal(decision.action, "hold");
});
