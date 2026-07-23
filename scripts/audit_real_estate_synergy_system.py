#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "real-estate-synergy-system.json"
MANIFEST = ROOT / "MANIFEST.stage-007r.json"
RECEIPT = ROOT / "evidence" / "readiness" / "2026-07-23-real-estate-synergy-system.json"

PUBLIC_SAFE_FILES = [
    CONFIG,
    MANIFEST,
    ROOT / "docs" / "operations" / "REAL_ESTATE_SYNERGY_SYSTEM.md",
    ROOT / "docs" / "handover" / "STAGE_007R_REAL_ESTATE_SYNERGY.md",
]

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
RAW_DRIVE_RE = re.compile(r"https://(?:drive|docs)\.google\.com/", re.I)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    config = load(CONFIG)
    manifest = load(MANIFEST)
    receipt = load(RECEIPT)
    errors: list[str] = []

    if config.get("stage") != "007r":
        errors.append("stage must be 007r")
    if not config["integration_decision"]["generic_crm_preserved"]:
        errors.append("generic CRM preservation missing")
    if config["integration_decision"]["existing_master_modified"]:
        errors.append("existing master mutation claimed")
    if config["integration_decision"]["real_source_rows_imported"] != 0:
        errors.append("real source import claimed")
    if config["import_controls"]["real_import_permitted"]:
        errors.append("real import enabled")
    if config["AI_controls"]["mode"] != "shadow_only":
        errors.append("AI must remain shadow-only")
    if config["current_decision"]["outreach_permitted"]:
        errors.append("outreach enabled")
    if config["current_decision"]["transaction_action_permitted"]:
        errors.append("transaction action enabled")
    if config["runtime_dependency"]["replacement"]:
        errors.append("Stage 007r must not replace A30")

    required_sheets = {
        "Property Sources", "Partners & Captors", "Visits", "Evidence & Media",
        "Renovation Estimates", "Reports & Approvals", "Fee Arrangements",
        "Synergy Event Log", "Source Registry", "Synergy Dashboard",
    }
    if not required_sheets.issubset(set(config["extension_sheets"])):
        errors.append("missing operational sheet contracts")

    if manifest["real_source_rows_in_github"] != 0:
        errors.append("manifest claims real rows in GitHub")
    if manifest["real_source_rows_imported"] != 0:
        errors.append("manifest claims real row import")
    if receipt["personal_data_imported"]:
        errors.append("receipt claims personal-data import")
    if receipt["full_property_addresses_imported"]:
        errors.append("receipt claims full-address import")

    for path in PUBLIC_SAFE_FILES:
        body = path.read_text(encoding="utf-8")
        if EMAIL_RE.search(body):
            errors.append(f"email-like literal found in {path.relative_to(ROOT)}")
        if RAW_DRIVE_RE.search(body):
            errors.append(f"raw Drive URL found in {path.relative_to(ROOT)}")

    result = {"stage": "007r", "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
