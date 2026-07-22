from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any

TERMINAL_LEAD_STATES = {"closed", "lost", "converted", "disqualified"}
TERMINAL_OPPORTUNITY_STAGES = {"won", "lost", "closed"}


def _day(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value[:10]).date()


def _is_overdue(value: str | None, as_of: date) -> bool:
    parsed = _day(value)
    return parsed is not None and parsed < as_of


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _probability(value: Any) -> float:
    try:
        probability = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if 0 <= probability <= 1:
        probability *= 100
    return min(100.0, max(0.0, probability))


def build_weekly_management_digest(snapshot: dict[str, Any], *, as_of: str) -> dict[str, Any]:
    """Build an aggregate-only, deterministic management digest.

    The function never sends messages, writes CRM stages, approves proposals or
    infers collected cash from opportunity state. Input rows must be pseudonymous
    or aggregate-safe before they reach this boundary.
    """
    today = _day(as_of)
    if today is None:
        raise ValueError("as_of must be an ISO date")

    leads = list(snapshot.get("leads", []))
    opportunities = list(snapshot.get("opportunities", []))
    activities = list(snapshot.get("activities", []))
    delivery_jobs = list(snapshot.get("delivery_jobs", []))
    automations = list(snapshot.get("automations", []))
    interviews = list(snapshot.get("interviews", []))
    linear_issues = list(snapshot.get("linear_issues", []))

    open_leads = [row for row in leads if str(row.get("status", "")).lower() not in TERMINAL_LEAD_STATES]
    overdue_leads = [row for row in open_leads if _is_overdue(row.get("next_action_date"), today)]
    qualified_leads = [row for row in leads if str(row.get("status", "")).lower() in {"qualified", "converted"}]

    open_opportunities = [
        row for row in opportunities
        if str(row.get("stage", "")).lower() not in TERMINAL_OPPORTUNITY_STAGES
    ]
    overdue_opportunities = [row for row in open_opportunities if _is_overdue(row.get("next_step_date"), today)]
    open_pipeline = round(sum(_money(row.get("value_eur")) for row in open_opportunities), 2)
    weighted_pipeline = round(
        sum(_money(row.get("value_eur")) * _probability(row.get("probability_pct")) / 100 for row in open_opportunities),
        2,
    )
    won_revenue = round(
        sum(_money(row.get("value_eur")) for row in opportunities if str(row.get("stage", "")).lower() == "won"),
        2,
    )
    collected_cash = round(
        sum(_money(row.get("collected_eur")) for row in opportunities if bool(row.get("payment_confirmed"))),
        2,
    )

    completed_activities = [row for row in activities if str(row.get("status", "")).lower() == "completed"]
    delivery_hours = round(sum(_money(row.get("actual_hours")) for row in delivery_jobs), 2)
    estimated_delivery_hours = round(sum(_money(row.get("estimated_hours")) for row in delivery_jobs), 2)
    capacity_ratio = round(delivery_hours / estimated_delivery_hours, 3) if estimated_delivery_hours else 0.0
    overdue_deliveries = [
        row for row in delivery_jobs
        if str(row.get("status", "")).lower() not in {"complete", "closed", "cancelled"}
        and _is_overdue(row.get("due_date"), today)
    ]

    failed_automations = [row for row in automations if str(row.get("status", "")).lower() in {"failed", "error"}]
    overdue_linear = [
        row for row in linear_issues
        if str(row.get("status", "")).lower() not in {"done", "completed", "cancelled"}
        and _is_overdue(row.get("due_date"), today)
    ]

    problem_counts: Counter[str] = Counter()
    segment_counts: Counter[str] = Counter()
    referral_signals = 0
    willingness_values: list[float] = []
    for interview in interviews:
        segment = str(interview.get("segment", "unclassified")).strip() or "unclassified"
        segment_counts[segment] += 1
        for code in interview.get("problem_codes", []):
            problem_counts[str(code)] += 1
        if interview.get("referral_signal") is True:
            referral_signals += 1
        willingness = _money(interview.get("willingness_to_pay_eur"))
        if willingness > 0:
            willingness_values.append(willingness)

    actions: list[dict[str, Any]] = []
    def action(priority: str, owner_route: str, reason: str, count: int) -> None:
        if count:
            actions.append({
                "priority": priority,
                "owner_route": owner_route,
                "reason": reason,
                "count": count,
                "human_decision_required": True,
            })

    action("critical", "Founder → Custodian", "failed automations require evidence and rollback review", len(failed_automations))
    action("high", "Founder → Sales", "overdue lead follow-ups require a human decision", len(overdue_leads))
    action("high", "Founder → Sales", "overdue opportunity next steps require a human decision", len(overdue_opportunities))
    action("high", "Founder → Delivery", "overdue delivery jobs require a recovery plan", len(overdue_deliveries))
    action("high", "Founder → Programme", "overdue Linear issues require reprioritisation", len(overdue_linear))
    if len(interviews) < 10:
        action("medium", "Founder → Research", "customer-discovery target is not yet complete", 10 - len(interviews))

    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda item: (priority_order[item["priority"]], item["owner_route"], item["reason"]))

    digest = {
        "schema_version": 1,
        "period": {"as_of": today.isoformat()},
        "metrics": {
            "leads_total": len(leads),
            "leads_open": len(open_leads),
            "leads_qualified": len(qualified_leads),
            "leads_overdue": len(overdue_leads),
            "opportunities_open": len(open_opportunities),
            "opportunities_overdue": len(overdue_opportunities),
            "open_pipeline_eur": open_pipeline,
            "weighted_pipeline_eur": weighted_pipeline,
            "won_revenue_eur": won_revenue,
            "collected_cash_eur": collected_cash,
            "activities_completed": len(completed_activities),
            "delivery_hours_actual": delivery_hours,
            "delivery_hours_estimated": estimated_delivery_hours,
            "delivery_capacity_ratio": capacity_ratio,
            "delivery_jobs_overdue": len(overdue_deliveries),
            "automations_failed": len(failed_automations),
            "linear_issues_overdue": len(overdue_linear),
            "interviews_completed": len(interviews),
            "interview_referral_signals": referral_signals,
            "median_willingness_to_pay_eur": sorted(willingness_values)[len(willingness_values) // 2] if willingness_values else 0.0,
        },
        "research": {
            "top_problem_codes": problem_counts.most_common(5),
            "segments": sorted(segment_counts.items()),
        },
        "action_queue": actions,
        "controls": {
            "aggregate_only": True,
            "external_message_sent": False,
            "crm_stage_mutated": False,
            "proposal_or_invoice_approved": False,
            "human_review_required": True,
        },
    }
    canonical = json.dumps(digest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest["digest_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return digest
