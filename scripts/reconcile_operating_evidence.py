#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.operating_evidence import build_operating_evidence_receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile a public-safe CRM/Linear/interview snapshot")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    receipt = build_operating_evidence_receipt(snapshot, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "receipt_sha256": receipt["receipt_sha256"],
        "human_review_required": receipt["controls"]["human_review_required"],
        "external_message_sent": receipt["controls"]["external_message_sent"],
        "crm_mutated": receipt["controls"]["crm_mutated"],
    }, indent=2))


if __name__ == "__main__":
    main()
