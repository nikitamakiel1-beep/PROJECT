#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.acquisition import (  # noqa: E402
    AcquisitionPolicyError,
    build_acquisition_plan,
    build_idealista_search_request,
    connector_map,
    connector_readiness,
    load_connector_registry,
    validate_candidate,
)
from intelligence.real_estate.release_approval import (  # noqa: E402
    ReleaseApprovalCustody,
    ReleaseApprovalError,
    build_release_artifact_binding,
)
from intelligence.real_estate.report_release import (  # noqa: E402
    ReportReleaseError,
    build_local_command,
    build_report_job,
    execute_local_report_job,
    renderer_readiness,
    verify_report_outputs,
)

CONNECTORS = ROOT / "config" / "real-estate-source-connectors.json"
RENDERER = ROOT / "config" / "real-estate-report-renderer.json"
SOURCE_SCHEMA = ROOT / "schemas" / "crm" / "real-estate" / "source-candidate.schema.json"


class ArchitectureReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_connector_registry(CONNECTORS)
        cls.renderer = json.loads(RENDERER.read_text(encoding="utf-8"))
        cls.source_schema = json.loads(SOURCE_SCHEMA.read_text(encoding="utf-8"))

    @staticmethod
    def candidate(**updates):
        value = {
            "candidate_id": "SRC-CAND-SYNTHETIC-001",
            "connector_id": "supervised_url_capture",
            "source_kind": "idealista",
            "capture_mode": "manual_capture",
            "rights_status": "client_authorised",
            "captured_at": "2026-07-23T00:00:00+00:00",
            "external_reference": "SYNTHETIC-REF-001",
            "source_url_token": "restricted://source/synthetic-001",
            "off_market_claimed": False,
            "off_market_verified": False,
            "facts": {
                "price_eur": 90000,
                "municipality": "Synthetic City",
                "province": "Synthetic Province",
                "area_m2": 75,
                "bedrooms": 3,
                "bathrooms": 1,
            },
            "media_policy": {
                "reuse_permitted": False,
                "rights_basis": "none",
                "media_tokens": [],
            },
            "review_status": "approved",
            "reviewer_token": "restricted://reviewer/source-001",
        }
        value.update(updates)
        return value

    @staticmethod
    def report_approvals():
        return {
            role: {
                "status": "approved",
                "reviewer_token": f"restricted://reviewer/{index}",
            }
            for index, role in enumerate(
                (
                    "financial_reviewer",
                    "evidence_reviewer",
                    "legal_reviewer",
                    "commercial_reviewer",
                ),
                start=1,
            )
        }

    def test_connector_registry_has_unique_ids(self):
        connectors = connector_map(self.registry)
        self.assertEqual(len(connectors), len(self.registry["connectors"]))
        self.assertIn("idealista_search_api", connectors)
        self.assertIn("catastro_public_services", connectors)

    def test_registry_explicitly_blocks_uncontrolled_scraping(self):
        self.assertFalse(self.registry["principles"]["robots_or_scrapers_without_written_permission"])
        idealista = connector_map(self.registry)["idealista_search_api"]
        self.assertIn("web_scraping", idealista["forbidden"])

    def test_idealista_api_is_not_ready_without_provider_access(self):
        connector = connector_map(self.registry)["idealista_search_api"]
        readiness = connector_readiness(
            connector,
            {"IDEALISTA_API_KEY": "synthetic", "IDEALISTA_API_SECRET": "synthetic"},
        )
        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.reason, "provider_access_required")

    def test_idealista_request_builder_never_executes(self):
        request = build_idealista_search_request(
            country="es",
            operation="sale",
            property_type="homes",
            center="41.3874,2.1686",
            distance_m=5000,
            max_price=150000,
        )
        self.assertFalse(request["execute"])
        self.assertFalse(request["portal_scraping_permitted"])
        self.assertEqual(request["connector_id"], "idealista_search_api")

    def test_manual_candidate_builds_no_write_plan(self):
        plan = build_acquisition_plan(self.candidate(), self.registry)
        self.assertFalse(plan["real_writes_permitted"])
        self.assertFalse(plan["external_contact_permitted"])
        self.assertFalse(plan["portal_scraping_permitted"])
        self.assertEqual(plan["channel"]["classification"], "idealista_listing")
        self.assertFalse(plan["channel"]["psi_plus_eligible"])
        self.assertIn("Property Sources", plan["rows"])

    def test_off_market_candidate_is_channel_eligible(self):
        candidate = self.candidate(
            source_kind="off_market",
            off_market_claimed=True,
            off_market_verified=True,
        )
        plan = build_acquisition_plan(candidate, self.registry)
        self.assertTrue(plan["channel"]["psi_plus_eligible"])
        self.assertTrue(plan["channel"]["channel_eligible"])

    def test_unverified_rights_are_rejected(self):
        with self.assertRaisesRegex(AcquisitionPolicyError, "rights"):
            validate_candidate(
                self.candidate(rights_status="unverified"),
                self.registry,
            )

    def test_raw_url_is_rejected(self):
        candidate = self.candidate()
        candidate["source_url"] = "https://example.invalid/listing"
        with self.assertRaisesRegex(AcquisitionPolicyError, "raw URL"):
            validate_candidate(candidate, self.registry)

    def test_release_approvals_require_three_distinct_reviewers(self):
        binding = build_release_artifact_binding(
            connector_registry=self.registry,
            report_renderer=self.renderer,
            source_candidate_schema=self.source_schema,
            release_manifest={"release": "synthetic"},
        )
        custody = ReleaseApprovalCustody(binding)
        digest = custody.release_digest
        for index, role in enumerate(
            (
                "source_policy_reviewer",
                "privacy_reviewer",
                "architecture_release_approver",
            ),
            start=1,
        ):
            custody.approve(
                role=role,
                reviewer_token=f"restricted://reviewer/release-{index}",
                approved_at="2026-07-23T00:00:00+00:00",
                evidence_token=f"restricted://evidence/release-{index}",
                bound_release_digest=digest,
            )
        self.assertTrue(custody.qualification()["qualified"])
        self.assertTrue(custody.qualification()["release_or_deployment_permitted"])
        self.assertFalse(custody.qualification()["live_source_acquisition_permitted"])

    def test_release_approval_rejects_reused_reviewer(self):
        custody = ReleaseApprovalCustody({"artifact": "A"})
        digest = custody.release_digest
        custody.approve(
            role="source_policy_reviewer",
            reviewer_token="restricted://reviewer/shared",
            approved_at="2026-07-23T00:00:00+00:00",
            evidence_token="restricted://evidence/one",
            bound_release_digest=digest,
        )
        with self.assertRaisesRegex(ReleaseApprovalError, "distinct"):
            custody.approve(
                role="privacy_reviewer",
                reviewer_token="restricted://reviewer/shared",
                approved_at="2026-07-23T00:00:00+00:00",
                evidence_token="restricted://evidence/two",
                bound_release_digest=digest,
            )

    def test_release_digest_change_invalidates_approvals(self):
        artifacts = {"artifact": "A"}
        custody = ReleaseApprovalCustody(artifacts)
        digest = custody.release_digest
        custody.approve(
            role="source_policy_reviewer",
            reviewer_token="restricted://reviewer/one",
            approved_at="2026-07-23T00:00:00+00:00",
            evidence_token="restricted://evidence/one",
            bound_release_digest=digest,
        )
        artifacts["artifact"] = "B"
        self.assertIn("source_policy_reviewer", custody.qualification()["stale_roles"])

    def test_report_job_requires_verified_evidence(self):
        with self.assertRaisesRegex(ReportReleaseError, "unverified evidence"):
            build_report_job(
                property_id="PROP-SYN-1",
                project_code="SYN_BA_RI01",
                underwriting_case_id="UW-SYN-1",
                scenario_ids=["SCN-SYN-1"],
                calculation_version="synthetic-v1",
                input_snapshot_digest="sha256:" + "a" * 64,
                template_version="synthetic-template-v1",
                evidence=[{
                    "evidence_id": "EVD-1",
                    "validation_status": "review_required",
                    "restricted_pointer": "restricted://evidence/1",
                }],
                media=[],
                approvals=self.report_approvals(),
                source_candidate_digest="sha256:" + "b" * 64,
            )

    def test_report_job_requires_distinct_reviewers(self):
        approvals = self.report_approvals()
        approvals["legal_reviewer"]["reviewer_token"] = approvals["financial_reviewer"]["reviewer_token"]
        with self.assertRaisesRegex(ReportReleaseError, "distinct"):
            build_report_job(
                property_id="PROP-SYN-1",
                project_code="SYN_BA_RI01",
                underwriting_case_id="UW-SYN-1",
                scenario_ids=["SCN-SYN-1"],
                calculation_version="synthetic-v1",
                input_snapshot_digest="sha256:" + "a" * 64,
                template_version="synthetic-template-v1",
                evidence=[],
                media=[],
                approvals=approvals,
                source_candidate_digest="sha256:" + "b" * 64,
            )

    def test_local_report_adapter_executes_fake_renderer_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            output.mkdir()
            template = root / "template.pptx"
            workbook = root / "workbook.xlsx"
            template.write_bytes(b"synthetic-template")
            workbook.write_bytes(b"synthetic-workbook")
            entrypoint = root / "fake_renderer.py"
            entrypoint.write_text(
                "import os\n"
                "from pathlib import Path\n"
                "out=Path(os.environ['ALMA_REPORT_OUTPUT_DIR'])\n"
                "code=os.environ['ALMA_REPORT_PROJECT_CODE']\n"
                "(out/f'{code}.pptx').write_bytes(b'PPTX-SYNTHETIC')\n"
                "(out/f'{code}.pdf').write_bytes(b'PDF-SYNTHETIC')\n",
                encoding="utf-8",
            )
            env = {
                "AUTOPPTX_ENTRYPOINT": str(entrypoint),
                "AUTOPPTX_WORKDIR": str(root),
                "AUTOPPTX_TEMPLATE_PATH": str(template),
                "AUTOPPTX_WORKBOOK_PATH": str(workbook),
                "AUTOPPTX_OUTPUT_DIR": str(output),
                "AUTOPPTX_PDF_CONVERTER": "none",
            }
            self.assertTrue(renderer_readiness(self.renderer, env)["ready"])
            job = build_report_job(
                property_id="PROP-SYN-1",
                project_code="SYN_BA_RI01",
                underwriting_case_id="UW-SYN-1",
                scenario_ids=["SCN-SYN-1"],
                calculation_version="synthetic-v1",
                input_snapshot_digest="sha256:" + "a" * 64,
                template_version="synthetic-template-v1",
                evidence=[{
                    "evidence_id": "EVD-1",
                    "validation_status": "verified",
                    "restricted_pointer": "restricted://evidence/1",
                }],
                media=[{
                    "media_id": "MED-1",
                    "rights_status": "owned",
                    "restricted_pointer": "restricted://media/1",
                }],
                approvals=self.report_approvals(),
                source_candidate_digest="sha256:" + "b" * 64,
            )
            plan = build_local_command(job, self.renderer, env)
            self.assertFalse(plan["shell"])
            receipt = execute_local_report_job(
                job,
                plan,
                explicit_execution_approval=True,
                timeout_seconds=30,
            )
            self.assertTrue(receipt["success"])
            verified = verify_report_outputs(
                job=job,
                output_dir=output,
                pdf_required=True,
            )
            self.assertTrue(verified["archive_ready"])
            self.assertTrue(verified["external_share_ready"])
            self.assertFalse(verified["external_delivery_permitted"])

    def test_release_modules_do_not_import_network_clients(self):
        for relative in (
            "intelligence/real_estate/acquisition.py",
            "intelligence/real_estate/report_release.py",
        ):
            body = (ROOT / relative).read_text(encoding="utf-8")
            for forbidden in (
                "import requests",
                "import httpx",
                "googleapiclient",
                "gspread",
                "selenium",
                "playwright",
                "beautifulsoup",
            ):
                self.assertNotIn(forbidden, body.casefold())


if __name__ == "__main__":
    unittest.main()
