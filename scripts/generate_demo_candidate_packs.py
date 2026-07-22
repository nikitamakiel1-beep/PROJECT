#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


SAFETY = {
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


def evidence(candidate_id, task, framework, metrics, baseline, segments, *, good=True, limitations=()):
    safety = dict(SAFETY)
    rollback = f"rollback/{candidate_id}" if good else ""
    if not good:
        safety["rollback_verified"] = False
        safety["memorisation_test_passed"] = False
    item = {
        "candidate_id": candidate_id,
        "task": task,
        "framework": framework,
        "dataset_id": "colonial-candidate-lab-synthetic-v1",
        "dataset_digest": "a" * 64,
        "code_commit": "synthetic-demo",
        "seed": 126,
        "metrics": metrics,
        "baseline_metrics": baseline,
        "segment_metrics": segments,
        "quantization_metrics": {"relative_quality_loss": 0.01, "speedup": 1.5},
        "safety_results": safety,
        "limitations": list(limitations),
        "rollback_artifact": rollback,
        "status": "shadow_candidate",
    }
    pack = {"evidence": item, "gate": {"promotion_permitted": False, "human_approval_required": True}}
    pack["pack_digest"] = digest(pack)
    return pack


def main():
    output = Path("candidate-demo-packs")
    output.mkdir(parents=True, exist_ok=True)
    packs = [
        evidence(
            "contrastive-rag-demo-v1",
            "embedding",
            "torch",
            {"retrieval_mrr": 0.82, "expected_calibration_error": 0.02, "brier_score": 0.05},
            {"retrieval_mrr": 0.38},
            {"industrial": {"mrr": 0.81}, "services": {"mrr": 0.80}, "professional": {"mrr": 0.79}},
            limitations=("synthetic knowledge units",),
        ),
        evidence(
            "tiny-lora-demo-v1",
            "language_model",
            "transformers-peft",
            {"train_loss": 1.20, "validation_loss": 1.28, "test_perplexity": 3.3, "expected_calibration_error": 0.04, "brier_score": 0.08},
            {"test_perplexity": 6.8},
            {"industrial": {"quality": 0.79}, "services": {"quality": 0.77}},
            limitations=("randomly initialised base", "synthetic byte-level corpus"),
        ),
        evidence(
            "geometric-yolo-demo-v1",
            "vision",
            "ultralytics",
            {"map50": 0.30, "precision": 0.42, "recall": 0.38, "expected_calibration_error": 0.14, "brier_score": 0.24},
            {"map50": 0.28},
            {"document": {"map50": 0.31}, "chart": {"map50": 0.29}, "logo": {"map50": 0.28}},
            good=False,
            limitations=("geometric scenes only",),
        ),
    ]
    for pack in packs:
        candidate_id = pack["evidence"]["candidate_id"]
        (output / f"{candidate_id}.json").write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "packs": len(packs)}, indent=2))


if __name__ == "__main__":
    main()
