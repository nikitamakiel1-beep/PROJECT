#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_crm.memory import (  # noqa: E402
    CalibrationMonitor,
    DriftMonitor,
    IncidentMemory,
    ModelPromotionGate,
    OutcomeLedger,
    ReplayBuffer,
    outcome_event,
)
from intelligence.venture_brain import AutonomousVenturePlanner  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def synthetic_events(count=120, model="candidate-v1"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = []
    for index in range(count):
        outcome = 1 if index % 2 == 0 else 0
        prediction = 0.92 if outcome else 0.08
        events.append(
            outcome_event(
                entity_id=f"LEAD-{index:04d}",
                model_version=model,
                prediction=prediction,
                outcome=outcome,
                segment="industrial" if index % 3 else "services",
                decision="create_opportunity" if outcome else "nurture",
                features={"fit": 0.8 if outcome else 0.3, "activity": 0.7 if outcome else 0.2},
                evidence={"cycle": index, "digest": f"synthetic-{index}"},
                occurred_at=(start + timedelta(days=index)).isoformat(),
            )
        )
    return events


def run():
    evidence = []

    def case(name, function):
        function()
        evidence.append({"case": name, "result": "passed"})

    def append_only_ledger():
        event = synthetic_events(1)[0]
        ledger = OutcomeLedger([event])
        require(len(ledger.events) == 1, "event was not stored")
        require(len(ledger.digest()) == 64, "ledger digest invalid")
        try:
            ledger.append(event)
        except ValueError as error:
            require("duplicate" in str(error), "duplicate failure reason missing")
        else:
            raise AssertionError("duplicate outcome event was accepted")

    case("outcome ledger is append-only and duplicate-safe", append_only_ledger)

    def calibration():
        events = synthetic_events(120)
        report = CalibrationMonitor.evaluate(events)
        require(report.sample_count == 120, "calibration sample count wrong")
        require(report.brier_score < 0.01, "well-separated synthetic predictions have high Brier score")
        require(report.expected_calibration_error < 0.10, "synthetic calibration error too high")
        require(report.log_loss < 0.10, "synthetic log loss too high")
        require(len(report.bins) >= 2, "calibration bins missing")

    case("calibration monitor produces bounded evidence", calibration)

    def replay_balanced():
        events = synthetic_events(60)
        selected = ReplayBuffer(capacity=40, seed=7).select(events, 12)
        require(len(selected) == 12, "replay selection length wrong")
        segments = {event.segment for event in selected}
        require(segments == {"industrial", "services"}, "segment-aware replay lost a segment")
        again = ReplayBuffer(capacity=40, seed=7).select(events, 12)
        require([event.event_id for event in selected] == [event.event_id for event in again], "replay selection is not deterministic")

    case("replay is deterministic and segment-aware", replay_balanced)

    def drift_monitoring():
        baseline = [{"fit": 0.50 + (index % 5) * 0.01, "activity": 0.40 + (index % 3) * 0.02} for index in range(100)]
        stable = [{"fit": 0.51 + (index % 5) * 0.01, "activity": 0.41 + (index % 3) * 0.02} for index in range(100)]
        shifted = [{"fit": 0.90 + (index % 5) * 0.01, "activity": 0.05 + (index % 3) * 0.01} for index in range(100)]
        stable_report = DriftMonitor.compare(baseline, stable)
        shifted_report = DriftMonitor.compare(baseline, shifted)
        require(not stable_report.drift_detected, "stable population triggered drift")
        require(shifted_report.drift_detected, "large population shift was not detected")
        require(shifted_report.maximum_score > stable_report.maximum_score, "shifted drift score did not increase")

    case("feature drift detects material change", drift_monitoring)

    def incident_memory():
        memory = IncidentMemory()
        incident = memory.record("calibration", "high", "candidate-v1", "a" * 64, "return to shadow")
        require(incident["status"] == "open", "incident did not open")
        resolved = memory.resolve(incident["incident_id"], "candidate rejected; baseline retained")
        require(resolved["status"] == "resolved", "incident did not resolve")
        require(len(memory.incidents) == 1, "incident memory count wrong")

    case("incident memory is append-only and resolvable", incident_memory)

    def promotion_fail_closed():
        events = synthetic_events(20)
        calibration_report = CalibrationMonitor.evaluate(events)
        drift_report = DriftMonitor.compare([{"fit": 0.5}], [{"fit": 0.5}])
        decision = ModelPromotionGate().evaluate(
            active_model="active-v1",
            candidate_model="candidate-v2",
            calibration=calibration_report,
            drift=drift_report,
            baseline_brier=0.25,
            red_team_passed=False,
            rollback_verified=False,
            temporal_split_verified=False,
            segment_review_passed=False,
            human_approved=False,
        )
        require(not decision.permitted, "incomplete candidate was promoted")
        require("insufficient_labelled_outcomes" in decision.reasons, "sample gate missing")
        require("human_approval_required" in decision.reasons, "human approval gate missing")
        require(decision.requires_human, "promotion did not retain human custody")

    case("model promotion is fail-closed", promotion_fail_closed)

    def promotion_evidence_complete():
        events = synthetic_events(120)
        calibration_report = CalibrationMonitor.evaluate(events)
        baseline = [{"fit": 0.5 + (index % 3) * 0.01} for index in range(120)]
        current = [{"fit": 0.505 + (index % 3) * 0.01} for index in range(120)]
        drift_report = DriftMonitor.compare(baseline, current)
        decision = ModelPromotionGate().evaluate(
            active_model="active-v1",
            candidate_model="candidate-v2",
            calibration=calibration_report,
            drift=drift_report,
            baseline_brier=0.20,
            red_team_passed=True,
            rollback_verified=True,
            temporal_split_verified=True,
            segment_review_passed=True,
            human_approved=True,
        )
        require(decision.permitted, f"complete candidate remained blocked: {decision.reasons}")
        require(decision.status == "approved_for_reviewed_promotion", "promotion status incorrect")

    case("complete evidence can pass reviewed promotion gate", promotion_evidence_complete)

    def planner_provider_priority():
        metrics = {key: 0.8 for key in (
            "provider_gate", "compliance_ready", "crm_data_quality", "website_quality", "interviews_progress",
            "demonstrations_progress", "pipeline_health", "delivery_capacity", "automation_reliability",
            "labelled_outcomes_progress", "drift_health", "incident_health", "partner_network_progress",
            "funding_radar_progress", "conversion_validation", "revenue_validation"
        )}
        metrics["provider_gate"] = 0.0
        planner = AutonomousVenturePlanner()
        first = planner.plan(3, metrics, {"provider": "not-run"})
        second = planner.plan(3, metrics, {"provider": "not-run"})
        require(first.selected_domain == "provider_runtime", f"provider gate was not prioritised: {first.selected_domain}")
        require(first.plan_id == second.plan_id, "planner is not deterministic")
        require(first.next_stage == 4, "planner did not advance n to n+1")
        require("Stage 004" in first.instruction_markdown, "next instruction stage number missing")
        require("External communication or publishing" in first.instruction_markdown, "prohibited actions missing")
        require("Generate the instruction for Stage 005" in first.instruction_markdown, "recursive handoff requirement missing")

    case("neural planner produces deterministic n-to-n-plus-one instruction", planner_provider_priority)

    def planner_compliance_blocker():
        metrics = {key: 0.9 for key in (
            "provider_gate", "compliance_ready", "crm_data_quality", "website_quality", "interviews_progress",
            "demonstrations_progress", "pipeline_health", "delivery_capacity", "automation_reliability",
            "labelled_outcomes_progress", "drift_health", "incident_health", "partner_network_progress",
            "funding_radar_progress", "conversion_validation", "revenue_validation"
        )}
        metrics["pipeline_health"] = 0.0
        metrics["compliance_ready"] = 0.2
        decision = AutonomousVenturePlanner().plan(7, metrics, {"source": "synthetic"})
        if decision.selected_domain in {"sales_pipeline", "customer_discovery", "partnerships_funding"}:
            require(decision.blocked, "communication-sensitive work ignored compliance blocker")
            require("communication_compliance_not_ready" in decision.blocker_reasons, "compliance blocker missing")

    case("planner preserves compliance custody", planner_compliance_blocker)

    print(json.dumps({"ok": True, "tests": evidence}, indent=2))


if __name__ == "__main__":
    run()
