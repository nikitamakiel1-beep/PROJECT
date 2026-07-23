"""Media staging and end-to-end AutoPPTX pipeline plans for RC2."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

from .autopptx_workspace import AutoPPTXPipelineError, natural_key, validate_project_code


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def _copy_ordered(
    files: Iterable[str | Path],
    destination: Path,
    prefix: str,
) -> list[dict[str, Any]]:
    source_paths = [Path(item) for item in files]
    for path in source_paths:
        if not path.is_absolute() or not path.is_file() or path.stat().st_size == 0:
            raise AutoPPTXPipelineError(f"invalid media file: {path}")
    copied: list[dict[str, Any]] = []
    for index, source in enumerate(
        sorted(source_paths, key=lambda item: natural_key(item.name)),
        start=1,
    ):
        suffix = source.suffix.casefold() or ".jpg"
        target = destination / f"{index:02d}_{prefix}{suffix}"
        shutil.copy2(source, target)
        copied.append({"source": str(source), "target": str(target)})
    return copied


def stage_autopptx_media(
    *,
    workspace: Mapping[str, str],
    property_media: list[Mapping[str, Any]],
    zone_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if zone_evidence.get("evidence_type") != "lavanguardia_census_income_zone":
        raise AutoPPTXPipelineError("verified La Vanguardia zone evidence required")
    if zone_evidence.get("manual_confirmation") is not True:
        raise AutoPPTXPipelineError("zone evidence is not manually confirmed")

    piso_destination = Path(workspace["autopptx_piso"])
    zona_destination = Path(workspace["autopptx_zona"])
    property_files: list[Path] = []
    for item in property_media:
        rights = item.get("rights_status")
        if rights not in {"owned", "licensed", "client_authorised", "portal_authorised"}:
            raise AutoPPTXPipelineError("property media lacks report-use rights")
        path = Path(str(item.get("report_path") or item.get("source_path") or ""))
        property_files.append(path)

    property_copies = _copy_ordered(property_files, piso_destination, "piso")
    zone_files = [Path(zone_evidence["map_screenshot_path"])] + [
        Path(item["path"]) for item in zone_evidence["surroundings"]
    ]
    zone_copies = _copy_ordered(zone_files, zona_destination, "zona")
    result = {
        "property_media": property_copies,
        "zone_media": zone_copies,
        "property_media_count": len(property_copies),
        "zone_media_count": len(zone_copies),
        "minimum_zone_media_satisfied": len(zone_copies) >= 3,
    }
    result["staging_digest"] = canonical_digest(result)
    return result


def build_autopptx_pipeline_plan(
    *,
    project_code: str,
    workspace: Mapping[str, str],
    workbook_plan: Mapping[str, Any],
    zone_evidence: Mapping[str, Any],
    media_staging: Mapping[str, Any],
    report_job: Mapping[str, Any],
) -> dict[str, Any]:
    code = validate_project_code(project_code)
    if workbook_plan.get("project_code") != code:
        raise AutoPPTXPipelineError("workbook plan project code mismatch")
    if zone_evidence.get("project_code") != code:
        raise AutoPPTXPipelineError("zone evidence project code mismatch")
    if report_job.get("project_code") != code:
        raise AutoPPTXPipelineError("report job project code mismatch")
    if not media_staging.get("minimum_zone_media_satisfied"):
        raise AutoPPTXPipelineError("map screenshot and at least two surroundings images required")
    if report_job.get("generation_status") != "approved_for_local_generation":
        raise AutoPPTXPipelineError("report job is not approved for generation")

    plan = {
        "schema_version": 1,
        "plan_type": "autopptx_end_to_end_local_pipeline",
        "project_code": code,
        "workspace": dict(workspace),
        "bound_digests": {
            "workbook_plan": workbook_plan["plan_digest"],
            "zone_evidence": zone_evidence["evidence_digest"],
            "media_staging": media_staging["staging_digest"],
            "report_job": report_job["job_digest"],
        },
        "steps": [
            {"order": 1, "action": "write_usando_workbook", "executor": "windows_excel_com"},
            {"order": 2, "action": "force_full_recalculation", "executor": "windows_excel_com"},
            {"order": 3, "action": "review_strategy_profitability", "executor": "named_human"},
            {"order": 4, "action": "verify_zone_slide_inputs", "executor": "named_human"},
            {"order": 5, "action": "run_autopptx_main", "executor": "local_python_shell_false"},
            {"order": 6, "action": "export_pdf", "executor": "powerpoint_com"},
            {"order": 7, "action": "run_report_checklist", "executor": "named_human"},
            {"order": 8, "action": "hash_and_archive_outputs", "executor": "local_python"},
        ],
        "slide_requirements": {
            "slide_6_services_review": True,
            "slide_8_zone_map": True,
            "slide_8_household_income": zone_evidence["household_income_eur"],
            "slide_8_zone": zone_evidence["zone"],
            "property_photo_slides": True,
        },
        "execution_controls": {
            "Excel_and_PPTX_files_must_be_closed_before_execution": True,
            "explicit_execution_approval_required": True,
            "real_client_delivery_permitted": False,
            "offer_or_purchase_action_permitted": False,
            "network_access_permitted": False,
        },
    }
    plan["pipeline_digest"] = canonical_digest(plan)
    return plan
