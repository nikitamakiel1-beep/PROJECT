#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.evidence import CandidateEvidence, EvidenceGate  # noqa: E402
from ml_runtime.heavy_federation import (  # noqa: E402
    build_dataset_bundle,
    discover_candidate_packs,
    federate_heavy_evidence,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def safety() -> dict[str, bool]:
    return {
        "pii_scan_passed": True,
        "memorisation_test_passed": True,
        "prompt_injection_test_passed": True,
        "reward_hacking_test_passed": True,
        "model_extraction_test_passed": True,
        "rollback_verified": True,
        "temporal_split_verified": True,
        "segment_review_passed": True,
    }


def make_pack(root: Path, candidate: str, task: str) -> dict:
    candidate_dir = root / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    rollback = candidate_dir / "rollback.bin"
    rollback.write_bytes((candidate + task).encode("utf-8"))
    if task == "language_model":
        metrics = {"train_loss": 0.20, "validation_loss": 0.21, "test_perplexity": 2.0, "runtime_seconds": 4.0, "rollback_artifact_bytes": 12.0}
        baseline = {"test_perplexity": 10.0}
    elif task == "embedding":
        metrics = {"retrieval_mrr": 0.80, "runtime_seconds": 3.0, "rollback_artifact_bytes": 12.0}
        baseline = {"retrieval_mrr": 0.30}
    else:
        metrics = {"map50": 0.80, "precision": 0.90, "recall": 0.90, "runtime_seconds": 5.0, "rollback_artifact_bytes": 12.0}
        baseline = {"map50": 0.10}
    evidence = CandidateEvidence(
        candidate_id=f"heavy-{candidate}-shadow-test",
        task=task,
        framework=f"test-{candidate}",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest="a" * 64,
        code_commit="test-commit",
        seed=130,
        metrics=metrics,
        baseline_metrics=baseline,
        segment_metrics={"segment_a": {"quality": 0.80}, "segment_b": {"quality": 0.79}},
        quantization_metrics={},
        safety_results=safety(),
        limitations=("synthetic test candidate",),
        rollback_artifact=f"{candidate}/rollback.bin",
    )
    gate = EvidenceGate().evaluate(evidence)
    return EvidenceGate.write_pack(candidate_dir / "evidence", evidence, gate)


def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="heavy-federation-test-"))
    try:
        first = build_dataset_bundle(workspace / "dataset-a", seed=130)
        second = build_dataset_bundle(workspace / "dataset-b", seed=130)
        require(first["dataset_digest"] == second["dataset_digest"], "dataset federation input is not deterministic")
        require(first["total_records"] == 348, "unexpected governed dataset record count")
        require(first["production_data_used"] is False, "dataset builder claimed production data")

        candidates = workspace / "candidates"
        make_pack(candidates, "lora", "language_model")
        make_pack(candidates, "embedding", "embedding")
        make_pack(candidates, "yolo", "vision")
        reference = ROOT / "config" / "microcandidate-reference.json"
        report_path = workspace / "heavy-runtime-review.json"
        report = federate_heavy_evidence(candidates, reference, report_path)
        repeated = federate_heavy_evidence(candidates, reference, workspace / "heavy-runtime-review-2.json")

        require(report["candidate_count"] == 3, "federation did not discover all candidates")
        require(report["missing_tasks"] == [], "complete candidate set reported missing tasks")
        require(report["complete_candidate_set"] is True, "candidate set not marked complete")
        require(report["promotion_permitted"] is False, "federation permitted promotion")
        require(report["human_review_required"] is True, "human review custody missing")
        require(report["production_deployment"] is False, "production deployment was enabled")
        require(report["crm_decision_use"] is False, "CRM decision use was enabled")
        require(report["microcandidate_reference"]["direct_comparability"] is False, "unlike candidate tasks were declared directly comparable")
        require(all(item["directly_comparable"] is False for item in report["frontier"]), "frontier contains an invalid direct comparison")
        require(report["federation_digest"] == repeated["federation_digest"], "federation digest is not deterministic")
        require(report_path.exists(), "federation report was not written")

        pack_path = next((candidates / "yolo" / "evidence").glob("*.json"))
        payload = json.loads(pack_path.read_text(encoding="utf-8"))
        payload["evidence"]["metrics"]["map50"] = 0.99
        pack_path.write_text(json.dumps(payload), encoding="utf-8")
        packs, missing = discover_candidate_packs(candidates)
        require(len(packs) == 2, "tampered pack was not rejected")
        require("vision" in missing, "tampered vision pack did not create missing-task evidence")

        print(json.dumps({
            "ok": True,
            "dataset_digest": first["dataset_digest"],
            "federation_digest": report["federation_digest"],
            "candidate_count": report["candidate_count"],
        }, indent=2, sort_keys=True))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
