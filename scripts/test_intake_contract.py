#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"intake contract validation failed: {message}")


def main() -> None:
    contract = json.loads((ROOT / "schemas/crm/sheets-contract.json").read_text(encoding="utf-8"))
    services = json.loads((ROOT / "schemas/services.json").read_text(encoding="utf-8"))
    lead_schema = json.loads((ROOT / "schemas/crm/lead.schema.json").read_text(encoding="utf-8"))
    core = (ROOT / "automations/google-apps-script/IntakeCore.gs").read_text(encoding="utf-8")
    adapter = (ROOT / "automations/google-apps-script/Code.gs").read_text(encoding="utf-8")
    provider_test = (ROOT / "automations/google-apps-script/ProviderTest.gs").read_text(encoding="utf-8")
    config = (ROOT / "apps/web/config.js").read_text(encoding="utf-8")

    required_intake_sheets = {"Companies", "Contacts", "Leads", "Opportunities", "Activities", "Automation Log"}
    if not required_intake_sheets.issubset(set(contract["sheets"])):
        fail("sheet contract is missing an intake-critical CRM sheet")
    for name, headers in contract["sheets"].items():
        if len(headers) != len(set(headers)):
            fail(f"duplicate header in {name}")

    intake_owned_sheets = {"Companies", "Contacts", "Leads", "Activities", "Automation Log"}
    for name in intake_owned_sheets:
        for header in contract["sheets"][name]:
            if repr(header).replace('"', "'") not in core and f"'{header}'" not in core:
                fail(f"intake core header missing: {name}.{header}")
    if "Opportunities" not in contract["sheets"] or "Next Step Date" not in contract["sheets"]["Opportunities"]:
        fail("opportunity contract is incomplete")

    active_codes = {item["code"] for item in services if item["status"] == "active"}
    schema_codes = set(lead_schema["properties"]["service_code"]["enum"])
    if not active_codes.issubset(schema_codes):
        fail("active service codes are absent from lead schema")
    if "demoMode: true" not in config or 'intakeEndpoint: ""' not in config:
        fail("public website is not safely held in demonstration mode")
    for token in ["assertSheetContracts_", "applyPlanTransaction_", "deleteRow", "SYNTHETIC_ONLY", "Automation Log", "synthetic_injected_write_failure"]:
        if token not in adapter:
            fail(f"Apps Script adapter lacks required control: {token}")
    for token in ["preparePlan", "stableId", "existing_contact_company_precedence", "makeLogRecord"]:
        if token not in core:
            fail(f"intake core lacks required behavior: {token}")
    for token in ["runProviderHttpSuite", "cleanupToCounts_", "WEB_APP_URL", "injected_write_failure"]:
        if token not in provider_test:
            fail(f"provider test runner lacks required behavior: {token}")

    for script in ["Code.gs", "IntakeCore.gs", "ProviderTest.gs"]:
        syntax = subprocess.run(
            ["node", "-e", "const fs=require('fs'); new Function(fs.readFileSync(process.argv[1],'utf8'));", str(ROOT / "automations/google-apps-script" / script)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if syntax.returncode:
            fail(f"Apps Script syntax error in {script}: " + (syntax.stderr or syntax.stdout))

    result = subprocess.run(
        ["node", str(ROOT / "scripts/intake_contract_harness.js")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        fail(result.stderr or result.stdout)
    evidence = json.loads(result.stdout)
    if not evidence.get("ok") or any(test.get("result") != "passed" for test in evidence.get("tests", [])):
        fail("synthetic harness did not pass every case")
    if len(evidence["tests"]) < 9:
        fail("synthetic harness coverage is incomplete")
    print(f"intake contract validation passed ({len(evidence['tests'])} synthetic cases)")


if __name__ == "__main__":
    main()
