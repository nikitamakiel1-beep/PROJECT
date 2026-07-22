#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_runtime.evidence import CandidateEvidence, EvidenceGate  # noqa: E402
from ml_runtime.governance import DatasetBundleBuilder, DatasetPolicyError, validate_no_pii  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    results = []

    def case(name, function):
        function()
        results.append({"case": name, "result": "passed"})

    def deterministic_bundle():
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = DatasetBundleBuilder(seed=126).build(first_dir)
            second = DatasetBundleBuilder(seed=126).build(second_dir)
            require(first["signature"]["manifest_digest"] == second["signature"]["manifest_digest"], "dataset bundle is not deterministic")
            require(first["manifest"] == second["manifest"], "dataset manifests differ")
            require(len(first["manifest"]["files"]) == 10, "unexpected dataset file count")

    case("dataset generation is deterministic", deterministic_bundle)

    def temporal_and_segment_splits():
        with tempfile.TemporaryDirectory() as directory:
            DatasetBundleBuilder(seed=126).build(directory)
            card = json.loads((Path(directory) / "DATASET_CARD.json").read_text(encoding="utf-8"))
            for task, splits in card["splits"].items():
                require(splits["train"]["last_date"] < splits["validation"]["first_date"], f"{task} train/validation leakage")
                require(splits["validation"]["last_date"] < splits["test"]["first_date"], f"{task} validation/test leakage")
                require(splits["test"]["records"] > 0, f"{task} test split empty")
            require(set(card["splits"]["crm"]["train"]["segments"]) == {"b2b_industrial", "b2b_services", "b2c_professional"}, "CRM segments incomplete")

    case("temporal and segment isolation enforced", temporal_and_segment_splits)

    def pii_rejected():
        for payload in (
            {"email": "person@example.test"},
            {"safe": "person@example.test"},
            {"safe": "https://example.test"},
            {"phone": "123456789"},
        ):
            try:
                validate_no_pii(payload)
            except DatasetPolicyError:
                pass
            else:
                raise AssertionError(f"PII payload was accepted: {payload}")

    case("PII and raw identifiers are rejected", pii_rejected)

    def manifest_tamper_detectable():
        with tempfile.TemporaryDirectory() as directory:
            evidence = DatasetBundleBuilder(seed=126, signing_key="synthetic-test-key").build(directory)
            require(evidence["signature"]["mode"] == "hmac_sha256", "signed mode missing")
            original = evidence["signature"]["manifest_digest"]
            file_path = Path(directory) / "crm" / "train.jsonl"
            file_path.write_text(file_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            import hashlib
            changed = hashlib.sha256(file_path.read_bytes()).hexdigest()
            require(changed != evidence["manifest"]["files"]["crm/train.jsonl"]["sha256"], "tampering was not detectable")
            require(len(original) == 64, "manifest digest invalid")

    case("dataset tampering is detectable", manifest_tamper_detectable)

    def base_evidence(task="language_model"):
        return CandidateEvidence(
            candidate_id=f"synthetic-{task}-candidate",
            task=task,
            framework="synthetic-test",
            dataset_id="colonial-candidate-lab-synthetic-v1",
            dataset_digest="a" * 64,
            code_commit="test",
            seed=126,
            metrics={"train_loss": 1.0, "validation_loss": 1.1, "test_perplexity": 2.0, "retrieval_mrr": 0.8, "map50": 0.7, "precision": 0.8, "recall": 0.8},
            baseline_metrics={"test_perplexity": 3.0, "retrieval_mrr": 0.4, "map50": 0.1},
            segment_metrics={"segment": {"score": 0.7}},
            quantization_metrics={"relative_quality_loss": 0.02},
            safety_results={key: True for key in EvidenceGate.REQUIRED_SAFETY},
            limitations=("synthetic",),
            rollback_artifact="rollback.bin",
        )

    def review_gate_passes_but_never_promotes():
        gate = EvidenceGate().evaluate(base_evidence())
        require(gate["eligible_for_human_review"], f"complete evidence blocked: {gate['reasons']}")
        require(not gate["promotion_permitted"], "gate promoted candidate automatically")
        require(gate["human_approval_required"], "human approval custody missing")

    case("complete evidence only reaches human review", review_gate_passes_but_never_promotes)

    def safety_failure_blocks():
        evidence = base_evidence()
        unsafe = replace(evidence, safety_results={**evidence.safety_results, "memorisation_test_passed": False})
        gate = EvidenceGate().evaluate(unsafe)
        require(not gate["eligible_for_human_review"], "unsafe candidate passed review gate")
        require("missing_or_failed:memorisation_test_passed" in gate["reasons"], "safety failure reason missing")

    case("failed red-team control blocks candidate", safety_failure_blocks)

    def overfit_and_quantization_block():
        evidence = base_evidence()
        bad = replace(
            evidence,
            metrics={**evidence.metrics, "train_loss": 0.1, "validation_loss": 0.8},
            quantization_metrics={"relative_quality_loss": 0.20},
        )
        reasons = EvidenceGate().evaluate(bad)["reasons"]
        require("overfit_gap_above_limit" in reasons, "overfit gap not detected")
        require("quantization_quality_loss_above_limit" in reasons, "quantization regression not detected")

    case("overfitting and quantization regressions block review", overfit_and_quantization_block)

    def runtime_lock_matches_requirements():
        config = json.loads((ROOT / "config" / "optional-ml-runtime.json").read_text(encoding="utf-8"))
        requirements = {}
        for line in (ROOT / "requirements" / "optional-ml-cpu.txt").read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                name, version = line.split("==", 1)
                requirements[name] = version
        require(config["packages"] == requirements, "runtime lock and requirements disagree")
        require(config["network_policy"]["model_download"] is False, "model downloads are not blocked")
        require(config["promotion"]["automatic"] is False, "automatic promotion enabled")

    case("optional runtime is pinned and fail-closed", runtime_lock_matches_requirements)

    print(json.dumps({"ok": True, "tests": results}, indent=2))


if __name__ == "__main__":
    run()
