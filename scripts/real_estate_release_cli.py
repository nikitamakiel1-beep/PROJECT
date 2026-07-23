#!/usr/bin/env python3
"""Local operator CLI for the real-estate architecture release candidate."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.acquisition import (  # noqa: E402
    build_acquisition_plan,
    build_idealista_search_request,
    load_connector_registry,
)
from intelligence.real_estate.report_release import (  # noqa: E402
    build_local_command,
    build_report_job,
    execute_local_report_job,
    renderer_readiness,
    verify_report_outputs,
)

DEFAULT_REGISTRY = ROOT / "config" / "real-estate-source-connectors.json"
DEFAULT_RENDERER = ROOT / "config" / "real-estate-report-renderer.json"


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def emit(value: Any, output: str | None) -> None:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    if output:
        Path(output).write_text(body + "\n", encoding="utf-8")
    else:
        print(body)


def source_plan(args: argparse.Namespace) -> int:
    registry = load_connector_registry(args.registry)
    candidate = load_json(args.candidate)
    plan = build_acquisition_plan(candidate, registry, environment=os.environ)
    emit(plan, args.output)
    return 0


def idealista_request(args: argparse.Namespace) -> int:
    request = build_idealista_search_request(
        country="es",
        operation=args.operation,
        property_type=args.property_type,
        center=args.center,
        distance_m=args.distance,
        max_price=args.max_price,
        min_price=args.min_price,
    )
    emit(request, args.output)
    return 0


def report_job(args: argparse.Namespace) -> int:
    payload = load_json(args.input)
    job = build_report_job(
        property_id=payload["property_id"],
        project_code=payload["project_code"],
        underwriting_case_id=payload["underwriting_case_id"],
        scenario_ids=list(payload["scenario_ids"]),
        calculation_version=payload["calculation_version"],
        input_snapshot_digest=payload["input_snapshot_digest"],
        template_version=payload["template_version"],
        evidence=list(payload["evidence"]),
        media=list(payload["media"]),
        approvals=dict(payload["approvals"]),
        source_candidate_digest=payload["source_candidate_digest"],
    )
    emit(job, args.output)
    return 0


def renderer_status(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    status = renderer_readiness(config, os.environ)
    emit(status, args.output)
    return 0 if status["ready"] else 2


def report_command(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    job = load_json(args.job)
    plan = build_local_command(job, config, os.environ)
    emit(plan, args.output)
    return 0


def execute_report(args: argparse.Namespace) -> int:
    if args.approve_local_execution != "I_APPROVE_LOCAL_EXECUTION":
        raise ValueError(
            "pass --approve-local-execution I_APPROVE_LOCAL_EXECUTION"
        )
    job = load_json(args.job)
    plan = load_json(args.command_plan)
    receipt = execute_local_report_job(
        job,
        plan,
        explicit_execution_approval=True,
        timeout_seconds=args.timeout,
    )
    emit(receipt, args.output)
    return 0 if receipt["success"] else 1


def verify_report(args: argparse.Namespace) -> int:
    job = load_json(args.job)
    result = verify_report_outputs(
        job=job,
        output_dir=args.output_dir,
        pdf_required=args.pdf_required,
    )
    emit(result, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local, no-network operator CLI for real-estate RC1"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("source-plan")
    command.add_argument("candidate")
    command.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    command.add_argument("--output")
    command.set_defaults(handler=source_plan)

    command = sub.add_parser("idealista-request")
    command.add_argument("--operation", choices=("sale", "rent"), required=True)
    command.add_argument("--property-type", default="homes")
    command.add_argument("--center", required=True)
    command.add_argument("--distance", type=int, required=True)
    command.add_argument("--max-price", type=float)
    command.add_argument("--min-price", type=float)
    command.add_argument("--output")
    command.set_defaults(handler=idealista_request)

    command = sub.add_parser("report-job")
    command.add_argument("input")
    command.add_argument("--output")
    command.set_defaults(handler=report_job)

    command = sub.add_parser("renderer-status")
    command.add_argument("--config", default=str(DEFAULT_RENDERER))
    command.add_argument("--output")
    command.set_defaults(handler=renderer_status)

    command = sub.add_parser("report-command")
    command.add_argument("job")
    command.add_argument("--config", default=str(DEFAULT_RENDERER))
    command.add_argument("--output")
    command.set_defaults(handler=report_command)

    command = sub.add_parser("execute-report")
    command.add_argument("job")
    command.add_argument("command_plan")
    command.add_argument("--approve-local-execution", required=True)
    command.add_argument("--timeout", type=int, default=600)
    command.add_argument("--output")
    command.set_defaults(handler=execute_report)

    command = sub.add_parser("verify-report")
    command.add_argument("job")
    command.add_argument("output_dir")
    command.add_argument("--pdf-required", action="store_true")
    command.add_argument("--output")
    command.set_defaults(handler=verify_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
