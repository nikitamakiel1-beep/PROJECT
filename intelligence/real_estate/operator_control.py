"""Local case-control manifest, readiness score and next-action guidance."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Any, Mapping


class OperatorControlError(ValueError):
    pass


ACTION_CATALOGUE = {
    "source_intake": {
        "automatic": "Create the source record, project code and restricted pointers.",
        "manual": "Paste the listing link or enter the confidential opportunity, then confirm source and media rights.",
    },
    "property_facts": {
        "automatic": "Normalise supported listing fields and identify missing evidence.",
        "manual": "Confirm the address, occupancy, expenses, legal documents and any seller-declared facts.",
    },
    "financial_underwriting": {
        "automatic": "Build the USANDO update plan, select B3, recalculate and collect scenario outputs.",
        "manual": "Review transfer tax, financing, rents, renovation, expenses and approve each viable strategy.",
    },
    "zone_evidence": {
        "automatic": "Generate and validate the La Vanguardia capture plan and evidence bundle.",
        "manual": "Search the exact address, confirm the census section, record the visible value and legend, and save the screenshot.",
    },
    "media": {
        "automatic": "Hash, classify, naturally order and stage authorised property and zone media.",
        "manual": "Confirm rights, reject sensitive or poor images, and approve any AI-cleaned property photo.",
    },
    "report_generation": {
        "automatic": "Bind inputs, run AutoPPTX locally, export PDF and verify output hashes.",
        "manual": "Keep Excel and the target PPTX closed, then inspect every slide and the final PDF.",
    },
    "report_approvals": {
        "automatic": "Validate distinct financial, evidence, legal and commercial approval tokens.",
        "manual": "Obtain four separate approvals after the report checklist is complete.",
    },
    "due_diligence": {
        "automatic": "Track missing legal, technical, occupancy and building evidence.",
        "manual": "Complete the visit, registry, charges, ITE/habitability, occupancy and community checks.",
    },
    "client_decision": {
        "automatic": "Bind the client decision to the current property and calculation snapshot.",
        "manual": "Obtain explicit written approval with maximum price, financing and reservation terms.",
    },
}


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def _validate_project_code(project_code: str) -> str:
    code = str(project_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_\-]{6,80}", code):
        raise OperatorControlError("invalid project code")
    return code


def build_case_control(
    *,
    project_code: str,
    title: str,
    source_kind: str,
    created_on: str,
    component_ids: list[str],
) -> dict[str, Any]:
    code = _validate_project_code(project_code)
    if source_kind not in {"listing_link", "confidential", "off_market", "bank_or_fund", "manual"}:
        raise OperatorControlError("unsupported source kind")
    if not title.strip():
        raise OperatorControlError("case title required")
    unknown = [item for item in component_ids if item not in ACTION_CATALOGUE]
    if unknown:
        raise OperatorControlError(f"unknown case components: {unknown}")
    control = {
        "schema_version": 1,
        "control_type": "real_estate_operator_case",
        "project_code": code,
        "title": title.strip(),
        "source_kind": source_kind,
        "created_on": created_on,
        "updated_on": created_on,
        "components": {
            component_id: {
                "status": "not_started",
                "evidence": [],
                "notes": [],
                "actor_token": None,
                "updated_on": None,
            }
            for component_id in component_ids
        },
        "external_actions_permitted": False,
        "purchase_execution_permitted": False,
    }
    control["control_digest"] = canonical_digest(control)
    return control


def update_component(
    *,
    control: Mapping[str, Any],
    component_id: str,
    status: str,
    updated_on: str,
    actor_token: str,
    evidence_pointer: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    result = deepcopy(dict(control))
    components = result.get("components")
    if not isinstance(components, dict) or component_id not in components:
        raise OperatorControlError(f"unknown component: {component_id}")
    if status not in {
        "not_started",
        "in_progress",
        "ready_for_review",
        "approved",
        "blocked",
        "not_applicable",
    }:
        raise OperatorControlError("unsupported component status")
    if not actor_token.startswith("restricted://"):
        raise OperatorControlError("restricted actor token required")
    if evidence_pointer is not None and not evidence_pointer.startswith("restricted://"):
        raise OperatorControlError("evidence pointer must remain restricted")

    record = components[component_id]
    record["status"] = status
    record["actor_token"] = actor_token
    record["updated_on"] = updated_on
    if evidence_pointer and evidence_pointer not in record["evidence"]:
        record["evidence"].append(evidence_pointer)
        record["evidence"].sort()
    if note and note.strip() and note.strip() not in record["notes"]:
        record["notes"].append(note.strip())
    result["updated_on"] = updated_on
    result.pop("control_digest", None)
    result["control_digest"] = canonical_digest(result)
    return result


def _gate_state(statuses: Mapping[str, str], required: list[str]) -> dict[str, Any]:
    missing = [item for item in required if statuses.get(item) != "approved"]
    blocked = [item for item in required if statuses.get(item) == "blocked"]
    return {
        "ready": not missing,
        "missing": missing,
        "blocked": blocked,
    }


def evaluate_case(
    *,
    policy: Mapping[str, Any],
    control: Mapping[str, Any],
) -> dict[str, Any]:
    if control.get("control_type") != "real_estate_operator_case":
        raise OperatorControlError("invalid case control document")
    definitions = policy.get("case_components")
    values = policy.get("case_status_values")
    gates = policy.get("case_gates")
    if not isinstance(definitions, list) or not isinstance(values, Mapping) or not isinstance(gates, Mapping):
        raise OperatorControlError("case policy is incomplete")
    components = control.get("components")
    if not isinstance(components, Mapping):
        raise OperatorControlError("case components missing")

    scored_weight = 0.0
    achieved = 0.0
    results: list[dict[str, Any]] = []
    statuses: dict[str, str] = {}
    for definition in definitions:
        component_id = str(definition["id"])
        record = components.get(component_id)
        if not isinstance(record, Mapping):
            raise OperatorControlError(f"case component missing: {component_id}")
        status = str(record.get("status") or "not_started")
        if status not in values:
            raise OperatorControlError(f"invalid status for {component_id}: {status}")
        statuses[component_id] = status
        weight = float(definition["weight"])
        value = values[status]
        if value is not None:
            scored_weight += weight
            achieved += weight * float(value)
        results.append(
            {
                "id": component_id,
                "label": definition.get("label", component_id),
                "weight": weight,
                "status": status,
                "completion": None if value is None else round(float(value) * 100, 1),
                "evidence_count": len(record.get("evidence") or []),
                "automatic_action": ACTION_CATALOGUE[component_id]["automatic"],
                "manual_action": ACTION_CATALOGUE[component_id]["manual"],
            }
        )
    score = 0.0 if scored_weight == 0 else round(achieved / scored_weight * 100, 1)
    gate_results = {
        gate_id: _gate_state(statuses, list(required))
        for gate_id, required in gates.items()
    }
    next_components = [
        item
        for item in results
        if item["status"] not in {"approved", "not_applicable"}
    ]
    next_components.sort(
        key=lambda item: (
            0 if item["status"] == "blocked" else 1,
            -item["weight"],
            item["id"],
        )
    )
    summary = {
        "schema_version": 1,
        "project_code": control["project_code"],
        "title": control["title"],
        "score_percent": score,
        "components": results,
        "gates": gate_results,
        "blocked_components": [item["id"] for item in results if item["status"] == "blocked"],
        "next_actions": [
            {
                "component": item["id"],
                "manual": item["manual_action"],
                "automatic": item["automatic_action"],
            }
            for item in next_components[:5]
        ],
        "external_actions_permitted": False,
        "purchase_execution_permitted": False,
    }
    summary["summary_digest"] = canonical_digest(summary)
    return summary


def render_case_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        f"# Case status — {summary['project_code']}",
        "",
        f"**Readiness: {summary['score_percent']}%**",
        "",
        "| Component | Weight | Status | Completion |",
        "|---|---:|---|---:|",
    ]
    for item in summary["components"]:
        completion = "N/A" if item["completion"] is None else f"{item['completion']:.1f}%"
        lines.append(
            f"| {item['label']} | {item['weight']:.0f}% | {item['status']} | {completion} |"
        )
    lines.extend(["", "## Gates", ""])
    for gate, state in summary["gates"].items():
        lines.append(f"- {gate}: {'READY' if state['ready'] else 'NOT READY'}")
        if state["missing"]:
            lines.append("  Missing: " + ", ".join(state["missing"]))
    lines.extend(["", "## Next actions", ""])
    if summary["next_actions"]:
        for action in summary["next_actions"]:
            lines.append(f"1. **{action['component']} — manual:** {action['manual']}")
            lines.append(f"   Automation: {action['automatic']}")
    else:
        lines.append("1. No incomplete components recorded.")
    return "\n".join(lines).rstrip() + "\n"
