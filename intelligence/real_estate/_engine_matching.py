"""Transparent, human-gated real-estate mandate matching."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ._engine_common import (
    number,
    optional_number,
    stable_digest,
    stable_id,
)


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
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "InvestorMandate":
        return cls(
            mandate_id=str(payload["mandate_id"]),
            lead_id=str(payload["lead_id"]),
            budget_min_eur=number(payload["budget"]["min_eur"]),
            budget_max_eur=number(payload["budget"]["max_eur"]),
            preferred_regions=tuple(
                str(item).casefold()
                for item in payload.get("preferred_regions", [])
            ),
            preferred_cities=tuple(
                str(item).casefold()
                for item in payload.get("preferred_cities", [])
            ),
            strategies=tuple(
                str(item) for item in payload["strategies"]
            ),
            min_gross_yield=number(
                payload.get("return_requirements", {}).get(
                    "min_gross_yield"
                )
            ),
            min_net_yield=number(
                payload.get("return_requirements", {}).get(
                    "min_net_yield"
                )
            ),
            min_monthly_cash_flow_eur=number(
                payload.get("return_requirements", {}).get(
                    "min_monthly_cash_flow_eur"
                )
            ),
            max_renovation_eur=optional_number(
                payload.get("budget", {}).get("max_renovation_eur")
            ),
            risk_appetite=str(
                payload.get("risk_appetite", "medium")
            ),
        )


def score_match(
    mandate_payload: Mapping[str, Any],
    property_record: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    mandate = InvestorMandate.from_payload(mandate_payload)

    strategy_score = (
        1.0 if scenario["strategy"] in mandate.strategies else 0.0
    )

    total_cost = number(
        scenario["metrics"]["total_acquisition_cost_eur"]
    )
    if mandate.budget_min_eur <= total_cost <= mandate.budget_max_eur:
        budget_score = 1.0
    else:
        distance = min(
            abs(total_cost - mandate.budget_min_eur),
            abs(total_cost - mandate.budget_max_eur),
        )
        span = max(
            mandate.budget_max_eur - mandate.budget_min_eur,
            1.0,
        )
        budget_score = max(0.0, 1.0 - distance / span)

    location = property_record["location"]
    city = str(location.get("city") or "").casefold()
    region = str(
        location.get("autonomous_community") or ""
    ).casefold()
    if not mandate.preferred_cities and not mandate.preferred_regions:
        geography_score = 0.7
    elif (
        city in mandate.preferred_cities
        or region in mandate.preferred_regions
    ):
        geography_score = 1.0
    else:
        geography_score = 0.0

    metrics = scenario["metrics"]
    requirements: list[float] = []
    for actual, minimum in (
        (
            number(metrics.get("gross_yield")),
            mandate.min_gross_yield,
        ),
        (
            number(metrics.get("net_yield")),
            mandate.min_net_yield,
        ),
        (
            number(metrics.get("monthly_cash_flow_eur")),
            mandate.min_monthly_cash_flow_eur,
        ),
    ):
        if minimum <= 0:
            requirements.append(0.8)
        else:
            requirements.append(
                min(max(actual / minimum, 0.0), 1.0)
            )
    return_score = sum(requirements) / len(requirements)

    renovation = number(
        scenario["assumptions"].get("renovation_eur")
    )
    if mandate.max_renovation_eur is None:
        renovation_score = 0.8
    elif renovation <= mandate.max_renovation_eur:
        renovation_score = 1.0
    else:
        renovation_score = max(
            0.0,
            1
            - (renovation - mandate.max_renovation_eur)
            / max(mandate.max_renovation_eur, 1),
        )

    confidence = min(
        number(property_record.get("data_confidence")),
        number(scenario.get("data_confidence")),
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

    explanations: list[str] = []
    if budget_score == 1:
        explanations.append(
            "Total acquisition cost is inside the mandate budget."
        )
    if geography_score == 1:
        explanations.append(
            "Property geography matches the mandate."
        )
    if strategy_score == 1:
        explanations.append(
            "Rental strategy is permitted by the mandate."
        )
    if return_score >= 0.8:
        explanations.append(
            "Return assumptions substantially satisfy the mandate."
        )
    if confidence < 0.7:
        explanations.append(
            "Data confidence is below the preferred review threshold."
        )

    match_id = stable_id(
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
        "evidence_digest": stable_digest(
            {
                "match_id": match_id,
                "scores": scores,
                "property_digest": property_record[
                    "source_record_digest"
                ],
                "scenario_id": scenario["scenario_id"],
            }
        ),
    }


def build_crm_merge_plan(
    *,
    mandate_payload: Mapping[str, Any],
    property_record: Mapping[str, Any],
    scenarios: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    scenario_list = list(scenarios)
    matches = [
        score_match(mandate_payload, property_record, scenario)
        for scenario in scenario_list
    ]
    matches.sort(
        key=lambda item: (
            -item["scores"]["overall"],
            item["scenario_id"],
        )
    )

    return {
        "schema_version": 1,
        "commercial_objects": {
            "lead_id": mandate_payload["lead_id"],
            "contact_id": mandate_payload.get("contact_id"),
            "commercial_opportunity_creation_permitted": False,
            "reason": (
                "A property match is not a commercial CRM Opportunity. "
                "A human must separately approve a service engagement."
            ),
        },
        "real_estate_objects": {
            "property_id": property_record["property_id"],
            "scenario_ids": [
                scenario["scenario_id"]
                for scenario in scenario_list
            ],
            "matches": matches,
        },
        "writes_permitted": False,
        "external_communication_permitted": False,
        "human_review_required": True,
        "plan_digest": stable_digest(
            {
                "mandate_id": mandate_payload["mandate_id"],
                "property_id": property_record["property_id"],
                "match_ids": [
                    item["match_id"] for item in matches
                ],
            }
        ),
    }
