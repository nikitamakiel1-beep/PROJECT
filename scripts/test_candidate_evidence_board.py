#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.review_board import CandidateReviewBoard, ShadowRolloutSimulator  # noqa: E402


SAFETY_PASS = {
    "pii_scan_passed": True,
    "memorisation_test_passed": True,
    "prompt_injection_test_passed": True,
    "reward_hacking_test_passed": True,
    "model_extraction_test_passed": True,
    "rollback_verified": True,
    "temporal_split_verified": True,
    "segment_review_passed": True,
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pack(candidate_id="embedding-good", task="embedding", good=True):
    if task == "embedding":
        metrics = {
            "retrieval_mrr": 0.82 if good else 0.31,
            "expected_calibration_error": 0.02 if good else 0.18,
            "brier_score": 0.05 if good else 0.28,
        }
        baseline = {"retrieval_mrr": 0.38}
        segments = {
            "b2b_industrial": {"retrieval_mrr": 0.81},
            "b2b_services": {"retrieval_mrr": 0.80},
            "b2c_professional": {"retrieval_mrr": 0.79},
        }
    elif task == "language_model":
        metrics = {
            "train_loss": 1.2,
            "validation_loss": 1.28 if good else 1.82,
            "test_perplexity": 3.3 if good else 7.5,
            "expected_calibration_error": 0.04,
            "brier_score": 0.08,
        }
        baseline = {"test_perplexity": 6.8}
        segments = {"industrial": {"perplexity_inverse": 0.30}, "services": {"perplexity_inverse": 0.29}}
    else:
        metrics = {
            "map50": 0.79 if good else 0.30,
            "precision": 0.82 if good else 0.42,
            "recall": 0.77 if good else 0.38,
            "expected_calibration_error": 0.04,
            "brier_score": 0.09,
        }
        baseline = {"map50": 0.28}
        segments = {"document": {"map50": 0.78}, "chart": {"map50": 0.76}, "logo": {"map50": 0.75}}
    safety = dict(SAFETY_PASS)
    if not good:
        safety["memorisation_test_passed"] = False
        safety["rollback_verified"] = False
    evidence = {
        "candidate_id": candidate_id,
        "task": task,
        "framework": "torch",
        "dataset_id": "synthetic-v1",
        "dataset_digest": "a" * 64,
        "code_commit": "abc123",
        "seed": 126,
        "metrics": metrics,
        "baseline_metrics": baseline,
        "segment_metrics": segments,
        "quantization_metrics": {"relative_quality_loss": 0.01, "speedup": 1.6},
        "safety_results": safety,
        "limitations": ["synthetic data only"],
        "rollback_artifact": "artifacts/model.rollback" if good else "",
        "status": "shadow_candidate",
    }
    payload = {"evidence": evidence, "gate": {"promotion_permitted": False}}
    payload["pack_digest"] = digest(payload)
    return payload


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    results = []

    def case(name, function):
        function()
        results.append({"case": name, "result": "passed"})

    def strong_candidate():
        card = CandidateReviewBoard().evaluate(pack())
        require(card.decision == "eligible_for_extended_shadow", f"unexpected decision: {card.decision} {card.blockers}")
        require(card.board_score >= 0.85, "strong candidate board score too low")
        require(card.shadow_rollout.stable, "strong candidate rollout is not stable")
        require(card.promotion_permitted is False, "board permitted automatic promotion")
        require(card.human_review_required is True, "human custody missing")
        require("synthetic data only" in card.limitations, "declared limitation was lost")
        require(not any(item.startswith("declared_limitation") for item in card.blockers), "limitations were converted to blockers")

    case("strong candidate can reach extended shadow only", strong_candidate)

    def failed_candidate():
        card = CandidateReviewBoard().evaluate(pack("embedding-bad", good=False))
        require(card.decision == "reject_or_rework", "unsafe candidate was not rejected")
        require("rollback_not_verified" in card.blockers, "rollback blocker missing")
        require("missing_or_failed:memorisation_test_passed" in card.blockers, "privacy blocker missing")
        require(card.rollback_status == "blocked", "rollback status incorrect")
        require("Hestia→Pallas" in card.route_debt, "privacy route debt missing")

    case("unsafe candidate routes back to responsible colonies", failed_candidate)

    def language_overfit():
        card = CandidateReviewBoard().evaluate(pack("lora-overfit", task="language_model", good=False))
        require("overfit_gap_above_limit" in card.blockers, "overfit gap was not blocked")
        require("perplexity_does_not_beat_baseline" in card.blockers, "perplexity baseline blocker missing")

    case("language overfitting and baseline regression are blocked", language_overfit)

    def weak_vision():
        card = CandidateReviewBoard().evaluate(pack("vision-weak", task="vision", good=False))
        require("map50_does_not_beat_baseline" not in card.blockers, "test fixture baseline unexpectedly exceeds map50")
        require("vision_precision_or_recall_below_floor" in card.blockers, "vision floor blocker missing")

    case("vision precision and recall floors are enforced", weak_vision)

    def deterministic_rollout():
        simulator = ShadowRolloutSimulator()
        first = simulator.simulate(pack())
        second = simulator.simulate(pack())
        require(asdict(first) == asdict(second), "shadow rollout is not deterministic")
        require(first.simulated_decisions == 240, "default rollout size changed")
        require(len(first.digest) == 64, "rollout digest invalid")

    case("shadow rollout and rollback drill are deterministic", deterministic_rollout)

    def board_comparison():
        board = CandidateReviewBoard().compare([
            pack("embedding-good"),
            pack("lora-good", task="language_model"),
            pack("vision-bad", task="vision", good=False),
        ])
        require(board["candidate_count"] == 3, "candidate count wrong")
        require(board["promotion_permitted"] is False, "comparison permitted promotion")
        require(board["human_review_required"] is True, "comparison lost human custody")
        require("embedding-good" in board["eligible_for_extended_shadow"], "strong embedding candidate missing")
        require("vision-bad" in board["rejected_or_rework"], "weak vision candidate missing")
        require(len(board["board_digest"]) == 64, "board digest invalid")

    case("multi-candidate board preserves fail-closed custody", board_comparison)

    def cli_roundtrip():
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "packs.json"
            output_path = root / "board.json"
            input_path.write_text(json.dumps([pack(), pack("vision-good", task="vision")]), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "review_candidate_packs.py"), str(input_path), "--output", str(output_path)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            board = json.loads(output_path.read_text(encoding="utf-8"))
            require(summary["candidate_count"] == 2, "CLI summary count wrong")
            require(board["candidate_count"] == 2, "CLI board count wrong")
            require(board["promotion_permitted"] is False, "CLI board permitted promotion")

    case("review CLI emits deterministic board artifact", cli_roundtrip)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
