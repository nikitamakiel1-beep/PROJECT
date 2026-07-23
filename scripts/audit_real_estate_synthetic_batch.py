#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "real-estate-synthetic-batch.json"
MANIFEST = ROOT / "MANIFEST.stage-009r.json"
RECEIPT = ROOT / "evidence" / "readiness" / "2026-07-23-real-estate-synthetic-batch.json"
RUNTIME = ROOT / "intelligence" / "real_estate" / "batch.py"
FIXTURE = ROOT / "fixtures" / "real_estate" / "stage009r-synthetic-opportunities.csv"

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
    fixture_source = FIXTURE.read_text(encoding="utf-8")
    errors: list[str] = []

    if config.get("stage") != "009r":
        errors.append("wrong stage")
    if config.get("execution_mode") != "local_synthetic_batch_only":
        errors.append("execution mode is not local synthetic only")
    controls = config["controls"]
    for key in (
        "real_source_file_access_permitted",
        "network_access_permitted",
        "Drive_access_permitted",
        "real_CRM_write_permitted",
        "external_communication_permitted",
    ):
        if controls[key]:
            errors.append(f"forbidden control enabled: {key}")

    forbidden = imported_roots(runtime_source) & FORBIDDEN_IMPORTS
    if forbidden:
        errors.append(f"forbidden imports: {sorted(forbidden)}")
    if EMAIL_RE.search(fixture_source) or URL_RE.search(fixture_source):
        errors.append("fixture contains email or URL-like content")

    rows = list(csv.DictReader(fixture_source.splitlines()))
    if len(rows) != 2:
        errors.append("expected exactly two synthetic fixture rows")
    if any(not str(row.get("CODI", "")).startswith("SYN_") for row in rows):
        errors.append("non-synthetic external code in fixture")

    if manifest.get("real_source_rows_in_github") != 0:
        errors.append("manifest claims real source rows")
    if receipt.get("real_source_rows_imported") != 0:
        errors.append("receipt claims real row import")
    if not receipt.get("deterministic_local_bundle_only"):
        errors.append("receipt does not confirm local deterministic bundle")

    result = {"stage": "009r", "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
