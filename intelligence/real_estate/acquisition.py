"""Authorised source acquisition planning for Spanish property candidates.

This module never scrapes a portal and never performs a network request. It
validates connector policy, candidate provenance and channel eligibility, then
returns a deterministic no-write plan for the governed CRM vertical.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .synergy import canonical_digest


class AcquisitionPolicyError(ValueError):
    """Raised when a candidate violates the authorised-source policy."""


ALLOWED_RIGHTS = {
    "owned",
    "licensed",
    "client_authorised",
    "public_source",
    "contracted_feed",
}


@dataclass(frozen=True)
class ConnectorReadiness:
    connector_id: str
    ready: bool
    status: str
    missing_environment: tuple[str, ...]
    reason: str | None = None


def load_connector_registry(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise AcquisitionPolicyError("unsupported connector registry version")
    connectors = payload.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        raise AcquisitionPolicyError("connector registry is empty")
    ids = [str(item.get("id")) for item in connectors]
    if len(ids) != len(set(ids)):
        raise AcquisitionPolicyError("duplicate connector id")
    return payload


def connector_map(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): dict(item) for item in registry["connectors"]}


def connector_readiness(
    connector: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
) -> ConnectorReadiness:
    environment = environment or {}
    required = tuple(str(name) for name in connector.get("credentials", []))
    missing = tuple(name for name in required if not environment.get(name))
    status = str(connector.get("status", "unknown"))
    ready = bool(connector.get("allowed")) and not missing and status not in {
        "agreement_required",
        "access_request_required",
    }
    reason = None
    if missing:
        reason = "missing_environment"
    elif status == "agreement_required":
        reason = "written_agreement_required"
    elif status == "access_request_required":
        reason = "provider_access_required"
    elif not connector.get("allowed"):
        reason = "connector_disabled"
    return ConnectorReadiness(
        connector_id=str(connector["id"]),
        ready=ready,
        status=status,
        missing_environment=missing,
        reason=reason,
    )


def _reject_raw_sensitive_values(value: Any, path: str = "candidate") -> list[str]:
    blocked_keys = {
        "url",
        "source_url",
        "email",
        "phone",
        "full_address",
        "cadastral_reference",
        "owner_name",
        "advertiser_name",
    }
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in blocked_keys and child not in (None, ""):
                violations.append(child_path)
            violations.extend(_reject_raw_sensitive_values(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violations.extend(_reject_raw_sensitive_values(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if value.startswith(("http://", "https://")):
            violations.append(path)
        if value.startswith("restricted://") and not value.startswith(
            ("restricted://source/", "restricted://media/", "restricted://reviewer/")
        ):
            violations.append(path)
    return sorted(set(violations))


def classify_channel(
    candidate: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    claimed = bool(candidate.get("off_market_claimed"))
    verified = bool(candidate.get("off_market_verified"))
    source_kind = str(candidate["source_kind"])

    if verified:
        classification = "off_market"
    elif source_kind == "idealista":
        classification = "idealista_listing"
    elif source_kind in {"bank_asset_portal", "fund_portal"}:
        classification = "bank_or_fund"
    elif source_kind == "social_source":
        classification = "social_capture"
    else:
        classification = "non_idealista_portal"

    if claimed and not verified:
        review_warning = "off_market_claim_requires_verification"
    else:
        review_warning = None

    rules = registry["channel_rules"][classification]
    return {
        "classification": classification,
        "psi_plus_eligible": bool(rules["psi_plus_eligible"]),
        "channel_eligible": bool(rules["channel_eligible"]),
        "reason": str(rules["reason"]),
        "review_warning": review_warning,
    }


def validate_candidate(
    candidate: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    required = {
        "candidate_id",
        "connector_id",
        "source_kind",
        "capture_mode",
        "rights_status",
        "captured_at",
        "external_reference",
        "facts",
        "media_policy",
        "review_status",
    }
    missing = sorted(required - set(candidate))
    if missing:
        raise AcquisitionPolicyError(f"missing candidate fields: {missing}")
    if not str(candidate["candidate_id"]).startswith("SRC-CAND-"):
        raise AcquisitionPolicyError("governed candidate id required")

    connectors = connector_map(registry)
    connector_id = str(candidate["connector_id"])
    if connector_id not in connectors:
        raise AcquisitionPolicyError("unknown connector")
    connector = connectors[connector_id]
    if not connector.get("allowed"):
        raise AcquisitionPolicyError("connector is disabled")
    if str(candidate["capture_mode"]) != str(connector["mode"]):
        raise AcquisitionPolicyError("capture mode does not match connector")

    rights = str(candidate["rights_status"])
    if rights not in ALLOWED_RIGHTS:
        raise AcquisitionPolicyError("approved source rights required")
    if candidate["review_status"] != "approved":
        raise AcquisitionPolicyError("named source review approval required")

    violations = _reject_raw_sensitive_values(candidate)
    if violations:
        raise AcquisitionPolicyError(
            "raw URL, identity or property-identifying data must remain restricted: "
            + ", ".join(violations)
        )

    media = candidate["media_policy"]
    if media.get("reuse_permitted") and media.get("rights_basis") == "none":
        raise AcquisitionPolicyError("media reuse requires a rights basis")

    facts = candidate["facts"]
    for field in ("price_eur", "municipality", "province"):
        if facts.get(field) in (None, ""):
            raise AcquisitionPolicyError(f"missing required fact: {field}")

    channel = classify_channel(candidate, registry)
    readiness = connector_readiness(connector, environment)
    return {
        "valid": True,
        "candidate_digest": canonical_digest(candidate),
        "connector": connector,
        "connector_readiness": {
            "ready": readiness.ready,
            "status": readiness.status,
            "missing_environment": list(readiness.missing_environment),
            "reason": readiness.reason,
        },
        "channel": channel,
    }


def build_acquisition_plan(
    candidate: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validation = validate_candidate(candidate, registry, environment=environment)
    digest = validation["candidate_digest"]
    source_id = "SRC-" + sha256(digest.encode("utf-8")).hexdigest()[:20].upper()
    facts = candidate["facts"]
    channel = validation["channel"]

    property_source_row = {
        "Source ID": source_id,
        "Property ID": None,
        "Source Type": candidate["source_kind"],
        "Source Organisation ID": candidate.get("source_organisation_id"),
        "Source Contact ID": None,
        "Portal or Channel": candidate["connector_id"],
        "Source URL Token": candidate.get("source_url_token"),
        "External Reference": candidate["external_reference"],
        "First Seen": candidate["captured_at"],
        "Last Verified": candidate["captured_at"],
        "Asking Price €": facts["price_eur"],
        "Off-Market Claimed": bool(candidate.get("off_market_claimed")),
        "Off-Market Verified": bool(candidate.get("off_market_verified")),
        "Channel Eligibility": channel["classification"],
        "Rights Status": candidate["rights_status"],
        "Data Confidence %": 100 if candidate["capture_mode"] in {"official_api", "partner_feed"} else 70,
        "Internal Owner": None,
        "Evidence Link": None,
        "Status": "reviewed",
        "Notes": channel.get("review_warning"),
    }
    staging_row = {
        "Import ID": "IMP-" + source_id.removeprefix("SRC-"),
        "Source Profile": candidate["connector_id"],
        "Source Row": candidate["external_reference"],
        "External Code": None,
        "Source Record Digest": digest,
        "Rights Status": candidate["rights_status"],
        "PII Detected": False,
        "Restricted Fields Detected": False,
        "Import Status": "review_required",
        "Quarantine Reason": None,
        "Imported Property ID": None,
        "Imported Scenario IDs": None,
        "Reviewed By": candidate.get("reviewer_token"),
        "Review Date": candidate["captured_at"],
        "Notes": "Candidate requires deduplication, project ID allocation and underwriting.",
    }
    plan = {
        "plan_type": "authorised_property_source_candidate",
        "candidate_id": candidate["candidate_id"],
        "candidate_digest": digest,
        "connector_id": candidate["connector_id"],
        "connector_ready": validation["connector_readiness"]["ready"],
        "channel": channel,
        "rows": {
            "Property Sources": [property_source_row],
            "RE Import Staging": [staging_row],
        },
        "next_gates": [
            "deduplicate_property",
            "allocate_project_id",
            "collect_cadastral_and_visit_evidence",
            "approve_underwriting_inputs",
            "generate_report_after_approval",
        ],
        "real_writes_permitted": False,
        "external_contact_permitted": False,
        "portal_scraping_permitted": False,
    }
    plan["plan_digest"] = canonical_digest(plan)
    return plan


def build_idealista_search_request(
    *,
    country: str,
    operation: str,
    property_type: str,
    center: str,
    distance_m: int,
    max_price: float | None = None,
    min_price: float | None = None,
) -> dict[str, Any]:
    """Build, but do not execute, an official Idealista Search API request."""
    if country.lower() != "es":
        raise AcquisitionPolicyError("RC1 is configured for Spain")
    if operation not in {"sale", "rent"}:
        raise AcquisitionPolicyError("unsupported operation")
    if distance_m <= 0:
        raise AcquisitionPolicyError("distance must be positive")
    params: dict[str, Any] = {
        "country": country.lower(),
        "operation": operation,
        "propertyType": property_type,
        "center": center,
        "distance": distance_m,
    }
    if max_price is not None:
        params["maxPrice"] = max_price
    if min_price is not None:
        params["minPrice"] = min_price
    request = {
        "connector_id": "idealista_search_api",
        "method": "POST",
        "endpoint_alias": "IDEALISTA_SEARCH_API_ENDPOINT",
        "parameters": params,
        "credentials_required": ["IDEALISTA_API_KEY", "IDEALISTA_API_SECRET"],
        "execute": False,
        "portal_scraping_permitted": False,
    }
    request["request_digest"] = canonical_digest(request)
    return request
