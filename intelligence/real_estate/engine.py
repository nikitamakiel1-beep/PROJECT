"""Governed real-estate CRM vertical.

This module converts private opportunity-workbook rows into pseudonymous property,
scenario and match objects. It does not import raw clients, contacts, URLs,
cadastral references or free-text notes into repository evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping


MODEL_VERSION = "real-estate-underwriting-v0.1"
STATUS_MAP = {
    "excel": "discovered",
    "wip": "analysis_in_progress",
    "validat": "validated",
    "validado": "validated",
    "ppt": "presentation_ready",
    "compartit": "shared",
    "compartido": "shared",
    "reservat": "reserved",
    "reservado": "reserved",
    "descartat": "rejected",
    "descartado": "rejected",
}
STRATEGIES = {
    "traditional_rental": {
        "enabled_field": "Tradicional",
        "renovation_field": "REFORMA ESTIMADA TRADICIONAL",
        "rent_fields": {
            "downside": "Downside Tradicional",
            "base": "Base Tradicional",
            "upside": "Upside Tradicional",
        },
        "maintenance_field": "MANTENIMIENTO TRADICIONAL",
    },
    "room_rental": {
        "enabled_field": "Habitacional",
        "renovation_field": "REFORMA ESTIMADA HABITACIONES",
        "rent_fields": {
            "downside": "Downside Habitacions",
            "base": "Base Habitacions",
            "upside": "Upside Habitacions",
        },
        "maintenance_field": "MANTENIMIENTO HABITACIONAL",
    },
    "temporary_rental": {
        "enabled_field": "Temporal",
        "renovation_field": "REFORMA ESTIMADA TEMPORAL",
        "rent_fields": {
            "downside": "Downside Temporal",
            "base": "Base Temporal",
            "upside": "Upside Temporal",
        },
        "maintenance_field": "MANTENIMIENTO TEMPORAL",
    },
}
QUARANTINED_FIELDS = {
    "Responsable",
    "Clientes potenciales",
    "CARACTERISTIQUES PIS",
}
PRIVATE_TOKEN_FIELDS = {
    "Ref.Catastral": "cadastral_reference_token",
    "Link": "listing_url_token",
}
PII_MARKERS = {
    "email",
    "phone",
    "telefono",
    "teléfono",
    "full name",
    "contact name",
    "client name",
    "cliente",
    "clientes potenciales",
    "responsable",
}


class RealEstateGovernanceError(ValueError):
    """Raised when the source row or rights state violates the import boundary."""


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any, length: int) -> str:
    digest = sha256("|".join("" if part is None else str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:length].upper()}"


def _token(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _stable_id("TOKEN", str(value).strip(), length=16)


def _owner_alias(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _stable_id("OWNER", str(value).strip().casefold(), length=12)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = str(value).strip().replace("€", "").replace("%", "")
        text = text.replace(" ", "")
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            text = text.replace(",", "")
        try:
            result = float(text)
        except ValueError as exc:
            raise RealEstateGovernanceError(f"non-numeric value: {value!r}") from exc
    if not math.isfinite(result):
        raise RealEstateGovernanceError("numeric values must be finite")
    return result


def _optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _number(value)


def _integer(value: Any) -> int | None:
    number = _optional_number(value)
    if number is None:
        return None
    return int(round(number))


def _yes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"si", "sí", "yes", "true", "1", "x"}


def _normalise_status(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return STATUS_MAP.get(text, "analysis_in_progress" if text else "discovered")


def _normalise_text(value: Any, max_length: int = 120) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:max_length] or None


def _monthly_payment(principal: float, annual_rate: float, years: float) -> float:
    if principal <= 0 or years <= 0:
        return 0.0
    periods = int(round(years * 12))
    if periods <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate <= 0:
        return principal / periods
    factor = (1 + monthly_rate) ** periods
    return principal * monthly_rate * factor / (factor - 1)


def _confidence(row: Mapping[str, Any], required: Iterable[str]) -> float:
    required_list = list(required)
    if not required_list:
        return 0.0
    present = sum(1 for field in required_list if row.get(field) not in (None, ""))
    return round(present / len(required_list), 6)


def assert_rights_gate(rights_status: str) -> None:
    if rights_status not in {"owned", "licensed", "client_authorised", "public_source"}:
        raise RealEstateGovernanceError(
            "row-level import blocked: source rights must be owned, licensed, client_authorised or public_source"
        )


def detect_sensitive_fields(row: Mapping[str, Any]) -> list[str]:
    found: set[str] = set()
    for key, value in row.items():
        lowered = str(key).casefold()
        if any(marker in lowered for marker in PII_MARKERS) and value not in (None, ""):
            found.add(str(key))
        if str(key) in PRIVATE_TOKEN_FIELDS and value not in (None, ""):
            found.add(str(key))
        if str(key) in QUARANTINED_FIELDS and value not in (None, ""):
            found.add(str(key))
    return sorted(found)


def normalise_property_row(
    row: Mapping[str, Any],
    *,
    source_profile: str,
    source_row: int,
    rights_status: str,
) -> dict[str, Any]:
    assert_rights_gate(rights_status)
    external_code = _normalise_text(row.get("CODI"), 80)
    if not external_code:
        raise RealEstateGovernanceError("CODI is required")
    city = _normalise_text(row.get("Ciudad"), 100)
    if not city:
        raise RealEstateGovernanceError("Ciudad is required")
    source_record_digest = _stable_digest({
        "source_profile": source_profile,
        "source_row": source_row,
        "external_code": external_code,
        "row": {key: row.get(key) for key in sorted(row)},
    })
    property_id = _stable_id("PROP", source_profile, external_code, length=12)
    property_record = {
        "schema_version": 1,
        "property_id": property_id,
        "external_code": external_code,
        "source_organisation_id": (
            _stable_id("COMP", _normalise_text(row.get("Inmo"), 100), length=12)
            if _normalise_text(row.get("Inmo"), 100)
            else None
        ),
        "source_record_digest": source_record_digest,
        "location": {
            "address_alias": None,
            "city": city,
            "province": _normalise_text(row.get("Provincia"), 100),
            "autonomous_community": _normalise_text(row.get("CCAA"), 100),
        },
        "features": {
            "property_type": None,
            "area_m2": _optional_number(row.get("M2")),
            "bedrooms": _integer(row.get("Habitaciones")),
            "bathrooms": _optional_number(row.get("Baños")),
            "floor": _normalise_text(row.get("Planta"), 30),
            "has_elevator": _yes(row.get("Ascensor")) if row.get("Ascensor") not in (None, "") else None,
            "occupancy_status": (
                "rented_recently"
                if _yes(row.get("INMUEBLE ALQUILADO ÚLTIMOS 5 AÑOS?"))
                else None
            ),
            "room_rental_units": _integer(row.get("Habitaciones (en habitacional)")),
        },
        "private_tokens": {
            "cadastral_reference_token": _token(row.get("Ref.Catastral")),
            "listing_url_token": _token(row.get("Link")),
        },
        "acquisition_status": _normalise_status(row.get("Estat")),
        "data_confidence": _confidence(
            row,
            [
                "CODI", "PRECIO DE COMPRA", "Ciudad", "Provincia", "CCAA",
                "Tradicional", "Habitacional", "Temporal", "Estat", "Inmo",
            ],
        ),
        "rights_status": rights_status,
        "internal_owner_alias": _owner_alias(row.get("Responsable")),
        "last_verified": None,
        "notes_summary": None,
    }
    scenarios = build_scenarios(row, property_id=property_id)
    import_receipt = {
        "source_profile": source_profile,
        "source_row": source_row,
        "source_record_digest": source_record_digest,
        "external_code": external_code,
        "sensitive_fields_detected": detect_sensitive_fields(row),
        "quarantined_fields": [
            field for field in sorted(set(QUARANTINED_FIELDS) | set(PRIVATE_TOKEN_FIELDS))
            if row.get(field) not in (None, "")
        ],
        "property_id": property_id,
        "scenario_ids": [item["scenario_id"] for item in scenarios],
        "import_permitted": True,
        "repository_evidence_permitted": False,
    }
    return {"property": property_record, "scenarios": scenarios, "import_receipt": import_receipt}


def build_scenarios(row: Mapping[str, Any], *, property_id: str) -> list[dict[str, Any]]:
    purchase_price = _number(row.get("PRECIO DE COMPRA"))
    financing_ratio = _number(row.get("FINANCIACION"))
    if financing_ratio > 1:
        financing_ratio /= 100
    financing_ratio = min(max(financing_ratio, 0.0), 1.0)
    interest_rate = _number(row.get("Tipo interes")
    if interest_rate > 1:
        interest_rate /= 100
    loan_term_years = _number(row.get("Años prestamo"))
    reference_value = _number(row.get("Valor referencia"))
    transfer_tax_rate = _number(row.get("Transfer Tax Rate"), 0.0)
    transfer_tax = max(purchase_price, reference_value) * transfer_tax_rate
    notary_registry = _number(row.get("GASTOS NOTARIA & CO"))
    if notary_registry == 0 and purchase_price:
        notary_registry = purchase_price * 0.015 + 600
    common = {
        "purchase_price_eur": purchase_price,
        "transfer_tax_eur": transfer_tax,
        "notary_registry_eur": notary_registry,
        "agency_fee_eur": _number(row.get("HONORARIOS INMOBILIARIA")),
        "advisory_fee_eur": _number(row.get("HONORARIOS MAUMER CAPITAL")),
        "other_costs_eur": _number(row.get("Other Costs"),
        "financing_ratio": financing_ratio,
        "interest_rate": interest_rate,
        "loan_term_years": loan_term_years,
        "monthly_property_tax_eur": _number(row.get("IBI")),
        "monthly_community_eur": _number(row.get("COMUNIDAD")),
        "monthly_insurance_eur": _number(row.get("SEGURO HOGAR")),
        "vacancy_rate": _number(row.get("Vacancy Rate"), 0.0),
    }
    result: list[dict[str, Any]] = []
    for strategy, config in STRATEGIES.items():
        if not _yes(row.get(config["enabled_field"])):
            continue
        renovation = _number(row.get(config["renovation_field"]))
        maintenance = _number(row.get(config["maintenance_field"]))
        for band, rent_field in config["rent_fields"].items():
            if row.get(rent_field) in (None, ""):
                continue
            monthly_rent = _number(row.get(rent_field))
            assumptions = {
                **common,
                "renovation_eur": renovation,
                "monthly_rent_eur": monthly_rent,
                "monthly_maintenance_eur": maintenance,
            }
            metrics = calculate_metrics(assumptions)
            scenario_id = _stable_id("SCN", property_id, strategy, band, length=16)
            result.append({
                "schema_version": 1,
                "scenario_id": scenario_id,
                "property_id": property_id,
                "strategy": strategy,
                "scenario_band": band,
                "assumptions": assumptions,
                "metrics": metrics,
                "data_confidence": _confidence(
                    row,
                    [
                        "PRECIO DE COMPRA", config["renovation_field"], rent_field,
                        "IBI", "COMUNIDAD", "HONORARIOS INMOBILIARIA",
                        "HONORARIOS MAUMER CAPITAL", "Tipo interes", "Años prestamo",
                    ],
                ),
                "model_version": MODEL_VERSION,
            })
    return result


def calculate_metrics(assumptions: Mapping[str, Any]) -> dict[str, float]:
    purchase = _number(assumptions.get("purchase_price_eur"))
    renovation = _number(assumptions.get("renovation_eur"))
    tax = _number(assumptions.get("transfer_tax_eur"))
    notary = _number(assumptions.get("notary_registry_eur"))
    agency = _number(assumptions.get("agency_fee_eur"))
    advisory = _number(assumptions.get("advisory_fee_eur"))
    other = _number(assumptions.get("other_costs_eur"))
    financing_ratio = min(max(_number(assumptions.get("financing_ratio")), 0), 1)
    rate = min(max(_number(assumptions.get("interest_rate")), 0), 1)
    years = max(_number(assumptions.get("loan_term_years")), 0)
    monthly_rent = _number(assumptions.get("monthly_rent_eur"))
    vacancy = min(max(_number(assumptions.get("vacancy_rate")), 0), 1)
    monthly_opex = sum(
        _number(assumptions.get(field))
        for field in (
            "monthly_property_tax_eur",
            "monthly_community_eur",
            "monthly_maintenance_eur",
            "monthly_insurance_eur",
        )
    )
    total_cost = purchase + renovation + tax + notary + agency + advisory + other
    financed = purchase * financing_ratio
    debt_service = _monthly_payment(financed, rate, years)
    effective_rent = monthly_rent * (1 - vacancy)
    monthly_noi = effective_rent - monthly_opex
    monthly_cash_flow = monthly_noi - debt_service
    annual_rent = effective_rent * 12
    annual_noi = monthly_noi * 12
    cash_invested = max(total_cost - financed, 0)
    gross_yield = annual_rent / total_cost if total_cost else 0.0
    net_yield = annual_noi / total_cost if total_cost else 0.0
    cash_on_cash = monthly_cash_flow * 12 / cash_invested if cash_invested else 0.0
    roe = cash_on_cash
    return {
        "total_acquisition_cost_eur": round(total_cost, 2),
        "monthly_debt_service_eur": round(debt_service, 2),
        "gross_yield": round(gross_yield, 8),
        "net_yield": round(net_yield, 8),
        "roe": round(roe, 8),
        "cash_on_cash": round(cash_on_cash, 8),
        "monthly_cash_flow_eur": round(monthly_cash_flow, 2),
    }


@dataclass(frozen=True)
class InvestorMandate:
    mandate_id: str
    lead_id: str
    budget_min_eur: float
    budget_max_eur: float
    preferred_regions: tuple[str, ...]
    preferred_cities: tuple[str, ...]
    strategies: tuple[str, ...]
    min_gross_yield: float = 0.0
    min_net_yield: float = 0.0
    min_monthly_cash_flow_eur: float = 0.0
    max_renovation_eur: float | None = None
    risk_appetite: str = "medium"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "InvestorMandate":
        return cls(
            mandate_id=str(payload["mandate_id"]),
            lead_id=str(payload["lead_id"]),
            budget_min_eur=_number(payload["budget"]["min_eur"]),
            budget_max_eur=_number(payload["budget"]["max_eur"]),
            preferred_regions=tuple(str(item).casefold() for item in payload.get("preferred_regions", [])),
            preferred_cities=tuple(str(item).casefold() for item in payload.get("preferred_cities", [])),
            strategies=tuple(str(item) for item in payload["strategies"]),
            min_gross_yield=_number(payload.get("return_requirements", {}).get("min_gross_yield")),
            min_net_yield=_number(payload.get("return_requirements", {}).get("min_net_yield")),
            min_monthly_cash_flow_eur=_number(payload.get("return_requirements", {}).get("min_monthly_cash_flow_eur")),
            max_renovation_eur=_optional_number(payload.get("budget", {}).get("max_renovation_eur")),
            risk_appetite=str(payload.get("risk_appetite", "medium")),
        )


def score_match(
    mandate_payload: Mapping[str, Any],
    property_record: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    mandate = InvestorMandate.from_payload(mandate_payload)
    if scenario["strategy"] not in mandate.strategies:
        strategy_score = 0.0
    else:
        strategy_score = 1.0
    total_cost = _number(scenario["metrics"]["total_acquisition_cost_eur"])
    if mandate.budget_min_eur <= total_cost <= mandate.budget_max_eur:
        budget_score = 1.0
    else:
        distance = min(abs(total_cost - mandate.budget_min_eur), abs(total_cost - mandate.budget_max_eur))
        span = max(mandate.budget_max_eur - mandate.budget_min_eur, 1.0)
        budget_score = max(0.0, 1.0 - distance / span)
    location = property_record["location"]
    city = str(location.get("city") or "").casefold()
    region = str(location.get("autonomous_community") or "").casefold()
    if not mandate.preferred_cities and not mandate.preferred_regions:
        geography_score = 0.7
    elif city in mandate.preferred_cities or region in mandate.preferred_regions:
        geography_score = 1.0
    else:
        geography_score = 0.0
    metrics = scenario["metrics"]
    gross = _number(metrics.get("gross_yield"))
    net = _number(metrics.get("net_yield"))
    cash_flow = _number(metrics.get("monthly_cash_flow_eur"))
    requirement_scores = []
    for actual, minimum in (
        (gross, mandate.min_gross_yield),
        (net, mandate.min_net_yield),
        (cash_flow, mandate.min_monthly_cash_flow_eur),
    ):
        if minimum <= 0:
            requirement_scores.append(0.8)
        else:
            requirement_scores.append(min(max(actual / minimum, 0.0), 1.0))
    return_score = sum(requirement_scores) / len(requirement_scores)
    renovation = _number(scenario["assumptions"].get("renovation_eur"))
    if mandate.max_renovation_eur is None:
        renovation_score = 0.8
    elif renovation <= mandate.max_renovation_eur:
        renovation_score = 1.0
    else:
        renovation_score = max(0.0, 1 - (renovation - mandate.max_renovation_eur) / max(mandate.max_renovation_eur, 1))
    confidence = min(
        _number(property_record.get("data_confidence")),
        _number(scenario.get("data_confidence")),
    )
    risk_score = renovation_score * (0.6 + 0.4 * confidence)
    overall = (
        budget_score * 0.24
        + geography_score * 0.18
        + strategy_score * 0.18
        + return_score * 0.24
        + risk_score * 0.10
        + confidence * 0.06
    )
    explanations = []
    if budget_score == 1:
        explanations.append("Total acquisition cost is inside the mandate budget.")
    if geography_score == 1:
        explanations.append("Property geography matches the mandate.")
    if strategy_score == 1:
        explanations.append("Rental strategy is permitted by the mandate.")
    if return_score >= 0.8:
        explanations.append("Return assumptions substantially satisfy the mandate.")
    if confidence < 0.7:
        explanations.append("Data confidence is below the preferred review threshold.")
    match_id = _stable_id(
        "MATCH",
        mandate.mandate_id,
        property_record["property_id"],
        scenario["scenario_id"],
        length=16,
    )
    scores = {
        "overall": round(min(max(overall, 0), 1), 6),
        "budget": round(budget_score, 6),
        "geography": round(geography_score, 6),
        "strategy": round(strategy_score, 6),
        "return": round(return_score, 6),
        "risk": round(risk_score, 6),
        "confidence": round(confidence, 6),
    }
    evidence_digest = _stable_digest({
        "match_id": match_id,
        "scores": scores,
        "property_digest": property_record["source_record_digest"],
        "scenario_id": scenario["scenario_id"],
    })
    return {
        "schema_version": 1,
        "match_id": match_id,
        "mandate_id": mandate.mandate_id,
        "property_id": property_record["property_id"],
        "scenario_id": scenario["scenario_id"],
        "scores": scores,
        "status": "review_required",
        "human_approved": False,
        "explanations": explanations,
        "evidence_digest": evidence_digest,
    }


def build_crm_merge_plan(
    *,
    mandate_payload: Mapping[str, Any],
    property_record: Mapping[str, Any],
    scenarios: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    matches = [score_match(mandate_payload, property_record, scenario) for scenario in scenarios]
    matches.sort(key=lambda item: (-item["scores"]["overall"], item["scenario_id"]))
    return {
        "schema_version": 1,
        "commercial_objects": {
            "lead_id": mandate_payload["lead_id"],
            "contact_id": mandate_payload.get("contact_id"),
            "commercial_opportunity_creation_permitted": False,
            "reason": "A property match is not a commercial CRM Opportunity. A human must separately approve a service engagement.",
        },
        "real_estate_objects": {
            "property_id": property_record["property_id"],
            "scenario_ids": [scenario["scenario_id"] for scenario in scenarios],
            "matches": matches,
        },
        "writes_permitted": False,
        "external_communication_permitted": False,
        "human_review_required": True,
        "plan_digest": _stable_digest({
            "mandate_id": mandate_payload["mandate_id"],
            "property_id": property_record["property_id"],
            "match_ids": [item["match_id"] for item in matches],
        }),
    }
