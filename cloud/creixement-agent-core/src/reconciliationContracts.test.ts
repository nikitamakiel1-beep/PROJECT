import test from "node:test";
import assert from "node:assert/strict";
import { reconcileRuntime } from "./reconciliation.js";
import { validateCapabilityInvocation } from "./capabilityContracts.js";

test("critical runtime drift requires approval rather than silent repair", () => {
  const findings = reconcileRuntime([
    { key: "crm", kind: "connector", desired: { runtimeReady: true }, autoRemediate: true },
  ], [
    { key: "crm", kind: "connector", observed: { runtimeReady: false }, observedAt: "2026-09-09T00:00:00Z" },
  ]);
  assert.equal(findings[0]?.severity, "critical");
  assert.equal(findings[0]?.remediation, "approval_required");
});

test("capability contract blocks forbidden external effect", () => {
  const result = validateCapabilityInvocation({
    key: "report.draft", version: "1", description: "draft only", inputSchemaRef: "schema:report-input", outputSchemaRef: "schema:report-output",
    requiredEvidenceKinds: ["governed_source"], requiredRights: ["read"], maxAutonomy: "L2", reversible: true,
    receiptRequired: true, idempotencyRequired: true, maxExternalCostEur: 0, allowedProviders: ["internal"],
    forbiddenEffects: ["public_publish"], active: true,
  }, {
    capabilityKey: "report.draft", providerKey: "internal", autonomyLevel: "L2", evidenceKinds: ["governed_source"], rights: ["read"],
    reversible: true, hasReceiptAdapter: true, hasIdempotencyKey: true, estimatedExternalCostEur: 0, effects: ["public_publish"],
  });
  assert.equal(result.allowed, false);
});
