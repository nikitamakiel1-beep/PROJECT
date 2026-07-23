#!/usr/bin/env python3
"""Controlled stage handoff manager.

This script does not invent or execute business decisions. It validates the
stage contract and advances the repository to an instruction already written
and reviewed by the current stage.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "orchestration/state.json"
CURRENT_PATH = ROOT / "orchestration/CURRENT.md"
REQUIRED_INSTRUCTION_HEADINGS = [
    "## Objective", "## Read first", "## Work", "## Acceptance criteria",
    "## Exclusions", "## Required handoff"
]
REQUIRED_REPORT_HEADINGS = [
    "## Outcome", "## Tests and evidence", "## Risks and unresolved items",
    "## Rollback", "## Next instruction"
]


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def validate_markdown(path: Path, headings: list[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing file: {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    for heading in headings:
        if heading not in text:
            errors.append(f"{path.relative_to(ROOT)} missing heading: {heading}")
    if len(text.strip()) < 300:
        errors.append(f"{path.relative_to(ROOT)} is too short to be actionable")
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    state = load_state()
    instruction = ROOT / state["current_instruction"]
    errors.extend(validate_markdown(instruction, REQUIRED_INSTRUCTION_HEADINGS))
    previous = ROOT / state["previous_report"]
    errors.extend(validate_markdown(previous, REQUIRED_REPORT_HEADINGS))
    if state["current_stage"] != state["last_completed_stage"] + 1:
        errors.append("current_stage must equal last_completed_stage + 1")
    return errors


def show() -> None:
    state = load_state()
    print(json.dumps(state, indent=2))
    instruction = ROOT / state["current_instruction"]
    print("\n--- CURRENT INSTRUCTION ---\n")
    print(instruction.read_text(encoding="utf-8"))


def complete(stage: int, report: str, next_instruction: str) -> None:
    state = load_state()
    if stage != state["current_stage"]:
        raise SystemExit(f"expected stage {state['current_stage']}, received {stage}")
    report_path = ROOT / report
    next_path = ROOT / next_instruction
    errors = []
    errors.extend(validate_markdown(report_path, REQUIRED_REPORT_HEADINGS))
    errors.extend(validate_markdown(next_path, REQUIRED_INSTRUCTION_HEADINGS))
    match = re.search(r"stage-(\d{3})", next_instruction)
    if not match or int(match.group(1)) != stage + 1:
        errors.append("next instruction filename must contain the next sequential stage number")
    if errors:
        raise SystemExit("handoff validation failed:\n- " + "\n- ".join(errors))
    state.update({
        "last_completed_stage": stage,
        "current_stage": stage + 1,
        "previous_report": report,
        "current_instruction": next_instruction,
        "status": "ready",
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    CURRENT_PATH.write_text(
        f"# Current stage\n\n"
        f"- Stage: **{stage + 1:03d}**\n"
        f"- Instruction: [`{next_instruction.replace('orchestration/', '')}`]"
        f"({next_instruction.replace('orchestration/', '')})\n"
        f"- Previous report: [`{report.replace('orchestration/', '')}`]"
        f"({report.replace('orchestration/', '')})\n"
        f"- State: `ready`\n\n"
        "The executing agent must read the instruction and prior report before modifying files.\n",
        encoding="utf-8"
    )
    print(f"advanced to stage {stage + 1:03d}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    sub.add_parser("validate")
    c = sub.add_parser("complete")
    c.add_argument("--stage", type=int, required=True)
    c.add_argument("--report", required=True)
    c.add_argument("--next-instruction", required=True)
    args = parser.parse_args()
    if args.command == "show":
        show()
    elif args.command == "validate":
        errors = validate()
        if errors:
            raise SystemExit("validation failed:\n- " + "\n- ".join(errors))
        print("orchestration contract valid")
    else:
        complete(args.stage, args.report, args.next_instruction)


if __name__ == "__main__":
    main()
