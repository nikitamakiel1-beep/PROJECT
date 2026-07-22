#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "config" / "company-formation-readiness.json"
OPERATOR_PACK = ROOT / "config" / "market-entry-operator-pack.json"
LICENSING = ROOT / "config" / "market-entry-licensing.json"
STAGING = ROOT / "config" / "staging-release.json"

SEQUENCE_IDS = (
    "OWNER_COMPANY_DECISION",
    "CORPORATE_NAME",
    "REGISTERED_OFFICE",
    "MUNICIPAL_PATH",
    "CORPORATE_PURPOSE",
    "CNAE_IAE",
    "GOVERNANCE",
    "CAPITAL_CONTRIBUTION",
    "CIRCE_DUE_OR_NOTARY",
    "FORMATION_DEED",
    "PROVISIONAL_NIF",
    "MERCANTILE_REGISTRY",
    "DEFINITIVE_NIF",
    "SOCIAL_SECURITY",
    "INVOICE_SYSTEM",
    "ONLINE_DATA_AI_ACTIVATION",
)
FROZEN_REVIEWS = {
    "professional_privacy_review",
    "professional_legal_review",
    "professional_invoicing_review",
    "exact_CNAE_IAE_confirmation",
    "municipal_address_specific_confirmation",
    "administrator_social_security_confirmation",
}
REQUIRED_EXCLUSIONS = {
    "legal advice",
    "tax advice",
    "regulated financial advice",
    "statutory accounts auditing",
    "certified or sworn translation",
    "real-estate intermediation",
    "insurance investment or credit intermediation",
    "autonomous high-impact employment credit biometric emotion or sensitive-data decisions",
}
UNSAFE_DECISION_KEYS = (
    "legal_entity_exists",
    "incorporation_execution_permitted",
    "official_filings_permitted",
    "live_publication_permitted",
    "live_intake_permitted",
    "client_personal_data_permitted",
    "paid_contracting_permitted",
    "invoice_issue_permitted",
    "payment_collection_permitted",
    "paid_delivery_permitted",
)
UNSUPPORTED_SEQUENCE_STATUSES = {
    "verified",
    "approved",
    "complete",
    "completed",
    "incorporated",
    "registered",
    "filed",
    "submitted",
}


def canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit(company: dict, operator_pack: dict, licensing: dict, staging: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    owner = company.get("owner_decision", {})
    if owner.get("operating_form") != "COMPANY":
        blockers.append("operating_form_must_be_company")
    if owner.get("company_form") != "SOCIEDAD_LIMITADA_UNIPERSONAL":
        blockers.append("company_form_must_be_provisional_SLU")
    if owner.get("decision_status") != "owner_selected_architecture_only":
        blockers.append("owner_decision_status_invalid")
    if owner.get("shareholder_count") != 1:
        blockers.append("synthetic_SLU_shareholder_count_must_be_one")
    for key in ("legal_entity_exists", "company_incorporated", "official_name_reserved", "registered_office_confirmed"):
        if owner.get(key) is not False:
            blockers.append(f"unsafe_owner_claim:{key}")

    capital = company.get("capital_plan", {})
    if capital.get("currency") != "EUR":
        blockers.append("capital_currency_must_be_EUR")
    if capital.get("legal_minimum_eur") != 1:
        blockers.append("legal_minimum_capital_mismatch")
    if capital.get("recommended_eur") != 3000 or capital.get("selected_planning_amount_eur") != 3000:
        blockers.append("recommended_capital_plan_must_be_3000")
    if capital.get("contribution_status") != "not_contributed":
        blockers.append("capital_must_not_be_claimed_as_contributed")
    safeguards = capital.get("under_3000_safeguards", {})
    if safeguards.get("legal_reserve_percent_of_profit") != 20:
        blockers.append("sub_3000_legal_reserve_rule_missing")
    if safeguards.get("reserve_until_capital_plus_reserve_eur") != 3000:
        blockers.append("sub_3000_reserve_threshold_missing")
    if safeguards.get("liquidation_shortfall_liability_reference_eur") != 3000:
        blockers.append("sub_3000_liquidation_reference_missing")

    governance = company.get("governance_plan", {})
    if governance.get("administrator_model") != "sole_administrator_provisional":
        blockers.append("administrator_model_must_remain_provisional")
    if governance.get("administrator_appointment_status") != "not_executed":
        blockers.append("administrator_appointment_cannot_be_executed")
    if governance.get("social_security_classification") != "provisional_autonomo_societario_review_required":
        blockers.append("social_security_classification_must_remain_provisional")
    if governance.get("social_security_verified") is not False:
        blockers.append("social_security_cannot_be_claimed_verified")

    sequence = company.get("formation_sequence", [])
    if tuple(item.get("id") for item in sequence) != SEQUENCE_IDS:
        blockers.append("formation_sequence_mismatch")
    if tuple(item.get("order") for item in sequence) != tuple(range(1, len(SEQUENCE_IDS) + 1)):
        blockers.append("formation_sequence_order_invalid")
    for item in sequence:
        control_id = item.get("id", "unknown")
        status = item.get("status")
        if not item.get("evidence_required") or not item.get("blocks"):
            blockers.append(f"incomplete_formation_control:{control_id}")
        if status in UNSUPPORTED_SEQUENCE_STATUSES:
            blockers.append(f"unsupported_formation_status:{control_id}")
    if sequence and sequence[0].get("status") != "owner_decision_recorded_not_incorporated":
        blockers.append("company_decision_record_must_not_claim_incorporation")

    purpose = company.get("corporate_purpose_draft", {})
    if purpose.get("status") != "bounded_draft_not_approved":
        blockers.append("corporate_purpose_must_remain_unapproved_draft")
    exclusions = set(purpose.get("excluded_regulated_activities", []))
    missing_exclusions = sorted(REQUIRED_EXCLUSIONS - exclusions)
    if missing_exclusions:
        blockers.append(f"regulated_activity_exclusions_missing:{','.join(missing_exclusions)}")
    if not purpose.get("permitted_activity_families"):
        blockers.append("corporate_purpose_permitted_scope_missing")
    if set(purpose.get("final_wording_requires", [])) != {
        "professional_legal_review",
        "notarial_acceptance",
        "activity_classification_alignment",
    }:
        blockers.append("corporate_purpose_final_review_contract_mismatch")

    custody = company.get("restricted_custody", {})
    if "restricted Drive storage" not in custody.get("storage_rule", ""):
        blockers.append("restricted_custody_storage_rule_missing")
    if "never in public source control" not in custody.get("storage_rule", ""):
        blockers.append("public_source_control_prohibition_missing")
    required_forbidden_fields = {
        "NIF_or_personal_ID",
        "full_address",
        "bank_account",
        "signature",
        "certificate_password",
        "tax_filing_copy",
        "Social_Security_number",
        "beneficial_owner_identity",
    }
    if set(custody.get("forbidden_public_fields", [])) != required_forbidden_fields:
        blockers.append("forbidden_public_field_set_mismatch")
    if len(custody.get("document_classes", [])) < 10:
        blockers.append("restricted_document_class_set_incomplete")

    frozen = company.get("frozen_reviews", {})
    for key in sorted(FROZEN_REVIEWS):
        if frozen.get(key) != "frozen_by_owner":
            blockers.append(f"company_review_not_frozen:{key}")

    decision = company.get("current_decision", {})
    if decision.get("company_route_selected") is not True:
        blockers.append("company_route_selection_missing")
    if decision.get("formation_readiness_build_permitted") is not True:
        blockers.append("formation_readiness_build_must_be_permitted")
    for key in UNSAFE_DECISION_KEYS:
        if decision.get(key) is not False:
            blockers.append(f"unsafe_company_decision:{key}")

    operator_state = operator_pack.get("current_state", {})
    for key in ("website_indexable", "website_real_intake", "paid_contracting_permitted", "invoice_issue_permitted", "client_personal_data_permitted"):
        if operator_state.get(key) is not False:
            blockers.append(f"unsafe_operator_pack_state:{key}")
    if operator_state.get("professional_reviews") != "frozen_by_owner":
        blockers.append("operator_pack_professional_reviews_must_remain_frozen")

    licensing_decision = licensing.get("current_decision", {})
    for key in ("live_publication_permitted", "live_intake_permitted", "paid_contracting_permitted", "client_personal_data_permitted"):
        if licensing_decision.get(key) is not False:
            blockers.append(f"unsafe_licensing_decision:{key}")

    if staging.get("profile") != "staging" or staging.get("synthetic_only") is not True:
        blockers.append("staging_profile_invalid")
    if staging.get("indexable") is not False or staging.get("public_intake_permitted") is not False or staging.get("client_data_permitted") is not False:
        blockers.append("staging_safety_boundary_invalid")
    endpoint = str(staging.get("endpoint", ""))
    if not endpoint.startswith("https://") or ".invalid/" not in endpoint:
        blockers.append("staging_endpoint_not_reserved_invalid")

    warnings.extend([
        "The company route and provisional S.L.U. architecture are owner decisions, not evidence that a legal person exists.",
        "No corporate name, registered office, capital contribution, deed, NIF, Mercantile Registry entry, Social Security registration or invoice system is represented as completed.",
        "The EUR 3,000 amount is a planning recommendation; no capital has been contributed or made available to a company.",
        "Professional legal, tax, privacy, invoicing, activity-classification, municipal and Social Security reviews remain frozen.",
        "The staged website remains synthetic, noindex and unable to trade or collect personal data.",
    ])

    body = {
        "schema_version": 1,
        "as_of": company.get("as_of"),
        "jurisdiction": company.get("jurisdiction"),
        "company_route_selected": owner.get("operating_form") == "COMPANY",
        "company_form_planned": owner.get("company_form"),
        "formation_control_count": len(sequence),
        "official_filings_verified": 0,
        "legal_entity_exists": False,
        "company_incorporated": False,
        "capital_contributed": False,
        "formation_readiness_ready": not blockers,
        "synthetic_staging_permitted": not blockers,
        "incorporation_execution_permitted": False,
        "live_publication_permitted": False,
        "live_intake_permitted": False,
        "client_personal_data_permitted": False,
        "paid_contracting_permitted": False,
        "invoice_issue_permitted": False,
        "payment_collection_permitted": False,
        "paid_delivery_permitted": False,
        "professional_approval_inferred": False,
        "human_review_required": True,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {**body, "evidence_digest": canonical_digest(body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", type=Path, default=COMPANY)
    parser.add_argument("--operator-pack", type=Path, default=OPERATOR_PACK)
    parser.add_argument("--licensing", type=Path, default=LICENSING)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        json.loads(args.company.read_text(encoding="utf-8")),
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
