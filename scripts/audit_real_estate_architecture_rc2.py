#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [
    ROOT / "config" / "real-estate-zone-lavanguardia.json",
    ROOT / "config" / "real-estate-authorised-media-cleanup.json",
    ROOT / "config" / "real-estate-autopptx-rc2.json",
]
RUNTIME_FILES = [
    ROOT / "intelligence" / "real_estate" / "zone_evidence.py",
    ROOT / "intelligence" / "real_estate" / "media_rights.py",
    ROOT / "intelligence" / "real_estate" / "autopptx_workspace.py",
    ROOT / "intelligence" / "real_estate" / "autopptx_release_plan.py",
    ROOT / "intelligence" / "real_estate" / "autopptx_pipeline.py",
]
RECEIPT = (
    ROOT
    / "evidence"
    / "readiness"
    / "2026-07-23-real-estate-architecture-rc2.json"
)
MANIFEST = ROOT / "MANIFEST.real-estate-architecture-rc2.json"
MANUAL = ROOT / "docs" / "manuals" / "REAL_ESTATE_GREATER_OPERATOR_MANUAL.md"

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
    zone, media, autopptx = [
        json.loads(path.read_text(encoding="utf-8")) for path in CONFIGS
    ]
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if zone["capture_mode"]["automatic_page_scraping"]:
        errors.append("La Vanguardia scraping enabled")
    if zone["zone_classification"]["income_thresholds_eur"] is not None:
        errors.append("unverified zone thresholds hard-coded")
    if zone["report_controls"]["map_watermark_removal_permitted"]:
        errors.append("map watermark removal enabled")
    if media["controls"]["overwrite_original"]:
        errors.append("original media overwrite enabled")
    if "lavanguardia_map_capture" not in media["cleanup_forbidden_source_types"]:
        errors.append("La Vanguardia capture not blocked from cleanup")
    if autopptx["workbook"]["selected_project_cell"] != "B3":
        errors.append("USANDO selected project control changed")
    if autopptx["workbook"]["recalculation"] != "CalculateFullRebuild":
        errors.append("full Excel recalculation not required")

    for path in RUNTIME_FILES:
        forbidden = imported_roots(path) & FORBIDDEN_IMPORTS
        if forbidden:
            errors.append(f"forbidden imports in {path}: {sorted(forbidden)}")

    manual = MANUAL.read_text(encoding="utf-8")
    for phrase in (
        "La Vanguardia address-to-zone workflow",
        "Watermark handling hierarchy",
        "Updating the USANDO workbook",
        "Mandatory slide review",
        "Final acquisition approval",
    ):
        if phrase not in manual:
            errors.append(f"manual section missing: {phrase}")

    if receipt["zone_thresholds_verified"]:
        errors.append("receipt incorrectly claims verified thresholds")
    if receipt["real_CRM_writes_added"]:
        errors.append("receipt claims real CRM writes")

    files = manifest.get("files", [])
    if files != sorted(files):
        errors.append("manifest files are not sorted")
    if len(files) != len(set(files)):
        errors.append("manifest contains duplicate files")

    print(json.dumps({"release": "rc2", "passed": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
