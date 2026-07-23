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
        "IBI": 13.47,
        "COMUNIDAD": 60,
        "MANTENIMIENTO TRADICIONAL": 17.61,
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
        assert marker in str(exc)
    else:
        raise AssertionError(f"expected RealEstateGovernanceError containing {marker!r}")


def main() -> None:
    tests: list[dict] = []

    expect_error(
        lambda: normalise_property_row(
            synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="unverified"
        ),
        "source rights",
    )
    tests.append({"case": "rights_gate", "result": "passed"})

    first = normalise_property_row(
        synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="client_authorised"
    )
    second = normalise_property_row(
        synthetic_row(), source_profile="RE-SOURCE-001", source_row=6, rights_status="client_authorised"
    )
    assert first == second
    assert first["property"]["property_id"].startswith("PROP-")
    assert first["property"]["acquisition_status"] == "validated"
    tests.append({"case": "deterministic_normalisation", "result": "passed"})

    sensitive = detect_sensitive_fields(synthetic_row())
    for required in ("Responsable", "Clientes potenciales", "Ref.Catastral", "Link", "CARACTERISTIQUES PIS"):
        assert required in sensitive
    public_text = json.dumps(first["property"], ensure_ascii=False)
    assert "Synthetic Client" not in public_text
    assert "Synthetic Operator" not in public_text
    assert "example.invalid" not in public_text
    assert "SYNTHETIC-CAD-001" not in public_text
    assert "Synthetic notes" not in public_text
    tests.append({"case": "sensitive_field_quarantine", "result": "passed"})

    assert len(first["scenarios"]) == 9
    assert {item["strategy"] for item in first["scenarios"]} == {
        "traditional_rental", "room_rental", "temporary_rental"
    }
    assert {item["scenario_band"] for item in first["scenarios"]} == {"downside", "base", "upside"}
    tests.append({"case": "three_strategy_scenarios", "result": "passed"})

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
    assert round(metric["gross_yield"], 4) == round(12000 / 129000, 4)
    tests.append({"case": "transparent_underwriting", "result": "passed"})

    base_room = next(
        item for item in first["scenarios"]
        if item["strategy"] == "room_rental" and item["scenario_band"] == "base"
    )
    match = score_match(mandate(), first["property"], base_room)
    assert match["scores"]["overall"] > 0.75
    assert match["human_approved"] is False
    assert match["status"] == "review_required"
    tests.append({"case": "investor_match", "result": "passed"})

    incompatible = copy.deepcopy(mandate())
    incompatible["strategies"] = ["resale"]
    bad_match = score_match(incompatible, first["property"], base_room)
    assert bad_match["scores"]["strategy"] == 0
    assert bad_match["scores"]["overall"] < HX]ÚÈœØÛÜ™\È—VÈ›Ý™\˜[—Bˆ\ÝË˜\[™
È˜Ø\ÙHŽˆœÝ˜]YÞWÛZ\ÛX]Ú‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆ[ˆHZ[ØÜ›WÛY\™ÙWÜ[ŠˆX[™]WÜ^[ØY[X[™]J
Kˆ›Ü\WÜ™XÛÜ™Yš\œÝÈœ›Ü\H—KˆØÙ[˜\š[ÜÏYš\œÝÈœØÙ[˜\š[ÜÈ—Kˆ
Bˆ\ÜÙ\[–ÈÜš]\×Ü\›Z]Y—H\È˜[ÙBˆ\ÜÙ\[–È™^\›˜[ØÛÛ[][šXØ][Û—Ü\›Z]Y—H\È˜[ÙBˆ\ÜÙ\[–È˜ÛÛ[Y\˜ÚX[ÛØš™XÝÈ—VÈ˜ÛÛ[Y\˜ÚX[ÛÜÜ[š]WØÜ™X][Û—Ü\›Z]Y—H\È˜[ÙBˆ\ÜÙ\[Š[–Èœ™X[Ù\Ý]WÛØš™XÝÈ—VÈ›X]Ú\È—JHOHBˆ\ÝË˜\[™
È˜Ø\ÙHŽˆ˜ÛÛ[Y\˜ÚX[Ü›Ü\WÜÙ\\˜][Ûˆ‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆZ\ÜÚ[™ÈHÞ[]X×Ü›ÝÊ
BˆZ\ÜÚ[™ÖÈÓÑH—HHˆ‚ˆ^XÝÙ\œ›ÜŠˆ[X™Nˆ›Ü›X[\ÙWÜ›Ü\WÜ›ÝÊˆZ\ÜÚ[™ËÛÝ\˜ÙWÜ›Ùš[OH”‘KTÓÕTÑKLH‹ÛÝ\˜ÙWÜ›ÝÏMËšYÚ×ÜÝ]\ÏH›ÝÛ™Y‚ˆ
KˆÓÑH‹ˆ
Bˆ\ÝË˜\[™
È˜Ø\ÙHŽˆœ™\]Z\™YÜ›Ü\WØÛÙH‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆX[›Ü›YYHÞ[]X×Ü›ÝÊ
BˆX[›Ü›YYÈ”‘PÒSÈHÓÓTH—HH››ÝXK[[X™\ˆ‚ˆ^XÝÙ\œ›ÜŠˆ[X™Nˆ›Ü›X[\ÙWÜ›Ü\WÜ›ÝÊˆX[›Ü›YYÛÝ\˜ÙWÜ›Ùš[OH”‘KTÓÕTÑKLH‹ÛÝ\˜ÙWÜ›ÝÏNšYÚ×ÜÝ]\ÏH›XÙ[œÙY‚ˆ
Kˆ››Û‹[[Y\šXÈ‹ˆ
Bˆ\ÝË˜\[™
È˜Ø\ÙHŽˆ›X[›Ü›YYÙš[˜[˜ÚX[Ý˜[YH‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆ˜\Ù[[™HHœÛÛ‹›ØYÊ
“ÓÕÈ˜ÛÛ™šYÈˆÈœ™X[Y\Ý]KXÜ›K]™\XØ[šœÛÛˆŠKœ™XYÝ^
[˜ÛÙ[™ÏH]‹NŠJBˆ\ÜÙ\˜\Ù[[™VÈ˜]]Üš]WØ›Ý[™\šY\È—VÈœ™X[Ù\Ý]WØXÝ[Û—ÛÝÛ™\ˆ—Bˆ\ÜÙ\˜\Ù[[™VÈ˜Ý\œ™[ÙXÚ\Ú[Ûˆ—VÈœ™X[Ú[\ÜÜ\›Z]Y—H\È˜[ÙBˆ\ÝË˜\[™
È˜Ø\ÙHŽˆ˜LŒ×Ø˜\Ù[[™WÜ™\Ù\™Y‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆÛÝ\˜ÙWÛX\[™ÈHœÛÛ‹›ØYÊˆ
“ÓÕÈ˜ÛÛ™šYÈˆÈœ™X[Y\Ý]K]ÛÜšØ›ÛÚËYšY[[X\[™ËšœÛÛˆŠKœ™XYÝ^
[˜ÛÙ[™ÏH]‹NŠBˆ
Bˆ\ÜÙ\ÛÝ\˜ÙWÛX\[™ÖÈœ™\ÜÚ]ÜžWÚ[\ÜÜ\›Z]Y—H\È˜[ÙBˆ\ÜÙ\ÛÝ\˜ÙWÛX\[™ÖÈ›ØœÙ\™YÜ™XÛÜ™ØÛÝ[—HOHÍÌˆXÝ[ÛœÈHÂˆ][VÈœÛÝ\˜ÙH—Nˆ][K™Ù]
˜XÝ[ÛˆŠBˆ›Üˆ][H[ˆÛÝ\˜ÙWÛX\[™ÖÈ™šY[ÛX\[™ÜÈ—BˆYˆ][K™Ù]
˜XÝ[ÛˆŠBˆBˆ\ÜÙ\XÝ[ÛœÖÈÛY[\ÈÝ[˜ÚX[\È—HOHœ]X\˜[[™H‚ˆ\ÜÙ\XÝ[ÛœÖÈ”™Y‹Ø]\Ý˜[—HOHœš]˜]WÙš]™WÛÛ›H‚ˆ\ÝË˜\[™
È˜Ø\ÙHŽˆœÛÝ\˜ÙWÛX\[™×ÙÛÝ™\›˜[˜ÙH‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆÛÛ˜XÝHœÛÛ‹›ØYÊˆ
“ÓÕÈœØÚ[X\ÈˆÈ˜Ü›HˆÈœ™X[Y\Ý]HˆÈœ[[YK\ÚY]ËXÛÛ˜XÝšœÛÛˆŠKœ™XYÝ^
[˜ÛÙ[™ÏH]‹NŠBˆ
Bˆ\ÜÙ\”›Ü\Y\Èˆ[ˆÛÛ˜XÝÈœÚY]È—Bˆ\ÜÙ\”›Ü\HØÙ[˜\š[ÜÈˆ[ˆÛÛ˜XÝÈœÚY]È—Bˆ\ÜÙ\’[™\ÝÜˆX[™]\Èˆ[ˆÛÛ˜XÝÈœÚY]È—Bˆ\ÜÙ\”›Ü\HX]Ú\Èˆ[ˆÛÛ˜XÝÈœÚY]È—Bˆ\ÜÙ\ÛÛ˜XÝÈœš[˜Ú\\È—VÈž™\›×ØÛY[ÜÝ]WÝ˜[Y—H\ÈYBˆ\ÝË˜\[™
È˜Ø\ÙHŽˆ™^[œÚ[Û—ØÛÛ˜XÝ‹œ™\Ý[Žˆœ\ÜÙYŸJB‚ˆš[
œÛÛ‹™[\ÊÈ›ÚÈŽˆYK\ÝÈŽˆ\ÝßK[™[LŠJB‚‚šYˆ×Û˜[YW×ÈOH—×ÛXZ[—×ÈŽ‚ˆXZ[Š
B