#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("real_estate_vertical_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    mod = load_module(ROOT / "scripts" / "audit_real_estate_crm_vertical.py")
    vertical = load("config/real-estate-crm-vertical.json")
    contract = load("schemas/crm/real-estate/import-contract.json")
    sheets = load("schemas/crm/sheets-contract.json")
    lead = load("schemas/crm/lead.schema.json")
    staging = load("config/staging-release.json")
    operator = load("config/market-entry-operator-pack.json")
    audit = lambda v=vertical, c=contract: mod.audit(v, c, sheets, lead, staging, operator)
    cases: list[str] = []

    result = audit()
    assert result["blockers"] == [] and result["vertical_schema_ready"] is True
    assert result["source_rows_imported"] == 0
    cases.append("baseline")

    integration = vertical["integration_decision"]
    assert integration["mode"] == "additive_vertical_extension"
    assert integration["generic_CRM_preserved"] is True
    assert integration["generic_intake_modified"] is False
    cases.append("additive_integration")

    bridge = vertical["generic_CRM_bridge"]
    assert set(bridge["preserved_tables"]) == mod.GENERIC_TABLES
    assert bridge["bridge_keys"]["counterparty_to_company"] == "Company ID"
    assert bridge["bridge_keys"]["counterparty_or_investor_to_contact"] == "Contact ID"
    assert bridge["bridge_keys"]["real_estate_deal_to_generic_opportunity"] == "Opportunity ID"
    cases.append("generic_CRM_bridge")

    assert set(lead["required"]) == {"submission_id", "company_name", "contact_name", "email", "service_code", "consent_version"}
    assert not {"property_id", "deal_id", "investor_id"}.intersection(lead["properties"])
    cases.append("generic_lead_unchanged")

    model = {x["entity"]: x["schema"] for x in vertical["entity_model"]}
    assert model == mod.ENTITY_SCHEMAS and len(model) == 8
    cases.append("normalized_entities")

    assert set(vertical["extension_sheets"]) == mod.EXTENSION_SHEETS
    assert set(contract["destination_extension_sheets"]) == mod.EXTENSION_SHEETS
    cases.append("extension_sheets")

    profiles = vertical["source_profiles"]
    assert {x["alias"] for x in profiles} == mod.SOURCE_ALIASES
    assert all(x["source_records_in_GitHub"] is False and x["source_records_imported"] == 0 for x in profiles)
    cases.append("source_profiles_no_rows")

    mappings = vertical["workbook_mapping"]
    assert mappings["mapping_status"] == "column_level_only_no_rows"
    assert any(x["source"] == "TIR" for x in mappings["opportunity_examples"])
    assert any(x["source"] == "Contact Email" for x in mappings["agency_examples"])
    cases.append("source_column_mapping")

    assert contract["mode"] == "dry_run_quarantine_only"
    assert contract["source_records_permitted"] is False
    assert contract["source_custody"]["raw_workbooks_in_GitHub"] is False
    cases.append("restricted_import_contract")

    dedup = contract["deduplication"]
    assert "No single weak key may overwrite" in dedup["rule"]
    assert len(contract["quarantine_reasons"]) >= 10
    cases.append("dedup_and_quarantine")

    formula = vertical["formula_and_metric_controls"]
    assert formula["source_formulas_are_authoritative"] is False
    assert formula["formula_version_required"] and formula["input_provenance_required"] and formula["human_review_required"]
    cases.append("formula_provenance")

    authority = vertical["authority_boundaries"]
    assert "habitual paid property mediation" in authority["Creixement_prohibited_scope"]
    assert authority["agent_registration_status"] == "not_verified_for_any_source_record"
    cases.append("real_estate_authority_boundary")

    ai = vertical["AI_controls"]
    assert ai["mode"] == "shadow_only" and ai["named_human_required"] is True
    assert "investor selection or ranking for solicitation" in ai["prohibited"]
    cases.append("AI_shadow_boundary")

    bad = deepcopy(vertical)
    bad["integration_decision"]["generic_intake_modified"] = True
    assert "forbidden_integration_claim:generic_intake_modified" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_generic_intake_mutation")

    bad = deepcopy(vertical)
    bad["source_profiles"][0]["source_records_imported"] = 1
    assert any(x.startswith("source_records_claimed_imported:") for x in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"])
    cases.append("reject_source_record_import")

    bad = deepcopy(vertical)
    bad["current_decision"]["real_import_permitted"] = True
    assert "unsafe_vertical_decision:real_import_permitted" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_real_import_activation")

    bad = deepcopy(vertical)
    bad["current_decision"]["autonomous_outreach_permitted"] = True
    assert "unsafe_vertical_decision:autonomous_outreach_permitted" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_autonomous_outreach")

    bad_contract = deepcopy(contract)
    bad_contract["deduplication"]["rule"] = "Overwrite on name match"
    assert "weak_key_overwrite_guard_missing" in mod.audit(vertical, bad_contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_weak_key_overwrite")

    bad = deepcopy(vertical)
    bad["formula_and_metric_controls"]["source_formulas_are_authoritative"] = True
    assert "source_formulas_cannot_be_authoritative" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_authoritative_source_formula")

    bad = deepcopy(vertical)
    bad["authority_boundaries"]["Creixement_prohibited_scope"].remove("habitual paid property mediation")
    assert "Creixement_real_estate_boundary_incomplete" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_intermediation_boundary_removal")

    bad = deepcopy(vertical)
    bad["AI_controls"]["prohibited"].remove("investor selection or ranking for solicitation")
    assert "AI_prohibited_action_set_incomplete" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_investor_selection")

    bad = deepcopy(vertical)
    bad["current_decision"]["offer_or_financing_action_permitted"] = True
    assert "unsafe_vertical_decision:offer_or_financing_action_permitted" in mod.audit(bad, contract, sheets, lead, staging, operator)["blockers"]
    cases.append("reject_offer_financing_action")

    first = audit()
    second = audit()
    assert first["evidence_digest"] == second["evidence_digest"]
    cases.append("deterministic_receipt")

    assert len(cases) == 23
    print(f"real-estate CRM vertical validation passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
