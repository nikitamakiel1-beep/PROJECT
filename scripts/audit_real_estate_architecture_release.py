#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "config" / "real-estate-architecture-release.json"
CONNECTORS = ROOT / "config" / "real-estate-source-connectors.json"
RENDERER = ROOT / "config" / "real-estate-report-renderer.json"
MANIFEST = ROOT / "MANIFEST.real-estate-architecture-rc1.json"
RECEIPT = ROOT / "evidence" / "readiness" / "2026-07-23-real-estate-architecture-rc1.json"

RUNTIME_PATHS = [
    ROOT / "intelligence" / "real_estate" / "acquisition.py",
    ROOT / "intelligence" / "real_estate" / "report_release.py",
    ROOT / "intelligence" / "real_estate" / "release_approval.py",
    ROOT / "scripts" / "real_estate_release_cli.py",
]
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "selenium",
    "playwright",
    "bs4",
    "scrapy",
    "googleapiclient",
    "gspread",
    "smtplib",
    "socket",
}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    release = load(RELEASE)
    connectors = load(CONNECTORS)
    renderer = load(RENDERER)
    manifest = load(MANIFEST)
    receipt = load(RECEIPT)
    errors: list[str] = []

    if release.get("release_id") != "REAL-ESTATE-ARCHITECTURE-RC1":
        errors.append("wrong release id")
    if release.get("release_branch") != "release/real-estate-architecture-rc1":
        errors.append("wrong release branch")

    decision = release["current_decision"]
    for key in (
        "live_portal_acquisition_permitted",
        "real_data_import_permitted",
        "report_local_generation_permitted",
        "report_external_delivery_permitted",
        "merge_to_main_permitted",
        "deployment_permitted",
    ):
        if decision[key]:
            errors.append(f"forbidden release decision enabled: {key}")

    principles = connectors["principles"]
    if principles["robots_or_scrapers_without_written_permission"]:
        errors.append("uncontrolled scraping enabled")
    if not principles["authorised_access_only"]:
        errors.append("authorised-source rule disabled")

    connector_ids = [item["id"] for item in connectors["connectors"]]
    if len(connector_ids) != len(set(connector_ids)):
        errors.append("duplicate connector id")
    required_connectors = {
        "idealista_search_api",
        "supervised_url_capture",
        "partner_feed",
        "catastro_public_services",
        "ine_json_api",
    }
    if not required_connectors.issubset(set(connector_ids)):
        errors.append("required connector contract missing")

    idealista = next(
        item for item in connectors["connectors"] if item["id"] == "idealista_search_api"
    )
    if idealista["status"] != "access_request_required":
        errors.append("Idealista provider-access gate is not closed")
    if "web_scraping" not in idealista["forbidden"]:
        errors.append("Idealista scraping prohibition missing")

    controls = renderer["release_controls"]
    if not controls["all_report_reviewers_distinct"]:
        errors.append("distinct report reviewers not required")
    if not controls["report_outputs_must_be_hashed"]:
        errors.append("report output hashes not required")
    if controls["generated_report_shareable_by_default"]:
        errors.append("generated reports are shareable by default")
    if len(renderer["known_repairs_required_before_live_execution"]) < 8:
        errors.append("known AutoPPTX repair set is incomplete")

    for path in RUNTIME_PATHS:
        roots = imported_roots(path)
        forbidden = sorted(roots & FORBIDDEN_IMPORTS)
        if forbidden:
            errors.append(f"forbidden imports in {path}: {forbidden}")
        body = path.read_text(encoding="utf-8")
        if SECRET_ASSIGNMENT_RE.search(body):
            errors.append(f"possible embedded secret in {path}")

    files = manifest.get("files", [])
    if manifest.get("schema_version") != 2:
        errors.append("manifest schema version must be 2")
    if files != sorted(files):
        errors.append("manifest file list is not sorted")
    if "MANIFEST.real-estate-architecture-rc1.json" not in files:
        errors.append("manifest does not own itself")
    if manifest.get("real_source_rows_in_github") != 0:
        errors.append("manifest claims real source rows")

    if receipt.get("real_source_rows_imported") != 0:
        errors.append("readiness receipt claims a real import")
    if receipt.get("live_portal_access_enabled"):
        errors.append("readiness receipt claims live portal access")
    if receipt.get("external_report_delivery_enabled"):
        errors.append("readiness receipt claims external report delivery")

    result = {
        "release": "REAL-ESTATE-ARCHITECTURE-RC1",
        "passed": not errors,
        "errors": errors,
        "live_portal_acquisition_permitted": False,
        "real_CRM_writes_permitted": False,
        "external_report_delivery_permitted": False,
    }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
