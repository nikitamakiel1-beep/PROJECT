#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.pre_client_readiness import (  # noqa: E402
    audit_pre_client_readiness,
    verify_readiness_report,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def crm_snapshot() -> dict:
    contract = json.loads((ROOT / "schemas" / "crm" / "sheets-contract.json").read_text(encoding="utf-8"))
    sheets = {}
    for name, headers in contract["sheets"].items():
        sheets[name] = {"headers": headers, "business_rows": 0}
    for name, view in contract["operational_views"].items():
        if name in {"Dashboard", "Config"}:
            sheets[name] = {"headers": view["columns"], "business_rows": 0}
    return {"sheets": sheets}


def complete_activation() -> dict:
    return {
        "provider_a01_9_of_9": True,
        "provider_a02_idempotency": True,
        "provider_neural_bridge": True,
        "provider_cleanup_verified": True,
        "privacy_professional_approval": True,
        "legal_and_invoicing_professional_approval": True,
        "website_publication_qa": True,
        "human_live_release_approval": True,
    }


def run() -> None:
    results: list[dict[str, str]] = []

    def case(name: str, fn) -> None:
        fn()
        results.append({"case": name, "result": "passed"})

    def source_ready_without_clients() -> None:
        report = audit_pre_client_readiness(ROOT, crm_snapshot=crm_snapshot())
        require(report["states"]["source_ready"] is True, "source should be ready")
        require(report["states"]["construction_ready"] is True, "website should be construction-ready")
        require(report["states"]["crm_architecture_ready"] is True, "CRM architecture should be ready")
        require(report["states"]["client_acquisition_ready"] is True, "pre-client system should be ready")
        require(report["states"]["live_intake_ready"] is False, "live intake must remain blocked")
        require(report["states"]["paid_delivery_ready"] is False, "paid delivery must remain blocked")
        require(report["source_completion_pct"] == 100.0, "source completion should be 100%")
        require(verify_readiness_report(report), "readiness digest did not verify")

    case("source and CRM are ready without clients", source_ready_without_clients)

    def route_and_language_contract() -> None:
        config = json.loads((ROOT / "config" / "pre-client-readiness.json").read_text(encoding="utf-8"))
        content = json.loads((ROOT / "config" / "web-route-content.json").read_text(encoding="utf-8"))
        routes = config["required_website_routes"]
        require(len(routes) == 10, "expected ten website routes")
        expected = {route for route in routes if route != "index.html"}
        require(set(content["routes"]) == expected, "route contract mismatch")
        require(all(set(content["routes"][route]) == {"en", "es"} for route in expected), "route language parity failed")

    case("ten bilingual route definitions are complete", route_and_language_contract)

    def preview_build_is_safe() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "preview"
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_web_release.py"),
                "--profile", "preview", "--output", str(output),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            info = json.loads((output / "RELEASE_BUILD.json").read_text(encoding="utf-8"))
            require(info["route_count"] == 10, "preview route count drift")
            require(info["intake_enabled"] is False, "preview intake enabled")
            require(info["indexable"] is False, "preview became indexable")
            require("Disallow: /" in (output / "robots.txt").read_text(encoding="utf-8"), "preview robots unsafe")
            require(all((output / route).is_file() for route in info["routes"]), "preview route missing")
            require(all("noindex,nofollow" in (output / route).read_text(encoding="utf-8") for route in info["routes"]), "preview route lost noindex")

    case("preview release is complete and non-live", preview_build_is_safe)

    def staging_requires_https_and_stays_noindex() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "staging"
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_web_release.py"),
                "--profile", "staging",
                "--endpoint", "https://synthetic.invalid/exec",
                "--output", str(output),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            info = json.loads((output / "RELEASE_BUILD.json").read_text(encoding="utf-8"))
            require(info["intake_enabled"] is True, "staging endpoint not enabled")
            require(info["synthetic_only"] is True, "staging not marked synthetic")
            require(info["indexable"] is False, "staging became indexable")
            require("https://synthetic.invalid/exec" in (output / "config.js").read_text(encoding="utf-8"), "staging endpoint missing")
            require("noindex,nofollow" in (output / "services.html").read_text(encoding="utf-8"), "staging route lost noindex")

    case("staging is HTTPS-only and synthetic", staging_requires_https_and_stays_noindex)

    def live_build_fails_without_evidence() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_web_release.py"),
                "--profile", "live",
                "--endpoint", "https://live.invalid/exec",
                "--output", str(Path(temp_dir) / "live"),
            ], cwd=ROOT, capture_output=True, text=True)
            require(result.returncode != 0, "live build passed without evidence")
            require("activation gates are incomplete" in result.stderr + result.stdout, "unexpected live failure")

    case("live release fails closed without activation evidence", live_build_fails_without_evidence)

    def live_build_passes_with_complete_evidence() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            evidence = temp / "activation.json"
            evidence.write_text(json.dumps(complete_activation()), encoding="utf-8")
            output = temp / "live"
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_web_release.py"),
                "--profile", "live",
                "--endpoint", "https://live.invalid/exec",
                "--activation-evidence", str(evidence),
                "--output", str(output),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            info = json.loads((output / "RELEASE_BUILD.json").read_text(encoding="utf-8"))
            require(info["indexable"] is True, "approved live release not indexable")
            require(info["synthetic_only"] is False, "live release still synthetic")
            require("index,follow" in (output / "index.html").read_text(encoding="utf-8"), "live index not activated")
            require("index,follow" in (output / "legal.html").read_text(encoding="utf-8"), "live legal route not activated")
            require("Allow: /" in (output / "robots.txt").read_text(encoding="utf-8"), "live robots blocked")
            require((output / "SHA256SUMS").is_file(), "live checksums missing")

    case("complete evidence can build a live artifact", live_build_passes_with_complete_evidence)

    def crm_header_drift_is_detected() -> None:
        snapshot = crm_snapshot()
        snapshot["sheets"]["Leads"]["headers"] = snapshot["sheets"]["Leads"]["headers"][:-1]
        report = audit_pre_client_readiness(ROOT, crm_snapshot=snapshot)
        require(report["states"]["crm_architecture_ready"] is False, "CRM header drift accepted")
        failed = {item["name"] for item in report["checks"] if not item["passed"]}
        require("crm_headers_Leads" in failed, "Lead header failure not surfaced")

    case("CRM header drift fails readiness", crm_header_drift_is_detected)

    def service_alias_and_layers_are_controlled() -> None:
        contract = json.loads((ROOT / "schemas" / "crm" / "sheets-contract.json").read_text(encoding="utf-8"))
        require(contract["service_codes"]["legacy_aliases"] == {"OSP": "IOP"}, "legacy alias drift")
        require(contract["service_codes"]["active_principal"] == ["IVA", "CRM", "IOP"], "principal service drift")
        require(contract["service_codes"]["addon"] == ["WAB"], "add-on drift")
        require(contract["service_codes"]["hidden_until_delivery_evidence"] == ["ISS"], "hidden bundle drift")

    case("service codes and legacy alias are controlled", service_alias_and_layers_are_controlled)

    def complete_activation_changes_only_gate_state() -> None:
        report = audit_pre_client_readiness(ROOT, crm_snapshot=crm_snapshot(), activation_evidence=complete_activation())
        require(report["states"]["live_intake_ready"] is True, "complete activation did not open live intake")
        require(report["states"]["paid_delivery_ready"] is True, "complete legal activation did not open paid delivery")
        require(report["controls"]["external_message_sent"] is False, "audit sent a message")
        require(report["controls"]["crm_mutated"] is False, "audit mutated CRM")

    case("activation evidence changes readiness without side effects", complete_activation_changes_only_gate_state)

    def source_config_contains_no_live_endpoint() -> None:
        config = (ROOT / "apps" / "web" / "config.js").read_text(encoding="utf-8")
        require('intakeEndpoint: ""' in config, "source contains an endpoint")
        require("demoMode: true" in config, "source is not demonstration-safe")
        require("https://live.invalid" not in config, "test endpoint leaked into source")

    case("source remains endpoint-free", source_config_contains_no_live_endpoint)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
