from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    task: str
    framework: str
    dataset_id: str
    dataset_digest: str
    code_commit: str
    seed: int
    metrics: dict[str, float]
    baseline_metrics: dict[str, float]
    segment_metrics: dict[str, dict[str, float]]
    quantization_metrics: dict[str, float]
    safety_results: dict[str, bool]
    limitations: tuple[str, ...]
    rollback_artifact: str
    status: str = "shadow_candidate"

    def __post_init__(self) -> None:
        if self.status != "shadow_candidate":
            raise ValueError("candidate evidence must remain shadow")
        for group in (self.metrics, self.baseline_metrics, self.quantization_metrics):
            for name, value in group.items():
                if not math.isfinite(float(value)):
                    raise ValueError(f"non-finite metric: {name}")
        if len(self.dataset_digest) != 64:
            raise ValueError("dataset digest must be SHA-256")

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class EvidenceGate:
    """Fail-closed reviewed-candidate gate.

    This does not deploy or promote. It only decides whether evidence is complete
    enough to request a human review.
    """

    REQUIRED_SAFETY = (
        "pii_scan_passed",
        "memorisation_test_passed",
        "prompt_injection_test_passed",
        "reward_hacking_test_passed",
        "model_extraction_test_passed",
        "rollback_verified",
        "temporal_split_verified",
        "segment_review_passed",
    )

    def evaluate(self, evidence: CandidateEvidence) -> dict[str, Any]:
        reasons: list[str] = []
        for key in self.REQUIRED_SAFETY:
            if not evidence.safety_results.get(key, False):
                reasons.append(f"missing_or_failed:{key}")
        if not evidence.rollback_artifact:
            reasons.append("missing_rollback_artifact")
        if not evidence.segment_metrics:
            reasons.append("missing_segment_metrics")
        if evidence.task == "language_model":
            if evidence.metrics.get("test_perplexity", float("inf")) >= evidence.baseline_metrics.get("test_perplexity", float("inf")):
                reasons.append("perplexity_does_not_beat_baseline")
            if evidence.metrics.get("validation_loss", float("inf")) - evidence.metrics.get("train_loss", float("inf")) > 0.35:
                reasons.append("overfit_gap_above_limit")
        elif evidence.task == "embedding":
            if evidence.metrics.get("retrieval_mrr", 0.0) <= evidence.baseline_metrics.get("retrieval_mrr", 0.0):
                reasons.append("retrieval_does_not_beat_baseline")
        elif evidence.task == "vision":
            if evidence.metrics.get("map50", 0.0) <= evidence.baseline_metrics.get("map50", 0.0):
                reasons.append("map50_does_not_beat_baseline")
            if evidence.metrics.get("precision", 0.0) < 0.50 or evidence.metrics.get("recall", 0.0) < 0.50:
                reasons.append("vision_precision_or_recall_below_floor")
        if evidence.quantization_metrics:
            if evidence.quantization_metrics.get("relative_quality_loss", 0.0) > 0.05:
                reasons.append("quantization_quality_loss_above_limit")
        return {
            "candidate_id": evidence.candidate_id,
            "evidence_digest": evidence.digest(),
            "eligible_for_human_review": not reasons,
            "promotion_permitted": False,
            "human_approval_required": True,
            "reasons": reasons,
        }

    @staticmethod
    def write_pack(path: str | Path, evidence: CandidateEvidence, decision: Mapping[str, Any], signing_key: str | None = None) -> dict[str, Any]:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        payload = {"evidence": asdict(evidence), "gate": dict(decision)}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        key = signing_key if signing_key is not None else os.getenv("MODEL_EVIDENCE_SIGNING_KEY", "")
        signature = hmac.new(key.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest() if key else ""
        pack = {
            **payload,
            "pack_digest": digest,
            "signature_mode": "hmac_sha256" if key else "unsigned_synthetic",
            "signature": signature,
        }
        (path / f"{evidence.candidate_id}.json").write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")
        return pack
