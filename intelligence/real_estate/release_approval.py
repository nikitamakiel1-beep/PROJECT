"""Digest-bound approval custody for the real-estate architecture release."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .synergy import canonical_digest


class ReleaseApprovalError(ValueError):
    pass


REQUIRED_ROLES = (
    "source_policy_reviewer",
    "privacy_reviewer",
    "architecture_release_approver",
)


@dataclass(frozen=True)
class ApprovalRecord:
    role: str
    reviewer_token: str
    status: str
    approved_at: str
    bound_release_digest: str
    evidence_token: str
    reason: str | None = None


@dataclass
class ReleaseApprovalCustody:
    release_artifacts: Mapping[str, Any]
    approvals: dict[str, ApprovalRecord] = field(default_factory=dict)

    @property
    def release_digest(self) -> str:
        return canonical_digest(self.release_artifacts)

    def approve(
        self,
        *,
        role: str,
        reviewer_token: str,
        approved_at: str,
        evidence_token: str,
        bound_release_digest: str,
    ) -> ApprovalRecord:
        if role not in REQUIRED_ROLES:
            raise ReleaseApprovalError("unknown release approval role")
        if not reviewer_token.startswith("restricted://reviewer/"):
            raise ReleaseApprovalError("restricted reviewer token required")
        if not evidence_token.startswith("restricted://evidence/"):
            raise ReleaseApprovalError("restricted approval evidence required")
        if bound_release_digest != self.release_digest:
            raise ReleaseApprovalError("approval digest does not match release")
        for existing_role, record in self.approvals.items():
            if existing_role != role and record.reviewer_token == reviewer_token:
                raise ReleaseApprovalError("release reviewers must be distinct")
        record = ApprovalRecord(
            role=role,
            reviewer_token=reviewer_token,
            status="approved",
            approved_at=approved_at,
            bound_release_digest=bound_release_digest,
            evidence_token=evidence_token,
        )
        self.approvals[role] = record
        return record

    def reject(
        self,
        *,
        role: str,
        reviewer_token: str,
        approved_at: str,
        evidence_token: str,
        bound_release_digest: str,
        reason: str,
    ) -> ApprovalRecord:
        if not reason.strip():
            raise ReleaseApprovalError("rejection reason required")
        if role not in REQUIRED_ROLES:
            raise ReleaseApprovalError("unknown release approval role")
        if bound_release_digest != self.release_digest:
            raise ReleaseApprovalError("approval digest does not match release")
        record = ApprovalRecord(
            role=role,
            reviewer_token=reviewer_token,
            status="rejected",
            approved_at=approved_at,
            bound_release_digest=bound_release_digest,
            evidence_token=evidence_token,
            reason=reason.strip(),
        )
        self.approvals[role] = record
        return record

    def qualification(self) -> dict[str, Any]:
        current_digest = self.release_digest
        missing = [role for role in REQUIRED_ROLES if role not in self.approvals]
        rejected = [
            role
            for role, record in self.approvals.items()
            if record.status == "rejected"
        ]
        stale = [
            role
            for role, record in self.approvals.items()
            if record.bound_release_digest != current_digest
        ]
        reviewers = [
            self.approvals[role].reviewer_token
            for role in REQUIRED_ROLES
            if role in self.approvals
        ]
        duplicate_reviewers = len(reviewers) != len(set(reviewers))
        qualified = not missing and not rejected and not stale and not duplicate_reviewers
        return {
            "qualified": qualified,
            "release_digest": current_digest,
            "missing_roles": missing,
            "rejected_roles": rejected,
            "stale_roles": stale,
            "duplicate_reviewers": duplicate_reviewers,
            "live_source_acquisition_permitted": False,
            "external_report_delivery_permitted": False,
            "release_or_deployment_permitted": qualified,
        }

    def receipt(self) -> dict[str, Any]:
        qualification = self.qualification()
        approvals = {
            role: {
                "reviewer_token": record.reviewer_token,
                "status": record.status,
                "approved_at": record.approved_at,
                "bound_release_digest": record.bound_release_digest,
                "evidence_token": record.evidence_token,
                "reason": record.reason,
            }
            for role, record in sorted(self.approvals.items())
        }
        payload = {
            "schema_version": 1,
            "release_digest": self.release_digest,
            "approvals": approvals,
            "qualification": qualification,
        }
        payload["receipt_digest"] = canonical_digest(payload)
        return payload


def build_release_artifact_binding(
    *,
    connector_registry: Mapping[str, Any],
    report_renderer: Mapping[str, Any],
    source_candidate_schema: Mapping[str, Any],
    release_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts = {
        "connector_registry_digest": canonical_digest(connector_registry),
        "report_renderer_digest": canonical_digest(report_renderer),
        "source_candidate_schema_digest": canonical_digest(source_candidate_schema),
        "release_manifest_digest": canonical_digest(release_manifest),
    }
    artifacts["architecture_digest"] = canonical_digest(artifacts)
    return artifacts
