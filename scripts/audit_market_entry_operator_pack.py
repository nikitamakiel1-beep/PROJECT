#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_PACK = ROOT / "config" / "market-entry-operator-pack.json"
LICENSING = ROOT / "config" / "market-entry-licensing.json"
STAGING = ROOT / "config" / "staging-release.json"

SEQUENCE_IDS = (
    "OPERATING_FORM",
    "MUNICIPAL_PATH",
    "AEAT_036",
    "IAE_CLASSIFICATION",
    "RETA_OR_ENTITY",
    "INVOICE_SYSTEM",
    "ONLINE_PROVIDER_INFO",
    "DATA_AND_AI_CONTROLS",
)
SERVICE_CODES = {"IVA", "CRM", "IOP", "WAB", "ISS", "WEB", "AI"}
FROZEN_REVIEWS = {
    "professional_privacy_review",
    "professional_legal_review",
    "professional_invoicing_review",
}
REGULATED_BOUNDARY_MARKERS = {
    "IVA": {"audit of annual accounts", "financial statement assurance", "legal compliance certification", "tax certification"},
    "CRM": {"selling personal data", "autonomous prospect contact"},
    "IOP": {"legal translation certification", "guaranteed commercial outcomes"},
    "WAB": {"autonomous outbound messaging"},
    "AI": {"employment decisions", "credit eligibility decisions", "biometric categorisation", "emotion recognition"},
}


def canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit(operator_pack: dict, licensing: dict, staging: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    state = operator_pack.get("current_state", {})
    if state.get("website_profile") != "synthetic_staging":
        blockers.append("website_profile_must_be_synthetic_staging")
    for key in ("website_indexable", "website_real_intake", "paid_contracting_permitted", "invoice_issue_permitted", "client_personal_data_permitted"):
        if state.get(key) is not False:
            blockers.append(f"unsafe_current_state:{key}")
    if state.get("known_clients") != 0:
        blockers.append("known_clients_must_remain_zero_in_public_operator_pack")
    if state.get("professional_reviews") != "frozen_by_owner":
        blockers.append("professional_reviews_must_remain_frozen")

    sequence = operator_pack.get("pre_invoice_sequence", [])
    sequence_ids = tuple(item.get("id") for item in sequence)
    if sequence_ids != SEQUENCE_IDS:
        blockers.append("pre_invoice_sequence_mismatch")
    if tuple(item.get("order") for item in sequence) != tuple(range(1, len(SEQUENCE_IDS) + 1)):
        blockers.append("pre_invoice_sequence_order_invalid")
    for item in sequence:
        if not item.get("evidence_required") or not item.get("blocks"):
            blockers.append(f"incomplete_sequence_control:{item.get('id', 'unknown')}")
        if item.get("status") in {"verified", "approved", "complete"}:
            blockers.append(f"unsupported_verified_status:{item.get('id', 'unknown')}")

    services = operator_pack.get("service_boundaries", [])
    service_map = {item.get("service_code"): item for item in services}
    if set(service_map) != SERVICE_CODES:
        blockers.append("service_boundary_set_mismatch")
    for code, required_markers in REGULATED_BOUNDARY_MARKERS.items():
        prohibited = set(service_map.get(code, {}).get("prohibited_scope", []))
        missing = sorted(required_markers - prohibited)
        if missing:
            blockers.append(f"regulated_boundary_missing:{code}:{','.join(missing)}")
    for item in services:
        if not item.get("permitted_scope") or not item.get("prohibited_scope"):
            blockers.append(f"service_boundary_incomplete:{item.get('service_code', 'unknown')}")

    owner_instruction = operator_pack.get("owner_instruction", {})
    for key in sorted(FROZEN_REVIEWS):
        if owner_instruction.get(key) != "frozen_by_owner":
            blockers.append(f"operator_review_not_frozen:{key}")

    licensing_frozen = licensing.get("frozen_reviews", {})
    for key in sorted(FROZEN_REVIEWS):
        if licensing_frozen.get(key) != "frozen_by_owner":
            blockers.append(f"licensing_review_not_frozen:{key}")
    decision = licensing.get("current_decision", {})
    for key in ("live_publication_permitted", "live_intake_permitted", "paid_contracting_permitted", "client_personal_data_permitted"):
        if decision.get(key) is not False:
            blockers.append(f"unsafe_licensing_decision:{key}")

    if staging.get("profile") != "staging" or staging.get("synthetic_only") is not True:
        blockers.append("staging_profile_invalid")
    if staging.get("indexable") is not False or staging.get("public_intake_permitted") is not False or staging.get("client_data_permitted") is not False:
        blockers.append("staging_safety_boundary_invalid")
    endpoint = str(staging.get("endpoint", ""))
    if not endpoint.startswith("https://") or ".invalid/" not in endpoint:
        blockers.append("staging_endpoint_not_reserved_invalid")

    evidence_register = operator_pack.get("official_evidence_register", {})
    required_fields = {
        "control_id", "authority", "filing_or_decision_date", "effective_date",
        "receipt_location", "reviewer", "status", "expiry_or_review_date", "notes",
    }
    if set(evidence_register.get("fields", [])) != required_fields:
        blockers.append("official_evidence_register_fields_mismatch")
    if "verified" not in evidence_register.get("allowed_statuses", []):
        blockers.append("official_evidence_register_missing_verified_state")
    if "never in public source control" not in evidence_register.get("storage_rule", ""):
        blockers.append("official_evidence_storage_rule_missing")

    warnings.extend([
        "No official business registration, tax, Social Security, municipal, privacy or invoicing approval is represented as completed.",
        "No sector-specific professional licence was identified for the bounded service scope; this remains a non-final classification while professional review is frozen.",
        "The staged website is a technical inspection artifact and is not permission to trade.",
    ])

    body = {
        "schema_version": 1,
        "as_of": operator_pack.get("as_of"),
        "jurisdiction": operator_pack.get("jurisdiction"),
        "sequence_control_count": len(sequence),
        "service_boundary_count": len(services),
        "official_filings_verified": 0,
        "operator_pack_ready": not blockers,
        "staging_build_permitted": not blockers,
        "live_publication_permitted": False,
        "live_intake_permitted": False,
        "paid_contracting_permitted": False,
        "invoice_issue_permitted": False,
        "client_personal_data_permitted": False,
        "professional_approval_inferred": False,
        "human_review_required": True,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {**body, "evidence_digest": canonical_digest(body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operator-pack", type=Path, default=OPERATOR_PACK)
    parser.add_argument("--licensing", type=Path, default=LICENSING)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        json.loads(args.operator_pack.read_text(encoding="utf-8")),
        json.loads(args.licensing.read_text(encoding="utf-8")),
        json.loads(args.staging.read_text(encoding="utf-8")),
    )
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if result["blockers"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
