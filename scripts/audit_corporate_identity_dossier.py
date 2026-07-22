#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "config" / "corporate-identity-dossier.json"
COMPANY = ROOT / "config" / "company-formation-readiness.json"
OPERATOR = ROOT / "config" / "market-entry-operator-pack.json"
STAGING = ROOT / "config" / "staging-release.json"

NAME_COUNT = 5
OFFICE_IDS = {"HOME_OFFICE", "COWORKING_PHYSICAL", "VIRTUAL_MAIL_ONLY", "DEDICATED_OFFICE"}
CNAE_CODES = {"70.20", "62.20", "62.10", "62.90", "73.11", "73.20", "73.30", "74.12", "74.30", "85.59"}
IAE_HEADINGS = {"849.9", "845", "844", "933.9"}
FUE_QUESTION_IDS = {
    "MUNICIPALITY", "FULL_ADDRESS", "ACTIVITY_DESCRIPTION", "PREMISES_TYPE",
    "PUBLIC_ACCESS", "CLIENT_VISITS", "EMPLOYEES_ON_SITE", "WORKS_REQUIRED",
    "SIGNAGE", "STORAGE_OR_INVENTORY", "EQUIPMENT_AND_POWER",
    "NOISE_EMISSIONS_OR_HAZARDS", "FLOOR_AREA_M2", "OPENING_HOURS",
    "ACCESSIBILITY_AND_FIRE_CONTROLS", "LEASE_OWNER_COMMUNITY_CONSENT",
}
UNSAFE_KEYS = (
    "name_availability_checked", "name_certificate_obtained",
    "trademark_or_domain_action_performed", "registered_office_selected",
    "real_address_present", "FUE_submission_performed", "CNAE_confirmed",
    "IAE_confirmed", "notary_or_PAE_instructed", "legal_entity_exists",
    "incorporation_execution_permitted", "live_publication_permitted",
    "live_intake_permitted", "client_personal_data_permitted",
    "paid_contracting_permitted", "invoice_issue_permitted",
    "payment_collection_permitted", "paid_delivery_permitted",
)


def digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit(dossier: dict, company: dict, operator: dict, staging: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    context = dossier.get("company_context", {})
    if context.get("operating_form") != "COMPANY":
        blockers.append("company_context_operating_form_invalid")
    if context.get("planned_company_form") != "SOCIEDAD_LIMITADA_UNIPERSONAL":
        blockers.append("company_context_form_invalid")
    for key in ("legal_entity_exists", "company_incorporated"):
        if context.get(key) is not False:
            blockers.append(f"unsafe_company_context:{key}")
    if context.get("brand_seed_status") != "owner_project_label_not_registered_mark":
        blockers.append("brand_seed_must_not_be_claimed_as_registered")

    strategy = dossier.get("corporate_name_strategy", {})
    names = strategy.get("ordered_candidates", [])
    if strategy.get("application_limit") != NAME_COUNT or len(names) != NAME_COUNT:
        blockers.append("corporate_name_candidate_count_mismatch")
    if tuple(item.get("order") for item in names) != tuple(range(1, NAME_COUNT + 1)):
        blockers.append("corporate_name_order_invalid")
    if len({item.get("name") for item in names}) != NAME_COUNT:
        blockers.append("corporate_name_candidates_not_unique")
    for item in names:
        name = str(item.get("name", ""))
        if not name.endswith("S.L.U."):
            blockers.append(f"corporate_name_missing_SLU:{item.get('order', 'unknown')}")
        if item.get("availability_status") != "not_checked":
            blockers.append(f"unsupported_name_availability:{item.get('order', 'unknown')}")
        if item.get("certificate_status") != "not_requested":
            blockers.append(f"unsupported_name_certificate:{item.get('order', 'unknown')}")
        for score_key in (
            "distinctiveness_score", "scope_flexibility_score", "cross_language_score",
            "regulatory_neutrality_score", "brand_cohesion_score",
        ):
            if item.get(score_key) not in {1, 2, 3, 4, 5}:
                blockers.append(f"invalid_name_score:{item.get('order', 'unknown')}:{score_key}")

    rules = strategy.get("RMC_rules", {})
    expected_rules = {
        "maximum_names_per_request": 5,
        "names_must_be_ordered_by_preference": True,
        "social_form_must_be_included": True,
        "certified_name_must_match_deed_exactly": True,
        "favourable_certificate_reservation_months": 6,
        "certificate_valid_for_deed_months": 3,
        "preliminary_consultation_is_binding": False,
        "deed_unlock_requires": "favourable_RMC_negative_name_certificate",
    }
    for key, value in expected_rules.items():
        if rules.get(key) != value:
            blockers.append(f"RMC_rule_mismatch:{key}")
    parallel = strategy.get("parallel_brand_checks", {})
    for key in ("trademark_screen", "domain_screen", "social_handle_screen", "linguistic_and_reputation_screen"):
        if parallel.get(key) != "not_started":
            blockers.append(f"unsupported_brand_action:{key}")
    if "never replace" not in parallel.get("rule", ""):
        blockers.append("brand_checks_do_not_replace_RMC_rule_missing")

    office = dossier.get("registered_office_strategy", {})
    if office.get("selected_option") is not None or office.get("real_address_present") is not False:
        blockers.append("registered_office_must_remain_unselected_and_redacted")
    options = {item.get("id"): item for item in office.get("options", [])}
    if set(options) != OFFICE_IDS:
        blockers.append("registered_office_option_set_mismatch")
    if options.get("COWORKING_PHYSICAL", {}).get("status") != "provisional_preferred_not_selected":
        blockers.append("coworking_preference_must_remain_provisional")
    if options.get("VIRTUAL_MAIL_ONLY", {}).get("status") != "not_recommended_without_professional_review":
        blockers.append("mail_only_virtual_office_guard_missing")
    for option_id, item in options.items():
        if not item.get("required_evidence") or not item.get("principal_risks"):
            blockers.append(f"incomplete_registered_office_option:{option_id}")
    required_tests = {
        "effective_management_alignment", "principal_establishment_alignment",
        "lawful_right_to_use_address", "public_disclosure_acceptance",
        "authority_mail_reliability", "bank_and_notary_KYC_acceptance",
        "municipal_FUE_compatibility", "lease_owner_and_community_constraints",
        "client_visit_and_employee_plan", "address_change_contingency",
    }
    if set(office.get("mandatory_decision_tests", [])) != required_tests:
        blockers.append("registered_office_decision_tests_mismatch")

    fue = dossier.get("FUE_input_questionnaire", {})
    if fue.get("submission_performed") is not False:
        blockers.append("FUE_submission_cannot_be_claimed")
    questions = {item.get("id"): item for item in fue.get("questions", [])}
    if set(questions) != FUE_QUESTION_IDS:
        blockers.append("FUE_question_set_mismatch")
    if questions.get("FULL_ADDRESS", {}).get("value") != "restricted_not_supplied":
        blockers.append("full_address_must_remain_restricted_not_supplied")
    if questions.get("MUNICIPALITY", {}).get("value") != "not_supplied":
        blockers.append("municipality_must_remain_not_supplied")
    if any(item.get("required") is not True for item in questions.values()):
        blockers.append("FUE_question_not_required")
    if "exact municipality, address, use and authority response" not in fue.get("unlock_rule", ""):
        blockers.append("FUE_unlock_rule_incomplete")

    activity = dossier.get("activity_classification_candidates", {})
    if activity.get("CNAE_version") != "CNAE-2025":
        blockers.append("CNAE_version_must_be_2025")
    cnae = {item.get("code"): item for item in activity.get("CNAE_candidates", [])}
    if set(cnae) != CNAE_CODES:
        blockers.append("CNAE_candidate_set_mismatch")
    if activity.get("CNAE_primary_candidate") not in CNAE_CODES:
        blockers.append("CNAE_primary_candidate_invalid")
    if any(item.get("status") != "candidate_unconfirmed" for item in cnae.values()):
        blockers.append("CNAE_candidate_claimed_confirmed")
    if cnae.get("74.30", {}).get("boundary") != "does_not_authorise_sworn_or_certified_translation":
        blockers.append("translation_classification_boundary_missing")
    iae = {item.get("heading"): item for item in activity.get("IAE_candidates", [])}
    if set(iae) != IAE_HEADINGS:
        blockers.append("IAE_candidate_set_mismatch")
    if any(item.get("status") != "candidate_unconfirmed" for item in iae.values()):
        blockers.append("IAE_candidate_claimed_confirmed")
    if "separate systems" not in activity.get("IAE_system_rule", ""):
        blockers.append("CNAE_IAE_separation_rule_missing")
    if activity.get("CNAE_confirmed") is not False or activity.get("IAE_confirmed") is not False:
        blockers.append("activity_classifications_must_remain_unconfirmed")

    handoff = dossier.get("notary_PAE_handoff", {})
    if handoff.get("route_selected") is not False or handoff.get("notary_or_PAE_instructed") is not False:
        blockers.append("notary_PAE_route_must_remain_unselected")
    required_placeholders = {
        "founder_identity", "beneficial_owner_identity", "full_registered_office",
        "corporate_name_certificate", "capital_contribution_evidence",
        "administrator_acceptance_and_identity", "tax_and_Social_Security_identifiers",
        "bank_details", "electronic_certificate_data",
    }
    if set(handoff.get("restricted_placeholders", [])) != required_placeholders:
        blockers.append("notary_PAE_restricted_placeholder_set_mismatch")
    if len(handoff.get("pre_handoff_gates", [])) < 8:
        blockers.append("notary_PAE_pre_handoff_gates_incomplete")

    decision = dossier.get("current_decision", {})
    if decision.get("identity_dossier_build_permitted") is not True:
        blockers.append("identity_dossier_build_not_permitted")
    if decision.get("name_candidates_prepared") != NAME_COUNT:
        blockers.append("name_candidate_decision_count_mismatch")
    for key in UNSAFE_KEYS:
        if decision.get(key) is not False:
            blockers.append(f"unsafe_identity_decision:{key}")

    company_decision = company.get("current_decision", {})
    for key in ("legal_entity_exists", "incorporation_execution_permitted", "official_filings_permitted", "live_publication_permitted", "paid_contracting_permitted", "invoice_issue_permitted", "payment_collection_permitted", "paid_delivery_permitted"):
        if company_decision.get(key) is not False:
            blockers.append(f"unsafe_company_upstream:{key}")
    operator_state = operator.get("current_state", {})
    for key in ("website_indexable", "website_real_intake", "paid_contracting_permitted", "invoice_issue_permitted", "client_personal_data_permitted"):
        if operator_state.get(key) is not False:
            blockers.append(f"unsafe_operator_upstream:{key}")
    if staging.get("profile") != "staging" or staging.get("synthetic_only") is not True:
        blockers.append("staging_profile_invalid")
    if staging.get("indexable") is not False or staging.get("public_intake_permitted") is not False or staging.get("client_data_permitted") is not False:
        blockers.append("staging_safety_boundary_invalid")
    if ".invalid/" not in str(staging.get("endpoint", "")):
        blockers.append("staging_endpoint_not_reserved_invalid")

    warnings.extend([
        "The five corporate names are unverified planning candidates; no availability consultation or certificate request has occurred.",
        "Creixement is an owner project label, not a registered trademark claim.",
        "No real address, office contract or municipal submission is present.",
        "CNAE-2025 and IAE candidates are hypotheses and require factual and professional confirmation.",
        "The notary/PAE dossier is a redacted template and no professional has been instructed.",
        "The company still does not exist and all commercial activation remains blocked.",
    ])

    body = {
        "schema_version": 1,
        "as_of": dossier.get("as_of"),
        "jurisdiction": dossier.get("jurisdiction"),
        "identity_dossier_ready": not blockers,
        "name_candidates_prepared": len(names),
        "name_availability_checked": False,
        "name_certificate_obtained": False,
        "registered_office_selected": False,
        "real_address_present": False,
        "FUE_submission_performed": False,
        "CNAE_confirmed": False,
        "IAE_confirmed": False,
        "notary_or_PAE_instructed": False,
        "legal_entity_exists": False,
        "synthetic_staging_permitted": not blockers,
        "live_publication_permitted": False,
        "paid_contracting_permitted": False,
        "invoice_issue_permitted": False,
        "payment_collection_permitted": False,
        "professional_approval_inferred": False,
        "human_review_required": True,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {**body, "evidence_digest": digest(body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossier", type=Path, default=DOSSIER)
    parser.add_argument("--company", type=Path, default=COMPANY)
    parser.add_argument("--operator", type=Path, default=OPERATOR)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        json.loads(args.dossier.read_text(encoding="utf-8")),
        json.loads(args.company.read_text(encoding="utf-8")),
        json.loads(args.operator.read_text(encoding="utf-8")),
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
