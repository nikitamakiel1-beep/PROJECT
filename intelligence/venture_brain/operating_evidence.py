from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Any, Iterable

from intelligence.venture_brain.management_digest import build_weekly_management_digest


FORBIDDEN_KEYS = {
    "name",
    "contact_name",
    "company_name",
    "email",
    "phone",
    "telephone",
    "address",
    "website",
    "url",
    "recording_url",
    "transcript",
    "raw_notes",
    "password",
    "secret",
    "token",
    "api_key",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{7,}\d)(?!\d)")

CRM_TABLES = ("leads", "opportunities", "activities", "delivery_jobs", "automations")
INTERVIEW_TARGET_MIX = {
    "local_sme": 5,
    "referral_professional": 2,
    "business_support": 1,
    "specialist_b2b_leader": 2,
}


def _iso_day(value: str) -> date:
    try:
        return datetime.fromisoformat(value[:10]).date()
    except (TypeError, ValueError) as exc:
        raise ValueError("date values must use ISO YYYY-MM-DD") from exc


def _walk(value: Any, *, path: str = "snapshot") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            yield child, item
            yield from _walk(item, path=child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, path=f"{path}[{index}]")


def validate_public_safe_snapshot(snapshot: dict[str, Any]) -> None:
    """Reject direct identifiers, credentials and unbounded private text.

    The evidence adapter is intentionally narrower than the CRM. Connector-side
    extraction must pseudonymise or aggregate records before this boundary.
    """
    for path, value in _walk(snapshot):
        key = path.rsplit(".", 1)[-1].split("[", 1)[0].lower()
        if key in FORBIDDEN_KEYS:
            raise ValueError(f"forbidden field at {path}")
        if not isinstance(value, str):
            continue
        if EMAIL_RE.search(value):
            raise ValueError(f"email-like value at {path}")
        if URL_RE.search(value):
            raise ValueError(f"URL-like value at {path}")
        if PHONE_RE.search(value) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(f"phone-like value at {path}")
        if len(value) > 500:
            raise ValueError(f"unbounded text at {path}")


def build_interview_execution_queue() -> list[dict[str, Any]]:
    profiles = [
        ("local_sme", "SME with an existing website and visible international potential", "Barcelona area", "warm introduction or permission conversation"),
        ("local_sme", "SME with an existing website and visible international potential", "Barcelona area", "warm introduction or permission conversation"),
        ("local_sme", "SME with a multilingual or export-facing website", "Barcelona area", "local network or telephone permission request"),
        ("local_sme", "specialist services SME with lead-follow-up friction", "Barcelona area", "warm introduction or in-person permission"),
        ("local_sme", "industrial or design SME with international sales materials", "Barcelona area", "local network or permission conversation"),
        ("referral_professional", "accountant, gestor, web professional or consultant", "Catalonia", "warm professional introduction"),
        ("referral_professional", "accountant, gestor, web professional or consultant", "Catalonia", "warm professional introduction"),
        ("business_support", "chamber, association, PAE or enterprise-support contact", "Barcelona or Catalonia", "official enquiry or human telephone request"),
        ("specialist_b2b_leader", "founder or commercial manager in specialist B2B", "Spain", "warm introduction or permission conversation"),
        ("specialist_b2b_leader", "founder or commercial manager in specialist B2B", "Spain", "warm introduction or permission conversation"),
    ]
    queue: list[dict[str, Any]] = []
    for index, (segment, profile, geography, route) in enumerate(profiles, start=1):
        queue.append({
            "queue_slot": f"Q-{index:03d}",
            "target_segment": segment,
            "target_profile": profile,
            "geographic_scope": geography,
            "preferred_human_route": route,
            "contact_basis_required": True,
            "status": "unassigned",
            "human_outreach_required": True,
            "crm_seeded": False,
        })
    return queue


def _assert_source_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    expected = dict(snapshot.get("source_assertions", {}))
    actual = {table: len(list(snapshot.get(table, []))) for table in CRM_TABLES}
    actual["interviews"] = len(list(snapshot.get("interviews", [])))
    actual["linear_issues"] = len(list(snapshot.get("linear_issues", [])))
    for key, expected_count in expected.items():
        if key not in actual:
            raise ValueError(f"unsupported source assertion: {key}")
        if int(expected_count) != actual[key]:
            raise ValueError(f"source count mismatch for {key}: expected {expected_count}, observed {actual[key]}")
    return actual


def _linear_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        raw = str(row.get("status", "unknown")).strip().lower().replace(" ", "_")
        if raw in {"completed", "done"}:
            raw = "done"
        elif raw in {"started", "in_progress", "in-progress"}:
            raw = "in_progress"
        elif raw in {"unstarted", "todo", "backlog"}:
            raw = "todo"
        counts[raw] += 1
    counts["open"] = sum(count for state, count in counts.items() if state not in {"done", "cancelled", "canceled", "open"})
    return dict(sorted(counts.items()))


def _quality_warnings(source_counts: dict[str, int]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    business_rows = source_counts["leads"] + source_counts["opportunities"] + source_counts["activities"]
    if business_rows == 0:
        warnings.append({
            "code": "CRM_ZERO_STATE",
            "severity": "high",
            "message": "CRM contains no lead, opportunity or activity records.",
            "human_decision_required": True,
        })
    if source_counts["automations"] == 0:
        warnings.append({
            "code": "NO_AUTOMATION_EVIDENCE",
            "severity": "medium",
            "message": "Automation Log contains no executed workflow evidence.",
            "human_decision_required": True,
        })
    if source_counts["interviews"] == 0:
        warnings.append({
            "code": "NO_INTERVIEW_EVIDENCE",
            "severity": "high",
            "message": "Customer-discovery evidence remains at 0 completed interviews.",
            "human_decision_required": True,
        })
    return warnings


def build_operating_evidence_receipt(snapshot: dict[str, Any], *, as_of: str) -> dict[str, Any]:
    validate_public_safe_snapshot(snapshot)
    today = _iso_day(as_of)
    source_counts = _assert_source_counts(snapshot)
    digest_input = {key: deepcopy(snapshot.get(key, [])) for key in (*CRM_TABLES, "interviews", "linear_issues")}
    digest = build_weekly_management_digest(digest_input, as_of=today.isoformat())

    programme_gates = []
    for gate in snapshot.get("programme_gates", []):
        if str(gate.get("status", "")).lower() in {"done", "completed", "cancelled", "canceled"}:
            continue
        programme_gates.append({
            "issue_id": str(gate.get("issue_id", "UNSPECIFIED")),
            "priority": str(gate.get("priority", "high")),
            "owner_route": str(gate.get("owner_route", "Founder → Programme")),
            "reason": str(gate.get("reason", "open programme gate requires a human decision")),
            "due_date": gate.get("due_date"),
            "human_decision_required": True,
        })
    programme_gates.sort(key=lambda item: (item["priority"], item["issue_id"]))

    queue = build_interview_execution_queue()
    segment_counts = Counter(item["target_segment"] for item in queue)
    if dict(segment_counts) != INTERVIEW_TARGET_MIX:
        raise AssertionError("interview queue mix drift")

    receipt = {
        "schema_version": 1,
        "as_of": today.isoformat(),
        "source_counts": source_counts,
        "linear_status_counts": _linear_status_counts(list(snapshot.get("linear_issues", []))),
        "management_digest": digest,
        "quality_warnings": _quality_warnings(source_counts),
        "programme_gates": programme_gates,
        "interview_execution": {
            "target": 10,
            "assigned": sum(1 for item in queue if item["status"] != "unassigned"),
            "completed": source_counts["interviews"],
            "segment_mix": dict(sorted(segment_counts.items())),
            "queue": queue,
        },
        "controls": {
            "public_safe": True,
            "human_review_required": True,
            "external_message_sent": False,
            "crm_mutated": False,
            "linear_mutated": False,
            "provider_activated": False,
        },
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    receipt["receipt_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return receipt


def verify_operating_evidence_receipt(receipt: dict[str, Any]) -> bool:
    supplied = str(receipt.get("receipt_sha256", ""))
    unsigned = deepcopy(receipt)
    unsigned.pop("receipt_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return supplied == sha256(canonical.encode("utf-8")).hexdigest()
