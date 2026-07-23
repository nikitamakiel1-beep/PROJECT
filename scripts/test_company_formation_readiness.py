#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    mod = load_module(ROOT / "scripts" / "audit_company_formation_readiness.py", "company_readiness_audit")
    company = json.loads((ROOT / "config" / "company-formation-readiness.json").read_text(encoding="utf-8"))
    operator_pack = json.loads((ROOT / "config" / "market-entry-operator-pack.json").read_text(encoding="utf-8"))
    licensing = json.loads((ROOT / "config" / "market-entry-licensing.json").read_text(encoding="utf-8"))
    staging = json.loads((ROOT / "config" / "staging-release.json").read_text(encoding="utf-8"))

    cases: list[str] = []

    baseline = mod.audit(company, operator_pack, licensing, staging)
    assert baseline["blockers"] == []
    assert baseline["formation_readiness_ready"] is True
    assert baseline["company_route_selected"] is True
    assert baseline["official_filings_verified"] == 0
    assert baseline["legal_entity_exists"] is False
    cases.append("baseline_company_readiness_passes_without_claiming_formation")

    owner = company["owner_decision"]
    assert owner["operating_form"] == "COMPANY"
    assert owner["company_form"] == "SOCIEDAD_LIMITADA_UNIPERSONAL"
    assert owner["shareholder_count"] == 1
    cases.append("owner_company_route_and_provisional_SLU_are_explicit")

    capital = company["capital_plan"]
    assert capital["legal_minimum_eur"] == 1
    assert capital["recommended_eur"] == 3000
    assert capital["contribution_status"] == "not_contributed"
    assert capital["under_3000_safeguards"]["legal_reserve_percent_of_profit"] == 20
    cases.append("capital_plan_distinguishes_law_recommendation_and_contribution")

    assert tuple(item["id"] for item in company["formation_sequence"]) == mod.SEQUENCE_IDS
    assert tuple(item["order"] for item in company["formation_sequence"]) == tuple(range(1, 17))
    cases.append("company_formation_sequence_is_exact_and_ordered")

    assert company["formation_sequence"][0]["status"] == "owner_decision_recorded_not_incorporated"
    assert company["current_decision"]["legal_entity_exists"] is False
    cases.append("owner_decision_cannot_become_legal_entity_claim")

    sequence = {item["id"]: item for item in company["formation_sequence"]}
    assert "formation_deed" in sequence["CORPORATE_NAME"]["blocks"]
    assert "municipal_path" in sequence["REGISTERED_OFFICE"]["blocks"]
    cases.append("name_and_address_gate_deed_and_municipal_path")

    assert "exact municipality, address and use" in sequence["MUNICIPAL_PATH"]["evidence_required"]
    cases.append("municipal_classification_is_address_specific")

    purpose = company["corporate_purpose_draft"]
    for marker in mod.REQUIRED_EXCLUSIONS:
        assert marker in purpose["excluded_regulated_activities"]
    assert purpose["status"] == "bounded_draft_not_approved"
    cases.append("corporate_purpose_is_bounded_and_unapproved")

    governance = company["governance_plan"]
    assert governance["social_security_classification"] == "provisional_autonomo_societario_review_required"
    assert governance["social_security_verified"] is False
    cases.append("administrator_social_security_route_remains_provisional")

    custody = company["restricted_custody"]
    assert "never in public source control" in custody["storage_rule"]
    assert "NIF_or_personal_ID" in custody["forbidden_public_fields"]
    assert "bank_account" in custody["forbidden_public_fields"]
    cases.append("sensitive_incorporation_evidence_is_restricted")

    tampered = deepcopy(company)
    tampered["owner_decision"]["legal_entity_exists"] = True
    assert "unsafe_owner_claim:legal_entity_exists" in mod.audit(tampered, operator_pack, licensing, staging)["blockers"]
    cases.append("false_legal_entity_claim_is_rejected")

    tampered = deepcopy(company)
    tampered["formation_sequence"][10]["status"] = "verified"
    assert "unsupported_formation_status:PROVISIONAL_NIF" in mod.audit(tampered, operator_pack, licensing, staging)["blockers"]
    cases.append("unverified_official_filing_cannot_be_promoted")

    tampered = deepcopy(company)
    tampered["capital_plan"]["legal_minimum_eur"] = 0
    assert "legal_minimum_capital_mismatch" in mod.audit(tampered, operator_pack, licensing, staging)["blockers"]
    cases.append("invalid_capital_floor_is_rejected")

    tampered = deepcopy(company)
    tampered["current_decision"]["invoice_issue_permitted"] = True
    assert "unsafe_company_decision:invoice_issue_permitted" in mod.audit(tampered, operator_pack, licensing, staging)["blockers"]
    cases.append("invoice_activation_bypass_is_rejected")

    tampered = deepcopy(company)
    tampered["corporate_purpose_draft"]["excluded_regulated_activities"].remove("legal advice")
    assert any(item.startswith("regulated_activity_exclusions_missing:") for item in mod.audit(tampered, operator_pack, licensing, staging)["blockers"])
    cases.append("missing_regulated_activity_exclusion_is_rejected")

    first = mod.audit(company, operator_pack, licensing, staging)
    second = mod.audit(company, operator_pack, licensing, staging)
    assert first["evidence_digest"] == second["evidence_digest"]
    cases.append("company_readiness_receipt_is_deterministic")

    assert len(cases) == 16
    print(f"company-formation readiness validation passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
