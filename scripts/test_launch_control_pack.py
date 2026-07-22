#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: str) -> str:
    target = ROOT / path
    require(target.exists(), f"missing launch-control file: {path}")
    return target.read_text(encoding="utf-8")


def run() -> None:
    results: list[dict[str, str]] = []

    def case(name: str, fn) -> None:
        fn()
        results.append({"case": name, "result": "passed"})

    services = {item["code"]: item for item in json.loads(read("schemas/services.json"))}

    def service_templates_match_catalogue() -> None:
        mapping = {
            "IVA": "templates/services/visibility-audit.md",
            "CRM": "templates/services/crm-setup-handover.md",
            "IOP": "templates/services/sales-one-pager.md",
        }
        for code, path in mapping.items():
            content = read(path)
            service = services[code]
            require(f"Service code: `{code}`" in content, f"{code} template missing canonical code")
            require(f"€{service['price_eur']}" in content, f"{code} template price drift")
            require(
                f"Target delivery: {service['delivery_days']} working days" in content,
                f"{code} template delivery-day drift",
            )
            require(
                f"Included revisions: {service['revision_limit']}" in content,
                f"{code} template revision-limit drift",
            )

    case("service templates match canonical catalogue", service_templates_match_catalogue)

    def proposal_and_qa_are_fail_closed() -> None:
        proposal = read("templates/commercial/proposal.md")
        checklist = read("templates/commercial/quality-checklist.md")
        for marker in (
            "Payment condition",
            "Cancellation and rescheduling",
            "Commercial/legal wording verified",
            "Client credentials must be shared through an approved secure channel",
        ):
            require(marker in proposal, f"proposal control missing: {marker}")
        for marker in (
            "Critical or high defects block external delivery",
            "Human release decision",
            "Demonstration content is visibly labelled",
            "Actual delivery time",
        ):
            require(marker in checklist, f"QA control missing: {marker}")

    case("proposal and delivery QA remain human gated", proposal_and_qa_are_fail_closed)

    def privacy_and_commercial_controls_block_activation() -> None:
        privacy = read("templates/compliance/privacy-intake-placeholder.md")
        register = read("templates/compliance/launch-control-register.md")
        terms = read("templates/commercial/commercial-terms-control.md")
        for marker in (
            "ACTIVATION BLOCKED",
            "lawful basis",
            "Processor and transfer register",
            "Retention and deletion decisions",
            "Rights-request procedure",
            "Incident escalation",
            "Activation gate",
        ):
            require(marker in privacy, f"privacy control missing: {marker}")
        require("BLOCKED" in register, "launch register has no blocking state")
        require("Human activation approval" in register, "human activation control missing")
        require("No identifiers or private addresses" in terms, "public-identity safety marker missing")
        require("Pre-issue gate" in terms, "commercial pre-issue gate missing")

    case("privacy and commercial activation controls are explicit", privacy_and_commercial_controls_block_activation)

    def demonstrations_are_fictional_and_complete() -> None:
        register = read("demonstrations/DEMONSTRATION_REGISTER.md")
        demos = {
            "IVA": "demonstrations/IVA_NORTHLINE_DEMO.md",
            "CRM": "demonstrations/CRM_ARCHIPELAGO_DEMO.md",
            "IOP": "demonstrations/IOP_VERDE_FORMA_DEMO.md",
        }
        require("Not a client result" in register, "demonstration register missing public label")
        for code, path in demos.items():
            content = read(path)
            require(content.count("fictional") >= 2, f"{code} demonstration lacks repeated fictional label")
            require("Not a client result" in content, f"{code} demonstration lacks no-client-result label")
            require(f"Service code:** {code}" in content, f"{code} demonstration lacks service code")
            require(f"€{services[code]['price_eur']}" in content, f"{code} demonstration price drift")
            for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", content):
                require(email.endswith(".example"), f"non-reserved email in demonstration: {email}")
            require("https://docs.google.com/spreadsheets/" not in content, "live spreadsheet URL in demo")
            require("script.google.com" not in content, "provider URL in demo")

    case("three demonstrations are complete and public safe", demonstrations_are_fictional_and_complete)

    def provider_runbook_retains_stage_gate() -> None:
        runbook = read("docs/setup/STAGE_003_PROVIDER_ACTIVATION_RUNBOOK.md")
        for marker in (
            "runProviderHttpSuite()",
            "runDailyFollowUpDigest()",
            "SYNTHETIC_ONLY",
            "9/9 passed",
            "Cleanup failure blocks Stage 003",
            "The stage pointer must not move on the basis of source tests alone",
        ):
            require(marker in runbook, f"provider runbook missing gate: {marker}")

    case("provider activation runbook remains evidence gated", provider_runbook_retains_stage_gate)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
