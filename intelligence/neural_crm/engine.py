from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import math
import re
from typing import Any, Iterable, Mapping, Sequence

from .agents import CognitiveColony, EvidenceLedger
from .model import NeuralCRMModel, NeuralPrediction
from .policy import ActionClass, AutonomyMode, DecisionPolicy


MODEL_VERSION = "neural-crm-shadow-v0.1"
CANONICAL_SERVICE_ALIASES = {"OSP": "IOP"}
TERMINAL_LEAD_STATUSES = {"closed", "lost", "converted", "disqualified"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "yes", "1", "active", "accepted", "recorded"}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _days_since(value: Any, today: date) -> int:
    parsed = _parse_date(value)
    if not parsed:
        return 999
    return max(0, (today - parsed).days)


def _days_overdue(value: Any, today: date) -> int:
    parsed = _parse_date(value)
    if not parsed:
        return 0
    return max(0, (today - parsed).days)


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(_text(part).lower() for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:12].upper()}"


def _hashed_text_vector(text: str, size: int = 8) -> list[float]:
    vector = [0.0] * size
    tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]{2,}", text.lower())
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = digest[0] % size
        sign = -1.0 if digest[1] % 2 else 1.0
        vector[bucket] += sign * (1.0 + min(len(token), 12) / 12.0)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _normalise_service_code(value: Any) -> tuple[str, tuple[str, ...]]:
    submitted = _text(value).upper()
    canonical = CANONICAL_SERVICE_ALIASES.get(submitted, submitted)
    warnings = (f"legacy_service_alias:{submitted}->{canonical}",) if canonical != submitted else ()
    return canonical, warnings


def _service_active(service: Mapping[str, Any]) -> bool:
    status = _text(service.get("status") or service.get("Status")).lower()
    active = service.get("active", service.get("Active"))
    return status == "active" or _bool(active)


def _service_price(service: Mapping[str, Any]) -> float:
    for key in ("price_eur", "Standard Price €", "standard_price_eur", "Beta Price €"):
        if key in service and _number(service.get(key), -1.0) >= 0.0:
            return _number(service.get(key))
    return 0.0


def _service_automation(service: Mapping[str, Any]) -> float:
    for key in ("automation_target_pct", "Automation Target %", "automation_pct"):
        if key in service:
            return _clip(_number(service.get(key)) / 100.0)
    return 0.0


def _service_delivery_days(service: Mapping[str, Any]) -> float:
    for key in ("delivery_days", "Delivery Days"):
        if key in service:
            return max(0.0, _number(service.get(key)))
    return 0.0


def _activity_features(activity: Mapping[str, Any], today: date) -> list[float]:
    days = _days_since(activity.get("Date"), today)
    outcome = (_text(activity.get("Outcome")) + " " + _text(activity.get("Summary"))).lower()
    activity_type = _text(activity.get("Activity Type")).lower()
    channel = _text(activity.get("Channel")).lower()
    positive = 1.0 if any(token in outcome for token in ("positive", "interested", "replied", "accepted", "meeting")) else 0.0
    response = 1.0 if any(token in outcome for token in ("reply", "replied", "response", "answered")) else 0.0
    meeting = 1.0 if "meeting" in outcome or "meeting" in activity_type or "call" in activity_type else 0.0
    direct_channel = 1.0 if channel in {"email", "phone", "video", "meeting", "whatsapp"} else 0.0
    duration = _clip(_number(activity.get("Duration Minutes")) / 60.0)
    recency = math.exp(-min(days, 365) / 45.0)
    return [recency, positive, response, meeting, direct_channel, duration]


def _relationship_value(contact: Mapping[str, Any], activities: Sequence[Mapping[str, Any]]) -> float:
    raw = _number(contact.get("Relationship Strength"), -1.0)
    if raw >= 0.0:
        return _clip(raw / 100.0 if raw > 1.0 else raw)
    positive = sum(_activity_features(activity, date.today())[1] for activity in activities)
    return _clip(0.12 + len(activities) * 0.06 + positive * 0.09)


def _consent_value(contact: Mapping[str, Any], lead: Mapping[str, Any]) -> float:
    consent = (_text(contact.get("Consent Status")) + " " + _text(lead.get("Consent Basis"))).lower()
    return 1.0 if any(token in consent for token in ("accepted", "recorded", "authorised", "requested", "assessment")) else 0.0


class NeuralCRMEngine:
    """Governed neural inference and opportunity-planning engine.

    The engine can autonomously analyse, rank and produce reversible internal
    plans. It defaults to shadow mode. External communication, financial edits,
    irreversible changes and model promotion remain under human custody.
    """

    def __init__(
        self,
        mode: AutonomyMode = AutonomyMode.SHADOW,
        minimum_fit_score: float = 60.0,
        model: NeuralCRMModel | None = None,
    ) -> None:
        self.mode = AutonomyMode(mode)
        self.minimum_fit_score = float(minimum_fit_score)
        self.model = model or NeuralCRMModel()
        self.policy = DecisionPolicy(self.mode)

    def _features(self, snapshot: Mapping[str, Any], today: date) -> dict[str, Any]:
        lead = dict(snapshot.get("lead") or {})
        company = dict(snapshot.get("company") or {})
        contact = dict(snapshot.get("contact") or {})
        service = dict(snapshot.get("service") or {})
        activities = [dict(item) for item in snapshot.get("activities") or []]

        service_code, alias_warnings = _normalise_service_code(
            lead.get("Service Interest") or service.get("code") or service.get("Service Code")
        )
        fit = _clip(_number(lead.get("Fit Score")) / 100.0)
        relationship = _relationship_value(contact, activities)
        consent = _consent_value(contact, lead)
        qualified = 1.0 if _text(lead.get("Status")).lower() == "qualified" else 0.0
        active = 1.0 if _service_active(service) else 0.0
        price = _service_price(service)
        automation = _service_automation(service)
        delivery_days = _service_delivery_days(service)
        days_since_contact = _days_since(lead.get("Last Contact") or contact.get("Last Contact"), today)
        overdue = _days_overdue(lead.get("Next Action Date"), today)
        website_present = 1.0 if _text(company.get("Website") or lead.get("Website")) else 0.0
        international_fit = _number(company.get("International Fit"), fit * 100.0)
        international_fit = _clip(international_fit / 100.0 if international_fit > 1.0 else international_fit)

        tabular = [
            fit,
            relationship,
            consent,
            qualified,
            active,
            _clip(price / 1000.0),
            _clip(automation),
            _clip(delivery_days / 30.0),
            _clip(len(activities) / 20.0),
            _clip(days_since_contact / 120.0),
            _clip(overdue / 30.0),
            _clip((website_present + international_fit) / 2.0),
        ]

        narrative = " ".join(
            _text(value)
            for value in (
                lead.get("Notes"),
                lead.get("Next Action"),
                company.get("Sector"),
                company.get("Subsector"),
                company.get("Notes"),
                service.get("name"),
                service.get("Service Name"),
            )
            if _text(value)
        )
        text_vector = _hashed_text_vector(narrative, 8)

        ordered_activities = sorted(activities, key=lambda item: _parse_date(item.get("Date")) or date.min)
        activity_sequence = [_activity_features(item, today) for item in ordered_activities[-20:]]

        graph_nodes = [
            [1.0, 0.0, 0.0, 0.0, international_fit, website_present],
            [0.0, 1.0, 0.0, 0.0, relationship, consent],
            [0.0, 0.0, 1.0, 0.0, fit, qualified],
            [0.0, 0.0, 0.0, 1.0, _clip(price / 1000.0), automation],
        ]
        adjacency = [
            [0.0, 1.0, 1.0, 0.0],
            [1.0, 0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 0.0],
        ]

        status = _text(lead.get("Status")).lower()
        activity_signal = _clip(len(activities) / 8.0)
        conversion_prior = _clip(0.08 + fit * 0.42 + qualified * 0.22 + consent * 0.08 + active * 0.08 + activity_signal * 0.12)
        urgency_prior = _clip(overdue / 14.0 + (0.15 if qualified else 0.0))
        churn_prior = _clip(days_since_contact / 120.0 - relationship * 0.35 + (0.20 if status in TERMINAL_LEAD_STATUSES else 0.0))
        relationship_prior = _clip(relationship * 0.72 + activity_signal * 0.18 + consent * 0.10)

        action_priors = [0.10, 0.12, 0.18, 0.10, 0.50]
        if not active or fit < self.minimum_fit_score / 100.0:
            action_priors = [0.34, 0.26, 0.10, 0.02, 0.28]
        elif not qualified:
            action_priors = [0.12, 0.18, 0.38, 0.05, 0.27]
        elif consent < 1.0:
            action_priors = [0.10, 0.42, 0.20, 0.03, 0.25]
        else:
            action_priors = [0.05, 0.08, 0.22, 0.50, 0.15]

        return {
            "lead": lead,
            "company": company,
            "contact": contact,
            "service": service,
            "activities": activities,
            "service_code": service_code,
            "warnings": list(alias_warnings),
            "fit_score": fit * 100.0,
            "relationship": relationship,
            "consent": consent,
            "qualified": bool(qualified),
            "active_service": bool(active),
            "price_eur": price,
            "tabular": tabular,
            "text_vector": text_vector,
            "activity_sequence": activity_sequence,
            "graph_nodes": graph_nodes,
            "adjacency": adjacency,
            "focus_index": 2,
            "priors": {
                "conversion": conversion_prior,
                "relationship": relationship_prior,
                "urgency": urgency_prior,
                "churn": churn_prior,
                "actions": action_priors,
            },
        }

    @staticmethod
    def _eligibility(features: Mapping[str, Any]) -> tuple[bool, list[str]]:
        lead = features["lead"]
        reasons: list[str] = []
        if _text(lead.get("Status")).lower() != "qualified":
            reasons.append("lead_status_not_qualified")
        if features["fit_score"] < 60.0:
            reasons.append("fit_score_below_minimum")
        if not features["active_service"]:
            reasons.append("service_not_active")
        if not _text(lead.get("Lead ID")):
            reasons.append("missing_lead_id")
        if not _text(lead.get("Company ID")):
            reasons.append("missing_company_id")
        if not _text(lead.get("Contact ID")):
            reasons.append("missing_contact_id")
        if not features["service_code"]:
            reasons.append("missing_service_code")
        return not reasons, reasons

    @staticmethod
    def _existing_opportunity(
        lead: Mapping[str, Any], service_code: str, existing_opportunities: Iterable[Mapping[str, Any]]
    ) -> Mapping[str, Any] | None:
        linked = _text(lead.get("Opportunity ID"))
        for opportunity in existing_opportunities:
            if linked and _text(opportunity.get("Opportunity ID")) == linked:
                return opportunity
            same_lead = _text(opportunity.get("Notes")).find(f"lead_id={_text(lead.get('Lead ID'))}") >= 0
            same_service, _ = _normalise_service_code(opportunity.get("Service Code"))
            if same_lead and same_service == service_code:
                return opportunity
        return None

    @staticmethod
    def _counterfactuals(prediction: NeuralPrediction, features: Mapping[str, Any]) -> list[dict[str, Any]]:
        base = prediction.conversion_probability
        candidates = [
            ("complete_discovery", 0.10 if not features["qualified"] else 0.04, "Collect explicit need, timing and decision process."),
            ("obtain_permission_or_reply", 0.08 if features["consent"] < 1.0 else 0.03, "Secure a direct response or permitted next contact."),
            ("strengthen_fit_evidence", 0.07 if features["fit_score"] < 80.0 else 0.02, "Add evidence for budget, urgency and international fit."),
        ]
        return [
            {
                "action": action,
                "estimated_conversion_probability": _clip(base + uplift),
                "estimated_uplift": uplift,
                "assumption": assumption,
                "execution": "human_or_bounded_internal_workflow",
            }
            for action, uplift, assumption in sorted(candidates, key=lambda item: item[1], reverse=True)
        ]

    def evaluate(
        self,
        snapshot: Mapping[str, Any],
        existing_opportunities: Iterable[Mapping[str, Any]] = (),
        human_approved: bool = False,
        synthetic_only: bool = True,
        today: date | None = None,
    ) -> dict[str, Any]:
        today = today or date.today()
        features = self._features(snapshot, today)
        lead_id = _text(features["lead"].get("Lead ID")) or "unresolved"
        cycle_id = _stable_id("NCYCLE", lead_id, features["service_code"], today.isoformat())
        ledger = EvidenceLedger(cycle_id, MODEL_VERSION)

        ledger.append(CognitiveColony.evidence(
            "Scout",
            f"service={features['service_code']}; fit={features['fit_score']:.1f}; active={features['active_service']}",
            0.95,
            (f"lead:{lead_id}", f"service:{features['service_code']}"),
            features["warnings"],
        ))
        ledger.append(CognitiveColony.evidence(
            "Cartographer",
            f"relationship_graph_nodes={len(features['graph_nodes'])}; activities={len(features['activities'])}",
            0.94,
            (f"lead:{lead_id}", "crm:company-contact-lead-service"),
        ))

        prediction = self.model.predict(
            features["tabular"],
            features["text_vector"],
            features["activity_sequence"],
            features["graph_nodes"],
            features["adjacency"],
            features["focus_index"],
            features["priors"],
        )
        ranked_actions = sorted(prediction.action_probabilities.items(), key=lambda item: item[1], reverse=True)
        recommended_action, recommended_probability = ranked_actions[0]
        ledger.append(CognitiveColony.evidence(
            "Analyst",
            f"conversion={prediction.conversion_probability:.4f}; uncertainty={prediction.uncertainty:.4f}",
            prediction.confidence,
            (f"cycle:{cycle_id}", f"model:{MODEL_VERSION}"),
        ))
        ledger.append(CognitiveColony.evidence(
            "Strategist",
            f"next_best_action={recommended_action}; probability={recommended_probability:.4f}",
            prediction.confidence,
            (f"lead:{lead_id}", f"cycle:{cycle_id}"),
        ))

        eligible, eligibility_reasons = self._eligibility(features)
        existing = self._existing_opportunity(features["lead"], features["service_code"], existing_opportunities)
        opportunity_id = _stable_id("OPP", lead_id, features["service_code"])
        opportunity_plan: dict[str, Any] | None = None
        action_class = ActionClass.INTERNAL_REVERSIBLE
        if eligible and existing is None:
            probability_pct = round(prediction.conversion_probability * 100.0, 2)
            expected_close = date.fromordinal(today.toordinal() + 14).isoformat()
            opportunity_plan = {
                "Opportunity ID": opportunity_id,
                "Company ID": _text(features["lead"].get("Company ID")),
                "Contact ID": _text(features["lead"].get("Contact ID")),
                "Service Code": features["service_code"],
                "Stage": "Qualified",
                "Value €": round(features["price_eur"], 2),
                "Probability %": probability_pct,
                "Weighted Value €": round(features["price_eur"] * prediction.conversion_probability, 2),
                "Created Date": today.isoformat(),
                "Expected Close": expected_close,
                "Won/Lost Date": "",
                "Loss Reason": "",
                "Proposal URL": "",
                "Invoice Status": "Not issued",
                "Payment Date": "",
                "Delivery Status": "Not started",
                "Linear Issue": "",
                "Client Folder URL": "",
                "Owner": _text(features["lead"].get("Owner")),
                "Next Step": "Human review of neural qualification and discovery evidence",
                "Next Step Date": today.isoformat(),
                "Notes": f"lead_id={lead_id}; model={MODEL_VERSION}; cycle={cycle_id}; neural_shadow=true",
            }

        policy = self.policy.decide(
            action_class,
            prediction.confidence,
            prediction.uncertainty,
            human_approved=human_approved,
            synthetic_only=synthetic_only,
        )

        if existing is not None:
            execution = "duplicate_existing_opportunity"
            mutation_permitted = False
        elif not eligible:
            execution = "hold_ineligible"
            mutation_permitted = False
        elif opportunity_plan is None:
            execution = "hold_no_plan"
            mutation_permitted = False
        else:
            execution = policy.execution
            mutation_permitted = policy.permitted

        audit_warnings = list(features["warnings"])
        if prediction.uncertainty > 0.28:
            audit_warnings.append("neural_uncertainty_above_reversible_auto_ceiling")
        if features["price_eur"] <= 0.0:
            audit_warnings.append("service_price_missing_or_zero")
        if existing is not None:
            audit_warnings.append("existing_opportunity_preserved")
        ledger.append(CognitiveColony.evidence(
            "Auditor",
            f"eligible={eligible}; existing={existing is not None}; warnings={len(audit_warnings)}",
            prediction.confidence,
            (f"cycle:{cycle_id}", "policy:neural-crm-custody-v1"),
            audit_warnings,
        ))
        ledger.append(CognitiveColony.evidence(
            "Custodian",
            f"execution={execution}; mutation_permitted={mutation_permitted}",
            1.0,
            (f"cycle:{cycle_id}", f"mode:{self.mode.value}"),
            (() if mutation_permitted else (policy.reason,)),
        ))

        return {
            "cycle_id": cycle_id,
            "model_version": MODEL_VERSION,
            "mode": self.mode.value,
            "synthetic_only": bool(synthetic_only),
            "service_code": features["service_code"],
            "prediction": {
                **asdict(prediction),
                "ranked_actions": [{"action": action, "probability": probability} for action, probability in ranked_actions],
            },
            "eligibility": {"eligible": eligible, "reasons": eligibility_reasons},
            "existing_opportunity": dict(existing) if existing is not None else None,
            "opportunity_plan": opportunity_plan,
            "execution": {
                "action": execution,
                "mutation_permitted": mutation_permitted,
                "requires_human": policy.requires_human,
                "policy_reason": policy.reason,
                "confidence_threshold": policy.confidence_threshold,
                "uncertainty_ceiling": policy.uncertainty_ceiling,
            },
            "counterfactuals": self._counterfactuals(prediction, features),
            "warnings": audit_warnings,
            "evidence_ledger": ledger.as_dict(),
        }
