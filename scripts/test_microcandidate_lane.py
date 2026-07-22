#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.micro_candidates import run_microcandidate_lane  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run_once(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    for name in ("lora", "embedding", "vision"):
        (path / name).mkdir(parents=True, exist_ok=True)
    return run_microcandidate_lane(path, seed=129)


def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="microcandidate-test-"))
    try:
        first = run_once(workspace / "first")
        second = run_once(workspace / "second")

        require(first["summary"]["dataset_digest"] == second["summary"]["dataset_digest"], "dataset generation is not deterministic")
        require(first["summary"]["board_digest"] == second["summary"]["board_digest"], "review board is not deterministic")
        require(first["summary"]["promotion_permitted"] is False, "microcandidate lane permitted promotion")
        require(first["summary"]["human_review_required"] is True, "human review custody missing")

        candidates = first["candidates"]
        lora = candidates["lora"]["evidence"]
        embedding = candidates["embedding"]["evidence"]
        vision = candidates["vision"]["evidence"]

        require(lora["metrics"]["test_perplexity"] < lora["baseline_metrics"]["test_perplexity"], "low-rank language adapter did not beat baseline")
        require(lora["metrics"]["validation_loss"] - lora["metrics"]["train_loss"] <= 0.35, "low-rank language adapter overfit")
        require(embedding["metrics"]["retrieval_mrr"] > embedding["baseline_metrics"]["retrieval_mrr"], "embedding candidate did not beat baseline")
        require(embedding["metrics"]["classification_accuracy"] >= 0.90, "embedding latent classifier accuracy below floor")
        require(vision["metrics"]["map50"] > vision["baseline_metrics"]["map50"], "vision proxy did not beat baseline")
        require(vision["metrics"]["precision"] >= 0.80 and vision["metrics"]["recall"] >= 0.80, "vision proxy precision or recall below smoke floor")
        require("not YOLO" in vision["limitations"], "vision proxy is not labelled honestly")

        for name, candidate in candidates.items():
            evidence = candidate["evidence"]
            require(evidence["safety_results"]["pii_scan_passed"], f"{name} PII gate failed")
            require(evidence["safety_results"]["rollback_verified"], f"{name} rollback gate failed")
            require(len(evidence["dataset_digest"]) == 64, f"{name} dataset digest invalid")
            require(Path(evidence["rollback_artifact"]).exists(), f"{name} rollback artifact missing")
            require(candidate["gate"]["promotion_permitted"] is False, f"{name} evidence gate permitted promotion")

        board = first["board"]
        require(board["candidate_count"] == 3, "review board candidate count incorrect")
        require(board["promotion_permitted"] is False, "review board permitted promotion")
        require(board["human_review_required"] is True, "review board removed human custody")
        require(all(card["shadow_rollout"]["simulated_decisions"] == 240 for card in board["cards"]), "shadow rollout cohort size changed")
        require((workspace / "first" / "candidate-review-board.json").exists(), "board artifact missing")
        require((workspace / "first" / "SUMMARY.json").exists(), "summary artifact missing")

        serialised = json.dumps(first["summary"], sort_keys=True)
        for forbidden in ("@", "http://", "https://", "password", "token"):
            require(forbidden not in serialised.lower(), f"forbidden value leaked into summary: {forbidden}")

        print(json.dumps({
            "ok": True,
            "candidate_ids": first["summary"]["candidate_ids"],
            "board_digest": first["summary"]["board_digest"],
            "decisions": {card["candidate_id"]: card["decision"] for card in board["cards"]},
        }, indent=2, sort_keys=True))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
