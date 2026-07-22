#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.heavy_rework_patch import (  # noqa: E402
    build_dataset_bundle,
    federate_heavy_evidence,
    run_heavy_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the governed heavy-runtime candidate federation v2.")
    parser.add_argument("command", choices=("generate", "embedding", "lora", "yolo", "federate"))
    parser.add_argument("--workspace", default="artifacts/heavy-federation")
    parser.add_argument("--seed", type=int, default=130)
    parser.add_argument("--reference", default="config/microcandidate-reference.json")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    if args.command == "generate":
        result = build_dataset_bundle(workspace, seed=args.seed)
    elif args.command in {"embedding", "lora", "yolo"}:
        result = run_heavy_candidate(args.command, workspace, seed=args.seed)
    else:
        result = federate_heavy_evidence(
            workspace / "candidates",
            args.reference,
            workspace / "heavy-runtime-review.json",
        )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
