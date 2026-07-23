#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "real-estate-synthetic-orchestrator.json"
MANIFEST = ROOT / "MANIFEST.stage-008r.json"
RECEIPT = ROOT / "evidence" / "readiness" / "2026-07-23-real-estate-synthetic-orchestrator.json"
RUNTIME = ROOT / "intelligence" / "real_estate" / "synergy.py"

FORBIDDEN_IMPORTS = {
    "requests", "googleapiclient", "gspread", "smtplib", "socket",
    "subprocess", "urllib", "httpx", "aiohttp",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def imported_roots(source: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source)
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
    source = RUNTIME.read_text(encoding="utf-8")
    errors: list[str] = []

    if config.get("stage") != "008r":
        errors.append("wrong stage")
    if config.get("execution_mode") != "synthetic_in_memory_only":
        errors.append("runtime is not synthetic/in-memory only")
    if config["controls"]["real_spreadsheet_writes_permitted"]:
        errors.append("real spreadsheet writes enabled")
    if config["controls"]["network_clients_permitted"]:
        errors.append("network clients enabled")
    if config["controls"]["external_communication_permitted"]:
        errors.append("external communication enabled")
    if config["controls"]["transaction_action_permitted"]:
        errors.append("transaction action enabled")
    if manifest["parallel_formula_engine_created"]:
        errors.append("parallel formula engine claimed")
    if manifest["real_source_rows_in_github"] != 0:
        errors.append("real source rows in GitHub")
    if manifest["real_source_rows_imported"] != 0:
        errors.append("real source rows imported")
    if not receipt["in_memory_fixture_only"]:
        errors.append("receipt does not confirm in-memory fixture")
    if receipt["network_client_added"] or receipt["real_spreadsheet_client_added"]:
        errors.append("receipt claims external client")

    forbidden = imported_roots(source) & FORBIDDEN_IMPORTS
    if forbidden:
        errors.append(f"forbidden runtime imports: {sorted(forbidden)}")
    if "class SyntheticFixture" not in source:
        errors.append("synthetic fixture missing")
    if "class SyntheticSynergyOrchestrator" not in source:
        errors.append("orchestrator missing")
    if re.search(r"real_writes_permitted[\"']?\s*[:=]\s*True", source):
        errors.append("real writes enabled in runtime source")

    result = {"stage": "008r", "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
