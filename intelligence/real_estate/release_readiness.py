"""Deterministic release-readiness scoring for the real-estate architecture.

The score is evidence-based and never overrides release gates. A high percentage
with a critical blocker is still reported as not releasable.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


class ReleaseReadinessError(ValueError):
    pass


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseReadinessError("JSON root must be an object")
    return value


def _evidence_record(evidence: Mapping[str, Any], criterion_id: str) -> Mapping[str, Any]:
    records = evidence.get("evidence")
    if not isinstance(records, Mapping):
        raise ReleaseReadinessError("evidence document must contain an evidence object")
    record = records.get(criterion_id)
    if not isinstance(record, Mapping):
        return {
            "status": "not_started",
            "note": "Evidence record is missing.",
            "next_action": f"Provide evidence for {criterion_id}.",
            "evidence": [],
        }
    return record


def evaluate_mode(
    *,
    policy: Mapping[str, Any],
    evidence: Mapping[str, Any],
    mode_id: str,
) -> dict[str, Any]:
    modes = policy.get("modes")
    if not isinstance(modes, Mapping) or mode_id not in modes:
        raise ReleaseReadinessError(f"unknown readiness mode: {mode_id}")
    mode = modes[mode_id]
    status_values = policy.get("status_values")
    if not isinstance(status_values, Mapping):
        raise ReleaseReadinessError("policy status_values missing")
    criteria = mode.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ReleaseReadinessError(f"mode has no criteria: {mode_id}")

    total_weight = sum(float(item["weight"]) for item in criteria)
    if round(total_weight, 8) != 100:
        raise ReleaseReadinessError(f"mode weights must total 100: {mode_id}")

    weighted_score = 0.0
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for criterion in criteria:
        criterion_id = str(criterion["id"])
        record = _evidence_record(evidence, criterion_id)
        status = str(record.get("status") or "not_started")
        if status not in status_values:
            raise ReleaseReadinessError(
                f"unsupported status for {criterion_id}: {status}"
            )
        value = float(status_values[status])
        weight = float(criterion["weight"])
        contribution = weight * value
        weighted_score += contribution
        result = {
            "id": criterion_id,
            "weight": weight,
            "critical": bool(criterion.get("critical")),
            "status": status,
            "completion": round(value * 100, 1),
            "contribution": round(contribution, 2),
            "note": str(record.get("note") or ""),
            "evidence": list(record.get("evidence") or []),
            "next_action": str(record.get("next_action") or ""),
        }
        results.append(result)
        if result["critical"] and status in {"blocked", "not_started"}:
            blockers.append(result)
        elif status in {"implemented_unvalidated", "partial", "not_started"}:
            warnings.append(result)

    score = round(weighted_score, 1)
    threshold = float(mode.get("decision_threshold", 100))
    if blockers:
        decision = "not_ready"
    elif score >= threshold:
        if mode_id == "architecture_package":
            decision = "ready_for_release_review"
        elif mode_id == "controlled_operator_use":
            decision = "controlled_use_ready"
        else:
            decision = "release_ready"
    else:
        decision = "not_ready"

    ranked_actions = sorted(
        [item for item in results if item["completion"] < 100 and item["next_action"]],
        key=lambda item: (
            0 if item in blockers else 1,
            -(item["weight"] * (100 - item["completion"])),
            item["id"],
        ),
    )
    report = {
        "schema_version": 1,
        "release": evidence.get("release") or policy.get("release"),
        "as_of": evidence.get("as_of"),
        "mode": mode_id,
        "label": mode.get("label", mode_id),
        "score_percent": score,
        "decision_threshold_percent": threshold,
        "decision": decision,
        "critical_blockers": [item["id"] for item in blockers],
        "warning_criteria": [item["id"] for item in warnings],
        "criteria": results,
        "next_actions": [item["next_action"] for item in ranked_actions[:10]],
        "score_is_not_release_authority": True,
    }
    report["report_digest"] = canonical_digest(report)
    return report


def evaluate_all_modes(
    *,
    policy: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    modes = policy.get("modes")
    if not isinstance(modes, Mapping):
        raise ReleaseReadinessError("policy modes missing")
    results = {
        mode_id: evaluate_mode(policy=policy, evidence=evidence, mode_id=mode_id)
        for mode_id in modes
    }
    summary = {
        "schema_version": 1,
        "release": evidence.get("release") or policy.get("release"),
        "as_of": evidence.get("as_of"),
        "modes": results,
    }
    summary["summary_digest"] = canonical_digest(summary)
    return summary


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        f"# Release readiness — {summary.get('release', 'unknown release')}",
        "",
        f"As of: {summary.get('as_of') or 'unspecified'}",
        "",
        "A percentage is an evidence-weighted progress indicator, not permission to release.",
        "",
    ]
    modes = summary.get("modes") or {}
    for mode_id, report in modes.items():
        lines.extend(
            [
                f"## {report['label']}",
                "",
                f"**{report['score_percent']}% — {report['decision']}**",
                "",
            ]
        )
        if report["critical_blockers"]:
            lines.append(
                "Critical blockers: " + ", ".join(report["critical_blockers"])
            )
            lines.append("")
        lines.append("| Criterion | Weight | Status | Completion |")
        lines.append("|---|---:|---|---:|")
        for item in report["criteria"]:
            lines.append(
                f"| {item['id']} | {item['weight']:.0f}% | {item['status']} | {item['completion']:.1f}% |"
            )
        lines.extend(["", "Next actions:", ""])
        if report["next_actions"]:
            lines.extend(f"1. {action}" for action in report["next_actions"])
        else:
            lines.append("1. No incomplete criteria recorded.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
