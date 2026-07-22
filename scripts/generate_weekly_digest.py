#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.management_digest import build_weekly_management_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an aggregate-only weekly venture management digest.")
    parser.add_argument("snapshot", type=Path, help="JSON snapshot containing pseudonymous or aggregate-safe CRM/programme records")
    parser.add_argument("--as-of", required=True, help="ISO date used for overdue calculations")
    parser.add_argument("--output", type=Path, default=Path("weekly-management-digest.json"))
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    digest = build_weekly_management_digest(snapshot, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "output": str(args.output),
        "digest_sha256": digest["digest_sha256"],
        "human_review_required": digest["controls"]["human_review_required"],
        "external_message_sent": digest["controls"]["external_message_sent"],
    }, indent=2))


if __name__ == "__main__":
    main()
