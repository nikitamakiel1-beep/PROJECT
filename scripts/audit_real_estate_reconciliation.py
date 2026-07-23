#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "real-estate-synthetic-reconciliation.json"
MANIFEST = ROOT / "MANIFEST.stage-010r.json"
RECEIPT = ROOT / "evidence" / "readiness" / "2026-07-23-real-estate-synthetic-reconciliation.json"
RUNTIME = ROOT / "intelligence" / "real_estate" / "reconciliation.py"
API = ROOT / "intelligence" / "real_estate" / "reconciliation_api.py"
FIXTURE = ROOT / "fixtures" / "real_estate" / "stage010r-synthetic-opportunities-target.csv"

FORBIDDEN_IMPORTS = {
    "requests", "googleapiclient", "gspread", "smtplib", "socket",
    "httpx", "aiohttp", "urllib",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r"https?://", re.I)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def imported_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> int:
    config = load(CONFIG)
    manifest = load(MANIFEST)
    receipt = load(RECEIPT)
    runtime_source = RUNTIME.read_text(encoding="utf-8")
    api_source = API.read_text(encoding="utf-8")
    fixture_source = FIXTURE.read_text(encoding="utf-8")
    errors: list[str] = []

    if config.get("stage") != "010r":
        errors.append("wrong stage")
    if config.get("execution_mode") != "local_synthetic_reconciliation_only":
        errors.append("execution mode is not local synthetic reconciliation")

    for key, value in config.get("safety", {}).items():
        if value:
            errors.append(f"forbidden safety control enabled: {key}")

    forbidden = (imported_roots(runtime_source) | imported_roots(api_source)) & FORBIDDEN_IMPORTS
    if forbidden:
        errors.append(f"forbidden imports: {sorted(forbidden)}")

    if EMAIL_RE.search(fixture_source) or URL_RE.search(fixture_source):
        errors.append("fixture contains email or URL-like content")
    rows = list(csv.DictReader(fixture_source.splitlines()))
    if len(rows) != 2:
        errors.append("expected exactly two target synthetic rows")
    if any(not str(row.get("CODI", "")).startswith("SYN_") for row in rows):
        errors.append("non-synthetic external code in target fixture")

    if manifest.get("real_source_rows_in_github") != 0:
        errors.append("manifest claims real source rows")
    if receipt.get("real_source_rows_imported") != 0:
        errors.append("receipt claims real row import")
    if not receipt.get("rollback_digest_restoration_tested"):
        errors.append("receipt does not confirm rollback digest restoration")
    if not receipt.get("tampered_bundle_rejection_tested"):
        errors.append("receipt does not confirm tampered bundle rejection")

    required_markers = (
        "operation digest mismatch",
        "mutation source digest mismatch",
        "mutation target digest mismatch",
        "rollback_verified",
        "real_writes_permitted",
    )
    for marker in required_markers:
        if marker not in runtime_source:
            errors.append(f"runtime marker missing: {marker}")

    result = {"stage": "010r", "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
