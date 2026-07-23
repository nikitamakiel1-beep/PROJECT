#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.engine import (  # noqa: E402
    RealEstateGovernanceError,
    build_crm_merge_plan,
    calculate_metrics,
    detect_sensitive_fields,
    normalise_property_row,
    score_match,
)


def synthetic_row() -> dict:
    return {
        "CODI": "BA-RI-001",
        "FINANCIACION": 0.70,
        "PRECIO DE COMPRA": 82500,
        "REFORMA ESTIMADA TRADICIONAL": 15000,
        "REFORMA ESTIMADA HABITACIONES": 16900,
        "REFORMA ESTIMADA TEMPORAL": 17900,
        "Tipo interes": 0.032,
        "Años prestamo": 25,
        "AÃ±os prestamo": 25,
        "Downside Tradicional": 500,
        "Base Tradicional": 700,
        "Upside Tradicional": 800,
        "Downside Habitacions": 1100,
        "Base Habitacions": 1300,
        "Upside Habitacions": 1450,
        "Downside Temporal": 1000,
        "Base Temporal": 1350,
        "Upside Temporal": 1600,
        "Habitaciones (en habitacional)": 3,
        "HONORARIOS INMOBILIARIA": 3509,
        "HONORARIOS MAUMER CAPITAL": 4356,
        "Valor referencia": 53778.47,
        "Transfer Tax Rate": 0.10,
        "GASTOS NOTARIA & CO": 1837.5,
        "Other Costs": 0,
        "Vacancy Rate": 0,
        "IBI": 13.47,
        "COMUNIDAD": 60,
        "MANTENIMIENTO TRADICIONAL": 17.61,
        "INMUEBLE ALQUILADO ÚLTIMOS 5 AÑOS?": "NO",
        "INMUEBLE ALQUILADO ÃšLTIMOS 5 AÃ‘OS?": "NO",
        "SEGURO HOGAR": 12.5,
        "MANTENIMIENTO HABITACIONAL": 130,
        "MANTENIMIENTO TEMPORAL": 135,
        "Responsable": "Synthetic Operator",
        "Estat": "Validat",
        "Inmo": "Synthetic Agency",
        "M2": 72,
        "Ciudad": "Synthetic City",
        "Provincia": "Synthetic Province",
        "CCAA": "Synthetic Region",
        "Tradicional": "SI",
        "Habitacional": "SI",
        "Temporal": "SI",
        "Habitaciones": 3,
        "Baños": 1,
        "BaÃ±os": 1,
        "Planta": "2",
        "Ascensor": "SI",
        "Visitat": "NO",
        "Clientes potenciales": "Synthetic Client",
        "Ref.Catastral": "SYNTHETIC-CAD-001",
        "Link": "https://example.invalid/property/001",
        "CARACTERISTIQUES PIS": "Synthetic notes that must remain quarantined.",
    }


def mandate() -> dict:
    return {
        "schema_version": 1,
        "mandate_id": "MAND-ABCDEF123456",
        "lead_id": "LEAD-SYNTHETIC-001",
        "contact_id": "CONTACT-SYNTHETIC-001",
        "investor_type": "individual",
        "budget": {
            "min_eur": 80000,
            "max_eur": 130000,
            "cash_available_eur": 45000,
            "financing_required": True,
            "max_ltv": 0.75,
            "max_renovation_eur": 20000,
        },
        "preferred_regions": ["Synthetic Region"],
        "preferred_cities": ["Synthetic City"],
        "strategies": ["traditional_rental", "room_rental"],
        "return_requirements": {
            "min_gross_yield": 0.07,
            "min_net_yield": 0.04,
            "min_monthly_cash_flow_eur": 100,
        },
        "min_bedrooms": 2,
        "risk_appetite": "medium",
        "timeline": "90 days",
        "status": "active",
        "contact_basis": "synthetic fixture",
    }


def expect_error(fn, marker: str) -> None:
    try:
        fn()
    except RealEstateGovernanceError as exc:
        assert marker in str(exc), str(exc)
    else:
        raise AssertionError(f"expected RealEstateGovernanceError containing {marker!r}")


def main() -> None:
    cases: list[str] = []

    expect_error(
        lambda: normalise_property_row(
            synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="unverified"
        ),
        "source rights",
    )
    cases.append("rights_gate")

    first = normalise_property_row(
        synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="client_authorised"
    )
    second = normalise_property_row(
        synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="client_authorised"
    )
    assert first == second
    assert first["property"]["property_id"].startswith("PROP-")
    assert first["property"]["acquisition_status"] == "validated"
    cases.append("deterministic_normalisation")

    sensitive = detect_sensitive_fields(synthetic_row())
    for name in ("Responsable", "Clientes potenciales", "Ref.Catastral", "Link", "CARACTERISTIQUES PIS"):
        assert name in sensitive
    public_text = json.dumps(first["property"], ensure_ascii=False)
    for raw in ("Synthetic Client", "Synthetic Operator", "example.invalid", "SYNTHETIC-CAD-001", "Synthetic notes"):
        assert raw not in public_text
    cases.append("sensitive_field_quarantine")

    assert len(first["scenarios"]) == 9
    assert {item["strategy"] for item in first["scenarios"]} == {
        "traditional_rental", "room_rental", "temporary_rental"
    }
    assert {item["scenario_band"] for item in first["scenarios"]} == {"downside", "base", "upside"}
    cases.append("three_strategy_scenarios")

    metric = calculate_metrics({
        "purchase_price_eur": 100000,
        "renovation_eur": 10000,
        "transfer_tax_eur": 10000,
        "notary_registry_eur": 2000,
        "agency_fee_eur": 3000,
        "advisory_fee_eur": 4000,
        "other_costs_eur": 0,
        "financing_ratio": 0,
        "interest_rate": 0,
        "loan_term_years": 0,
        "monthly_rent_eur": 1000,
        "monthly_property_tax_eur": 20,
        "monthly_community_eur": 50,
        "monthly_maintenance_eur": 30,
        "monthly_insurance_eur": 10,
        "vacancy_rate": 0,
    })
    assert metric["total_acquisition_cost_eur"] == 129000
    assert metric["monthly_debt_service_eur"] == 0
    assert metric["monthly_cash_flow_eur"] == 890
    cases.append("transparent_underwriting")

    base_room = next(
        item for item in first["scenarios"]
        if item["strategy"] == "room_rental" and item["scenario_band"] == "base"
    )
    match = score_match(mandate(), first["property"], base_room)
    assert match["scores"]["overall"] > 0.70
    assert match["human_approved"] is False
    assert match["status"] == "review_required"
    cases.append("pairwise_match")

    incompatible = copy.deepcopy(mandate())
    incompatible["strategies"] = ["resale"]
    bad_match = score_match(incompatible, first["property"], base_room)
    assert bad_match["scores"]["strategy"] == 0
    assert bad_match["human_approved"] is False
    cases.append("strategy_mismatch")

    merge_plan = build_crm_merge_plan(
        mandate_payload=mandate(),
        property_record=first["property"],
        scenarios=first["scenarios"],
    )
    assert merge_plan["writes_permitted"] is False
    assert merge_plan["external_communication_permitted"] is False
    assert merge_plan["human_review_required"] is True
    assert merge_plan["commercial_objects"]["commercial_opportunity_creation_permitted"] is False
    cases.append("commercial_property_separation")

    missing_code = synthetic_row()
    missing_code.pop("CODI")
    expect_error(
        lambda: normalise_property_row(
            missing_code, source_profile="RE-SOURCE-001", source_row=7, rights_status="owned"
        ),
        "CODI",
    )
    cases.append("missing_property_code")

    malformed = synthetic_row()
    malformed["PRECIO DE COMPRA"] = "not-a-number"
    expect_error(
        lambda: normalise_property_row(
            malformed, source_profile="RE-SOURCE-001", source_row=8, rights_status="owned"
        ),
        "non-numeric",
    )
    cases.append("malformed_financial_input")

    vertical = json.loads((ROOT / "config" / "real-estate-crm-vertical.json").read_text(encoding="utf-8"))
    assert vertical["integration_decision"]["generic_CRM_preserved"] is True
    assert vertical["current_decision"]["source_rows_imported"] == 0
    cases.append("A23_baseline_preserved")

    mapping = json.loads((ROOT / "config" / "real-estate-workbook-field-mapping.json").read_text(encoding="utf-8"))
    assert mapping["rights_status"] == "unverified"
    assert mapping["repository_import_permitted"] is False
    assert any(item["source"] == "CODI" for item in mapping["field_mappings"])
    cases.append("field_mapping_governance")

    contract = json.loads((ROOT / "schemas" / "crm" / "real-estate" / "runtime-sheets-contract.json").read_text(encoding="utf-8"))
    assert contract["principles"]["no_raw_source_rows_in_repository"] is True
    assert "Properties" in contract["sheets"]
    assert "Property Matches" in contract["sheets"]
    cases.append("runtime_sheet_contract")

    assert len(cases) == 13
    print(json.dumps({"suite": "real_estate_runtime", "passed": len(cases), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
