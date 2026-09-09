import test from "node:test";
import assert from "node:assert/strict";
import { compareGoldenCase, invalidateDigestBoundApprovals, tectumReleaseDecision } from "./tectumGovernance.js";

test("golden case passes inside numeric tolerance", () => {
  const result = compareGoldenCase(
    {
      caseRef: "golden-1",
      scenario: "Traditional",
      referenceModelVersion: "workbook-v5",
      cloudModelVersion: "cloud-v1",
      reference: { grossYieldPct: 7.5, netYieldPct: 5.3, units: 1 },
      cloud: { grossYieldPct: 7.50001, netYieldPct: 5.29999, units: 1 },
    },
    [
      { key: "grossYieldPct", absolute: 0.001, required: true },
      { key: "netYieldPct", absolute: 0.001, required: true },
      { key: "units", required: true },
    ],
  );
  assert.equal(result.passed, true);
});

test("golden case blocks on required mismatch", () => {
  const result = compareGoldenCase(
    {
      caseRef: "golden-2",
      scenario: "Rooms",
      referenceModelVersion: "workbook-v5",
      cloudModelVersion: "cloud-v1",
      reference: { netYieldPct: 6.2 },
      cloud: { netYieldPct: 5.8 },
    },
    [{ key: "netYieldPct", absolute: 0.01, required: true }],
  );
  assert.equal(result.passed, false);
});

test("Tectum release requires four approvals on the exact report digest", () => {
  const roles = ["underwriting", "evidence", "legal_tax", "commercial"];
  const decision = tectumReleaseDecision({
    sourceRightsValidated: true,
    evidenceComplete: true,
    taxAndMaterialClaimsDocumentVerified: true,
    underwritingGoldenEquivalencePassed: true,
    reportGoldenFidelityPassed: true,
    cloudUnderwritingRuntimeReady: true,
    cloudRendererRuntimeReady: true,
    reportDigest: "abc",
    approvals: roles.map((role) => ({ role, digest: "abc", approved: true })),
    requiredApprovalRoles: roles,
  });
  assert.equal(decision.ready, true);
});

test("any byte change invalidates prior report approvals", () => {
  const approvals = invalidateDigestBoundApprovals("old", "new", [
    { role: "underwriting", digest: "old", approved: true },
    { role: "evidence", digest: "old", approved: true },
  ]);
  assert.equal(approvals.every((x) => x.approved === false && x.invalidated === true), true);
});
