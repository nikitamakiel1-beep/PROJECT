from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def audit_pre_client_readiness(
    root: Path,
    *,
    crm_snapshot: dict[str, Any] | None = None,
    activation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit all pre-client source and architecture gates.

    Existing clients are not required. A header-only CRM is valid and must stay
    empty until real evidence exists.
    """
    root = root.resolve()
    config = _json(root / "config" / "pre-client-readiness.json")
    route_content = _json(root / "config" / "web-route-content.json")
    services = _json(root / "schemas" / "services.json")
    crm_contract = _json(root / "schemas" / "crm" / "sheets-contract.json")

    activation = dict(config["external_activation_gates"])
    for key, value in (activation_evidence or {}).items():
        if key in activation:
            activation[key] = bool(value)

    checks: list[Check] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append(Check(name, bool(condition), detail))

    required_routes = config["required_website_routes"]
    generated_routes = set(route_content.get("routes", {}))
    expected_generated = {route for route in required_routes if route != "index.html"}
    check(
        "website_route_contract",
        generated_routes == expected_generated,
        f"defined={sorted(generated_routes)}",
    )
    check(
        "website_route_language_parity",
        all(set(route_content["routes"][route]) == {"en", "es"} for route in generated_routes),
        "every generated route has EN and ES",
    )
    check(
        "website_assets_complete",
        all((root / "apps" / "web" / path).is_file() for path in config["required_website_assets"]),
        f"{len(config['required_website_assets'])} required assets",
    )

    source_html = (root / "apps" / "web" / "index.html").read_text(encoding="utf-8")
    source_config = (root / "apps" / "web" / "config.js").read_text(encoding="utf-8")
    check("source_site_noindex", "noindex,nofollow" in source_html, "source remains non-indexable")
    check("source_intake_disabled", "demoMode: true" in source_config and 'intakeEndpoint: ""' in source_config, "blank endpoint")
    check("release_builder_present", (root / "scripts" / "build_web_release.py").is_file(), "profile-aware release builder")

    codes = {item["code"] for item in services}
    active = {item["code"] for item in services if item.get("status") == "active"}
    check("canonical_service_codes", codes == set(config["canonical_service_codes"]), f"codes={sorted(codes)}")
    check("active_principal_services", active == set(config["active_principal_service_codes"]), f"active={sorted(active)}")
    check(
        "legacy_service_alias",
        crm_contract.get("service_codes", {}).get("legacy_aliases") == config["legacy_service_aliases"],
        "OSP is normalised to IOP",
    )
    check(
        "crm_zero_state_supported",
        crm_contract.get("zero_state", {}).get("valid_before_clients") is True,
        "header-only business tables are valid",
    )
    required_sheet_names = set(config["required_crm_sheets"])
    contract_sheet_names = set(crm_contract.get("sheets", {})) | set(crm_contract.get("operational_views", {}))
    check("crm_contract_complete", required_sheet_names <= contract_sheet_names, f"contract={sorted(contract_sheet_names)}")

    if crm_snapshot is not None:
        observed_sheets = crm_snapshot.get("sheets", {})
        check("crm_snapshot_sheet_set", required_sheet_names <= set(observed_sheets), f"observed={sorted(observed_sheets)}")
        for sheet, expected in crm_contract.get("sheets", {}).items():
            if sheet in required_sheet_names:
                observed = list(observed_sheets.get(sheet, {}).get("headers", []))
                check(f"crm_headers_{sheet}", observed == expected, f"observed={len(observed)} expected={len(expected)}")
        business_rows = sum(
            int(observed_sheets.get(sheet, {}).get("business_rows", 0))
            for sheet in ("Companies", "Contacts", "Leads", "Opportunities", "Activities")
        )
        check("no_clients_required", business_rows >= 0, f"business_rows={business_rows}; zero is valid")
    else:
        check("crm_snapshot_optional", True, "source audit does not require a connected CRM")

    source_map = {
        "website_routes_complete": all(item.passed for item in checks if item.name in {"website_route_contract","website_route_language_parity"}),
        "website_bilingual": next(item.passed for item in checks if item.name == "website_route_language_parity"),
        "website_light_dark": "igv-theme" in source_html,
        "website_mobile_desktop": 'name="viewport"' in source_html,
        "website_local_recommender": (root / "apps" / "web" / "assets" / "neural-recommender.mjs").is_file(),
        "website_demonstrations_complete": (root / "apps" / "web" / "assets" / "demonstrations.json").is_file(),
        "website_release_builder": (root / "scripts" / "build_web_release.py").is_file(),
        "crm_schema_complete": next(item.passed for item in checks if item.name == "crm_contract_complete"),
        "crm_zero_state_supported": next(item.passed for item in checks if item.name == "crm_zero_state_supported"),
        "crm_duplicate_safety_source_complete": (root / "automations" / "google-apps-script" / "IntakeCore.gs").is_file(),
        "crm_follow_up_source_complete": (root / "automations" / "google-apps-script" / "DailyFollowUp.gs").is_file(),
        "crm_neural_bridge_source_complete": (root / "automations" / "google-apps-script" / "NeuralBridge.gs").is_file(),
        "service_delivery_templates_complete": all(
            (root / "templates" / "services" / name).is_file()
            for name in ("visibility-audit.md", "crm-setup-handover.md", "sales-one-pager.md")
        ),
        "commercial_controls_source_complete": all(
            (root / "templates" / "commercial" / name).is_file()
            for name in ("proposal.md", "quality-checklist.md", "commercial-terms-control.md")
        ),
        "legal_placeholders_source_complete": {"privacy.html", "cookies.html", "legal.html"} <= generated_routes,
        "provider_bundle_source_complete": (root / "scripts" / "package_apps_script.py").is_file(),
        "rollback_and_cleanup_source_complete": (
            root / "docs" / "setup" / "STAGE_003_PROVIDER_ACTIVATION_RUNBOOK.md"
        ).is_file(),
    }
    for name in config["source_requirements"]:
        checks.append(Check(name, source_map.get(name, False), "source requirement"))

    source_ready = all(source_map[name] for name in config["source_requirements"])
    construction_ready = source_ready and (root / "scripts" / "build_web_release.py").is_file()
    crm_architecture_ready = all(
        item.passed for item in checks
        if item.name.startswith("crm_")
        or item.name in {"canonical_service_codes", "active_principal_services", "legacy_service_alias", "no_clients_required"}
    )
    client_acquisition_ready = source_ready and construction_ready and crm_architecture_ready

    live_keys = tuple(config["external_activation_gates"])
    live_intake_ready = client_acquisition_ready and all(activation[key] is True for key in live_keys)
    paid_delivery_ready = client_acquisition_ready and all(
        activation[key] is True for key in (
            "privacy_professional_approval",
            "legal_and_invoicing_professional_approval",
            "human_live_release_approval",
        )
    )

    requirement_checks = [item for item in checks if item.name in config["source_requirements"]]
    source_pct = round(100 * sum(item.passed for item in requirement_checks) / len(requirement_checks), 1)

    report = {
        "schema_version": 1,
        "as_of": config["as_of"],
        "states": {
            "source_ready": source_ready,
            "construction_ready": construction_ready,
            "crm_architecture_ready": crm_architecture_ready,
            "client_acquisition_ready": client_acquisition_ready,
            "live_intake_ready": live_intake_ready,
            "paid_delivery_ready": paid_delivery_ready,
        },
        "source_completion_pct": source_pct,
        "activation_gates": activation,
        "checks": [{"name": item.name, "passed": item.passed, "detail": item.detail} for item in checks],
        "controls": {
            "clients_required_for_source_readiness": False,
            "synthetic_client_records_created": False,
            "external_message_sent": False,
            "crm_mutated": False,
            "provider_activated": False,
            "professional_legal_approval_inferred": False,
            "human_release_required": True,
        },
    }
    report["report_sha256"] = _digest(report)
    return report


def verify_readiness_report(report: dict[str, Any]) -> bool:
    candidate = dict(report)
    supplied = candidate.pop("report_sha256", "")
    return bool(supplied) and supplied == _digest(candidate)
