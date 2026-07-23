#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.autopptx_pipeline import (  # noqa: E402
    build_autopptx_pipeline_plan,
    build_usando_update_plan,
    create_project_workspace,
    natural_key,
    stage_autopptx_media,
)
from intelligence.real_estate.media_rights import (  # noqa: E402
    MediaRightsError,
    build_authorised_cleanup_job,
    build_media_record,
)
from intelligence.real_estate.zone_evidence import (  # noqa: E402
    ZoneEvidenceError,
    build_zone_capture_plan,
    build_zone_evidence,
    classify_zone_from_thresholds,
)


class RC2Tests(unittest.TestCase):
    def _file(self, root: Path, name: str, body: bytes = b"x") -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def test_capture_plan_is_supervised_and_no_scraping(self):
        plan = build_zone_capture_plan(
            project_code="BA_BARCELONA_GRACIA01",
            exact_address="Carrer de Test 10, Barcelona",
            operator_token="restricted://operator/test",
        )
        self.assertTrue(plan["automation_boundary"]["manual_browser_capture_required"])
        self.assertFalse(plan["automation_boundary"]["page_scraping_permitted"])

    def test_zone_threshold_classifier(self):
        self.assertEqual(
            classify_zone_from_thresholds(10000, [15000, 25000, 35000, 50000]),
            1,
        )
        self.assertEqual(
            classify_zone_from_thresholds(52000, [15000, 25000, 35000, 50000]),
            5,
        )

    def test_zone_evidence_requires_map_and_two_surroundings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            map_file = self._file(root, "map.png")
            z1 = self._file(root, "z1.png")
            z2 = self._file(root, "z2.png")
            plan = build_zone_capture_plan(
                project_code="BA_BARCELONA_GRACIA01",
                exact_address="Carrer de Test 10, Barcelona",
                operator_token="restricted://operator/test",
            )
            evidence = build_zone_evidence(
                capture_plan=plan,
                capture_record={
                    "matched_address": "Carrer de Test 10, Barcelona",
                    "latitude": 41.4,
                    "longitude": 2.16,
                    "address_match_confidence": 0.99,
                    "household_income_eur": 42000,
                    "source_data_year": 2020,
                    "selected_zone": 4,
                    "legend_label": "reviewed fourth legend bucket",
                    "legend_version": "LV-2022-10-07-reviewed-v1",
                    "map_screenshot_path": str(map_file),
                    "manual_confirmation": True,
                    "surroundings": [
                        {
                            "path": str(z1),
                            "source_url": "https://example.test/1",
                            "rights_status": "owned",
                        },
                        {
                            "path": str(z2),
                            "source_url": "https://example.test/2",
                            "rights_status": "licensed",
                        },
                    ],
                },
                reviewed_thresholds=[15000, 25000, 35000, 50000],
            )
            self.assertEqual(evidence["zone"], 4)
            self.assertTrue(evidence["stale_data_warning_required"])
            self.assertFalse(evidence["watermark_removal_permitted_for_map"])

    def test_unconfirmed_zone_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = build_zone_capture_plan(
                project_code="BA_BARCELONA_GRACIA01",
                exact_address="Carrer de Test 10, Barcelona",
                operator_token="restricted://operator/test",
            )
            with self.assertRaisesRegex(ZoneEvidenceError, "manual confirmation"):
                build_zone_evidence(
                    capture_plan=plan,
                    capture_record={
                        "matched_address": "Carrer de Test 10, Barcelona",
                        "latitude": 41.4,
                        "longitude": 2.16,
                        "address_match_confidence": 0.99,
                        "household_income_eur": 42000,
                        "source_data_year": 2020,
                        "selected_zone": 4,
                        "legend_label": "bucket",
                        "legend_version": "v1",
                        "map_screenshot_path": str(self._file(root, "map.png")),
                        "manual_confirmation": False,
                        "surroundings": [],
                    },
                )

    def test_cleanup_requires_authorised_rights(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(Path(directory), "photo.jpg")
            record = build_media_record(
                media_id="M-1",
                source_path=source,
                source_type="portal_listing_photo",
                rights_status="unverified",
                authorisation_evidence="restricted://rights/test",
            )
            with self.assertRaisesRegex(MediaRightsError, "owned or authorised"):
                build_authorised_cleanup_job(
                    media_record=record,
                    output_dir=str(Path(directory) / "out"),
                    reviewer_token="restricted://reviewer/test",
                    reason="Prepare an authorised client-owned report image",
                )

    def test_map_capture_cleanup_is_forbidden(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(Path(directory), "map.jpg")
            record = build_media_record(
                media_id="M-2",
                source_path=source,
                source_type="lavanguardia_map_capture",
                rights_status="owned",
                authorisation_evidence="restricted://rights/test",
            )
            with self.assertRaisesRegex(MediaRightsError, "cannot be cleaned"):
                build_authorised_cleanup_job(
                    media_record=record,
                    output_dir=str(Path(directory) / "out"),
                    reviewer_token="restricted://reviewer/test",
                    reason="Attempted map cleanup should remain blocked",
                )

    def test_authorised_property_photo_cleanup_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._file(root, "photo.jpg")
            record = build_media_record(
                media_id="M-3",
                source_path=source,
                source_type="client_property_photo",
                rights_status="client_authorised",
                authorisation_evidence="restricted://rights/client-approval",
            )
            job = build_authorised_cleanup_job(
                media_record=record,
                output_dir=str(root / "out"),
                reviewer_token="restricted://reviewer/media",
                reason="Client authorised removal for the investment report",
            )
            self.assertTrue(job["preserve_original"])
            self.assertFalse(job["overwrite_original"])
            self.assertEqual(job["detector"], "Florence-2 open-vocabulary detection")

    def test_natural_media_order(self):
        self.assertLess(natural_key("2.jpg"), natural_key("10.jpg"))

    def test_usando_plan_binds_selector_and_tax(self):
        with tempfile.TemporaryDirectory() as directory:
            workbook = self._file(
                Path(directory),
                "Maumer_Capital-Oportunidades_USANDO.xlsx",
            )
            plan = build_usando_update_plan(
                project_code="BA_BARCELONA_GRACIA01",
                workbook_path=workbook,
                field_values={"PRECIO DE COMPRA": 100000, "M2": 70},
                source_profile="SYNTHETIC_TEST",
                explicit_transfer_tax_rate=0.10,
            )
            self.assertEqual(plan["selected_project_cell"], "B3")
            self.assertEqual(plan["field_values"]["Transfer Tax Rate"], 0.10)
            self.assertEqual(plan["formula_recalculation"], "CalculateFullRebuild")

    def test_end_to_end_pipeline_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = create_project_workspace(root, "BA_BARCELONA_GRACIA01")
            workbook = self._file(
                root,
                "Maumer_Capital-Oportunidades_USANDO.xlsx",
            )
            p1 = self._file(root, "10.jpg")
            p2 = self._file(root, "2.jpg")
            map_file = self._file(root, "map.png")
            z1 = self._file(root, "z1.png")
            z2 = self._file(root, "z2.png")
            capture_plan = build_zone_capture_plan(
                project_code="BA_BARCELONA_GRACIA01",
                exact_address="Carrer de Test 10, Barcelona",
                operator_token="restricted://operator/test",
            )
            zone = build_zone_evidence(
                capture_plan=capture_plan,
                capture_record={
                    "matched_address": "Carrer de Test 10, Barcelona",
                    "latitude": 41.4,
                    "longitude": 2.16,
                    "address_match_confidence": 1,
                    "household_income_eur": 42000,
                    "source_data_year": 2020,
                    "selected_zone": 4,
                    "legend_label": "bucket 4",
                    "legend_version": "v1",
                    "map_screenshot_path": str(map_file),
                    "manual_confirmation": True,
                    "surroundings": [
                        {
                            "path": str(z1),
                            "source_url": "https://example.test/1",
                            "rights_status": "owned",
                        },
                        {
                            "path": str(z2),
                            "source_url": "https://example.test/2",
                            "rights_status": "licensed",
                        },
                    ],
                },
            )
            staging = stage_autopptx_media(
                workspace=workspace,
                property_media=[
                    {"source_path": str(p1), "rights_status": "owned"},
                    {
                        "source_path": str(p2),
                        "rights_status": "client_authorised",
                    },
                ],
                zone_evidence=zone,
            )
            workbook_plan = build_usando_update_plan(
                project_code="BA_BARCELONA_GRACIA01",
                workbook_path=workbook,
                field_values={"PRECIO DE COMPRA": 100000},
                source_profile="TEST",
                explicit_transfer_tax_rate=0.10,
            )
            report_job = {
                "project_code": "BA_BARCELONA_GRACIA01",
                "generation_status": "approved_for_local_generation",
                "job_digest": "sha256:" + "a" * 64,
            }
            plan = build_autopptx_pipeline_plan(
                project_code="BA_BARCELONA_GRACIA01",
                workspace=workspace,
                workbook_plan=workbook_plan,
                zone_evidence=zone,
                media_staging=staging,
                report_job=report_job,
            )
            self.assertEqual(plan["slide_requirements"]["slide_8_zone"], 4)
            self.assertFalse(
                plan["execution_controls"]["real_client_delivery_permitted"]
            )


if __name__ == "__main__":
    unittest.main()
