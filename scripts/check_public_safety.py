#!/usr/bin/env python3
"""Reject operational identifiers, secrets and provider URLs in a public repository."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".gs", ".html", ".css", ".example"}
EXCLUDED_PARTS = {".git", "dist", "__pycache__"}
PATTERNS = {
    "Google Sheets file URL": re.compile(r"https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]{20,}"),
    "Apps Script web-app URL": re.compile(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "assigned spreadsheet ID": re.compile(r"SPREADSHEET_ID\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}"),
    "assigned live web-app URL": re.compile(r"WEB_APP_URL\s*[:=]\s*['\"]?https://"),
}


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"CODEOWNERS", ".gitignore", ".editorconfig"}


def main() -> None:
    findings: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts) or not is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {label}")
    if findings:
        raise SystemExit("public safety check failed:\n- " + "\n- ".join(findings))
    print("public safety check passed")


if __name__ == "__main__":
    main()
