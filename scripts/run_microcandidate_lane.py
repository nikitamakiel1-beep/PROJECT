#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.micro_candidates import run_microcandidate_lane  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Train dependency-free shadow microcandidates and adjudicate their evidence.")
    parser.add_argument("--output", default="artifacts/microcandidate-lane")
    parser.add_argument("--seed", type=int, default=129)
    args = parser.parse_args()
    result = run_microcandidate_lane(Path(args.output), seed=args.seed)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
