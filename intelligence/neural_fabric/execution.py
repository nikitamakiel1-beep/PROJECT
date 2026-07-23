from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Any, Mapping

from .multidimensional import MultiDimensionalConvEncoder


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


SERVICE_STEPS: Mapping[str, tuple[tuple[str, str, bool], ...]] = {
    "IVA": (
        ("collect_target_market_evidence", "evidence", False),
        ("score_priority_pages", "analysis", False),
        ("draft_30_day_actions", "build", False),
        ("approve_visibility_delivery", "approval", True),
    ),
    "CRM": (
        ("inventory_lead_sources", "evidence", False),
        ("define_pipeline_and_ownership", "design", False),
        ("configure_tracker_and_dashboard", "build", False),
        ("approve_crm_activation", "approval", True),
    ),
    "IOP": (
        ("confirm_audience_and_use_case", "evidence", False),
        ("collect_proof_and_objections", "analysis", False),
        ("draft_sales_one_pager", "build", False),
        ("approve_commercial_document", "approval", True),
    ),
}

CONNECTED_SERVICE = {"IVA": "IOP", "IOP": "CRM", "CRM": "IOP"}


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    service_code: str
    connected_service: str | None
    risk_score: float
    capacity_utilisation: float
    latent_energy: float
    confidence: float
    uncertainty: float
    blocked: bool
    blocker_reasons: tuple[str, ...]
    steps: tuple[dict[str, Any], ...]
    linear_issue_drafts: tuple[dict[str, Any], ...]
    evidence_digest: str


class ConnectedExecutionPlanner:
    """Generate bounded internal delivery work from multidimensional evidence.

    The planner uses the shared convolutional fabric to combine model evidence,
    service economics, temporal work progression, capacity and governance. It
    only returns reviewable plans and Linear-ready drafts; it never writes to
    Linear, contacts a person, changes pricing or activates production systems.
    """

    def __init__(self, seed: int = 20260722) -> None:
        self.seed = int(seed)

    @staticmethod
    def _service_code(value: Any) -> str:
        code = str(value or "").strip().upper()
        return "IOP" if code == "OSP" else code

    def _tensor_inputs(
        self,
        service_code: str,
        service: Mapping[str, Any],
        prediction: Mapping[str, Any],
        capacity: Mapping[str, Any],
        governance: Mapping[str, Any],
    ) -> tuple[list[float], list[float], list[list[float]], list[list[float]]]:
        confidence = _clip(_number(prediction.get("confidence")))
        uncertainty = _clip(_number(prediction.get("uncertainty")))
        urgency = _clip(_number(prediction.get("urgency_probability")))
        conversion = _clip(_number(prediction.get("conversion_probability")))
        price = max(0.0, _number(service.get("price_eur") or service.get("Standard Price €")))
        hours = max(0.0, _number(service.get("estimated_hours") or service.get("Estimated Hours")))
        delivery_days = max(0.0, _number(service.get("delivery_days") or service.get("Delivery Days")))
        automation = _clip(_number(service.get("automation_target_pct") or service.get("Automation Target %")) / 100.0)
        available_hours = max(0.0, _number(capacity.get("available_hours")))
        active_jobs = max(0.0, _number(capacity.get("active_jobs")))
        due_days = max(0.0, _number(capacity.get("days_until_due"), delivery_days))
        capacity_ratio = _clip(hours / max(available_hours, 0.01))
        due_pressure = _clip(1.0 - due_days / max(delivery_days * 1.5, 1.0))
        dependency_health = _clip(_number(capacity.get("dependency_health"), 1.0))
        governance_ready = 1.0 if bool(governance.get("human_owner_assigned")) else 0.0
        rollback_ready = 1.0 if bool(governance.get("rollback_defined")) else 0.0
        external_blocked = 1.0 if bool(governance.get("external_actions_blocked", True)) else 0.0

        tabular = [
            confidence,
            1.0 - uncertainty,
            urgency,
            conversion,
            _clip(price / 1000.0),
            _clip(hours / 12.0),
            _clip(delivery_days / 14.0),
            automation,
            capacity_ratio,
            _clip(active_jobs / 8.0),
            due_pressure,
            dependency_health,
        ]
        digest = hashlib.sha256(service_code.encode("utf-8")).digest()
        text = [((digest[index] / 255.0) * 2.0) - 1.0 for index in range(8)]
        activities = [
            [1.0, dependency_health, 0.0, 0.0, governance_ready, 0.10],
            [0.7, confidence, conversion, 0.0, governance_ready, 0.30],
            [0.4, automation, urgency, due_pressure, rollback_ready, 0.55],
            [0.2, 1.0 - uncertainty, capacity_ratio, due_pressure, external_blocked, 0.85],
        ]
        graph = [
            [1.0, 0.0, 0.0, 0.0, confidence, conversion],
            [0.0, 1.0, 0.0, 0.0, capacity_ratio, due_pressure],
            [0.0, 0.0, 1.0, 0.0, dependency_health, automation],
            [0.0, 0.0, 0.0, 1.0, governance_ready, rollback_ready],
        ]
        return tabular, text, activities, graph

    def plan(
        self,
        service_code: str,
        service: Mapping[str, Any],
        prediction: Mapping[str, Any],
        capacity: Mapping[str, Any],
        governance: Mapping[str, Any],
    ) -> ExecutionPlan:
        code = self._service_code(service_code)
        if code not in SERVICE_STEPS:
            raise ValueError("unsupported_service_code")
        tabular, text, activities, graph = self._tensor_inputs(code, service, prediction, capacity, governance)
        encoder = MultiDimensionalConvEncoder(random.Random(self.seed), 12, 8, 6, 6)
        latent = encoder.encode(tabular, text, activities, graph)
        latent_energy = math.sqrt(sum(value * value for value in latent) / len(latent))
        confidence = _clip(_number(prediction.get("confidence")))
        uncertainty = _clip(_number(prediction.get("uncertainty")))
        capacity_utilisation = tabular[8]
        due_pressure = tabular[10]
        dependency_health = tabular[11]
        risk_score = _clip(
            capacity_utilisation * 0.34
            + due_pressure * 0.24
            + uncertainty * 0.22
            + (1.0 - dependency_health) * 0.14
            + _clip(latent_energy / 2.0) * 0.06
        )

        blockers: list[str] = []
        if not bool(governance.get("human_owner_assigned")):
            blockers.append("human_owner_not_assigned")
        if not bool(governance.get("rollback_defined")):
            blockers.append("rollback_not_defined")
        if capacity_utilisation > 0.90:
            blockers.append("delivery_capacity_exceeded")
        if uncertainty > 0.28:
            blockers.append("model_uncertainty_above_bounded_limit")
        if dependency_health < 0.60:
            blockers.append("input_dependencies_unhealthy")

        step_records: list[dict[str, Any]] = []
        for index, (action, phase, human_gate) in enumerate(SERVICE_STEPS[code], start=1):
            step_records.append({
                "order": index,
                "action": action,
                "phase": phase,
                "human_gate": human_gate,
                "autonomous_internal": not human_gate,
                "depends_on": [] if index == 1 else [SERVICE_STEPS[code][index - 2][0]],
                "status": "blocked" if blockers and index > 1 else "ready",
            })
        connected = CONNECTED_SERVICE.get(code)
        step_records.append({
            "order": len(step_records) + 1,
            "action": "evaluate_connected_service",
            "phase": "connect",
            "service_code": connected,
            "human_gate": True,
            "autonomous_internal": True,
            "depends_on": [SERVICE_STEPS[code][-1][0]],
            "status": "planned",
        })

        plan_payload = {
            "service_code": code,
            "prediction": dict(prediction),
            "capacity": dict(capacity),
            "governance": dict(governance),
            "steps": step_records,
        }
        evidence_digest = _digest(plan_payload)
        plan_id = "NEXEC-" + _digest([code, evidence_digest])[:12].upper()
        issue_drafts = tuple({
            "title": f"{code} — {step['action'].replace('_', ' ')}",
            "description": (
                f"Execution plan `{plan_id}`. Phase: {step['phase']}. "
                f"Dependencies: {', '.join(step['depends_on']) or 'none'}. "
                f"Human gate: {step['human_gate']}. Evidence: `{evidence_digest}`."
            ),
            "priority": 2 if risk_score >= 0.65 else 3,
            "state": "Todo",
            "create_automatically": False,
        } for step in step_records)

        return ExecutionPlan(
            plan_id=plan_id,
            service_code=code,
            connected_service=connected,
            risk_score=risk_score,
            capacity_utilisation=capacity_utilisation,
            latent_energy=latent_energy,
            confidence=confidence,
            uncertainty=uncertainty,
            blocked=bool(blockers),
            blocker_reasons=tuple(blockers),
            steps=tuple(step_records),
            linear_issue_drafts=issue_drafts,
            evidence_digest=evidence_digest,
        )

    @staticmethod
    def as_dict(plan: ExecutionPlan) -> dict[str, Any]:
        return asdict(plan)
