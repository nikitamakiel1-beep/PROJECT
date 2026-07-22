#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.operating_evidence import (  # noqa: E402
    INTERVIEW_TARGET_MIX,
    build_interview_execution_queue,
    build_operating_evidence_receipt,
    verify_operating_evidence_receipt,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def base_snapshot() -> dict:
    linear_issues = []
    for index in range(18):
        linear_issues.append({"issue_id": f"DONE-{index:02d}", "status": "Done", "due_date": "2026-07-01"})
    for index in range(9):
        linear_issues.append({"issue_id": f"ACTIVE-{index:02d}", "status": "In Progress", "due_date": "2026-07-22"})
    for index in range(2):
        linear_issues.append({"issue_id": f"TODO-{index:02d}", "status": "Todo", "due_date": "2026-08-01"})
    return {
        "leads": [],
        "opportunities": [],
        "activities": [],
        "delivery_jobs": [],
        "automations": [],
        "interviews": [],
        "linear_issues": linear_issues,
        "source_assertions": {
            "leads": 0,
            "opportunities": 0,
            "activities": 0,
            "delivery_jobs": 0,
            "automations": 0,
            "interviews": 0,
            "linear_issues": 29,
        },
        "programme_gates": [
            {
                "issue_id": "NIK-110",
                "status": "In Progress",
                "priority": "P1",
                "owner_route": "Founder → Provider",
                "reason": "provider qualification evidence is incomplete",
                "due_date": "2026-08-01",
            },
            {
                "issue_id": "NIK-CLOSED",
                "status": "Done",
                "priority": "P3",
                "reason": "closed gate must be excluded",
            },
        ],
    }


def run() -> None:
    results: list[dict[str, str]] = []

    def case(name: str, fn) -> None:
        fn()
        results.append({"case": name, "result": "passed"})

    def interview_queue_contract() -> None:
        queue = build_interview_execution_queue()
        require(len(queue) == 10, "interview queue must contain ten slots")
        counts: dict[str, int] = {}
        for item in queue:
            counts[item["target_segment"]] = counts.get(item["target_segment"], 0) + 1
            require(item["status"] == "unassigned", "queue must not invent selected contacts")
            require(item["human_outreach_required"] is True, "outreach must remain human")
            require(item["contact_basis_required"] is True, "contact basis gate missing")
        require(counts == INTERVIEW_TARGET_MIX, "interview segment mix drift")

    case("ten-slot human-gated interview queue", interview_queue_contract)

    def zero_state_is_truthful() -> None:
        receipt = build_operating_evidence_receipt(base_snapshot(), as_of="2026-07-22")
        metrics = receipt["management_digest"]["metrics"]
        require(metrics["leads_total"] == 0, "zero-state lead count drift")
        require(metrics["open_pipeline_eur"] == 0, "zero-state pipeline must be zero")
        require(metrics["won_revenue_eur"] == 0, "zero-state revenue must be zero")
        require(metrics["collected_cash_eur"] == 0, "zero-state cash must be zero")
        require(receipt["linear_status_counts"] == {"done": 18, "in_progress": 9, "open": 11, "todo": 2}, "Linear state mismatch")
        require(len(receipt["quality_warnings"]) == 3, "zero-state must produce three evidence warnings")
        require(receipt["interview_execution"]["assigned"] == 0, "queue must not claim assignments")

    case("current zero-state remains explicit", zero_state_is_truthful)

    def due_today_is_not_overdue() -> None:
        receipt = build_operating_evidence_receipt(base_snapshot(), as_of="2026-07-22")
        require(receipt["management_digest"]["metrics"]["linear_issues_overdue"] == 0, "due-today issue treated as overdue")
        changed = base_snapshot()
        changed["linear_issues"][18]["due_date"] = "2026-07-21"
        receipt = build_operating_evidence_receipt(changed, as_of="2026-07-22")
        require(receipt["management_digest"]["metrics"]["linear_issues_overdue"] == 1, "past-due issue not detected")

    case("due-date boundary is exact", due_today_is_not_overdue)

    def cash_is_not_inferred_from_won() -> None:
        snapshot = base_snapshot()
        snapshot["opportunities"] = [{
            "opportunity_id": "OPP-001",
            "stage": "Won",
            "value_eur": 299,
            "payment_confirmed": False,
            "collected_eur": 299,
        }]
        snapshot["source_assertions"]["opportunities"] = 1
        receipt = build_operating_evidence_receipt(snapshot, as_of="2026-07-22")
        metrics = receipt["management_digest"]["metrics"]
        require(metrics["won_revenue_eur"] == 299, "won revenue missing")
        require(metrics["collected_cash_eur"] == 0, "cash inferred without confirmation")
        snapshot["opportunities"][0]["payment_confirmed"] = True
        receipt = build_operating_evidence_receipt(snapshot, as_of="2026-07-22")
        require(receipt["management_digest"]["metrics"]["collected_cash_eur"] == 299, "confirmed cash missing")

    case("won revenue and collected cash remain separate", cash_is_not_inferred_from_won)

    def source_assertions_fail_closed() -> None:
        snapshot = base_snapshot()
        snapshot["source_assertions"]["linear_issues"] = 28
        try:
            build_operating_evidence_receipt(snapshot, as_of="2026-07-22")
        except ValueError as exc:
            require("source count mismatch" in str(exc), "unexpected mismatch error")
        else:
            raise AssertionError("source-count mismatch was accepted")

    case("source reconciliation fails closed", source_assertions_fail_closed)

    def pii_is_rejected() -> None:
        snapshot = base_snapshot()
        snapshot["leads"] = [{"lead_id": "L-001", "email": "person@example.com", "status": "new"}]
        snapshot["source_assertions"]["leads"] = 1
        try:
            build_operating_evidence_receipt(snapshot, as_of="2026-07-22")
        except ValueError as exc:
            require("forbidden field" in str(exc) or "email-like" in str(exc), "unexpected PII error")
        else:
            raise AssertionError("PII-bearing snapshot was accepted")

    case("direct personal data is rejected", pii_is_rejected)

    def receipt_is_deterministic_and_tamper_evident() -> None:
        first = build_operating_evidence_receipt(base_snapshot(), as_of="2026-07-22")
        second = build_operating_evidence_receipt(base_snapshot(), as_of="2026-07-22")
        require(first["receipt_sha256"] == second["receipt_sha256"], "receipt digest is not deterministic")
        require(verify_operating_evidence_receipt(first), "valid receipt did not verify")
        first["source_counts"]["leads"] = 1
        require(not verify_operating_evidence_receipt(first), "tampered receipt still verified")

    case("receipt digest is deterministic and tamper evident", receipt_is_deterministic_and_tamper_evident)

    def cli_round_trip() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "snapshot.json"
            output = temp / "receipt.json"
            source.write_text(json.dumps(base_snapshot()), encoding="utf-8")
            subprocess.run([
                sys.executable,
                str(ROOT / "scripts" / "reconcile_operating_evidence.py"),
                str(source),
                "--as-of",
                "2026-07-22",
                "--output",
                str(output),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            require(verify_operating_evidence_receipt(receipt), "CLI receipt failed verification")
            require(receipt["controls"]["external_message_sent"] is False, "CLI claimed outbound action")
            require(receipt["controls"]["crm_mutated"] is False, "CLI claimed CRM mutation")
            require(len(receipt["programme_gates"]) == 1, "closed programme gate was not excluded")

    case("CLI produces a governed receipt", cli_round_trip)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
