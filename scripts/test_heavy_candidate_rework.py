#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.candidate_rework import _ece_brier  # noqa: E402
from ml_runtime.heavy_rework import RelativeUpliftRollout  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def pack(task, metrics, baseline, quant=None):
    return {
        "evidence": {
            "candidate_id": f"synthetic-{task}-v2",
            "task": task,
            "metrics": metrics,
            "baseline_metrics": baseline,
            "quantization_metrics": quant or {},
            "safety_results": {
                "pii_scan_passed": True,
                "memorisation_test_passed": True,
                "prompt_injection_test_passed": True,
                "reward_hacking_test_passed": True,
                "model_extraction_test_passed": True,
                "rollback_verified": True,
                "temporal_split_verified": True,
                "segment_review_passed": True,
            },
            "rollback_artifact": "rollback.bin",
        }
    }


def run():
    results = []

    def case(name, function):
        function()
        results.append({"case": name, "result": "passed"})

    def calibration_math():
        ece, brier = _ece_brier([0.99, 0.98, 0.02, 0.01], [1, 1, 0, 0])
        require(ece < 0.03, f"perfect calibration ECE too high: {ece}")
        require(brier < 0.001, f"perfect calibration Brier too high: {brier}")
        bad_ece, _ = _ece_brier([0.99, 0.98], [0, 0])
        require(bad_ece > 0.90, "overconfident errors were not detected")

    case("calibration metrics distinguish reliable confidence", calibration_math)

    def language_relative_uplift():
        rollout = RelativeUpliftRollout().simulate(
            pack(
                "language_model",
                {"test_perplexity": 187.0, "train_loss": 5.24, "validation_loss": 5.23, "expected_calibration_error": 0.04},
                {"test_perplexity": 256.0},
            )
        )
        require(rollout.stable, f"material relative perplexity improvement remained unstable: {rollout}")
        require(rollout.disagreement_rate <= 0.28, "relative uplift did not reduce disagreement")

    case("language rollout uses relative perplexity uplift", language_relative_uplift)

    def zero_uplift_rejected():
        rollout = RelativeUpliftRollout().simulate(pack("embedding", {"retrieval_mrr": 0.5}, {"retrieval_mrr": 0.5}))
        require(not rollout.stable, "zero-uplift embedding became stable")

    case("zero-uplift candidate remains blocked", zero_uplift_rejected)

    def runtime_contract():
        source = (ROOT / "ml_runtime" / "candidate_rework.py").read_text(encoding="utf-8")
        require('pretrained=False' in source, "YOLO pretrained-weight prohibition missing")
        require('epochs=18' in source, "extended bounded YOLO schedule missing")
        requirements = (ROOT / "requirements" / "heavy-embedding-cpu.txt").read_text(encoding="utf-8")
        for dependency in ("onnx==", "onnxruntime==", "numpy=="):
            require(dependency in requirements, f"embedding quantization dependency missing: {dependency}")

    case("v2 runtime retains offline and quantization controls", runtime_contract)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
