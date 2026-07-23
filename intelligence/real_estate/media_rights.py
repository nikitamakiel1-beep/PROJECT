"""Rights-gated media preparation and authorised watermark-cleanup adapter.

Watermark cleanup is permitted only for owned, licensed, client-authorised, or
explicitly portal-authorised property media. Map, news, Street View and other
third-party evidence captures must retain their original marks and attribution.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


class MediaRightsError(ValueError):
    pass


CLEANUP_RIGHTS = {"owned", "licensed", "client_authorised", "portal_authorised"}
NO_CLEANUP_SOURCE_TYPES = {
    "lavanguardia_map_capture",
    "news_map_capture",
    "streetview_capture",
    "map_screenshot",
    "public_source_capture",
}


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_media_record(
    *,
    media_id: str,
    source_path: str | Path,
    source_type: str,
    rights_status: str,
    authorisation_evidence: str,
    attribution: str = "",
) -> dict[str, Any]:
    path = Path(source_path)
    if not path.is_absolute() or not path.is_file() or path.stat().st_size == 0:
        raise MediaRightsError("media source must be an existing absolute file")
    if not authorisation_evidence.startswith("restricted://"):
        raise MediaRightsError("restricted authorisation evidence pointer required")
    record = {
        "schema_version": 1,
        "media_id": media_id,
        "source_path": str(path),
        "source_sha256": file_sha256(path),
        "source_type": source_type,
        "rights_status": rights_status,
        "authorisation_evidence": authorisation_evidence,
        "attribution": attribution,
        "original_preserved": True,
        "cleanup_status": "not_requested",
    }
    record["record_digest"] = canonical_digest(record)
    return record


def build_authorised_cleanup_job(
    *,
    media_record: Mapping[str, Any],
    output_dir: str | Path,
    reviewer_token: str,
    reason: str,
) -> dict[str, Any]:
    rights = str(media_record.get("rights_status") or "")
    source_type = str(media_record.get("source_type") or "")
    if rights not in CLEANUP_RIGHTS:
        raise MediaRightsError("watermark cleanup requires owned or authorised media rights")
    if source_type in NO_CLEANUP_SOURCE_TYPES:
        raise MediaRightsError("map, news and Street View captures cannot be cleaned")
    if not reviewer_token.startswith("restricted://reviewer/"):
        raise MediaRightsError("restricted reviewer token required")
    if len(str(reason).strip()) < 12:
        raise MediaRightsError("a specific cleanup reason is required")

    source = Path(str(media_record["source_path"]))
    destination = Path(output_dir)
    if not destination.is_absolute():
        raise MediaRightsError("cleanup output directory must be absolute")
    output_path = destination / source.name
    job = {
        "schema_version": 1,
        "job_type": "authorised_watermark_cleanup",
        "media_id": media_record["media_id"],
        "source_path": str(source),
        "source_sha256": media_record["source_sha256"],
        "output_dir": str(destination),
        "expected_output_path": str(output_path),
        "rights_status": rights,
        "authorisation_evidence": media_record["authorisation_evidence"],
        "reviewer_token": reviewer_token,
        "reason": str(reason).strip(),
        "detector": "Florence-2 open-vocabulary detection",
        "inpainter": "LaMA context-aware inpainting",
        "preserve_original": True,
        "overwrite_original": False,
        "execution_status": "approved_for_local_execution",
        "external_distribution_permitted": False,
    }
    job["job_digest"] = canonical_digest(job)
    return job


def build_watermarkremover_command(
    *,
    cleanup_job: Mapping[str, Any],
    entrypoint: str | Path,
) -> dict[str, Any]:
    entrypoint_path = Path(entrypoint)
    if not entrypoint_path.is_absolute() or not entrypoint_path.is_file():
        raise MediaRightsError("WatermarkRemover entrypoint must be an existing absolute file")
    source_dir = str(Path(cleanup_job["source_path"]).parent)
    output_dir = str(Path(cleanup_job["output_dir"]))
    command = [sys.executable, str(entrypoint_path), source_dir, output_dir]
    plan = {
        "command": command,
        "cwd": str(entrypoint_path.parent),
        "shell": False,
        "execute": False,
        "cleanup_job_digest": cleanup_job["job_digest"],
        "network_access_permitted": False,
        "overwrite_original": False,
    }
    plan["command_digest"] = canonical_digest(plan)
    return plan


def execute_cleanup_job(
    *,
    cleanup_job: Mapping[str, Any],
    command_plan: Mapping[str, Any],
    explicit_execution_approval: bool,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    if not explicit_execution_approval:
        raise MediaRightsError("explicit cleanup execution approval required")
    if cleanup_job.get("execution_status") != "approved_for_local_execution":
        raise MediaRightsError("cleanup job is not approved")
    if command_plan.get("shell") is not False:
        raise MediaRightsError("shell execution is forbidden")
    Path(cleanup_job["output_dir"]).mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        list(command_plan["command"]),
        cwd=command_plan["cwd"],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
        check=False,
    )
    receipt = {
        "cleanup_job_digest": cleanup_job["job_digest"],
        "command_digest": command_plan["command_digest"],
        "returncode": process.returncode,
        "success": process.returncode == 0,
        "stdout_digest": canonical_digest(process.stdout),
        "stderr_digest": canonical_digest(process.stderr),
        "original_preserved": True,
        "external_distribution_permitted": False,
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def verify_cleanup_output(cleanup_job: Mapping[str, Any]) -> dict[str, Any]:
    source = Path(cleanup_job["source_path"])
    output = Path(cleanup_job["expected_output_path"])
    if not source.is_file():
        raise MediaRightsError("original source file is missing")
    if file_sha256(source) != cleanup_job["source_sha256"]:
        raise MediaRightsError("original source digest changed")
    if not output.is_file() or output.stat().st_size == 0:
        raise MediaRightsError("cleaned output is missing or empty")
    result = {
        "media_id": cleanup_job["media_id"],
        "source_path": str(source),
        "source_sha256": file_sha256(source),
        "cleaned_path": str(output),
        "cleaned_sha256": file_sha256(output),
        "original_preserved": True,
        "rights_status": cleanup_job["rights_status"],
        "authorisation_evidence": cleanup_job["authorisation_evidence"],
        "ready_for_report_review": True,
        "external_distribution_permitted": False,
    }
    result["verification_digest"] = canonical_digest(result)
    return result
