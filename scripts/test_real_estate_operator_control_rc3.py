#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.autopptx_pipeline import (  # noqa: E402
    build_usando_update_plan,
    create_project_workspace,
    stage_autopptx_media,
)
from intelligence.real_estate.media_rights import (  # noqa: E402
    MediaRightsError,
    build_authorised_cleanup_job,
    build_media_record,
    build_watermarkremover_command,
)
from intelligence.real_estate.operator_control import (  # noqa: E402
    OperatorControlError,
    build_case_control,
    evaluate_case,
    render_case_markdown,
    update_component,
)
from intelligence.real_estate.release_readiness import (  # noqa: E402
    evaluate_all_modes,
    load_json,
    render_markdown,
)

POLICY = ROOT / "config" / "real-estate-release-readiness-rc3.json"
EVIDENCE = (
    ROOT
    / "evidence"
    / "readiness"
    / "2026-07-23-real-estate-release-evidence-rc3.json"
)


class RC3OperatorControlTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_json(POLICY)
        self.evidence = load_json(EVIDENCE)
        self.component_ids = [item["id"] for item in self.policy["case_components"]]

    def _file(self, root: Path, name: str, body: bytes) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def _case(self):
        return build_case_control(
            project_code="BA_BARCELONA_GRACIA01",
            title="Synthetic Barcelona case",
            source_kind="listing_link",
            created_on="2026-07-23",
            component_ids=self.component_ids,
        )

    def test_release_percentages_are_deterministic(self):
        summary = evaluate_all_modes(policy=self.policy, evidence=self.evidence)
        self.assertEqual(
            summary["modes"]["architecture_package"]["score_percent"], 98.8
        )
        self.assertEqual(
            summary["modes"]["controlled_operator_use"]["score_percent"], 81.5
        )
        self.assertEqual(
            summary["modes"]["live_client_production"]["score_percent"], 47.0
        )

    def test_release_decisions_do_not_follow_percentage_alone(self):
        summary = evaluate_all_modes(policy=self.policy, evidence=self.evidence)
        self.assertEqual(
            summary["modes"]["architecture_package"]["decision"],
            "ready_for_release_review",
        )
        self.assertEqual(
            summary["modes"]["controlled_operator_use"]["decision"],
            "controlled_use_ready",
        )
        self.assertEqual(
            summary["modes"]["live_client_production"]["decision"],
            "not_ready",
        )
        self.assertIn(
            "live_source_permissions",
            summary["modes"]["live_client_production"]["critical_blockers"],
        )

    def test_release_markdown_reports_all_three_modes(self):
        markdown = render_markdown(
            evaluate_all_modes(policy=self.policy, evidence=self.evidence)
        )
        self.assertIn("98.8%", markdown)
        self.assertIn("81.5%", markdown)
        self.assertIn("47.0%", markdown)
        self.assertIn("score is", markdown.casefold())

    def test_new_case_starts_at_zero(self):
        summary = evaluate_case(policy=self.policy, control=self._case())
        self.assertEqual(summary["score_percent"], 0.0)
        self.assertFalse(summary["gates"]["preanalysis_ready"]["ready"])
        self.assertFalse(summary["external_actions_permitted"])

    def test_approved_intake_and_facts_unlock_preanalysis(self):
        control = self._case()
        for component in ("source_intake", "property_facts"):
            control = update_component(
                control=control,
                component_id=component,
                status="approved",
                updated_on="2026-07-23",
                actor_token="restricted://operator/test",
                evidence_pointer=f"restricted://evidence/{component}",
            )
        summary = evaluate_case(policy=self.policy, control=control)
        self.assertEqual(summary["score_percent"], 20.0)
        self.assertTrue(summary["gates"]["preanalysis_ready"]["ready"])
        self.assertFalse(summary["gates"]["report_ready"]["ready"])

    def test_blocked_component_is_prioritised(self):
        control = update_component(
            control=self._case(),
            component_id="zone_evidence",
            status="blocked",
            updated_on="2026-07-23",
            actor_token="restricted://operator/test",
            note="Exact address unavailable",
        )
        summary = evaluate_case(policy=self.policy, control=control)
        self.assertEqual(summary["next_actions"][0]["component"], "zone_evidence")
        self.assertIn("zone_evidence", summary["blocked_components"])

    def test_non_restricted_evidence_pointer_is_rejected(self):
        with self.assertRaisesRegex(OperatorControlError, "restricted"):
            update_component(
                control=self._case(),
                component_id="source_intake",
                status="approved",
                updated_on="2026-07-23",
                actor_token="restricted://operator/test",
                evidence_pointer="https://example.test/private-record",
            )

    def test_case_markdown_contains_manual_and_automatic_actions(self):
        markdown = render_case_markdown(
            evaluate_case(policy=self.policy, control=self._case())
        )
        self.assertIn("manual:", markdown)
        self.assertIn("Automation:", markdown)
        self.assertIn("Readiness: 0.0%", markdown)

    def test_transfer_tax_is_reviewed_without_false_header_write(self):
        with tempfile.TemporaryDirectory() as directory:
            workbook = self._file(
                Path(directory),
                "Maumer_Capital-Oportunidades_USANDO.xlsx",
                b"synthetic workbook",
            )
            plan = build_usando_update_plan(
                project_code="BA_BARCELONA_GRACIA01",
                workbook_path=workbook,
                field_values={"PRECIO DE COMPRA": 100000},
                source_profile="SYNTHETIC",
                explicit_transfer_tax_rate=0.10,
            )
            self.assertEqual(plan["field_values"]["Transfer Tax Rate"], 0.10)
            self.assertIn("Transfer Tax Rate", plan["metadata_only_fields"])
            self.assertTrue(plan["manual_transfer_tax_binding_required"])
            self.assertEqual(plan["reviewed_assumptions"]["transfer_tax_rate"], 0.10)

    def test_cleanup_command_uses_isolated_single_file_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._file(root, "source" / "photo.jpg", b"source")
            entrypoint = self._file(root, "tool" / "remwm.py", b"print('test')")
            record = build_media_record(
                media_id="MEDIA-1",
                source_path=source,
                source_type="client_property_photo",
                rights_status="client_authorised",
                authorisation_evidence="restricted://rights/test",
            )
            job = build_authorised_cleanup_job(
                media_record=record,
                output_dir=root / "clean",
                reviewer_token="restricted://reviewer/media",
                reason="Client authorised cleanup for report use",
            )
            command = build_watermarkremover_command(
                cleanup_job=job,
                entrypoint=entrypoint,
            )
            self.assertEqual(command["command"][-2], job["isolated_input_dir"])
            self.assertEqual(command["command"][-1], job["isolated_output_dir"])
            self.assertNotEqual(Path(job["expected_output_path"]), source)
            self.assertTrue(job["single_media_isolation_required"])

    def test_cleanup_cannot_overwrite_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._file(root, "photo.jpg", b"source")
            record = build_media_record(
                media_id="MEDIA-2",
                source_path=source,
                source_type="client_property_photo",
                rights_status="owned",
                authorisation_evidence="restricted://rights/test",
            )
            with self.assertRaisesRegex(MediaRightsError, "overwrite"):
                build_authorised_cleanup_job(
                    media_record=record,
                    output_dir=root,
                    reviewer_token="restricted://reviewer/media",
                    reason="Owner authorised cleanup for report use",
                )

    def test_media_staging_removes_stale_and_duplicate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = create_project_workspace(root, "BA_BARCELONA_GRACIA01")
            piso = Path(workspace["autopptx_piso"])
            stale = self._file(piso, "01_piso.jpg", b"stale")
            property_a = self._file(root, "input" / "2.jpg", b"same")
            property_b = self._file(root, "input" / "10.jpg", b"same")
            map_file = self._file(root, "zone" / "map.png", b"map")
            zone_1 = self._file(root, "zone" / "1.png", b"zone1")
            zone_2 = self._file(root, "zone" / "2.png", b"zone2")
            zone = {
                "evidence_type": "lavanguardia_census_income_zone",
                "manual_confirmation": True,
                "evidence_digest": "sha256:" + "a" * 64,
                "source_data_year": 2020,
                "stale_data_warning_required": True,
                "map_screenshot_path": str(map_file),
                "surroundings": [{"path": str(zone_1)}, {"path": str(zone_2)}],
            }
            staging = stage_autopptx_media(
                workspace=workspace,
                property_media=[
                    {"source_path": str(property_a), "rights_status": "owned"},
                    {"source_path": str(property_b), "rights_status": "owned"},
                ],
                zone_evidence=zone,
            )
            self.assertEqual(staging["property_media_count"], 1)
            self.assertIn(str(property_b), staging["property_duplicate_sources_removed"])
            self.assertIn(str(stale), staging["stale_managed_files_removed"])
            self.assertFalse(stale.exists())
            self.assertTrue(staging["minimum_zone_media_satisfied"])


if __name__ == "__main__":
    unittest.main()
