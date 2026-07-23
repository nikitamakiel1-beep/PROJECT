"""Governed property normalization and underwriting calculations."""
from __future__ import annotations

from typing import Any, Mapping

from ._engine_common import (
    MODEL_VERSION,
    PRIVATE_TOKEN_FIELDS,
    QUARANTINED_FIELDS,
    STRATEGIES,
    RealEstateGovernanceError,
    assert_rights_gate,
    confidence,
    detect_sensitive_fields,
    first_value,
    integer,
    monthly_payment,
    normalise_status,
    normalise_text,
    number,
    optional_number,
    owner_alias,
    private_token,
    stable_digest,
    stable_id,
    yes,
)


def normalise_property_row(
    row: Mapping[str, Any],
    *,
    source_profile: str,
    source_row: int,
    rights_status: str,
) -> dict[str, Any]:
    assert_rights_gate(rights_status)

    external_code = normalise_text(row.get("CODI"), 80)
    if not external_code:
        raise RealEstateGovernanceError("CODI is required")

    city = normalise_text(row.get("Ciudad"), 100)
    if not city:
        raise RealEstateGovernanceError("Ciudad is required")

    source_record_digest = stable_digest(
        {
            "source_profile": source_profile,
            "source_row": source_row,
            "external_code": external_code,
            "row": {key: row.get(key) for key in sorted(row)},
        }
    )
    property_id = stable_id(
        "PROP",
        source_profile,
        external_code,
        length=12,
    )
    source_name = normalise_text(row.get("Inmo"), 100)

    property_record = {
        "schema_version": 1,
        "property_id": property_id,
        "external_code": external_code,
        "source_organisation_id": (
            stable_id("COMP", source_name, length=12)
            if source_name
            else None
        ),
        "source_record_digest": source_record_digest,
        "location": {
            "address_alias": None,
            "city": city,
            "province": normalise_text(row.get("Provincia"), 100),
            "autonomous_community": normalise_text(
                row.get("CCAA"),
                100,
            ),
        },
        "features": {
            "property_type": None,
            "area_m2": optional_number(row.get("M2")),
            "bedrooms": integer(row.get("Habitaciones")),
            "bathrooms": optional_number(
                first_value(row, "Baños", "BaÃ±os")
            ),
            "floor": normalise_text(row.get("Planta"), 30),
            "has_elevator": (
                yes(row.get("Ascensor"))
                if row.get("Ascensor") not in (None, "")
                else None
            ),
            "occupancy_status": (
                "rented_recently"
                if yes(
                    first_value(
                        row,
                        "INMUEBLE ALQUILADO ÚLTIMOS 5 AÑOS?",
                        "INMUEBLE ALQUILADO ÃšLTIMOS 5 AÃ‘OS?",
                    )
                )
                else None
            ),
            "room_rental_units": integer(
                row.get("Habitaciones (en habitacional)")
            ),
        },
        "private_tokens": {
            "cadastral_reference_token": private_token(
                row.get("Ref.Catastral")
            ),
            "listing_url_token": private_token(row.get("Link")),
        },
        "acquisition_status": normalise_status(row.get("Estat")),
        "data_confidence": confidence(
            row,
            [
                "CODI",
                "PRECIO DE COMPRA",
                "Ciudad",
                "Provincia",
                "CCAA",
                "Tradicional",
                "Habitacional",
                "Temporal",
                "Estat",
                "Inmo",
            ],
        ),
        "rights_status": rights_status,
        "internal_owner_alias": owner_alias(row.get("Responsable")),
        "last_verified": None,
        "notes_summary": None,
    }

    scenarios = build_scenarios(row, property_id=property_id)
    receipt = {
        "source_profile": source_profile,
        "source_row": source_row,
        "source_record_digest": source_record_digest,
        "external_code": external_code,
        "sensitive_fields_detected": detect_sensitive_fields(row),
        "quarantined_fields": [
            field
            for field in sorted(
                QUARANTINED_FIELDS | set(PRIVATE_TOKEN_FIELDS)
            )
            if row.get(field) not in (None, "")
        ],
        "property_id": property_id,
        "scenario_ids": [
            scenario["scenario_id"] for scenario in scenarios
        ],
        "import_permitted": True,
        "repository_evidence_permitted": False,
    }
    return {
        "property": property_record,
        "scenarios": scenarios,
        "import_receipt": receipt,
    }


def build_scenarios(
    row: Mapping[str, Any],
    *,
    property_id: str,
) -> list[dict[str, Any]]:
    purchase_price = number(row.get("PRECIO DE COMPRA"))
    financing_ratio = number(row.get("FINANCIACION"))
    if financing_ratio > 1:
        financing_ratio /= 100
    financing_ratio = min(max(financing_ratio, 0.0), 1.0)

    interest_rate = number(row.get("Tipo interes"))
    if interest_rate > 1:
        interest_rate /= 100

    loan_term_years = number(
        first_value(row, "Años prestamo", "AÃ±os prestamo")
    )
    reference_value = number(row.get("Valor referencia"))
    transfer_tax_rate = number(
        row.get("Transfer Tax Rate"),
        0.0,
    )
    transfer_tax = (
        max(purchase_price, reference_value) * transfer_tax_rate
    )

    notary_registry = number(row.get("GASTOS NOTARIA & CO"))
    if notary_registry == 0 and purchase_price:
        notary_registry = purchase_price * 0.015 + 600

    common = {
        "purchase_price_eur": purchase_price,
        "transfer_tax_eur": transfer_tax,
        "notary_registry_eur": notary_registry,
        "agency_fee_eur": number(
            row.get("HONORARIOS INMOBILIARIA")
        ),
        "advisory_fee_eur": number(
            row.get("HONORARIOS MAUMER CAPITAL")
        ),
        "other_costs_eur": number(row.get("Other Costs")),
        "financing_ratio": financing_ratio,
        "interest_rate": interest_rate,
        "loan_term_years": loan_term_years,
        "monthly_property_tax_eur": number(row.get("IBI")),
        "monthly_community_eur": number(row.get("COMUNIDAD")),
        "monthly_insurance_eur": number(row.get("SEGURO HOGAR")),
        "vacancy_rate": number(row.get("Vacancy Rate"), 0.0),
    }

    result: list[dict[str, Any]] = []
    for strategy, strategy_config in STRATEGIES.items():
        if not yes(row.get(strategy_config["enabled_field"])):
            continue

        renovation = number(
            row.get(strategy_config["renovation_field"])
        )
        maintenance = number(
            row.get(strategy_config["maintenance_field"])
        )

        for band, rent_field in strategy_config["rent_fields"].items():
            if row.get(rent_field) in (None, ""):
                continue

            assumptions = {
                **common,
                "renovation_eur": renovation,
                "monthly_rent_eur": number(row.get(rent_field)),
                "monthly_maintenance_eur": maintenance,
            }
            result.append(
                {
                    "schema_version": 1,
                    "scenario_id": stable_id(
                        "SCN",
                        property_id,
                        strategy,
                        band,
                        length=16,
                    ),
                    "property_id": property_id,
                    "strategy": strategy,
                    "scenario_band": band,
                    "assumptions": assumptions,
                    "metrics": calculate_metrics(assumptions),
                    "data_confidence": confidence(
                        row,
                        [
                            "PRECIO DE COMPRA",
                            strategy_config["renovation_field"],
                            rent_field,
                            "IBI",
                            "COMUNIDAD",
                            "HONORARIOS INMOBILIARIA",
                            "HONORARIOS MAUMER CAPITAL",
                            "Tipo interes",
                        ],
                    ),
                    "model_version": MODEL_VERSION,
                }
            )
    return result


def calculate_metrics(
    assumptions: Mapping[str, Any],
) -> dict[str, float]:
    purchase = number(assumptions.get("purchase_price_eur"))
    renovation = number(assumptions.get("renovation_eur"))
    transfer_tax = number(assumptions.get("transfer_tax_eur"))
    notary_registry = number(
        assumptions.get("notary_registry_eur")
    )
    agency_fee = number(assumptions.get("agency_fee_eur"))
    advisory_fee = number(assumptions.get("advisory_fee_eur"))
    other_costs = number(assumptions.get("other_costs_eur"))

    financing_ratio = min(
        max(number(assumptions.get("financing_ratio")), 0),
        1,
    )
    interest_rate = min(
        max(number(assumptions.get("interest_rate")), 0),
        1,
    )
    loan_term_years = max(
        number(assumptions.get("loan_term_years")),
        0,
    )
    monthly_rent = number(assumptions.get("monthly_rent_eur"))
    vacancy_rate = min(
        max(number(assumptions.get("vacancy_rate")), 0),
        1,
    )

    monthly_opex = sum(
        number(assumptions.get(field))
        for field in (
            "monthly_property_tax_eur",
            "monthly_community_eur",
            "monthly_maintenance_eur",
            "monthly_insurance_eur",
        )
    )

    total_cost = (
        purchase
        + renovation
        + transfer_tax
        + notary_registry
        + agency_fee
        + advisory_fee
        + other_costs
    )
    financed_amount = purchase * financing_ratio
    monthly_debt_service = monthly_payment(
        financed_amount,
        interest_rate,
        loan_term_years,
    )
    effective_rent = monthly_rent * (1 - vacancy_rate)
    monthly_noi = effective_rent - monthly_opex
    monthly_cash_flow = monthly_noi - monthly_debt_service
    cash_invested = max(total_cost - financed_amount, 0)

    gross_yield = (
        effective_rent * 12 / total_cost if total_cost else 0.0
    )
    net_yield = (
        monthly_noi * 12 / total_cost if total_cost else 0.0
    )
    cash_on_cash = (
        monthly_cash_flow * 12 / cash_invested
        if cash_invested
        else 0.0
    )

    return {
        "total_acquisition_cost_eur": round(total_cost, 2),
        "monthly_debt_service_eur": round(
            monthly_debt_service,
            2,
        ),
        "gross_yield": round(gross_yield, 8),
        "net_yield": round(net_yield, 8),
        "roe": round(cash_on_cash, 8),
        "cash_on_cash": round(cash_on_cash, 8),
        "monthly_cash_flow_eur": round(monthly_cash_flow, 2),
    }
