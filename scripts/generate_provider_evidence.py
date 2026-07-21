#!/usr/bin/env python3
"""Compile a privacy-minimised Stage 003 report from provider-suite JSON evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CASES = [
    "new_submission",
    "exact_retry",
    "existing_company_new_contact",
    "existing_contact",
    "malformed_email",
    "missing_company",
    "invalid_service",
    "injected_write_failure",
]
SHEETS = ["Companies", "Contacts", "Leads", "Activities", "Automation Log"]


def load_evidence(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"provider evidence rejected: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("provider evidence rejected: root must be an object")
    return data


def validate(data: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[str] = []
    if data.get("synthetic_only") is not True:
        errors.append("synthetic_only must be true")
    if data.get("passed") is not True:
        errors.append("provider suite did not pass")
    cleanup = data.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup.get("passed") is not True:
        errors.append("cleanup did not pass")
    run_id = str(data.get("run_id", ""))
    if not run_id.startswith("stage003-"):
        errors.append("run_id does not use the Stage 003 prefix")

    cases = data.get("cases")
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        cases = []
    names = [str(item.get("name", "")) for item in cases if isinstance(item, dict)]
    if names != EXPECTED_CASES:
        errors.append(f"case order mismatch: expected {EXPECTED_CASES}, received {names}")
    for item in cases:
        if not isinstance(item, dict) or item.get("passed") is not True:
            errors.append(f"case failed: {item.get('name', 'unknown') if isinstance(item, dict) else 'invalid'}")
        for key in ("expected_delta", "actual_delta"):
            delta = item.get(key, {}) if isinstance(item, dict) else {}
            if not isinstance(delta, dict) or any(sheet not in delta for sheet in SHEETS):
                errors.append(f"incomplete {key} for {item.get('name', 'unknown') if isinstance(item, dict) else 'invalid'}")
    if errors:
        raise SystemExit("provider evidence rejected:\n- " + "\n- ".join(errors))
    return cases


def response_summary(item: dict[str, Any]) -> str:
    response = item.get("response")
    if not isinstance(response, dict):
        return "unavailable"
    if response.get("ok") is True and response.get("duplicate") is True:
        return "accepted duplicate"
    if response.get("ok") is True:
        return "accepted"
    return f"rejected: {response.get('error', 'unknown_error')}"


def delta_text(delta: dict[str, Any]) -> str:
    return ", ".join(f"{sheet}={int(delta.get(sheet, 0))}" for sheet in SHEETS)


def compile_markdown(data: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    lines = [
        "# Stage 003 provider-runtime evidence",
        "",
        "## Decision",
        "",
        "**Provider gate passed.** This report is generated only when all expected HTTP cases and final cleanup pass.",
        "",
        "## Run metadata",
        "",
        f"- Run ID: `{data['run_id']}`",
        f"- Started: `{data.get('started_at', '')}`",
        f"- Finished: `{data.get('finished_at', '')}`",
        "- Synthetic-only execution: `true`",
        "- Production CRM modified: `false`",
        "- Deployment URL, spreadsheet ID, names, emails and submission IDs: intentionally omitted",
        "",
        "## Cases",
        "",
        "| Case | HTTP | Result | Expected row delta | Actual row delta |",
        "|---|---:|---|---|---|",
    ]
    for item in cases:
        lines.append(
            f"| `{item['name']}` | {int(item.get('response_code', 0))} | {response_summary(item)} | "
            f"{delta_text(item['expected_delta'])} | {delta_text(item['actual_delta'])} |"
        )
    lines.extend([
        "",
        "## Cleanup",
        "",
    ])
    cleanup = data["cleanup"]
    for sheet in SHEETS:
        result = cleanup.get("sheets", {}).get(sheet, {})
        lines.append(
            f"- {sheet}: removed `{int(result.get('removed', 0))}`, "
            f"final count restored=`{bool(result.get('passed'))}`"
        )
    lines.extend([
        "",
        "## Activation boundary",
        "",
        "Passing this synthetic provider gate does not activate public intake. Production activation still requires privacy wording, abuse controls, retention approval, repository privacy and an explicit human go/no-go decision.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "orchestration" / "evidence" / "stage-003-provider-runtime.md")
    args = parser.parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    data = load_evidence(input_path.resolve())
    cases = validate(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compile_markdown(data, cases), encoding="utf-8")
    print(f"provider evidence accepted: {output_path}")


if __name__ == "__main__":
    main()
