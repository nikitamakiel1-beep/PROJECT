#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.release_readiness import evaluate_all_modes  # noqa: E402

POLICY = ROOT / "config" / "real-estate-release-readiness-rc3.json"
EVIDENCE = (
    ROOT
    / "evidence"
    / "readiness"
    / "2026-07-23-real-estate-release-evidence-rc3.json"
)
MANUAL = ROOT / "docs" / "manuals" / "REAL_ESTATE_DAILY_OPERATOR_RUNBOOK_RC3.md"
MANIFEST = ROOT / "MANIFEST.real-estate-architecture-rc3.json"
RECEIPT = (
    ROOT
    / "evidence"
    / "readiness"
    / "2026-07-23-real-estate-architecture-rc3.json"
)

RUNTIME_FILES = [
    ROOT / "intelligence" / "real_estate" / "operator_control.py",
    ROOT / "intelligence" / "real_estate" / "release_readiness.py",
    ROOT / "intelligence" / "real_estate" / "media_rights.py",
    ROOT / "intelligence" / "real_estate" / "autopptx_workspace.py",
    ROOT / "intelligence" / "real_estate" / "autopptx_release_plan.py",
    ROOT / "scripts" / "real_estate_operator_control.py",
]
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "selenium",
    "playwright",
    "scrapy",
    "gspread",
    "googleapiclient",
    "smtplib",
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> int:
    errors: list[str] = []
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    summary = evaluate_all_modes(policy=policy, evidence=evidence)

    expected_scores = {
        "architecture_package": 98.8,
        "controlled_operator_use": 81.5,
        "live_client_production": 47.0,
    }
    for mode, expected in expected_scores.items():
        actual = summary["modes"][mode]["score_percent"]
        if actual != expected:
            errors.append(f"unexpected {mode} score: {actual} != {expected}")
    if summary["modes"]["architecture_package"]["decision"] != "ready_for_release_review":
        errors.append("architecture package decision is not review-ready")
    if summary["modes"]["controlled_operator_use"]["decision"] != "controlled_use_ready":
        errors.append("controlled operator mode is not ready")
    if summary["modes"]["live_client_production"]["decision"] != "not_ready":
        errors.append("live production is incorrectly marked ready")
    required_live_blockers = {
        "live_source_permissions",
        "live_source_adapters",
        "live_zone_validation",
        "live_workbook_golden_reports",
    }
    actual_live_blockers = set(
        summary["modes"]["live_client_production"]["critical_blockers"]
    )
    if not required_live_blockers.issubset(actual_live_blockers):
        errors.append("required live blockers are missing")

    for mode in policy["modes"].values():
        if sum(float(item["weight"]) for item in mode["criteria"]) != 100:
            errors.append("release mode weights do not total 100")
    if sum(float(item["weight"]) for item in policy["case_components"]) != 100:
        errors.append("case component weights do not total 100")

    for path in RUNTIME_FILES:
        forbidden = imported_roots(path) & FORBIDDEN_IMPORTS
        if forbidden:
            errors.append(f"forbidden imports in {path}: {sorted(forbidden)}")

    media_text = (ROOT / "intelligence" / "real_estate" / "media_rights.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "isolated_input_dir",
        "single_media_isolation_required",
        "output_files == [expected_staged]",
        "cleanup output cannot overwrite the original source",
    ):
        if phrase not in media_text:
            errors.append(f"media isolation control missing: {phrase}")

    staging_text = (
        ROOT / "intelligence" / "real_estate" / "autopptx_release_plan.py"
    ).read_text(encoding="utf-8")
    for phrase in (
        "stale_managed_files_removed",
        "duplicate_sources_removed",
        "target_sha256",
        "idempotent_media_staging_required",
    ):
        if phrase not in staging_text:
            errors.append(f"AutoPPTX staging control missing: {phrase}")

    workbook_text = (
        ROOT / "intelligence" / "real_estate" / "autopptx_workspace.py"
    ).read_text(encoding="utf-8")
    adapter_text = (ROOT / "scripts" / "windows_usando_excel_adapter.py").read_text(
        encoding="utf-8"
    )
    if "metadata_only_fields" not in workbook_text or "metadata_only_fields" not in adapter_text:
        errors.append("metadata-only transfer-tax control missing")
    if "manual_transfer_tax_binding_required" not in adapter_text:
        errors.append("transfer-tax binding receipt missing")

    manual_text = MANUAL.read_text(encoding="utf-8")
    for phrase in (
        "98.8%",
        "81.5%",
        "47.0%",
        "init-case",
        "release-status",
        "manual_transfer_tax_binding_required",
        "Current blockers to live production",
    ):
        if phrase not in manual_text:
            errors.append(f"operator manual requirement missing: {phrase}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if files != sorted(files):
        errors.append("manifest files are not sorted")
    if len(files) != len(set(files)):
        errors.append("manifest contains duplicates")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("scores") != expected_scores:
        errors.append("readiness receipt scores do not match policy")
    if receipt.get("live_client_production_permitted"):
        errors.append("receipt incorrectly permits live client production")

    print(json.dumps({"release": "rc3", "passed": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
