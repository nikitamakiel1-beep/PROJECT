#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
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
    audit_mod = load_module(ROOT / "scripts" / "audit_market_entry_licensing.py", "market_entry_audit")
    licensing = json.loads((ROOT / "config" / "market-entry-licensing.json").read_text(encoding="utf-8"))
    staging = json.loads((ROOT / "config" / "staging-release.json").read_text(encoding="utf-8"))

    cases = []

    baseline = audit_mod.audit(licensing, staging)
    assert baseline["blockers"] == []
    assert baseline["staging_build_permitted"] is True
    assert baseline["live_publication_permitted"] is False
    cases.append("baseline_audit_passes")

    assert licensing["sector_specific_authorisation"]["final_legal_opinion"] is False
    assert "no_specific_professional_licence_identified" in licensing["sector_specific_authorisation"]["classification"]
    cases.append("no_false_sector_licence_opinion")

    assert all(value == "frozen_by_owner" for value in licensing["frozen_reviews"].values())
    cases.append("professional_reviews_are_frozen")

    requirement_ids = {item["id"] for item in licensing["requirements"]}
    assert requirement_ids == audit_mod.REQUIRED_IDS
    cases.append("required_market_entry_controls_are_complete")

    b2c = next(item for item in licensing["requirements"] if item["id"] == "B2C_CONSUMER")
    complaints = next(item for item in licensing["requirements"] if item["id"] == "CATALONIA_COMPLAINT_FORMS")
    assert b2c["status"].startswith("conditional_")
    assert complaints["status"].startswith("conditional_")
    cases.append("consumer_controls_are_conditional_not_ignored")

    tampered = deepcopy(staging)
    tampered["endpoint"] = "https://staging.example.com/exec"
    assert any("reserved_invalid_domain" in item for item in audit_mod.audit(licensing, tampered)["blockers"])
    cases.append("real_staging_endpoint_is_rejected")

    tampered = deepcopy(licensing)
    tampered["current_decision"]["live_publication_permitted"] = True
    assert "unsafe_decision:live_publication_permitted" in audit_mod.audit(tampered, staging)["blockers"]
    cases.append("live_publication_cannot_bypass_frozen_review")

    tampered = deepcopy(licensing)
    tampered["frozen_reviews"]["professional_legal_review"] = "approved"
    assert "review_not_frozen:professional_legal_review" in audit_mod.audit(tampered, staging)["blockers"]
    cases.append("frozen_review_cannot_be_relabelled_approved")

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "web-staging"
        run = subprocess.run(
            [
                "python", str(ROOT / "scripts" / "build_web_release.py"),
                "--profile", "staging",
                "--endpoint", staging["endpoint"],
                "--output", str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stderr or run.stdout
        build = json.loads((output / "RELEASE_BUILD.json").read_text(encoding="utf-8"))
        config = (output / "config.js").read_text(encoding="utf-8")
        assert build["profile"] == "staging"
        assert build["synthetic_only"] is True
        assert build["indexable"] is False
        assert build["route_count"] == 10
        assert "Disallow: /" in (output / "robots.txt").read_text(encoding="utf-8")
        assert "noindex,nofollow" in (output / "index.html").read_text(encoding="utf-8")
        assert staging["endpoint"] in config
        cases.append("staging_artifact_is_synthetic_noindex_and_complete")

    first = audit_mod.audit(licensing, staging)
    second = audit_mod.audit(licensing, staging)
    assert first["evidence_digest"] == second["evidence_digest"]
    cases.append("audit_digest_is_deterministic")

    assert len(cases) == 10
    print(f"market-entry licensing validation passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
