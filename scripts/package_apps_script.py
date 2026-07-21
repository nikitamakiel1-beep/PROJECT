#!/usr/bin/env python3
"""Create a deterministic, public-safe Stage 003 Apps Script deployment bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "automations" / "google-apps-script"
FILES = [
    "IntakeCore.gs",
    "Code.gs",
    "ProviderTest.gs",
    "appsscript.json",
    "DEPLOYMENT.md",
    "SYNTHETIC_TEST.md",
]
FORBIDDEN = (
    "https://script.google.com/" + "macros/s/",
    "https://docs.google.com/" + "spreadsheets/d/",
    "-----BEGIN " + "PRIVATE KEY-----",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def deterministic_zip(source_dir: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(source_dir).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build(output_dir: Path, zip_path: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename in FILES:
        source = SOURCE / filename
        if not source.is_file():
            raise SystemExit(f"Apps Script bundle failed: missing {filename}")
        text = source.read_text(encoding="utf-8")
        for marker in FORBIDDEN:
            if marker in text:
                raise SystemExit(f"Apps Script bundle failed: operational value detected in {filename}")
        shutil.copy2(source, output_dir / filename)

    install_order = """Stage 003 synthetic provider bundle\n\nInstall in this order inside a bound Apps Script project:\n1. IntakeCore.gs\n2. Code.gs\n3. ProviderTest.gs\n4. appsscript.json, only when replacing the manifest intentionally\n\nThen follow DEPLOYMENT.md. Keep every identifier and deployment URL outside GitHub.\n"""
    (output_dir / "INSTALL_ORDER.txt").write_text(install_order, encoding="utf-8")

    checksums = {path.name: sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file()}
    info = {
        "artifact": "stage-003-apps-script-provider-bundle",
        "synthetic_only": True,
        "contains_credentials": False,
        "contains_provider_ids": False,
        "files": checksums,
    }
    (output_dir / "BUNDLE_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    deterministic_zip(output_dir, zip_path)
    print(f"Apps Script bundle passed: {zip_path} sha256={sha256(zip_path)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "apps-script")
    parser.add_argument("--zip", type=Path, default=ROOT / "dist" / "stage-003-apps-script.zip")
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    zip_path = args.zip if args.zip.is_absolute() else ROOT / args.zip
    build(output_dir.resolve(), zip_path.resolve())


if __name__ == "__main__":
    main()
