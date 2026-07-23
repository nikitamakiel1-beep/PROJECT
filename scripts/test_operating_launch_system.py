#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.management_digest import build_weekly_management_digest


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: str) -> str:
    target = ROOT / path
    require(target.exists(), f"missing operating-launch file: {path}")
    return target.read_text(encoding="utf-8")


def synthetic_snapshot() -> dict:
    return {
        "leads": [
            {"status": "qualified", "next_action_date": "2026-07-20"},
            {"status": "new", "next_action_date": "2026-07-30"},
            {"status": "lost", "next_action_date": "2026-07-01"},
        ],
        "opportunities": [
            {"stage": "proposal", "value_eur": 299, "probability_pct": 50, "next_step_date": "2026-07-21"},
            {"stage": "discovery", "value_eur": 149, "probability_pct": 0.25, "next_step_date": "2026-07-29"},
            {"stage": "won", "value_eur": 249, "payment_confirmed": True, "collected_eur": 249},
        ],
        "activities": [
            {"status": "completed"}, {"status": "planned"}, {"status": "completed"}
        ],
        "delivery_jobs": [
            {"status": "in_progress", "estimated_hours": 4, "actual_hours": 3, "due_date": "2026-07-20"},
            {"status": "complete", "estimated_hours": 2, "actual_hours": 2, "due_date": "2026-07-18"},
        ],
        "automations": [
            {"status": "success"}, {"status": "failed", "error_code": "SYNTHETIC_FAILURE"}
        ],
        "interviews": [
            {"segment": "industrial_b2b", "problem_codes": ["visibility", "proof"], "willingness_to_pay_eur": 149, "referral_signal": True},
            {"segment": "services_b2b", "problem_codes": ["visibility", "follow_up"], "willingness_to_pay_eur": 299, "referral_signal": False},
        ],
        "linear_issues": [
            {"status": "In Progress", "due_date": "2026-07-20"},
            {"status": "Done", "due_date": "2026-07-01"},
        ],
    }


def run() -> None:
    results: list[dict[str, str]] = []

    def case(name: str, fn) -> None:
        fn()
        results.append({"case": name, "result": "passed"})

    def digest_metrics_are_exact() -> None:
        digest = build_weekly_management_digest(synthetic_snapshot(), as_of="2026-07-22")
        metrics = digest["metrics"]
        require(metrics["leads_open"] == 2, "open lead count drift")
        require(metrics["leads_overdue"] == 1, "overdue lead count drift")
        require(metrics["open_pipeline_eur"] == 448.0, "open pipeline drift")
        require(metrics["weighted_pipeline_eur"] == 186.75, "weighted pipeline drift")
        require(metrics["won_revenue_eur"] == 249.0, "won revenue drift")
        require(metrics["collected_cash_eur"] == 249.0, "collected cash drift")
        require(metrics["automations_failed"] == 1, "automation failure count drift")

    case("weekly digest metrics are deterministic", digest_metrics_are_exact)

    def cash_is_not_inferred_from_won_stage() -> None:
        snapshot = synthetic_snapshot()
        snapshot["opportunities"][2].pop("payment_confirmed")
        snapshot["opportunities"][2].pop("collected_eur")
        digest = build_weekly_management_digest(snapshot, as_of="2026-07-22")
        require(digest["metrics"]["won_revenue_eur"] == 249.0, "won revenue missing")
        require(digest["metrics"]["collected_cash_eur"] == 0.0, "cash inferred from stage")

    case("collected cash requires explicit payment evidence", cash_is_not_inferred_from_won_stage)

    def action_queue_is_human_gated() -> None:
        digest = build_weekly_management_digest(synthetic_snapshot(), as_of="2026-07-22")
        require(digest["action_queue"], "action queue unexpectedly empty")
        require(all(item["human_decision_required"] for item in digest["action_queue"]), "automated action escaped human gate")
        controls = digest["controls"]
        require(controls["external_message_sent"] is False, "digest sent an external message")
        require(controls["crm_stage_mutated"] is False, "digest mutated CRM stage")
        require(controls["proposal_or_invoice_approved"] is False, "digest approved commercial action")

    case("management actions remain human gated", action_queue_is_human_gated)

    def research_evidence_is_aggregate_only() -> None:
        digest = build_weekly_management_digest(synthetic_snapshot(), as_of="2026-07-22")
        serialised = json.dumps(digest, ensure_ascii=False)
        require("@" not in serialised, "email-like data leaked into aggregate digest")
        require(digest["research"]["top_problem_codes"][0] == ["visibility", 2] or digest["research"]["top_problem_codes"][0] == ("visibility", 2), "problem aggregation drift")
        require(digest["metrics"]["interviews_completed"] == 2, "interview count drift")
        require(any(item["owner_route"] == "Founder → Research" for item in digest["action_queue"]), "missing interview completion action")

    case("interview evidence is aggregate and target-aware", research_evidence_is_aggregate_only)

    def shared_master_pack_is_complete() -> None:
        required = {
            "templates/commercial/qualification-checklist.md": ["Qualification decision", "Human approval", "Do not contact automatically"],
            "templates/commercial/client-input-request.md": ["Approved secure channel", "Data minimisation", "Input deadline"],
            "templates/commercial/handover-message.md": ["Human release approval", "Acceptance window", "No unsupported claim"],
            "templates/commercial/feedback-request.md": ["Optional", "No public use", "Explicit publication permission"],
            "templates/commercial/time-margin-record.md": ["Actual time", "Collected cash", "Contribution per hour"],
            "templates/research/customer-discovery-interview.md": ["Research, not a sales call", "Do not record without permission", "Problem codes"],
            "templates/research/interview-evidence-register.md": ["Pseudonymous interview ID", "No names", "Aggregate themes"],
        }
        for path, markers in required.items():
            content = read(path)
            for marker in markers:
                require(marker in content, f"{path} missing control: {marker}")

    case("shared sell-to-close and research masters are complete", shared_master_pack_is_complete)

    def automation_contract_is_fail_closed() -> None:
        spec = read("automations/specs/A16-operating-launch-system.yaml")
        for marker in (
            "external_outreach_requires_human_approval",
            "no_pipeline_stage_mutation",
            "collected_cash_requires_payment_confirmation",
            "interview_data_must_be_pseudonymous_or_aggregate",
            "weekly_digest_requires_human_review",
            "python scripts/test_operating_launch_system.py",
        ):
            require(marker in spec, f"A16 contract missing gate: {marker}")

    case("A16 operating contract remains fail closed", automation_contract_is_fail_closed)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
