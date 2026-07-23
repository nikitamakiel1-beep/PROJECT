#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.review_board import CandidateReviewBoard  # noqa: E402


def load_packs(path: Path) -> list[dict]:
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else [payload]
    packs = []
    for candidate in sorted(path.rglob("*.json")):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and ("evidence" in payload or "candidate_id" in payload):
            packs.append(payload)
    if not packs:
        raise SystemExit(f"no candidate evidence packs found in {path}")
    return packs


def main() -> None:
    parser = argparse.ArgumentParser(description="Review shadow candidate evidence packs.")
    parser.add_argument("input", type=Path, help="Evidence pack JSON file or directory")
    parser.add_argument("--output", type=Path, default=Path("candidate-review-board.json"))
    arguments = parser.parse_args()

    board = CandidateReviewBoard().compare(load_packs(arguments.input))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "candidate_count": board["candidate_count"],
        "eligible_for_extended_shadow": board["eligible_for_extended_shadow"],
        "rejected_or_rework": board["rejected_or_rework"],
        "promotion_permitted": board["promotion_permitted"],
        "board_digest": board["board_digest"],
        "output": str(arguments.output),
    }, indent=2))


if __name__ == "__main__":
    main()
