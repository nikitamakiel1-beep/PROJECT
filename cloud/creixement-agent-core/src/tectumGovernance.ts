import { stableDigest } from "./runtime.js";

export type TectumScenario = "Traditional" | "Rooms" | "Temporary";

export interface GoldenMetricTolerance {
  key: string;
  absolute?: number;
  relativePct?: number;
  required: boolean;
}

export interface GoldenCase {
  caseRef: string;
  scenario: TectumScenario;
  referenceModelVersion: string;
  cloudModelVersion: string;
  reference: Record<string, number | string | boolean | null>;
  cloud: Record<string, number | string | boolean | null>;
}

export interface MetricComparison {
  key: string;
  passed: boolean;
  reference: unknown;
  cloud: unknown;
  absoluteError?: number;
  relativeErrorPct?: number;
  reason: string;
}

export interface GoldenCaseResult {
  passed: boolean;
  caseRef: string;
  scenario: TectumScenario;
  comparisons: MetricComparison[];
  referenceDigest: string;
  cloudDigest: string;
}

function numericComparison(reference: number, cloud: number, tolerance: GoldenMetricTolerance): MetricComparison {
  const absoluteError = Math.abs(reference - cloud);
  const relativeErrorPct = Math.abs(reference) > 1e-12 ? (absoluteError / Math.abs(reference)) * 100 : undefined;
  const absolutePass = tolerance.absolute === undefined || absoluteError <= tolerance.absolute;
  const relativePass = tolerance.relativePct === undefined || (relativeErrorPct ?? (absoluteError === 0 ? 0 : Infinity)) <= tolerance.relativePct;
  return {
    key: tolerance.key,
    passed: absolutePass && relativePass,
    reference,
    cloud,
    absoluteError,
    ...(relativeErrorPct !== undefined ? { relativeErrorPct } : {}),
    reason: absolutePass && relativePass ? "within_tolerance" : "numeric_mismatch",
  };
}

export function compareGoldenCase(golden: GoldenCase, tolerances: GoldenMetricTolerance[]): GoldenCaseResult {
  const comparisons = tolerances.map((tolerance): MetricComparison => {
    const reference = golden.reference[tolerance.key];
    const cloud = golden.cloud[tolerance.key];
    if (reference === undefined || cloud === undefined) {
      return {
        key: tolerance.key,
        passed: !tolerance.required,
        reference,
        cloud,
        reason: tolerance.required ? "required_metric_missing" : "optional_metric_missing",
      };
    }
    if (typeof reference === "number" && typeof cloud === "number") {
      return numericComparison(reference, cloud, tolerance);
    }
    const passed = Object.is(reference, cloud);
    return { key: tolerance.key, passed, reference, cloud, reason: passed ? "exact_match" : "categorical_mismatch" };
  });

  return {
    passed: comparisons.every((x) => x.passed),
    caseRef: golden.caseRef,
    scenario: golden.scenario,
    comparisons,
    referenceDigest: stableDigest(golden.reference),
    cloudDigest: stableDigest(golden.cloud),
  };
}

export interface TectumReleaseInput {
  sourceRightsValidated: boolean;
  evidenceComplete: boolean;
  taxAndMaterialClaimsDocumentVerified: boolean;
  underwritingGoldenEquivalencePassed: boolean;
  reportGoldenFidelityPassed: boolean;
  cloudUnderwritingRuntimeReady: boolean;
  cloudRendererRuntimeReady: boolean;
  reportDigest: string;
  approvals: { role: string; digest: string; approved: boolean }[];
  requiredApprovalRoles: string[];
}

export interface TectumReleaseDecision {
  ready: boolean;
  blockers: string[];
}

export function tectumReleaseDecision(input: TectumReleaseInput): TectumReleaseDecision {
  const blockers: string[] = [];
  if (!input.sourceRightsValidated) blockers.push("source_rights_not_validated");
  if (!input.evidenceComplete) blockers.push("evidence_incomplete");
  if (!input.taxAndMaterialClaimsDocumentVerified) blockers.push("tax_or_material_claims_not_document_verified");
  if (!input.underwritingGoldenEquivalencePassed) blockers.push("underwriting_golden_equivalence_not_passed");
  if (!input.reportGoldenFidelityPassed) blockers.push("report_golden_fidelity_not_passed");
  if (!input.cloudUnderwritingRuntimeReady) blockers.push("cloud_underwriting_not_runtime_ready");
  if (!input.cloudRendererRuntimeReady) blockers.push("cloud_renderer_not_runtime_ready");
  if (!input.reportDigest.trim()) blockers.push("report_digest_missing");

  const byRole = new Map(input.approvals.map((approval) => [approval.role, approval]));
  for (const role of input.requiredApprovalRoles) {
    const approval = byRole.get(role);
    if (!approval?.approved) blockers.push(`approval_missing:${role}`);
    else if (approval.digest !== input.reportDigest) blockers.push(`approval_digest_mismatch:${role}`);
  }

  return { ready: blockers.length === 0, blockers };
}

export function invalidateDigestBoundApprovals(
  previousDigest: string,
  newDigest: string,
  approvals: { role: string; digest: string; approved: boolean }[],
): { role: string; digest: string; approved: boolean; invalidated: boolean }[] {
  const artifactChanged = previousDigest !== newDigest;
  return approvals.map((approval) => ({
    ...approval,
    approved: artifactChanged ? false : approval.approved,
    invalidated: artifactChanged && approval.approved,
  }));
}
