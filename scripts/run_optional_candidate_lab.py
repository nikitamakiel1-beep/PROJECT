#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.candidates import (  # noqa: E402
    OptionalRuntimeUnavailable,
    train_embedding_candidate,
    train_lora_candidate,
    train_yolo_candidate,
)
from ml_runtime.governance import DatasetBundleBuilder  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Colonial candidate laboratory.")
    parser.add_argument("command", choices=("generate", "lora", "embedding", "yolo", "all"))
    parser.add_argument("--workspace", default="artifacts/candidate-lab")
    parser.add_argument("--seed", type=int, default=126)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    dataset_root = workspace / "datasets"
    results: dict[str, object] = {}
    if args.command in {"generate", "all"} or not (dataset_root / "MANIFEST.json").exists():
        results["dataset"] = DatasetBundleBuilder(seed=args.seed).build(dataset_root)
    if args.command in {"lora", "all"}:
        results["lora"] = train_lora_candidate(dataset_root, workspace / "lora", seed=args.seed)
    if args.command in {"embedding", "all"}:
        results["embedding"] = train_embedding_candidate(dataset_root, workspace / "embedding", seed=args.seed)
    if args.command in {"yolo", "all"}:
        results["yolo"] = train_yolo_candidate(dataset_root, workspace / "yolo", seed=args.seed)
    print(json.dumps(results, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OptionalRuntimeUnavailable as error:
        print(json.dumps({"ok": False, "error": str(error), "instruction": "Install requirements/optional-ml-cpu.txt in an isolated environment."}, indent=2))
        raise SystemExit(2)
