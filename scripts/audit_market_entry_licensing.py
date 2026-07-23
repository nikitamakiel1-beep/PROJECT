#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LICENSING = ROOT / "config" / "market-entry-licensing.json"
STAGING = ROOT / "config" / "staging-release.json"

REQUIRED_IDS = {
    "AEAT_036", "IAE_CLASSIFICATION", "RETA", "MUNICIPAL_ACTIVITY",
    "LSSI_PROVIDER_INFORMATION", "GDPR_CONTROLLER", "GDPR_PROCESSOR",
    "B2C_CONSUMER", "CATALONIA_COMPLAINT_FORMS", "AI_ACT", "ROI_VIES",
    "PROFESSIONAL_INDEMNITY",
}


def canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit(licensing: dict, staging: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    ids = {item.get("id") for item in licensing.get("requirements", [])}
    missing = sorted(REQUIRED_IDS - ids)
    if missing:
        blockers.append("missing_requirement_ids:" + ",".join(missing))

    sector = licensing.get("sector_specific_authorisation", {})
    if sector.get("final_legal_opinion") is not False:
        blockers.append("sector_authorisation_must_not_be_presented_as_final_legal_opinion")
    if sector.get("professional_confirmation_state") != "frozen_by_owner":
        blockers.append("professional_sector_confirmation_not_frozen")

    frozen = licensing.get("frozen_reviews", {})
    required_frozen = {
        "professional_privacy_review",
        "professional_legal_review",
        "professional_invoicing_review",
        "exact_iae_heading_confirmation",
        "municipal_address_specific_confirmation",
    }
    for key in sorted(required_frozen):
        if frozen.get(key) != "frozen_by_owner":
            blockers.append(f"review_not_frozen:{key}")

    decision = licensing.get("current_decision", {})
    if decision.get("staging_build_permitted") is not True:
        blockers.append("staging_build_not_permitted")
    for key in ("live_publication_permitted", "live_intake_permitted", "paid_contracting_permitted", "client_personal_data_permitted"):
        if decision.get(key) is not False:
            blockers.append(f"unsafe_decision:{key}")

    if staging.get("profile") != "staging":
        blockers.append("release_profile_not_staging")
    endpoint = str(staging.get("endpoint", ""))
    if not endpoint.startswith("https://") or ".invalid/" not in endpoint:
        blockers.append("staging_endpoint_must_use_https_reserved_invalid_domain")
    for key in ("synthetic_only",):
        if staging.get(key) is not True:
            blockers.append(f"staging_{key}_must_be_true")
    for key in ("indexable", "public_intake_permitted", "client_data_permitted"):
        if staging.get(key) is not False:
            blockers.append(f"staging_{key}_must_be_false")
    if staging.get("professional_review_state") != "frozen_by_owner":
        blockers.append("staging_professional_review_not_frozen")

    if ids == REQUIRED_IDS:
        warnings.append("Exact IAE heading and municipality-specific activity procedure remain unresolved by design.")
        warnings.append("No sector-specific professional licence was identified for the current scope; this is not a final legal opinion.")

    body = {
        "schema_version": 1,
        "as_of": licensing.get("as_of"),
        "jurisdiction": licensing.get("jurisdiction"),
        "service_codes": licensing.get("business_scope", {}).get("services", []),
        "requirement_count": len(ids),
        "frozen_review_count": sum(value == "frozen_by_owner" for value in frozen.values()),
        "staging_build_permitted": not blockers and decision.get("staging_build_permitted") is True,
        "live_publication_permitted": False,
        "paid_contracting_permitted": False,
        "client_personal_data_permitted": False,
        "blockers": blockers,
        "warnings": warnings,
        "human_review_required": True,
        "legal_approval_inferred": False,
    }
    return {**body, "evidence_digest": canonical_digest(body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--licensing", type=Path, default=LICENSING)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
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
