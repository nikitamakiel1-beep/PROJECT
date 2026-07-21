#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "apps/web/index.html",
    "apps/web/assets/styles.css",
    "apps/web/assets/app.js",
    "apps/web/assets/translations.json",
    "apps/web/assets/demonstrations.json",
    "schemas/services.json",
    "schemas/crm/lead.schema.json",
    "automations/google-apps-script/Code.gs",
    "automations/google-apps-script/IntakeCore.gs",
    "automations/google-apps-script/ProviderTest.gs",
    "orchestration/state.json",
    "orchestration/CURRENT.md",
    "scripts/test_web.py",
    "scripts/intake_contract_harness.js",
    "scripts/test_intake_contract.py",
    "schemas/crm/sheets-contract.json"
]


def main() -> None:
    errors = []
    for path in REQUIRED:
        if not (ROOT / path).exists():
            errors.append(f"missing required file: {path}")
    for path in ROOT.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
    services = json.loads((ROOT / "schemas/services.json").read_text(encoding="utf-8"))
    codes = [item["code"] for item in services]
    if len(codes) != len(set(codes)):
        errors.append("duplicate service code")
    if not any(item.get("status") == "active" for item in services):
        errors.append("no active service")
    if (ROOT / "apps/web/assets/services.json").exists():
        errors.append("duplicate service catalogue found in website assets")
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    actual = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)
    listed = sorted(manifest.get("files", []))
    if actual != listed:
        missing = sorted(set(actual) - set(listed))
        stale = sorted(set(listed) - set(actual))
        errors.append(f"manifest mismatch; unlisted={missing}, stale={stale}")
    if errors:
        raise SystemExit("repository validation failed:\n- " + "\n- ".join(errors))
    print("repository validation passed")


if __name__ == "__main__":
    main()
