"""Idempotent media staging and end-to-end AutoPPTX pipeline plans."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable, Mapping

from .autopptx_workspace import AutoPPTXPipelineError, natural_key, validate_project_code


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _clear_managed_files(destination: Path, prefix: str) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"^\d{{2,}}_{re.escape(prefix)}\.[A-Za-z0-9]+$")
    removed: list[str] = []
    for path in destination.iterdir():
        if path.is_file() and pattern.fullmatch(path.name):
            path.unlink()
            removed.append(str(path))
    return sorted(removed)


def _copy_ordered(
    files: Iterable[str | Path],
    destination: Path,
    prefix: str,
) -> dict[str, Any]:
    if not destination.is_absolute():
        raise AutoPPTXPipelineError("AutoPPTX media destination must be absolute")
    source_paths = [Path(item) for item in files]
    for path in source_paths:
        if not path.is_absolute() or not path.is_file() or path.stat().st_size == 0:
            raise AutoPPTXPipelineError(f"invalid media file: {path}")

    stale_removed = _clear_managed_files(destination, prefix)
    copied: list[dict[str, Any]] = []
    duplicate_sources: list[str] = []
    seen_digests: set[str] = set()
    for source in sorted(source_paths, key=lambda item: natural_key(item.name)):
        digest = file_sha256(source)
        if digest in seen_digests:
            duplicate_sources.append(str(source))
            continue
        seen_digests.add(digest)
        index = len(copied) + 1
        suffix = source.suffix.casefold() or ".jpg"
        target = destination / f"{index:02d}_{prefix}{suffix}"
        shutil.copy2(source, target)
        target_digest = file_sha256(target)
        if target_digest != digest:
            raise AutoPPTXPipelineError(f"media digest mismatch after copy: {source}")
        copied.append(
            {
                "source": str(source),
                "source_sha256": digest,
                "target": str(target),
                "target_sha256": target_digest,
            }
        )
    return {
        "copies": copied,
        "duplicate_sources_removed": sorted(duplicate_sources),
        "stale_managed_files_removed": stale_removed,
    }


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
    if not zone_evidence.get("evidence_digest"):
        raise AutoPPTXPipelineError("zone evidence digest is required")
    if not zone_evidence.get("source_data_year"):
        raise AutoPPTXPipelineError("zone source data year is required")

    piso_destination = Path(workspace["autopptx_piso"])
    zona_destination = Path(workspace["autopptx_zona"])
    property_files: list[Path] = []
    for item in property_media:
        rights = item.get("rights_status")
        if rights not in {"owned", "licensed", "client_authorised", "portal_authorised"}:
            raise AutoPPTXPipelineError("property media lacks report-use rights")
        path = Path(str(item.get("report_path") or item.get("source_path") or ""))
        property_files.append(path)
    if not property_files:
        raise AutoPPTXPipelineError("at least one authorised property image is required")

    property_stage = _copy_ordered(property_files, piso_destination, "piso")
    zone_files = [Path(zone_evidence["map_screenshot_path"])] + [
        Path(item["path"]) for item in zone_evidence["surroundings"]
    ]
    zone_stage = _copy_ordered(zone_files, zona_destination, "zona")
    property_copies = property_stage["copies"]
    zone_copies = zone_stage["copies"]
    result = {
        "property_media": property_copies,
        "zone_media": zone_copies,
        "property_media_count": len(property_copies),
        "zone_media_count": len(zone_copies),
        "minimum_property_media_satisfied": len(property_copies) >= 1,
        "minimum_zone_media_satisfied": len(zone_copies) >= 3,
        "property_duplicate_sources_removed": property_stage[
            "duplicate_sources_removed"
        ],
        "zone_duplicate_sources_removed": zone_stage["duplicate_sources_removed"],
        "stale_managed_files_removed": sorted(
            property_stage["stale_managed_files_removed"]
            + zone_stage["stale_managed_files_removed"]
        ),
        "zone_source_data_year": zone_evidence["source_data_year"],
        "zone_stale_data_warning_required": bool(
            zone_evidence.get("stale_data_warning_required")
        ),
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
    if not media_staging.get("minimum_property_media_satisfied"):
        raise AutoPPTXPipelineError("at least one property image is required")
    if not media_staging.get("minimum_zone_media_satisfied"):
        raise AutoPPTXPipelineError("map screenshot and at least two surroundings images required")
    if report_job.get("generation_status") != "approved_for_local_generation":
        raise AutoPPTXPipelineError("report job is not approved for generation")

    steps = [
        {"order": 1, "action": "write_usando_workbook", "executor": "windows_excel_com"},
        {"order": 2, "action": "force_full_recalculation", "executor": "windows_excel_com"},
        {"order": 3, "action": "review_strategy_profitability", "executor": "named_human"},
        {"order": 4, "action": "verify_zone_slide_inputs", "executor": "named_human"},
        {"order": 5, "action": "run_autopptx_main", "executor": "local_python_shell_false"},
        {"order": 6, "action": "export_pdf", "executor": "powerpoint_com"},
        {"order": 7, "action": "run_report_checklist", "executor": "named_human"},
        {"order": 8, "action": "hash_and_archive_outputs", "executor": "local_python"},
    ]
    plan = {
        "schema_version": 2,
        "plan_type": "autopptx_end_to_end_local_pipeline",
        "project_code": code,
        "workspace": dict(workspace),
        "bound_digests": {
            "workbook_plan": workbook_plan["plan_digest"],
            "zone_evidence": zone_evidence["evidence_digest"],
            "media_staging": media_staging["staging_digest"],
            "report_job": report_job["job_digest"],
        },
        "steps": steps,
        "steps_digest": canonical_digest(steps),
        "slide_requirements": {
            "slide_6_services_review": True,
            "slide_8_zone_map": True,
            "slide_8_household_income": zone_evidence["household_income_eur"],
            "slide_8_zone": zone_evidence["zone"],
            "slide_8_source_data_year": zone_evidence["source_data_year"],
            "slide_8_stale_data_warning": bool(
                zone_evidence.get("stale_data_warning_required")
            ),
            "property_photo_slides": True,
        },
        "execution_controls": {
            "Excel_and_PPTX_files_must_be_closed_before_execution": True,
            "explicit_execution_approval_required": True,
            "real_client_delivery_permitted": False,
            "offer_or_purchase_action_permitted": False,
            "network_access_permitted": False,
            "idempotent_media_staging_required": True,
        },
    }
    plan["pipeline_digest"] = canonical_digest(plan)
    return plan
