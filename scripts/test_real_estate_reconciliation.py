#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.batch import (  # noqa: E402
    build_synthetic_batch,
    parse_synthetic_csv,
    process_synthetic_batch,
)
from intelligence.real_estate.reconciliation_api import (  # noqa: E402
    SyntheticReconciliationError,
    apply_mutation_plan,
    build_mutation_plan,
    compare_reconciliation_bundles,
    compare_snapshots,
    export_reconciliation_bundle,
    invert_mutation_plan,
    load_reconciliation_bundle,
    render_diff_markdown,
    snapshot_from_batch_result,
    validate_snapshot,
    verify_rollback,
)

BASE_FIXTURE = ROOT / "fixtures" / "real_estate" / "stage009r-synthetic-opportunities.csv"
TARGET_FIXTURE = ROOT / "fixtures" / "real_estate" / "stage010r-synthetic-opportunities-target.csv"


class Stage010rTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base_records = parse_synthetic_csv(BASE_FIXTURE.read_text(encoding="utf-8"))
        target_records = parse_synthetic_csv(TARGET_FIXTURE.read_text(encoding="utf-8"))
        duplicate = copy.deepcopy(target_records[1])
        duplicate["source_row"] = 4
        target_records.append(duplicate)

        before_batch = build_synthetic_batch(
            batch_id="SYN-BATCH-STAGE010R-BEFORE",
            source_profile="SYNTHETIC_OPPORTUNITIES",
            rights_status="owned",
            records=base_records,
        )
        after_batch = build_synthetic_batch(
            batch_id="SYN-BATCH-STAGE010R-AFTER",
            source_profile="SYNTHETIC_OPPORTUNITIES",
            rights_status="owned",
            records=target_records,
        )
        cls.before_result = process_synthetic_batch(before_batch)
        cls.after_result = process_synthetic_batch(after_batch)
        cls.before = snapshot_from_batch_result(cls.before_result)
        cls.after = snapshot_from_batch_result(cls.after_result)
        cls.diff = compare_snapshots(cls.before, cls.after)
        cls.plan = build_mutation_plan(cls.diff)

    def test_snapshots_are_valid_and_distinct(self) -> None:
        validate_snapshot(self.before)
        validate_snapshot(self.after)
        self.assertNotEqual(self.before["snapshot_digest"], self.after["snapshot_digest"])
        self.assertFalse(self.before["real_writes_permitted"])

    def test_property_diff_contains_add_change_remove(self) -> None:
        changes = self.diff["sheets"]["Properties"]
        self.assertEqual(changes["counts"]["added"], 1)
        self.assertEqual(changes["counts"]["removed"], 1)
        self.assertEqual(changes["counts"]["changed"], 1)
        self.assertEqual(changes["counts"]["unchanged"], 0)

    def test_scenario_diff_tracks_twenty_seven_mutations(self) -> None:
        changes = self.diff["sheets"]["Property Scenarios"]
        self.assertEqual(changes["counts"]["added"], 9)
        self.assertEqual(changes["counts"]["removed"], 9)
        self.assertEqual(changes["counts"]["changed"], 9)

    def test_quarantine_is_introduced(self) -> None:
        self.assertEqual(self.diff["totals"]["quarantines_introduced"], 1)
        quarantine = self.diff["quarantines"]["added"][0]["after"]
        self.assertEqual(quarantine["Reason"], "duplicate_external_code_in_batch")
        self.assertFalse(quarantine["Real Writes Permitted"])

    def test_field_level_change_is_explained(self) -> None:
        changed = self.diff["sheets"]["Property Scenarios"]["changed"][0]
        fields = {item["field"] for item in changed["field_changes"]}
        self.assertIn("Purchase Price €", fields)
        self.assertIn("Monthly Rent €", fields)

    def test_forward_plan_reaches_exact_target_digest(self) -> None:
        applied = apply_mutation_plan(self.before, self.plan)
        self.assertEqual(applied, self.after)
        self.assertEqual(applied["snapshot_digest"], self.after["snapshot_digest"])

    def test_inverse_plan_restores_exact_source_digest(self) -> None:
        target = apply_mutation_plan(self.before, self.plan)
        rollback = invert_mutation_plan(self.plan)
        restored = apply_mutation_plan(target, rollback)
        self.assertEqual(restored, self.before)

    def test_rollback_receipt_is_verified(self) -> None:
        receipt = verify_rollback(self.before, self.plan)
        self.assertTrue(receipt["rollback_verified"])
        self.assertEqual(
            receipt["restored_snapshot_digest"],
            receipt["original_snapshot_digest"],
        )
        self.assertFalse(receipt["real_writes_permitted"])

    def test_markdown_diff_is_human_readable(self) -> None:
        markdown = render_diff_markdown(self.diff)
        self.assertIn("# Synthetic Fixture Reconciliation", markdown)
        self.assertIn("## Properties", markdown)
        self.assertIn("## Quarantines", markdown)
        self.assertIn("Real writes", markdown)

    def test_reconciliation_bundle_is_deterministic(self) -> None:
        rollback = invert_mutation_plan(self.plan)
        receipt = verify_rollback(self.before, self.plan)
        with tempfile.TemporaryDirectory() as directory:
            first = export_reconciliation_bundle(
                self.after,
                destination=Path(directory) / "first.zip",
                diff=self.diff,
                forward_plan=self.plan,
                rollback_plan=rollback,
                rollback_receipt=receipt,
            )
            second = export_reconciliation_bundle(
                self.after,
                destination=Path(directory) / "second.zip",
                diff=self.diff,
                forward_plan=self.plan,
                rollback_plan=rollback,
                rollback_receipt=receipt,
            )
            self.assertEqual(first["bundle_digest"], second["bundle_digest"])
            self.assertIn("reconciliation/diff.md", first["files"])
            self.assertFalse(first["real_writes_permitted"])

    def test_bundle_round_trip_preserves_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "snapshot.zip"
            export_reconciliation_bundle(self.after, destination=bundle)
            loaded = load_reconciliation_bundle(bundle)
            self.assertEqual(loaded, self.after)

    def test_bundle_comparison_matches_direct_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            before_bundle = Path(directory) / "before.zip"
            after_bundle = Path(directory) / "after.zip"
            export_reconciliation_bundle(self.before, destination=before_bundle)
            export_reconciliation_bundle(self.after, destination=after_bundle)
            bundle_diff = compare_reconciliation_bundles(before_bundle, after_bundle)
            self.assertEqual(bundle_diff, self.diff)

    def test_tampered_bundle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.zip"
            tampered = Path(directory) / "tampered.zip"
            export_reconciliation_bundle(self.after, destination=original)
            with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(tampered, "w") as target:
                for name in source.namelist():
                    body = source.read(name)
                    if name == "snapshot.json":
                        body = b"{}"
                    target.writestr(name, body)
            with self.assertRaisesRegex(SyntheticReconciliationError, "digest mismatch"):
                load_reconciliation_bundle(tampered)

    def test_mutation_precondition_blocks_wrong_source(self) -> None:
        corrupted = copy.deepcopy(self.before)
        corrupted["snapshot_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(SyntheticReconciliationError, "snapshot digest mismatch"):
            apply_mutation_plan(corrupted, self.plan)

    def test_operation_tampering_is_rejected(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["row_id"] += "-TAMPERED"
        with self.assertRaisesRegex(SyntheticReconciliationError, "operation digest mismatch"):
            apply_mutation_plan(self.before, plan)


if __name__ == "__main__":
    unittest.main()
