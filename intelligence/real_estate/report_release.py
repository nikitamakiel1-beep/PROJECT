"""Governed local AutoPPTX/PDF report release adapter.

The adapter prepares immutable report jobs, verifies four-role approval custody,
and can execute a configured local Python entry point with ``shell=False``. It
never downloads portal content, opens Drive, or sends a generated report.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

from .synergy import canonical_digest


class ReportReleaseError(ValueError):
    pass


REPORT_ROLES = (
    "financial_reviewer",
    "evidence_reviewer",
    "legal_reviewer",
    "commercial_reviewer",
)


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def renderer_readiness(
    config: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = environment or os.environ
    renderer = config["renderer"]
    required_env = [
        renderer["programme_entrypoint_env"],
        renderer["programme_workdir_env"],
        renderer["template_path_env"],
        renderer["workbook_path_env"],
        renderer["output_dir_env"],
        renderer["pdf_converter"]["mode_env"],
    ]
    missing = [name for name in required_env if not environment.get(name)]
    path_fields = {
        "entrypoint": environment.get(renderer["programme_entrypoint_env"]),
        "workdir": environment.get(renderer["programme_workdir_env"]),
        "template": environment.get(renderer["template_path_env"]),
        "workbook": environment.get(renderer["workbook_path_env"]),
        "output_dir": environment.get(renderer["output_dir_env"]),
    }
    invalid_paths: list[str] = []
    for label, value in path_fields.items():
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            invalid_paths.append(f"{label}:not_absolute")
        elif label == "output_dir":
            if not path.exists() or not path.is_dir():
                invalid_paths.append(f"{label}:missing_directory")
        elif label in {"workdir"}:
            if not path.exists() or not path.is_dir():
                invalid_paths.append(f"{label}:missing_directory")
        elif not path.exists() or not path.is_file():
            invalid_paths.append(f"{label}:missing_file")

    converter = environment.get(renderer["pdf_converter"]["mode_env"])
    allowed_modes = renderer["pdf_converter"]["allowed_modes"]
    invalid_converter = converter is not None and converter not in allowed_modes
    ready = not missing and not invalid_paths and not invalid_converter
    return {
        "ready": ready,
        "missing_environment": missing,
        "invalid_paths": invalid_paths,
        "invalid_converter": invalid_converter,
        "converter": converter,
        "network_access": False,
        "Drive_access": False,
    }


def _validate_report_approvals(approvals: Mapping[str, Any]) -> None:
    missing = [role for role in REPORT_ROLES if role not in approvals]
    if missing:
        raise ReportReleaseError(f"missing report approvals: {missing}")
    reviewers: list[str] = []
    for role in REPORT_ROLES:
        record = approvals[role]
        if record.get("status") != "approved":
            raise ReportReleaseError(f"report role is not approved: {role}")
        token = str(record.get("reviewer_token") or "")
        if not token.startswith("restricted://reviewer/"):
            raise ReportReleaseError(f"invalid reviewer token for {role}")
        reviewers.append(token)
    if len(reviewers) != len(set(reviewers)):
        raise ReportReleaseError("all report reviewers must be distinct")


def build_report_job(
    *,
    property_id: str,
    project_code: str,
    underwriting_case_id: str,
    scenario_ids: list[str],
    calculation_version: str,
    input_snapshot_digest: str,
    template_version: str,
    evidence: list[Mapping[str, Any]],
    media: list[Mapping[str, Any]],
    approvals: Mapping[str, Any],
    source_candidate_digest: str,
) -> dict[str, Any]:
    if not property_id or not project_code:
        raise ReportReleaseError("property and project identifiers are required")
    if not scenario_ids:
        raise ReportReleaseError("at least one approved scenario is required")
    if not input_snapshot_digest.startswith("sha256:"):
        raise ReportReleaseError("input snapshot digest required")
    if not source_candidate_digest.startswith("sha256:"):
        raise ReportReleaseError("source candidate digest required")
    _validate_report_approvals(approvals)

    unverified_evidence = [
        str(item.get("evidence_id"))
        for item in evidence
        if item.get("validation_status") != "verified"
    ]
    if unverified_evidence:
        raise ReportReleaseError(
            "unverified evidence blocks generation: " + ", ".join(unverified_evidence)
        )
    invalid_evidence_tokens = [
        str(item.get("evidence_id"))
        for item in evidence
        if not str(item.get("restricted_pointer") or "").startswith("restricted://")
    ]
    if invalid_evidence_tokens:
        raise ReportReleaseError("all evidence must use restricted pointers")

    invalid_media: list[str] = []
    for item in media:
        rights = item.get("rights_status")
        pointer = str(item.get("restricted_pointer") or "")
        if rights not in {"owned", "licensed", "client_authorised", "portal_authorised"}:
            invalid_media.append(str(item.get("media_id")))
        elif not pointer.startswith("restricted://"):
            invalid_media.append(str(item.get("media_id")))
    if invalid_media:
        raise ReportReleaseError(
            "unapproved media blocks generation: " + ", ".join(invalid_media)
        )

    approval_digest = canonical_digest(approvals)
    job = {
        "schema_version": 1,
        "job_type": "autopptx_report_generation",
        "property_id": property_id,
        "project_code": project_code,
        "underwriting_case_id": underwriting_case_id,
        "scenario_ids": sorted(set(scenario_ids)),
        "calculation_version": calculation_version,
        "input_snapshot_digest": input_snapshot_digest,
        "source_candidate_digest": source_candidate_digest,
        "template_version": template_version,
        "evidence_ids": sorted(str(item["evidence_id"]) for item in evidence),
        "media_ids": sorted(str(item["media_id"]) for item in media),
        "approval_digest": approval_digest,
        "selected_project_control": "#Pre-analisis!B3",
        "selected_project_control_verified": True,
        "expected_outputs": {
            "pptx": f"{project_code}.pptx",
            "pdf": f"{project_code}.pdf",
        },
        "generation_status": "approved_for_local_generation",
        "share_status": "not_shareable",
        "external_delivery_permitted": False,
        "network_access_permitted": False,
        "Drive_access_permitted": False,
    }
    job["job_digest"] = canonical_digest(job)
    return job


def build_local_command(
    job: Mapping[str, Any],
    config: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = dict(environment or os.environ)
    readiness = renderer_readiness(config, environment)
    if not readiness["ready"]:
        raise ReportReleaseError(f"renderer is not ready: {readiness}")
    renderer = config["renderer"]
    entrypoint = Path(environment[renderer["programme_entrypoint_env"]])
    workdir = Path(environment[renderer["programme_workdir_env"]])
    output_dir = Path(environment[renderer["output_dir_env"]])
    job_file = output_dir / f"{job['project_code']}.report-job.json"
    command = [sys.executable, str(entrypoint)]
    plan = {
        "command": command,
        "cwd": str(workdir),
        "job_file": str(job_file),
        "environment_overrides": {
            "ALMA_REPORT_JOB_PATH": str(job_file),
            "ALMA_REPORT_JOB_DIGEST": job["job_digest"],
            "ALMA_REPORT_PROJECT_CODE": job["project_code"],
            "ALMA_REPORT_OUTPUT_DIR": str(output_dir),
            "ALMA_REPORT_PDF_CONVERTER": environment[
                renderer["pdf_converter"]["mode_env"]
            ],
        },
        "shell": False,
        "execute": False,
        "network_access_permitted": False,
        "Drive_access_permitted": False,
    }
    plan["command_plan_digest"] = canonical_digest(plan)
    return plan


def execute_local_report_job(
    job: Mapping[str, Any],
    command_plan: Mapping[str, Any],
    *,
    explicit_execution_approval: bool,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    if not explicit_execution_approval:
        raise ReportReleaseError("explicit local execution approval required")
    if job.get("generation_status") != "approved_for_local_generation":
        raise ReportReleaseError("job is not approved for generation")
    if command_plan.get("shell") is not False:
        raise ReportReleaseError("shell execution is forbidden")

    job_path = Path(command_plan["job_file"])
    job_path.write_text(
        json.dumps(job, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in command_plan["environment_overrides"].items()})
    process = subprocess.run(
        list(command_plan["command"]),
        cwd=command_plan["cwd"],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
        check=False,
    )
    receipt = {
        "job_digest": job["job_digest"],
        "command_plan_digest": command_plan["command_plan_digest"],
        "returncode": process.returncode,
        "stdout_digest": canonical_digest(process.stdout),
        "stderr_digest": canonical_digest(process.stderr),
        "success": process.returncode == 0,
        "external_delivery_permitted": False,
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def verify_report_outputs(
    *,
    job: Mapping[str, Any],
    output_dir: str | Path,
    pdf_required: bool,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    pptx = output_dir / job["expected_outputs"]["pptx"]
    pdf = output_dir / job["expected_outputs"]["pdf"]
    if not pptx.is_file() or pptx.stat().st_size == 0:
        raise ReportReleaseError("PPTX output is missing or empty")
    if pdf_required and (not pdf.is_file() or pdf.stat().st_size == 0):
        raise ReportReleaseError("PDF output is required but missing or empty")
    result = {
        "job_digest": job["job_digest"],
        "pptx_path": str(pptx),
        "pptx_sha256": file_sha256(pptx),
        "pdf_path": str(pdf) if pdf.is_file() else None,
        "pdf_sha256": file_sha256(pdf) if pdf.is_file() else None,
        "archive_ready": True,
        "external_share_ready": bool(pdf.is_file()) and pdf_required,
        "external_delivery_permitted": False,
    }
    result["verification_digest"] = canonical_digest(result)
    return result
