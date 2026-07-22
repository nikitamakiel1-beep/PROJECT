#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_fabric import ConnectedExecutionPlanner  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def base_inputs():
    return {
        "service": {
            "price_eur": 149,
            "estimated_hours": 2.5,
            "delivery_days": 3,
            "automation_target_pct": 55,
        },
        "prediction": {
            "confidence": 0.86,
            "uncertainty": 0.14,
            "urgency_probability": 0.72,
            "conversion_probability": 0.64,
        },
        "capacity": {
            "available_hours": 12,
            "active_jobs": 1,
            "days_until_due": 4,
            "dependency_health": 0.90,
        },
        "governance": {
            "human_owner_assigned": True,
            "rollback_defined": True,
            "external_actions_blocked": True,
        },
    }


def run():
    evidence = []

    def case(name, function):
        function()
        evidence.append({"case": name, "result": "passed"})

    def deterministic_plan():
        data = base_inputs()
        planner = ConnectedExecutionPlanner()
        first = planner.plan("IVA", **data)
        second = planner.plan("IVA", **data)
        require(first == second, "execution planning is not deterministic")
        require(first.service_code == "IVA", "wrong service code")
        require(first.connected_service == "IOP", "connected service path missing")
        require(len(first.steps) == 5, "expected four delivery steps plus one connection step")
        require(first.steps[-1]["action"] == "evaluate_connected_service", "connection step missing")
        require(all(issue["create_automatically"] is False for issue in first.linear_issue_drafts), "Linear drafts became automatic")
        require(len(first.evidence_digest) == 64, "evidence digest invalid")

    case("deterministic connected IVA execution plan", deterministic_plan)

    def capacity_block():
        data = base_inputs()
        data["service"]["estimated_hours"] = 10
        data["capacity"]["available_hours"] = 8
        plan = ConnectedExecutionPlanner().plan("CRM", **data)
        require(plan.blocked, "over-capacity plan was not blocked")
        require("delivery_capacity_exceeded" in plan.blocker_reasons, "capacity blocker missing")
        require(plan.risk_score >= 0.34, "capacity risk did not increase")

    case("capacity overload blocks execution", capacity_block)

    def governance_block():
        data = base_inputs()
        data["governance"]["human_owner_assigned"] = False
        data["governance"]["rollback_defined"] = False
        plan = ConnectedExecutionPlanner().plan("IOP", **data)
        require(plan.blocked, "missing governance did not block plan")
        require("human_owner_not_assigned" in plan.blocker_reasons, "owner blocker missing")
        require("rollback_not_defined" in plan.blocker_reasons, "rollback blocker missing")
        require(any(step["human_gate"] for step in plan.steps), "human gates disappeared")

    case("governance and rollback remain mandatory", governance_block)

    def uncertainty_block():
        data = base_inputs()
        data["prediction"]["uncertainty"] = 0.55
        plan = ConnectedExecutionPlanner().plan("OSP", **data)
        require(plan.service_code == "IOP", "legacy OSP alias not normalised")
        require("model_uncertainty_above_bounded_limit" in plan.blocker_reasons, "uncertainty blocker missing")

    case("legacy alias and uncertainty gate", uncertainty_block)

    def unsupported_service():
        data = base_inputs()
        try:
            ConnectedExecutionPlanner().plan("ISS", **data)
        except ValueError as error:
            require("unsupported_service_code" in str(error), "wrong unsupported-service error")
        else:
            raise AssertionError("unsupported hidden bundle was planned")

    case("unsupported hidden bundle fails closed", unsupported_service)

    print(json.dumps({
        "ok": True,
        "architecture": "multidimensional connected execution planner",
        "tests": evidence,
    }, indent=2))


if __name__ == "__main__":
    run()
