#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.batch import (  # noqa: E402
    SyntheticBatchError,
    build_synthetic_batch,
    export_fixture_bundle,
    parse_synthetic_csv,
    process_synthetic_batch,
    validate_fixture_contract,
)
from intelligence.real_estate.synergy import SyntheticSynergyOrchestrator  # noqa: E402

FIXTURE = ROOT / "fixtures" / "real_estate" / "stage009r-synthetic-opportunities.csv"
CONTRACT = ROOT / "schemas" / "crm" / "real-estate" / "runtime-sheets-contract.json"


class Stage009rTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.csv_text = FIXTURE.read_text(encoding="utf-8")
        cls.records = parse_synthetic_csv(cls.csv_text)
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def build_batch(self, records=None, rights_status="owned"):
        return build_synthetic_batch(
            batch_id="SYN-BATCH-STAGE009R-001",
            source_profile="SYNTHETIC_OPPORTUNITIES",
            rights_status=rights_status,
            records=self.records if records is None else records,
        )

    def test_csv_parser_preserves_two_rows(self) -> None:
        self.assertEqual(len(self.records), 2)
        self.assertEqual(self.records[0]["source_row"], 2)
        self.assertEqual(self.records[0]["row"]["CODI"], "SYN_BA_RI01")

    def test_two_rows_generate_eighteen_scenarios(self) -> None:
        result = process_synthetic_batch(self.build_batch())
        self.assertEqual(result["summary"]["counts"]["processed"], 2)
        self.assertEqual(result["fixture"].count("Properties"), 2)
        self.assertEqual(result["fixture"].count("Property Scenarios"), 18)
        self.assertEqual(result["fixture"].count("RE Import Staging"), 2)
        self.assertFalse(result["summary"]["real_writes_permitted"])

    def test_one_bad_rights_row_does_not_abort_batch(self) -> None:
        records = copy.deepcopy(self.records)
        records[1]["rights_status"] = "unverified"
        result = process_synthetic_batch(self.build_batch(records))
        self.assertEqual(result["summary"]["counts"]["processed"], 1)
        self.assertEqual(result["summary"]["counts"]["quarantined"], 1)
        self.assertEqual(result["fixture"].count("Properties"), 1)

    def test_duplicate_external_code_is_quarantined(self) -> None:
        records = copy.deepcopy(self.records)
        records[1]["row"]["CODI"] = records[0]["row"]["CODI"]
        result = process_synthetic_batch(self.build_batch(records))
        self.assertEqual(result["summary"]["counts"]["processed"], 1)
        self.assertEqual(result["summary"]["counts"]["quarantined"], 1)
        self.assertEqual(
            result["row_receipts"][1]["reason"],
            "duplicate_external_code_in_batch",
        )

    def test_replaying_batch_does_not_duplicate_fixture(self) -> None:
        runtime = SyntheticSynergyOrchestrator()
        first = process_synthetic_batch(self.build_batch(), orchestrator=runtime)
        second = process_synthetic_batch(self.build_batch(), orchestrator=runtime)
        self.assertEqual(first["summary"]["counts"]["processed"], 2)
        self.assertEqual(second["summary"]["counts"]["replayed"], 2)
        self.assertEqual(runtime.fixture.count("Properties"), 2)
        self.assertEqual(runtime.fixture.count("Property Scenarios"), 18)

    def test_fixture_matches_runtime_sheet_contract(self) -> None:
        result = process_synthetic_batch(self.build_batch())
        validation = validate_fixture_contract(result["fixture"], self.contract)
        self.assertTrue(validation["valid"], validation)

    def test_bundle_export_is_deterministic(self) -> None:
        result = process_synthetic_batch(self.build_batch())
        with tempfile.TemporaryDirectory() as directory:
            first = export_fixture_bundle(
                result["fixture"],
                batch_result=result,
                destination=Path(directory) / "first.zip",
                contract=self.contract,
            )
            second = export_fixture_bundle(
                result["fixture"],
                batch_result=result,
                destination=Path(directory) / "second.zip",
                contract=self.contract,
            )
            self.assertEqual(first["bundle_digest"], second["bundle_digest"])
            self.assertIn("manifest.json", first["files"])
            self.assertTrue(first["manifest"]["contract_validation"]["valid"])
            self.assertFalse(first["real_writes_permitted"])

    def test_non_synthetic_batch_is_rejected(self) -> None:
        batch = self.build_batch()
        batch["synthetic"] = False
        with self.assertRaisesRegex(SyntheticBatchError, "synthetic batch flag"):
            process_synthetic_batch(batch)

    def test_fixture_contains_no_network_clients(self) -> None:
        body = (ROOT / "intelligence" / "real_estate" / "batch.py").read_text(encoding="utf-8")
        for forbidden in (
            "googleapiclient",
            "gspread",
            "requests",
            "httpx",
            "smtplib",
            "send_email",
            "send_message",
        ):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
