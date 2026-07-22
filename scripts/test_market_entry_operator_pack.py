#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    mod = load_module(ROOT / "scripts" / "audit_market_entry_operator_pack.py", "operator_pack_audit")
    operator_pack = json.loads((ROOT / "config" / "market-entry-operator-pack.json").read_text(encoding="utf-8"))
    licensing = json.loads((ROOT / "config" / "market-entry-licensing.json").read_text(encoding="utf-8"))
    staging = json.loads((ROOT / "config" / "staging-release.json").read_text(encoding="utf-8"))

    cases: list[str] = []

    baseline = mod.audit(operator_pack, licensing, staging)
    assert baseline["blockers"] == []
    assert baseline["operator_pack_ready"] is True
    assert baseline["official_filings_verified"] == 0
    assert baseline["staging_build_permitted"] is True
    assert baseline["paid_contracting_permitted"] is False
    cases.append("baseline_operator_pack_passes_without_claiming_filings")

    assert tuple(item["id"] for item in operator_pack["pre_invoice_sequence"]) == mod.SEQUENCE_IDS
    cases.append("pre_invoice_sequence_is_exact_and_ordered")

    services = {item["service_code"]: item for item in operator_pack["service_boundaries"]}
    assert set(services) == mod.SERVICE_CODES
    cases.append("all_market_services_have_explicit_boundaries")

    assert "audit of annual accounts" in services["IVA"]["prohibited_scope"]
    assert "financial statement assurance" in services["IVA"]["prohibited_scope"]
    cases.append("visibility_audit_cannot_become_statutory_accounts_audit")

    assert "article_28_processor_agreement" in services["CRM"]["mandatory_before_client_data"]
    assert "autonomous prospect contact" in services["CRM"]["prohibited_scope"]
    cases.append("crm_service_requires_processor_custody_and_no_autonomous_contact")

    assert "autonomous outbound messaging" in services["WAB"]["prohibited_scope"]
    assert "client_account_ownership" in services["WAB"]["mandatory_before_delivery"]
    cases.append("whatsapp_setup_preserves_client_account_and_contact_control")

    for marker in ("employment decisions", "credit eligibility decisions", "biometric categorisation", "emotion recognition"):
        assert marker in services["AI"]["prohibited_scope"]
    assert "Article_50_transparency_assessment" in services["AI"]["mandatory_before_live"]
    cases.append("ai_scope_excludes_sensitive_decisions_and_requires_transparency")

    assert all(value == "frozen_by_owner" for key, value in operator_pack["owner_instruction"].items() if key.startswith("professional_"))
    assert operator_pack["current_state"]["professional_reviews"] == "frozen_by_owner"
    cases.append("professional_reviews_remain_frozen_not_approved")

    tampered = deepcopy(operator_pack)
    tampered["current_state"]["paid_contracting_permitted"] = True
    assert "unsafe_current_state:paid_contracting_permitted" in mod.audit(tampered, licensing, staging)["blockers"]
    cases.append("paid_contracting_bypass_is_rejected")

    tampered = deepcopy(operator_pack)
    tampered["pre_invoice_sequence"][2]["status"] = "verified"
    assert "unsupported_verified_status:AEAT_036" in mod.audit(tampered, licensing, staging)["blockers"]
    cases.append("official_registration_cannot_be_claimed_without_external_evidence")

    tampered = deepcopy(operator_pack)
    tampered["service_boundaries"] = [item for item in tampered["service_boundaries"] if item["service_code"] != "WEB"]
    assert "service_boundary_set_mismatch" in mod.audit(tampered, licensing, staging)["blockers"]
    cases.append("missing_service_boundary_is_rejected")

    first = mod.audit(operator_pack, licensing, staging)
    second = mod.audit(operator_pack, licensing, staging)
    assert first["evidence_digest"] == second["evidence_digest"]
    cases.append("operator_receipt_is_deterministic")

    assert len(cases) == 12
    print(f"market-entry operator pack validation passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
