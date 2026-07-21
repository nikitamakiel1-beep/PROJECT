#!/usr/bin/env python3
"""Build a self-contained, synthetic-only website preview artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SOURCE = ROOT / "apps" / "web"
SERVICE_SOURCE = ROOT / "schemas" / "services.json"
SERVICE_FETCH_SOURCE = "fetchJson('../../schemas/services.json')"
SERVICE_FETCH_PREVIEW = "fetchJson('schemas/services.json')"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output: Path) -> None:
    if not WEB_SOURCE.is_dir() or not SERVICE_SOURCE.is_file():
        raise SystemExit("preview build failed: website or canonical service source is missing")

    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WEB_SOURCE, output)

    schema_dir = output / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVICE_SOURCE, schema_dir / "services.json")

    app_path = output / "assets" / "app.js"
    app_text = app_path.read_text(encoding="utf-8")
    if SERVICE_FETCH_SOURCE not in app_text:
        raise SystemExit("preview build failed: canonical service fetch expression changed")
    app_path.write_text(app_text.replace(SERVICE_FETCH_SOURCE, SERVICE_FETCH_PREVIEW), encoding="utf-8")

    config_text = (output / "config.js").read_text(encoding="utf-8")
    if "demoMode: true" not in config_text or 'intakeEndpoint: ""' not in config_text:
        raise SystemExit("preview build failed: preview must remain synthetic-only with no endpoint")

    build_info = {
        "artifact": "international-growth-venture-web-preview",
        "synthetic_only": True,
        "intake_enabled": False,
        "canonical_service_source": "schemas/services.json",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", ""),
    }
    (output / "PREVIEW_BUILD.json").write_text(json.dumps(build_info, indent=2) + "\n", encoding="utf-8")

    files = sorted(path for path in output.rglob("*") if path.is_file())
    checksum_lines = [f"{file_sha256(path)}  {path.relative_to(output).as_posix()}" for path in files]
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if not (output / "index.html").is_file():
        raise SystemExit("preview build failed: index.html was not produced")
    print(f"preview build passed: {output} ({len(files) + 1} files)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "web-preview")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    build(output.resolve())


if __name__ == "__main__":
    main()
