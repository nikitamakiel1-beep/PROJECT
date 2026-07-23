#!/usr/bin/env python3
"""One-command local operator control for cases and release readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.autopptx_pipeline import create_project_workspace  # noqa: E402
from intelligence.real_estate.operator_control import (  # noqa: E402
    build_case_control,
    evaluate_case,
    render_case_markdown,
    update_component,
)
from intelligence.real_estate.release_readiness import (  # noqa: E402
    evaluate_all_modes,
    load_json,
    render_markdown,
)

DEFAULT_POLICY = ROOT / "config" / "real-estate-release-readiness-rc3.json"
DEFAULT_EVIDENCE = (
    ROOT
    / "evidence"
    / "readiness"
    / "2026-07-23-real-estate-release-evidence-rc3.json"
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def load_case(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("case control must be a JSON object")
    return value


def command_init(args: argparse.Namespace) -> int:
    policy = load_json(args.policy)
    component_ids = [item["id"] for item in policy["case_components"]]
    workspace = create_project_workspace(args.root, args.project_code)
    control = build_case_control(
        project_code=args.project_code,
        title=args.title,
        source_kind=args.source_kind,
        created_on=args.date,
        component_ids=component_ids,
    )
    case_path = Path(workspace["project"]) / "case-control.json"
    if case_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"case control already exists: {case_path}; use --overwrite deliberately"
        )
    write_json(case_path, control)
    summary = evaluate_case(policy=policy, control=control)
    markdown_path = Path(workspace["project"]) / "CASE_STATUS.md"
    markdown_path.write_text(render_case_markdown(summary), encoding="utf-8")
    emit(
        {
            "case_control": str(case_path),
            "status_report": str(markdown_path),
            "workspace": workspace,
            "summary": summary,
        }
    )
    return 0


def command_mark(args: argparse.Namespace) -> int:
    case_path = Path(args.case)
    control = load_case(case_path)
    updated = update_component(
        control=control,
        component_id=args.component,
        status=args.status,
        updated_on=args.date,
        actor_token=args.actor,
        evidence_pointer=args.evidence,
        note=args.note,
    )
    write_json(case_path, updated)
    policy = load_json(args.policy)
    summary = evaluate_case(policy=policy, control=updated)
    markdown_path = case_path.parent / "CASE_STATUS.md"
    markdown_path.write_text(render_case_markdown(summary), encoding="utf-8")
    emit({"case_control": str(case_path), "summary": summary})
    return 0


def command_status(args: argparse.Namespace) -> int:
    policy = load_json(args.policy)
    summary = evaluate_case(policy=policy, control=load_case(Path(args.case)))
    if args.markdown:
        Path(args.markdown).write_text(render_case_markdown(summary), encoding="utf-8")
    emit(summary)
    return 0


def command_release_status(args: argparse.Namespace) -> int:
    policy = load_json(args.policy)
    evidence = load_json(args.evidence)
    summary = evaluate_all_modes(policy=policy, evidence=evidence)
    if args.output_json:
        write_json(Path(args.output_json), summary)
    if args.output_markdown:
        Path(args.output_markdown).write_text(render_markdown(summary), encoding="utf-8")
    emit(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local real-estate operator case and release control"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-case", help="Create a project workspace and case control")
    init.add_argument("root")
    init.add_argument("project_code")
    init.add_argument("title")
    init.add_argument(
        "source_kind",
        choices=["listing_link", "confidential", "off_market", "bank_or_fund", "manual"],
    )
    init.add_argument("--date", required=True)
    init.add_argument("--policy", default=str(DEFAULT_POLICY))
    init.add_argument("--overwrite", action="store_true")
    init.set_defaults(func=command_init)

    mark = sub.add_parser("mark", help="Update one case component")
    mark.add_argument("case")
    mark.add_argument("component")
    mark.add_argument(
        "status",
        choices=[
            "not_started",
            "in_progress",
            "ready_for_review",
            "approved",
            "blocked",
            "not_applicable",
        ],
    )
    mark.add_argument("--date", required=True)
    mark.add_argument("--actor", required=True)
    mark.add_argument("--evidence")
    mark.add_argument("--note")
    mark.add_argument("--policy", default=str(DEFAULT_POLICY))
    mark.set_defaults(func=command_mark)

    status = sub.add_parser("status", help="Show one case readiness percentage")
    status.add_argument("case")
    status.add_argument("--policy", default=str(DEFAULT_POLICY))
    status.add_argument("--markdown")
    status.set_defaults(func=command_status)

    release = sub.add_parser(
        "release-status", help="Show architecture, operator and live release percentages"
    )
    release.add_argument("--policy", default=str(DEFAULT_POLICY))
    release.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    release.add_argument("--output-json")
    release.add_argument("--output-markdown")
    release.set_defaults(func=command_release_status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
