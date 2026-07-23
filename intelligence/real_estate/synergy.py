"""Synthetic-only event orchestrator for the governed real-estate vertical."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from .engine import (
    RealEstateGovernanceError,
    build_crm_merge_plan,
    detect_sensitive_fields,
    normalise_property_row,
)

SUPPORTED_EVENTS = {
    "realestate.property_case.created",
    "realestate.visit.submitted",
    "realestate.report.generated",
    "realestate.report.approved",
    "realestate.match.proposed",
}
ALLOWED_RIGHTS = {"owned", "licensed", "client_authorised", "public_source"}
RAW_KEYS = {
    "email", "phone", "full_name", "address", "full_address",
    "cadastral_reference", "listing_url", "client_name", "investor_name",
    "responsable", "clientes potenciales", "ref.catastral", "link",
    "caracteristiques pis",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r"https?://", re.I)


class SynergyRuntimeError(ValueError):
    pass


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def build_synthetic_event(
    event_type: str,
    *,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
    correlation_id: str,
    idempotency_key: str,
    occurred_at: str = "2026-07-23T00:00:00+00:00",
) -> dict[str, Any]:
    seed = f"{event_type}|{entity_type}|{entity_id}|{correlation_id}|{idempotency_key}"
    return {
        "event_id": "EVT-SYN-" + sha256(seed.encode()).hexdigest()[:20].upper(),
        "correlation_id": correlation_id,
        "event_type": event_type,
        "producer": "synthetic_fixture",
        "consumer": "synthetic_synergy_orchestrator",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "occurred_at": occurred_at,
        "idempotency_key": idempotency_key,
        "payload_digest": canonical_digest(payload),
        "human_gate_required": event_type in {
            "realestate.report.approved", "realestate.match.proposed"
        },
    }


def _restricted_paths(value: Any, path: str = "payload") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()
            child_path = f"{path}.{key}"
            if not name.endswith("_token") and name in RAW_KEYS and child not in (None, ""):
                found.append(child_path)
            found.extend(_restricted_paths(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_restricted_paths(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if EMAIL_RE.search(value) or URL_RE.search(value):
            found.append(path)
        if value.startswith("restricted://") and not value.startswith("restricted://synthetic/"):
            found.append(path)
    return sorted(set(found))


def _property_row(record: Mapping[str, Any]) -> dict[str, Any]:
    location = record["location"]
    features = record["features"]
    tokens = record["private_tokens"]
    return {
        "Property ID": record["property_id"],
        "External Code": record["external_code"],
        "Source Organisation ID": record.get("source_organisation_id"),
        "Source Record Digest": record["source_record_digest"],
        "Address Alias": None,
        "City": location.get("city"),
        "Province": location.get("province"),
        "Autonomous Community": location.get("autonomous_community"),
        "Property Type": features.get("property_type"),
        "Area m²": features.get("area_m2"),
        "Bedrooms": features.get("bedrooms"),
        "Bathrooms": features.get("bathrooms"),
        "Floor": features.get("floor"),
        "Elevator": features.get("has_elevator"),
        "Occupancy Status": features.get("occupancy_status"),
        "Cadastral Ref Token": tokens.get("cadastral_reference_token"),
        "Listing URL Token": tokens.get("listing_url_token"),
        "Acquisition Status": record.get("acquisition_status"),
        "Data Confidence %": round(float(record.get("data_confidence", 0)) * 100, 2),
        "Internal Owner": record.get("internal_owner_alias"),
        "Last Verified": record.get("last_verified"),
        "Notes": None,
    }


def _scenario_row(scenario: Mapping[str, Any]) -> dict[str, Any]:
    assumptions = scenario["assumptions"]
    metrics = scenario["metrics"]
    return {
        "Scenario ID": scenario["scenario_id"],
        "Property ID": scenario["property_id"],
        "Strategy": scenario["strategy"],
        "Scenario Band": scenario["scenario_band"],
        "Purchase Price €": assumptions.get("purchase_price_eur"),
        "Renovation €": assumptions.get("renovation_eur"),
        "Transfer Tax €": assumptions.get("transfer_tax_eur"),
        "Notary & Registry €": assumptions.get("notary_registry_eur"),
        "Agency Fee €": assumptions.get("agency_fee_eur"),
        "Advisory Fee €": assumptions.get("advisory_fee_eur"),
        "Other Costs €": assumptions.get("other_costs_eur"),
        "Financing Ratio %": round(float(assumptions.get("financing_ratio", 0)) * 100, 4),
        "Interest Rate %": round(float(assumptions.get("interest_rate", 0)) * 100, 4),
        "Loan Term Years": assumptions.get("loan_term_years"),
        "Monthly Rent €": assumptions.get("monthly_rent_eur"),
        "Monthly Debt Service €": metrics.get("monthly_debt_service_eur"),
        "Gross Yield %": round(float(metrics.get("gross_yield", 0)) * 100, 4),
        "Net Yield %": round(float(metrics.get("net_yield", 0)) * 100, 4),
        "ROE %": round(float(metrics.get("roe", 0)) * 100, 4),
        "Cash-on-Cash %": round(float(metrics.get("cash_on_cash", 0)) * 100, 4),
        "Monthly Cash Flow €": metrics.get("monthly_cash_flow_eur"),
        "Data Confidence %": round(float(scenario.get("data_confidence", 0)) * 100, 2),
        "Model Version": scenario.get("model_version"),
    }


@dataclass
class SyntheticFixture:
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def apply(self, plan: Mapping[str, Any]) -> None:
        if not plan.get("fixture_writes_permitted") or plan.get("real_writes_permitted"):
            raise SynergyRuntimeError("only fixture writes are permitted")
        for sheet, records in plan.get("rows", {}).items():
            self.rows.setdefault(sheet, []).extend(dict(item) for item in records)

    def count(self, sheet: str) -> int:
        return len(self.rows.get(sheet, []))


class SyntheticSynergyOrchestrator:
    def __init__(self, fixture: SyntheticFixture | None = None) -> None:
        self.fixture = fixture or SyntheticFixture()
        self._processed: dict[str, tuple[str, str]] = {}

    def process(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            self._validate_event(event, payload)
        except SynergyRuntimeError as exc:
            return self._quarantine(event, "invalid_event", [str(exc)])

        key = str(event["idempotency_key"])
        prior = self._processed.get(key)
        if prior:
            if prior[0] != event["payload_digest"]:
                return self._quarantine(event, "idempotency_conflict")
            return self._receipt(event, "replayed", prior[1], False)

        restricted = _restricted_paths(payload)
        if restricted:
            return self._quarantine(event, "restricted_payload", restricted)
        if payload.get("synthetic") is not True:
            return self._quarantine(event, "synthetic_flag_required")

        try:
            plan, artifacts = self._dispatch(str(event["event_type"]), payload)
        except (KeyError, TypeError, ValueError, RealEstateGovernanceError, SynergyRuntimeError) as exc:
            return self._quarantine(event, "handler_rejected", [str(exc)])

        plan = {
            **plan,
            "event_id": event["event_id"],
            "correlation_id": event["correlation_id"],
            "synthetic_only": True,
            "fixture_writes_permitted": True,
            "real_writes_permitted": False,
            "external_communication_permitted": False,
            "transaction_action_permitted": False,
        }
        plan_digest = canonical_digest(plan)
        plan["plan_digest"] = plan_digest
        self.fixture.apply(plan)
        self._processed[key] = (str(event["payload_digest"]), plan_digest)
        receipt = self._receipt(event, "processed", plan_digest, True)
        receipt.update({"plan": plan, "artifacts": artifacts})
        return receipt

    @staticmethod
    def _validate_event(event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        required = {
            "event_id", "correlation_id", "event_type", "producer", "consumer",
            "entity_type", "entity_id", "occurred_at", "idempotency_key",
            "payload_digest", "human_gate_required",
        }
        missing = sorted(required - set(event))
        if missing:
            raise SynergyRuntimeError(f"missing fields: {missing}")
        if event["event_type"] not in SUPPORTED_EVENTS:
            raise SynergyRuntimeError("event handler is not enabled in Stage 008r")
        if not str(event["event_id"]).startswith("EVT-SYN-"):
            raise SynergyRuntimeError("synthetic event ID required")
        if not str(event["idempotency_key"]).startswith("SYN-"):
            raise SynergyRuntimeError("synthetic idempotency key required")
        if event["payload_digest"] != canonical_digest(payload):
            raise SynergyRuntimeError("payload digest mismatch")

    def _dispatch(self, event_type: str, payload: Mapping[str, Any]):
        return {
            "realestate.property_case.created": self._property,
            "realestate.visit.submitted": self._visit,
            "realestate.report.generated": self._report_generated,
            "realestate.report.approved": self._report_approved,
            "realestate.match.proposed": self._match,
        }[event_type](payload)

    @staticmethod
    def _property(payload: Mapping[str, Any]):
        source_profile = str(payload["source_profile"])
        rights = str(payload["rights_status"])
        row = dict(payload["row"])
        if not source_profile.startswith("SYNTHETIC_"):
            raise SynergyRuntimeError("synthetic source profile required")
        if rights not in ALLOWED_RIGHTS:
            raise SynergyRuntimeError("approved source rights required")
        if detect_sensitive_fields(row):
            raise SynergyRuntimeError("A30 detected sensitive fields")
        result = normalise_property_row(
            row,
            source_profile=source_profile,
            source_row=int(payload["source_row"]),
            rights_status=rights,
        )
        receipt = result["import_receipt"]
        rows = {
            "Properties": [_property_row(result["property"])],
            "Property Scenarios": [_scenario_row(item) for item in result["scenarios"]],
            "RE Import Staging": [{
                "Import ID": "IMP-SYN-" + receipt["source_record_digest"][:16].upper(),
                "Source Profile": source_profile,
                "Source Row": int(payload["source_row"]),
                "External Code": receipt["external_code"],
                "Source Record Digest": receipt["source_record_digest"],
                "Rights Status": rights,
                "PII Detected": False,
                "Restricted Fields Detected": False,
                "Import Status": "approved",
                "Imported Property ID": receipt["property_id"],
                "Imported Scenario IDs": ",".join(receipt["scenario_ids"]),
                "Notes": "Synthetic fixture only.",
            }],
        }
        return {"plan_type": "property_case", "rows": rows}, result

    @staticmethod
    def _match(payload: Mapping[str, Any]):
        merge_plan = build_crm_merge_plan(
            mandate_payload=payload["mandate_payload"],
            property_record=payload["property_record"],
            scenarios=payload["scenarios"],
        )
        if merge_plan["writes_permitted"] or merge_plan["external_communication_permitted"]:
            raise SynergyRuntimeError("A30 crossed the no-action boundary")
        rows = []
        for match in merge_plan["real_estate_objects"]["matches"]:
            scores = match["scores"]
            rows.append({
                "Match ID": match["match_id"],
                "Mandate ID": match["mandate_id"],
                "Property ID": match["property_id"],
                "Scenario ID": match["scenario_id"],
                "Match Score %": round(scores["overall"] * 100, 2),
                "Budget Fit %": round(scores["budget"] * 100, 2),
                "Geography Fit %": round(scores["geography"] * 100, 2),
                "Strategy Fit %": round(scores["strategy"] * 100, 2),
                "Return Fit %": round(scores["return"] * 100, 2),
                "Risk Fit %": round(scores["risk"] * 100, 2),
                "Data Confidence %": round(scores["confidence"] * 100, 2),
                "Status": "review_required",
                "Human Approved": False,
            })
        return {"plan_type": "match_proposal", "rows": {"Property Matches": rows}}, merge_plan

    @staticmethod
    def _visit(payload: Mapping[str, Any]):
        visit = dict(payload["visit"])
        evidence = [dict(item) for item in visit.get("evidence_items", [])]
        for item in evidence:
            if item.get("rights_status") not in ALLOWED_RIGHTS:
                raise SynergyRuntimeError("approved evidence rights required")
            if not str(item.get("restricted_pointer", "")).startswith("restricted://synthetic/"):
                raise SynergyRuntimeError("synthetic restricted pointer required")
        visit_row = {
            "Visit ID": visit["visit_id"],
            "Property ID": visit["property_id"],
            "Visit Date": visit.get("visited_at"),
            "Visit Status": visit["visit_status"],
            "Access Status": visit.get("access_status", "unknown"),
            "ITE Status": visit.get("ite_status", "unknown"),
            "Habitability Status": visit.get("habitability_status", "unknown"),
            "Follow-up Required": bool(visit.get("follow_up_required", False)),
            "Internal Owner": "SYNTHETIC-GATE",
        }
        evidence_rows = [{
            "Evidence ID": item["evidence_id"],
            "Property ID": visit["property_id"],
            "Visit ID": visit["visit_id"],
            "Category": item["category"],
            "Rights Status": item["rights_status"],
            "Validation Status": item["validation_status"],
            "Restricted Token": item["restricted_pointer"],
        } for item in evidence]
        return {"plan_type": "visit", "rows": {"Visits": [visit_row], "Evidence & Media": evidence_rows}}, visit

    @staticmethod
    def _report_generated(payload: Mapping[str, Any]):
        report = dict(payload["report"])
        if report.get("share_status") not in (None, "not_shareable"):
            raise SynergyRuntimeError("generated report cannot already be shareable")
        row = SyntheticSynergyOrchestrator._report_row(report, "not_shareable")
        return {"plan_type": "report_generated", "rows": {"Reports & Approvals": [row]}}, report

    @staticmethod
    def _report_approved(payload: Mapping[str, Any]):
        report = dict(payload["report"])
        approvals = report["approvals"]
        roles = ("financial", "evidence", "legal", "commercial")
        if any(approvals.get(role, {}).get("status") != "approved" for role in roles):
            raise SynergyRuntimeError("four approved report roles required")
        reviewers = [str(approvals[role].get("reviewer_token", "")) for role in roles]
        if any(not token.startswith("restricted://synthetic/reviewer/") for token in reviewers):
            raise SynergyRuntimeError("synthetic reviewer tokens required")
        if len(set(reviewers)) != 4:
            raise SynergyRuntimeError("report approval roles must be separated")
        row = SyntheticSynergyOrchestrator._report_row(report, "approved")
        return {"plan_type": "report_approved", "rows": {"Reports & Approvals": [row]}}, report

    @staticmethod
    def _report_row(report: Mapping[str, Any], share_status: str) -> dict[str, Any]:
        approvals = report.get("approvals", {})
        return {
            "Report ID": report["report_id"],
            "Property ID": report["property_id"],
            "Scenario IDs": ",".join(report.get("scenario_ids", [])),
            "Report Type": report["report_type"],
            "Template Version": report["template_version"],
            "Calculation Version": report["calculation_version"],
            "PPTX URL": report.get("pptx_pointer"),
            "PDF URL": report.get("pdf_pointer"),
            "Generation Status": report.get("generation_status", "generated"),
            "Financial Approval": approvals.get("financial", {}).get("status", "pending"),
            "Evidence Approval": approvals.get("evidence", {}).get("status", "pending"),
            "Legal Review Status": approvals.get("legal", {}).get("status", "pending"),
            "Commercial Approval": approvals.get("commercial", {}).get("status", "pending"),
            "Share Status": share_status,
        }

    @staticmethod
    def _receipt(event: Mapping[str, Any], status: str, plan_digest: str, mutated: bool):
        return {
            "event_id": event["event_id"],
            "status": status,
            "idempotency_key": event["idempotency_key"],
            "plan_digest": plan_digest,
            "fixture_mutated": mutated,
            "real_writes_permitted": False,
            "external_communication_permitted": False,
            "transaction_action_permitted": False,
        }

    @staticmethod
    def _quarantine(event: Mapping[str, Any], reason: str, details: list[str] | None = None):
        return {
            "event_id": event.get("event_id"),
            "status": "quarantined",
            "reason": reason,
            "details": details or [],
            "fixture_mutated": False,
            "real_writes_permitted": False,
            "external_communication_permitted": False,
            "transaction_action_permitted": False,
        }
