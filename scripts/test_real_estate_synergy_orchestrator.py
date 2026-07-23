#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.synergy import (  # noqa: E402
    SyntheticSynergyOrchestrator,
    build_synthetic_event,
)


def safe_property_row() -> dict:
    return {
        "CODI": "SYN_BA_RI01",
        "FINANCIACION": 0.70,
        "PRECIO DE COMPRA": 82500,
        "REFORMA ESTIMADA TRADICIONAL": 15000,
        "REFORMA ESTIMADA HABITACIONES": 16900,
        "REFORMA ESTIMADA TEMPORAL": 17900,
        "Tipo interes": 0.032,
        "Años prestamo": 25,
        "AÃ±os prestamo": 25,
        "Downside Tradicional": 500,
        "Base Tradicional": 700,
        "Upside Tradicional": 800,
        "Downside Habitacions": 1100,
        "Base Habitacions": 1300,
        "Upside Habitacions": 1450,
        "Downside Temporal": 1000,
        "Base Temporal": 1350,
        "Upside Temporal": 1600,
        "Habitaciones (en habitacional)": 3,
        "HONORARIOS INMOBILIARIA": 3509,
        "HONORARIOS MAUMER CAPITAL": 4356,
        "Valor referencia": 53778.47,
        "Transfer Tax Rate": 0.10,
        "GASTOS NOTARIA & CO": 1837.50,
        "Other Costs": 0,
        "Vacancy Rate": 0,
        "IBI": 13.47,
        "COMUNIDAD": 60,
        "MANTENIMIENTO TRADICIONAL": 17.61,
        "SEGURO HOGAR": 12.5,
        "MANTENIMIENTO HABITACIONAL": 130,
        "MANTENIMIENTO TEMPORAL": 135,
        "Estat": "Validat",
        "Inmo": "Synthetic Agency",
        "M2": 72,
        "Ciudad": "Synthetic City",
        "Provincia": "Synthetic Province",
        "CCAA": "Synthetic Region",
        "Tradicional": "SI",
        "Habitacional": "SI",
        "Temporal": "SI",
        "Habitaciones": 3,
        "Baños": 1,
        "BaÃ±os": 1,
        "Planta": "2",
        "Ascensor": "SI",
        "Visitat": "NO",
    }


def mandate() -> dict:
    return {
        "schema_version": 1,
        "mandate_id": "MAND-SYN-ABCDEF123456",
        "lead_id": "LEAD-SYN-001",
        "contact_id": "CONTACT-SYN-001",
        "investor_type": "synthetic",
        "budget": {
            "min_eur": 80000,
            "max_eur": 130000,
            "cash_available_eur": 45000,
            "max_renovation_eur": 20000,
        },
        "preferred_regions": ["Synthetic Region"],
        "preferred_cities": ["Synthetic City"],
        "strategies": ["traditional_rental", "room_rental"],
        "return_requirements": {
            "min_gross_yield": 0.07,
            "min_net_yield": 0.04,
            "min_monthly_cash_flow_eur": 100,
        },
        "risk_appetite": "medium",
        "contact_basis": "synthetic_fixture",
    }


def property_payload(**overrides) -> dict:
    payload = {
        "synthetic": True,
        "source_profile": "SYNTHETIC_OPPORTUNITIES",
        "source_row": 6,
        "rights_status": "owned",
        "row": safe_property_row(),
    }
    payload.update(overrides)
    return payload


def event_for(event_type: str, payload: dict, key: str, entity_type: str = "property") -> dict:
    return build_synthetic_event(
        event_type,
        entity_type=entity_type,
        entity_id="SYN-ENTITY-001",
        payload=payload,
        correlation_id="SYN-CORRELATION-001",
        idempotency_key=key,
    )


class Stage008rTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = SyntheticSynergyOrchestrator()

    def create_property(self):
        payload = property_payload()
        event = event_for("realestate.property_case.created", payload, "SYN-PROPERTY-001")
        receipt = self.runtime.process(event, payload)
        self.assertEqual(receipt["status"], "processed", receipt)
        return receipt

    def test_property_import_is_synthetic_and_deterministic(self) -> None:
        first = self.create_property()
        self.assertFalse(first["real_writes_permitted"])
        self.assertFalse(first["external_communication_permitted"])
        self.assertEqual(self.runtime.fixture.count("Properties"), 1)
        self.assertEqual(self.runtime.fixture.count("Property Scenarios"), 9)
        self.assertEqual(self.runtime.fixture.count("RE Import Staging"), 1)

    def test_idempotent_replay_does_not_duplicate_rows(self) -> None:
        payload = property_payload()
        event = event_for("realestate.property_case.created", payload, "SYN-IDEMPOTENT-001")
        first = self.runtime.process(event, payload)
        second = self.runtime.process(event, payload)
        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["status"], "replayed")
        self.assertFalse(second["fixture_mutated"])
        self.assertEqual(self.runtime.fixture.count("Properties"), 1)

    def test_conflicting_idempotency_key_is_quarantined(self) -> None:
        original = property_payload()
        changed = property_payload()
        changed["row"]["PRECIO DE COMPRA"] = 90000
        first = event_for("realestate.property_case.created", original, "SYN-CONFLICT-001")
        second = event_for("realestate.property_case.created", changed, "SYN-CONFLICT-001")
        self.assertEqual(self.runtime.process(first, original)["status"], "processed")
        result = self.runtime.process(second, changed)
        self.assertEqual(result["reason"], "idempotency_conflict")
        self.assertEqual(self.runtime.fixture.count("Properties"), 1)

    def test_unverified_rights_are_quarantined(self) -> None:
        payload = property_payload(rights_status="unverified")
        result = self.runtime.process(
            event_for("realestate.property_case.created", payload, "SYN-RIGHTS-001"), payload
        )
        self.assertEqual(result["status"], "quarantined")
        self.assertEqual(self.runtime.fixture.count("Properties"), 0)

    def test_raw_listing_url_is_quarantined_before_A30(self) -> None:
        payload = property_payload()
        payload["row"]["Link"] = "https://example.invalid/property"
        result = self.runtime.process(
            event_for("realestate.property_case.created", payload, "SYN-URL-001"), payload
        )
        self.assertEqual(result["reason"], "restricted_payload")
        self.assertIn("payload.row.Link", result["details"])

    def test_pairwise_match_remains_review_required(self) -> None:
        created = self.create_property()["artifacts"]
        payload = {
            "synthetic": True,
            "mandate_payload": mandate(),
            "property_record": created["property"],
            "scenarios": created["scenarios"],
        }
        result = self.runtime.process(
            event_for("realestate.match.proposed", payload, "SYN-MATCH-001", "match"), payload
        )
        self.assertEqual(result["status"], "processed", result)
        self.assertFalse(result["artifacts"]["writes_permitted"])
        self.assertFalse(result["artifacts"]["external_communication_permitted"])
        self.assertTrue(result["artifacts"]["human_review_required"])
        self.assertTrue(all(row["Status"] == "review_required" for row in result["plan"]["rows"]["Property Matches"]))

    def test_visit_evidence_uses_restricted_synthetic_pointer(self) -> None:
        payload = {
            "synthetic": True,
            "visit": {
                "visit_id": "VIS-SYN-001",
                "property_id": "PROP-SYN-001",
                "visited_at": "2026-07-23T10:00:00+00:00",
                "visit_status": "completed",
                "access_status": "accessed",
                "evidence_items": [{
                    "evidence_id": "EVD-SYN-001",
                    "category": "living_room",
                    "rights_status": "owned",
                    "validation_status": "review_required",
                    "restricted_pointer": "restricted://synthetic/evidence/living-room-001",
                }],
            },
        }
        result = self.runtime.process(
            event_for("realestate.visit.submitted", payload, "SYN-VISIT-001", "visit"), payload
        )
        self.assertEqual(result["status"], "processed", result)
        self.assertEqual(self.runtime.fixture.count("Visits"), 1)
        self.assertEqual(self.runtime.fixture.count("Evidence & Media"), 1)

    def test_visit_with_unverified_media_rights_is_quarantined(self) -> None:
        payload = {
            "synthetic": True,
            "visit": {
                "visit_id": "VIS-SYN-002",
                "property_id": "PROP-SYN-002",
                "visit_status": "completed",
                "evidence_items": [{
                    "evidence_id": "EVD-SYN-002",
                    "category": "facade",
                    "rights_status": "unverified",
                    "validation_status": "review_required",
                    "restricted_pointer": "restricted://synthetic/evidence/facade-002",
                }],
            },
        }
        result = self.runtime.process(
            event_for("realestate.visit.submitted", payload, "SYN-VISIT-002", "visit"), payload
        )
        self.assertEqual(result["status"], "quarantined")
        self.assertEqual(self.runtime.fixture.count("Evidence & Media"), 0)

    def report_payload(self, approved: bool, duplicate_reviewers: bool = False) -> dict:
        roles = ("financial", "evidence", "legal", "commercial")
        approvals = {}
        for index, role in enumerate(roles):
            reviewer = 1 if duplicate_reviewers else index + 1
            approvals[role] = {
                "status": "approved" if approved else "pending",
                "reviewer_token": f"restricted://synthetic/reviewer/{reviewer}",
                "reviewed_at": "2026-07-23T12:00:00+00:00",
            }
        return {
            "synthetic": True,
            "report": {
                "report_id": "RPT-SYN-001",
                "property_id": "PROP-SYN-001",
                "scenario_ids": ["SCN-SYN-001"],
                "report_type": "investment_analysis",
                "template_version": "synthetic-template-v1",
                "calculation_version": "real-estate-underwriting-v0.1",
                "pptx_pointer": "restricted://synthetic/report/pptx-001",
                "pdf_pointer": "restricted://synthetic/report/pdf-001",
                "generation_status": "generated",
                "share_status": "not_shareable",
                "approvals": approvals,
            },
        }

    def test_generated_report_is_not_shareable(self) -> None:
        payload = self.report_payload(False)
        result = self.runtime.process(
            event_for("realestate.report.generated", payload, "SYN-REPORT-GEN-001", "report"), payload
        )
        self.assertEqual(result["status"], "processed", result)
        row = result["plan"]["rows"]["Reports & Approvals"][0]
        self.assertEqual(row["Share Status"], "not_shareable")

    def test_report_requires_four_distinct_approvers(self) -> None:
        payload = self.report_payload(True, duplicate_reviewers=True)
        result = self.runtime.process(
            event_for("realestate.report.approved", payload, "SYN-REPORT-BAD-001", "report"), payload
        )
        self.assertEqual(result["status"], "quarantined")

    def test_four_distinct_approvers_unlock_only_approved_state(self) -> None:
        payload = self.report_payload(True)
        result = self.runtime.process(
            event_for("realestate.report.approved", payload, "SYN-REPORT-OK-001", "report"), payload
        )
        self.assertEqual(result["status"], "processed", result)
        row = result["plan"]["rows"]["Reports & Approvals"][0]
        self.assertEqual(row["Share Status"], "approved")
        self.assertFalse(result["external_communication_permitted"])

    def test_runtime_contains_no_network_or_mail_client(self) -> None:
        body = (ROOT / "intelligence" / "real_estate" / "synergy.py").read_text(encoding="utf-8")
        for forbidden in ("googleapiclient", "requests", "smtplib", "send_email", "send_message", "gspread"):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
