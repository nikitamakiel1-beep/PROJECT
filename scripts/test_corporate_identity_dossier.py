#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("identity_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_audit(mod, dossier, company, operator, staging):
    return mod.audit(dossier, company, operator, staging)


def main() -> None:
    mod = load_module(ROOT / "scripts" / "audit_corporate_identity_dossier.py")
    load = lambda name: json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))
    dossier = load("corporate-identity-dossier.json")
    company = load("company-formation-readiness.json")
    operator = load("market-entry-operator-pack.json")
    staging = load("staging-release.json")
    cases = []

    result = run_audit(mod, dossier, company, operator, staging)
    assert result["blockers"] == [] and result["identity_dossier_ready"] is True
    cases.append("baseline")

    names = dossier["corporate_name_strategy"]["ordered_candidates"]
    assert len(names) == 5 and [x["order"] for x in names] == [1, 2, 3, 4, 5]
    cases.append("five_ordered_names")
    assert all(x["name"].endswith("S.L.U.") for x in names)
    cases.append("social_form_suffix")
    assert all(x["availability_status"] == "not_checked" and x["certificate_status"] == "not_requested" for x in names)
    cases.append("names_unverified")

    rules = dossier["corporate_name_strategy"]["RMC_rules"]
    assert rules["maximum_names_per_request"] == 5 and rules["preliminary_consultation_is_binding"] is False
    assert rules["favourable_certificate_reservation_months"] == 6 and rules["certificate_valid_for_deed_months"] == 3
    cases.append("RMC_rules")

    brand = dossier["corporate_name_strategy"]["parallel_brand_checks"]
    assert all(brand[k] == "not_started" for k in ("trademark_screen", "domain_screen", "social_handle_screen", "linguistic_and_reputation_screen"))
    cases.append("brand_checks_separate")

    office = dossier["registered_office_strategy"]
    assert office["selected_option"] is None and office["real_address_present"] is False
    assert {x["id"] for x in office["options"]} == mod.OFFICE_IDS
    cases.append("office_unselected")
    options = {x["id"]: x for x in office["options"]}
    assert options["COWORKING_PHYSICAL"]["status"] == "provisional_preferred_not_selected"
    assert options["VIRTUAL_MAIL_ONLY"]["status"] == "not_recommended_without_professional_review"
    cases.append("office_guard")

    fue = dossier["FUE_input_questionnaire"]
    questions = {x["id"]: x for x in fue["questions"]}
    assert fue["submission_performed"] is False and set(questions) == mod.FUE_QUESTION_IDS
    assert questions["FULL_ADDRESS"]["value"] == "restricted_not_supplied"
    cases.append("FUE_template")

    activity = dossier["activity_classification_candidates"]
    assert activity["CNAE_version"] == "CNAE-2025"
    assert {x["code"] for x in activity["CNAE_candidates"]} == mod.CNAE_CODES
    cases.append("CNAE_candidates")
    assert {x["heading"] for x in activity["IAE_candidates"]} == mod.IAE_HEADINGS
    assert "separate systems" in activity["IAE_system_rule"]
    cases.append("IAE_candidates")
    assert activity["CNAE_confirmed"] is False and activity["IAE_confirmed"] is False
    cases.append("classifications_unconfirmed")
    translation = next(x for x in activity["CNAE_candidates"] if x["code"] == "74.30")
    assert translation["boundary"] == "does_not_authorise_sworn_or_certified_translation"
    cases.append("translation_boundary")

    handoff = dossier["notary_PAE_handoff"]
    assert handoff["route_selected"] is False and handoff["notary_or_PAE_instructed"] is False
    cases.append("handoff_uninstructed")

    bad = deepcopy(dossier)
    bad["corporate_name_strategy"]["ordered_candidates"].pop()
    assert "corporate_name_candidate_count_mismatch" in run_audit(mod, bad, company, operator, staging)["blockers"]
    cases.append("reject_missing_name")

    bad = deepcopy(dossier)
    bad["corporate_name_strategy"]["ordered_candidates"][0]["name"] = "Creixement International Systems"
    assert "corporate_name_missing_SLU:1" in run_audit(mod, bad, company, operator, staging)["blockers"]
    cases.append("reject_missing_suffix")

    bad = deepcopy(dossier)
    bad["current_decision"]["name_certificate_obtained"] = True
    assert "unsafe_identity_decision:name_certificate_obtained" in run_audit(mod, bad, company, operator, staging)["blockers"]
    cases.append("reject_certificate_claim")

    first = run_audit(mod, dossier, company, operator, staging)
    second = run_audit(mod, dossier, company, operator, staging)
    assert first["evidence_digest"] == second["evidence_digest"]
    cases.append("deterministic_receipt")

    assert len(cases) == 18
    print(f"corporate identity dossier validation passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
