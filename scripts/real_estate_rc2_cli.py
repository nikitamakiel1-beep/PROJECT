#!/usr/bin/env python3
"""Local RC2 operator CLI. No web, Drive, CRM or messaging client is included."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.real_estate.autopptx_pipeline import (  # noqa: E402
    build_usando_update_plan,
    create_project_workspace,
)
from intelligence.real_estate.media_rights import (  # noqa: E402
    build_authorised_cleanup_job,
    build_media_record,
    build_watermarkremover_command,
)
from intelligence.real_estate.zone_evidence import (  # noqa: E402
    build_zone_capture_plan,
    build_zone_evidence,
)


def emit(value: object, output: str | None) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="RC2 real-estate local operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    workspace = sub.add_parser("create-workspace")
    workspace.add_argument("root")
    workspace.add_argument("project_code")
    workspace.add_argument("--output")

    zone_plan = sub.add_parser("zone-plan")
    zone_plan.add_argument("project_code")
    zone_plan.add_argument("exact_address")
    zone_plan.add_argument("operator_token")
    zone_plan.add_argument("--output")

    zone_evidence = sub.add_parser("zone-evidence")
    zone_evidence.add_argument("capture_plan")
    zone_evidence.add_argument("capture_record")
    zone_evidence.add_argument("--thresholds-json")
    zone_evidence.add_argument("--output")

    workbook = sub.add_parser("workbook-plan")
    workbook.add_argument("project_code")
    workbook.add_argument("workbook_path")
    workbook.add_argument("field_values_json")
    workbook.add_argument("source_profile")
    workbook.add_argument("transfer_tax_rate", type=float)
    workbook.add_argument("--output")

    media = sub.add_parser("cleanup-plan")
    media.add_argument("media_json")
    media.add_argument("output_dir")
    media.add_argument("reviewer_token")
    media.add_argument("reason")
    media.add_argument("entrypoint")
    media.add_argument("--output")

    args = parser.parse_args()
    if args.command == "create-workspace":
        emit(create_project_workspace(args.root, args.project_code), args.output)
    elif args.command == "zone-plan":
        emit(
            build_zone_capture_plan(
                project_code=args.project_code,
                exact_address=args.exact_address,
                operator_token=args.operator_token,
            ),
            args.output,
        )
    elif args.command == "zone-evidence":
        thresholds = json.loads(args.thresholds_json) if args.thresholds_json else None
        emit(
            build_zone_evidence(
                capture_plan=load_json(args.capture_plan),
                capture_record=load_json(args.capture_record),
                reviewed_thresholds=thresholds,
            ),
            args.output,
        )
    elif args.command == "workbook-plan":
        emit(
            build_usando_update_plan(
                project_code=args.project_code,
                workbook_path=args.workbook_path,
                field_values=load_json(args.field_values_json),
                source_profile=args.source_profile,
                explicit_transfer_tax_rate=args.transfer_tax_rate,
            ),
            args.output,
        )
    elif args.command == "cleanup-plan":
        payload = load_json(args.media_json)
        record = build_media_record(**payload)
        job = build_authorised_cleanup_job(
            media_record=record,
            output_dir=args.output_dir,
            reviewer_token=args.reviewer_token,
            reason=args.reason,
        )
        emit(
            {
                "media_record": record,
                "cleanup_job": job,
                "command_plan": build_watermarkremover_command(
                    cleanup_job=job,
                    entrypoint=args.entrypoint,
                ),
            },
            args.output,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
