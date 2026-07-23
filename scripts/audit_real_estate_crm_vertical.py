#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERTICAL = ROOT / "config" / "real-estate-crm-vertical.json"
IMPORT_CONTRACT = ROOT / "schemas" / "crm" / "real-estate" / "import-contract.json"
SHEETS_CONTRACT = ROOT / "schemas" / "crm" / "sheets-contract.json"
LEAD_SCHEMA = ROOT / "schemas" / "crm" / "lead.schema.json"
STAGING = ROOT / "config" / "staging-release.json"
OPERATOR = ROOT / "config" / "market-entry-operator-pack.json"

GENERIC_TABLES = {
    "Companies", "Contacts", "Leads", "Opportunities", "Activities", "Services", "Automation Log"
}
ENTITY_SCHEMAS = {
    "property": "schemas/crm/real-estate/property.schema.json",
    "deal": "schemas/crm/real-estate/opportunity.schema.json",
    "counterparty": "schemas/crm/real-estate/counterparty.schema.json",
    "investor_relationship": "schemas/crm/real-estate/investor.schema.json",
    "financing_scenario": "schemas/crm/real-estate/financing.schema.json",
    "underwriting_scenario": "schemas/crm/real-estate/underwriting.schema.json",
    "due_diligence_item": "schemas/crm/real-estate/due-diligence.schema.json",
    "fee_record": "schemas/crm/real-estate/fee.schema.json",
}
EXTENSION_SHEETS = {
    "Properties", "Real Estate Deals", "Counterparties", "Investors", "Financing",
    "Underwriting", "Due Diligence", "Fees", "Source Evidence", "Import Quarantine",
}
SOURCE_ALIASES = {"MAUMER_OPPORTUNITIES", "AGENCY_DIRECTORY"}
UNSAFE_DECISION_KEYS = (
    "dry_run_import_permitted", "real_import_permitted", "autonomous_outreach_permitted",
    "autonomous_investor_matching_permitted", "property_valuation_approval_permitted",
    "offer_or_financing_action_permitted", "transaction_mediation_permitted",
    "live_publication_permitted", "client_personal_data_permitted",
    "paid_contracting_permitted", "invoice_issue_permitted",
    "payment_collection_permitted", "paid_delivery_permitted",
)


def canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(vertical: dict, import_contract: dict, sheets: dict, lead: dict, staging: dict, operator: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    decision = vertical.get("integration_decision", {})
    if decision.get("mode") != "additive_vertical_extension":
        blockers.append("integration_mode_must_be_additive")
    for key in ("generic_CRM_preserved",):
        if decision.get(key) is not True:
            blockers.append(f"generic_CRM_not_preserved:{key}")
    for key in ("generic_intake_modified", "generic_sheets_contract_modified", "legal_business_merge_performed"):
        if decision.get(key) is not False:
            blockers.append(f"forbidden_integration_claim:{key}")
    if "information architecture" not in decision.get("meaning", ""):
        blockers.append("information_architecture_merge_boundary_missing")

    profiles = vertical.get("source_profiles", [])
    if {item.get("alias") for item in profiles} != SOURCE_ALIASES:
        blockers.append("source_profile_alias_set_mismatch")
    for profile in profiles:
        alias = profile.get("alias", "unknown")
        if not str(profile.get("restricted_pointer", "")).startswith("restricted://"):
            blockers.append(f"source_pointer_not_restricted:{alias}")
        if profile.get("source_records_in_GitHub") is not False:
            blockers.append(f"source_records_claimed_in_GitHub:{alias}")
        if profile.get("source_records_imported") != 0:
            blockers.append(f"source_records_claimed_imported:{alias}")
        if not profile.get("observed_domains"):
            blockers.append(f"source_profile_empty:{alias}")

    bridge = vertical.get("generic_CRM_bridge", {})
    if bridge.get("source_schema_version") != 3:
        blockers.append("generic_CRM_schema_version_mismatch")
    if set(bridge.get("preserved_tables", [])) != GENERIC_TABLES:
        blockers.append("generic_CRM_preserved_table_set_mismatch")
    if bridge.get("preserved_intake") != "automations/google-apps-script/IntakeCore.gs":
        blockers.append("generic_intake_reference_mismatch")
    bridge_keys = bridge.get("bridge_keys", {})
    if bridge_keys.get("counterparty_to_company") != "Company ID":
        blockers.append("company_bridge_missing")
    if bridge_keys.get("counterparty_or_investor_to_contact") != "Contact ID":
        blockers.append("contact_bridge_missing")
    if bridge_keys.get("real_estate_deal_to_generic_opportunity") != "Opportunity ID":
        blockers.append("opportunity_bridge_missing")
    if len(bridge.get("rules", [])) < 5:
        blockers.append("generic_CRM_bridge_rules_incomplete")

    if sheets.get("schema_version") != 3:
        blockers.append("upstream_sheets_contract_version_changed")
    if not GENERIC_TABLES.issubset(set(sheets.get("sheets", {}))):
        blockers.append("upstream_generic_tables_missing")
    expected_lead_required = {"submission_id", "company_name", "contact_name", "email", "service_code", "consent_version"}
    if set(lead.get("required", [])) != expected_lead_required:
        blockers.append("generic_lead_required_fields_changed")
    forbidden_lead_fields = {"property_id", "deal_id", "investor_id", "financing_id", "valuation_eur"}
    if forbidden_lead_fields.intersection(set(lead.get("properties", {}))):
        blockers.append("real_estate_fields_leaked_into_generic_lead")

    model = vertical.get("entity_model", [])
    model_map = {item.get("entity"): item.get("schema") for item in model}
    if model_map != ENTITY_SCHEMAS:
        blockers.append("real_estate_entity_model_mismatch")
    loaded_schemas: dict[str, dict] = {}
    for entity, relative in ENTITY_SCHEMAS.items():
        path = ROOT / relative
        if not path.exists():
            blockers.append(f"missing_entity_schema:{entity}")
            continue
        try:
            loaded_schemas[entity] = load_json(path)
        except Exception:
            blockers.append(f"invalid_entity_schema:{entity}")
    if set(loaded_schemas) == set(ENTITY_SCHEMAS):
        property_schema = loaded_schemas["property"]
        if property_schema.get("properties", {}).get("custody_class", {}).get("const") != "restricted_real_estate":
            blockers.append("property_restricted_custody_missing")
        deal_schema = loaded_schemas["deal"]
        if "generic_opportunity_id" not in deal_schema.get("required", []):
            blockers.append("deal_generic_opportunity_bridge_missing")
        counterparty = loaded_schemas["counterparty"]
        if "contact_authority" not in counterparty.get("required", []):
            blockers.append("counterparty_contact_authority_missing")
        investor = loaded_schemas["investor_relationship"]
        recommendation = investor.get("properties", {}).get("recommendation_state", {}).get("const")
        if recommendation != "no_automated_investment_recommendation":
            blockers.append("investor_recommendation_guard_missing")
        financing = loaded_schemas["financing_scenario"]
        if financing.get("properties", {}).get("advice_state", {}).get("const") != "no_mortgage_or_financial_advice_by_platform":
            blockers.append("financing_advice_guard_missing")
        underwriting = loaded_schemas["underwriting_scenario"]
        if underwriting.get("properties", {}).get("decision_state", {}).get("const") != "analysis_only_no_transaction_recommendation":
            blockers.append("underwriting_decision_guard_missing")
        diligence = loaded_schemas["due_diligence_item"]
        if diligence.get("properties", {}).get("approval_state", {}).get("const") != "platform_cannot_clear_due_diligence":
            blockers.append("due_diligence_clearance_guard_missing")

    if set(vertical.get("extension_sheets", [])) != EXTENSION_SHEETS:
        blockers.append("extension_sheet_set_mismatch")
    if set(import_contract.get("destination_extension_sheets", {})) != EXTENSION_SHEETS:
        blockers.append("import_destination_sheet_set_mismatch")
    if import_contract.get("mode") != "dry_run_quarantine_only":
        blockers.append("import_contract_mode_invalid")
    if import_contract.get("source_records_permitted") is not False:
        blockers.append("source_records_must_not_be_permitted")
    contract_bridges = import_contract.get("generic_CRM_bridges", {})
    if contract_bridges.get("company") != "Company ID" or contract_bridges.get("contact") != "Contact ID" or contract_bridges.get("opportunity") != "Opportunity ID":
        blockers.append("import_generic_bridge_mismatch")
    if "No single weak key may overwrite" not in import_contract.get("deduplication", {}).get("rule", ""):
        blockers.append("weak_key_overwrite_guard_missing")
    if len(import_contract.get("quarantine_reasons", [])) < 10:
        blockers.append("quarantine_reason_set_incomplete")
    source_custody = import_contract.get("source_custody", {})
    if source_custody.get("raw_workbooks_in_GitHub") is not False or source_custody.get("raw_rows_in_synthetic_CRM") is not False:
        blockers.append("raw_source_custody_invalid")
    execution = import_contract.get("execution", {})
    for key in ("dry_run_permitted", "real_import_permitted", "autonomous_outreach_permitted", "autonomous_investor_matching_permitted", "autonomous_offer_or_financing_action_permitted"):
        if execution.get(key) is not False:
            blockers.append(f"unsafe_import_execution:{key}")
    if execution.get("synthetic_fixture_import_permitted") is not True or execution.get("human_approval_required") is not True:
        blockers.append("synthetic_or_human_import_control_invalid")

    pipelines = vertical.get("pipelines", {})
    if set(pipelines) != {"property_sourcing", "agency_relationship", "investor_relationship", "deal_execution"}:
        blockers.append("pipeline_set_mismatch")
    if "offer_submitted_by_client" not in pipelines.get("deal_execution", []):
        blockers.append("client_owned_offer_stage_missing")
    if "contacted_by_human" not in pipelines.get("agency_relationship", []):
        blockers.append("human_contact_stage_missing")
    if "opportunity_presented_by_human" not in pipelines.get("investor_relationship", []):
        blockers.append("human_investor_presentation_stage_missing")

    formula = vertical.get("formula_and_metric_controls", {})
    if formula.get("source_formulas_are_authoritative") is not False:
        blockers.append("source_formulas_cannot_be_authoritative")
    for key in ("formula_version_required", "input_provenance_required", "human_review_required"):
        if formula.get(key) is not True:
            blockers.append(f"formula_control_missing:{key}")
    prohibited_repr = set(formula.get("prohibited_representations", []))
    if not {"certified property valuation", "guaranteed return", "investment recommendation", "mortgage advice"}.issubset(prohibited_repr):
        blockers.append("formula_prohibited_representation_set_incomplete")

    quarantine = vertical.get("deduplication_and_quarantine", {})
    if quarantine.get("weak_single_key_overwrite_permitted") is not False:
        blockers.append("weak_single_key_overwrite_permitted")
    if quarantine.get("ambiguous_match_action") != "quarantine" or quarantine.get("missing_authority_action") != "quarantine":
        blockers.append("quarantine_action_mismatch")
    if quarantine.get("manual_curated_record_overwrite_permitted") is not False:
        blockers.append("manual_curated_overwrite_permitted")

    custody = vertical.get("data_custody", {})
    if custody.get("raw_workbook_storage") != "restricted_Drive_only":
        blockers.append("raw_workbook_storage_rule_invalid")
    forbidden = set(custody.get("GitHub_forbidden", []))
    required_forbidden = {"real names", "emails", "phone numbers", "full property addresses", "investor identities", "bank or mortgage documents", "tax IDs", "signatures"}
    if not required_forbidden.issubset(forbidden):
        blockers.append("GitHub_forbidden_data_set_incomplete")
    if "processor_or_implementation_provider_only" not in custody.get("Creixement_role", ""):
        blockers.append("Creixement_data_role_boundary_missing")

    authority = vertical.get("authority_boundaries", {})
    prohibited_scope = set(authority.get("Creixement_prohibited_scope", []))
    required_prohibited = {"habitual paid property mediation", "transaction negotiation", "certified valuation", "investment or financial advice", "mortgage brokerage", "offer submission", "client fund custody"}
    if not required_prohibited.issubset(prohibited_scope):
        blockers.append("Creixement_real_estate_boundary_incomplete")
    if authority.get("agent_registration_status") != "not_verified_for_any_source_record":
        blockers.append("agent_registration_cannot_be_inferred")
    if "does not confer" not in authority.get("Catalonia_boundary", ""):
        blockers.append("Catalonia_agent_boundary_missing")

    ai = vertical.get("AI_controls", {})
    if ai.get("mode") != "shadow_only" or ai.get("named_human_required") is not True or ai.get("rollback_required") is not True:
        blockers.append("AI_shadow_human_rollback_controls_invalid")
    ai_prohibited = set(ai.get("prohibited", []))
    if not {"autonomous contact", "investor selection or ranking for solicitation", "transaction recommendation", "external submission"}.issubset(ai_prohibited):
        blockers.append("AI_prohibited_action_set_incomplete")

    current = vertical.get("current_decision", {})
    for key in ("vertical_schema_ready", "generic_CRM_preserved", "source_workbooks_profiled"):
        if current.get(key) is not True:
            blockers.append(f"required_current_decision_false:{key}")
    if current.get("source_rows_imported") != 0:
        blockers.append("source_rows_imported_must_be_zero")
    for key in ("personal_data_imported", "real_property_data_imported", "real_investor_data_imported"):
        if current.get(key) is not False:
            blockers.append(f"real_data_import_claim:{key}")
    for key in UNSAFE_DECISION_KEYS:
        if current.get(key) is not False:
            blockers.append(f"unsafe_vertical_decision:{key}")

    if staging.get("profile") != "staging" or staging.get("synthetic_only") is not True:
        blockers.append("staging_profile_invalid")
    if staging.get("indexable") is not False or staging.get("public_intake_permitted") is not False or staging.get("client_data_permitted") is not False:
        blockers.append("staging_safety_boundary_invalid")
    if ".invalid/" not in str(staging.get("endpoint", "")):
        blockers.append("staging_endpoint_not_reserved_invalid")
    operator_state = operator.get("current_state", {})
    for key in ("website_indexable", "website_real_intake", "paid_contracting_permitted", "invoice_issue_permitted", "client_personal_data_permitted"):
        if operator_state.get(key) is not False:
            blockers.append(f"unsafe_operator_upstream:{key}")

    warnings.extend([
        "The Maumer workbooks remain restricted source evidence; no source row has been copied or imported.",
        "The generic CRM and public intake remain unchanged and cannot create real-estate records.",
        "Underwriting outputs are internal scenarios with versioned formulas, provenance and human review, not valuations or investment recommendations.",
        "Creixement remains the CRM and workflow implementation provider and is not represented as the real-estate intermediary.",
        "All external outreach, investor presentation, offer, financing, due-diligence and transaction actions remain client-owned and blocked in this source stage.",
    ])

    body = {
        "schema_version": 1,
        "as_of": vertical.get("as_of"),
        "stage": vertical.get("stage"),
        "vertical_schema_ready": not blockers,
        "generic_CRM_preserved": not blockers,
        "entity_schema_count": len(loaded_schemas),
        "extension_sheet_count": len(import_contract.get("destination_extension_sheets", {})),
        "source_workbooks_profiled": len(profiles),
        "source_rows_imported": 0,
        "personal_data_imported": False,
        "real_property_data_imported": False,
        "real_investor_data_imported": False,
        "import_execution_permitted": False,
        "outreach_permitted": False,
        "investor_matching_permitted": False,
        "valuation_offer_financing_or_transaction_action_permitted": False,
        "synthetic_fixture_permitted": not blockers,
        "live_publication_permitted": False,
        "paid_contracting_permitted": False,
        "professional_approval_inferred": False,
        "human_review_required": True,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {**body, "evidence_digest": canonical_digest(body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", type=Path, default=VERTICAL)
    parser.add_argument("--import-contract", type=Path, default=IMPORT_CONTRACT)
    parser.add_argument("--sheets", type=Path, default=SHEETS_CONTRACT)
    parser.add_argument("--lead", type=Path, default=LEAD_SCHEMA)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--operator", type=Path, default=OPERATOR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        load_json(args.vertical), load_json(args.import_contract), load_json(args.sheets),
        load_json(args.lead), load_json(args.staging), load_json(args.operator),
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
