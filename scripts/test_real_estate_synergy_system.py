#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Stage007rTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (ROOT / "config" / "real-estate-synergy-system.json").read_text(encoding="utf-8")
        )
        cls.event_schema = json.loads(
            (ROOT / "schemas" / "crm" / "real-estate" / "synergy-event.schema.json").read_text(encoding="utf-8")
        )
        cls.report_schema = json.loads(
            (ROOT / "schemas" / "crm" / "real-estate" / "report-approval.schema.json").read_text(encoding="utf-8")
        )

    def test_generic_crm_preserved(self) -> None:
        decision = self.config["integration_decision"]
        self.assertTrue(decision["generic_crm_preserved"])
        self.assertFalse(decision["existing_master_modified"])

    def test_real_import_fail_closed(self) -> None:
        self.assertFalse(self.config["import_controls"]["real_import_permitted"])
        self.assertEqual(self.config["integration_decision"]["real_source_rows_imported"], 0)

    def test_independent_modules_present(self) -> None:
        ids = {module["id"] for module in self.config["modules"]}
        self.assertTrue({"visit_evidence", "renovation_estimator", "report_renderer", "property_client_matching"}.issubset(ids))

    def test_a30_runtime_is_extended_not_replaced(self) -> None:
        dependency = self.config["runtime_dependency"]
        self.assertEqual(dependency["automation"], "A30-real-estate-runtime-and-matching")
        self.assertFalse(dependency["replacement"])
        self.assertTrue((ROOT / dependency["engine"]).is_file())

    def test_event_idempotency_contract(self) -> None:
        required = set(self.event_schema["required"])
        self.assertTrue({"idempotency_key", "correlation_id", "payload_digest"}.issubset(required))

    def test_four_part_report_gate(self) -> None:
        required = set(self.report_schema["properties"]["approvals"]["required"])
        self.assertEqual(required, {"financial", "evidence", "legal", "commercial"})

    def test_all_external_actions_are_human_gated(self) -> None:
        self.assertTrue(all(self.config["human_gates"].values()))
        self.assertIn("autonomous contact", self.config["AI_controls"]["prohibited"])

    def test_restricted_github_custody(self) -> None:
        forbidden = set(self.config["systems_of_record"]["github"]["forbidden"])
        self.assertTrue({"real names", "full property addresses", "raw source rows"}.issubset(forbidden))

    def test_audit_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_real_estate_synergy_system.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
