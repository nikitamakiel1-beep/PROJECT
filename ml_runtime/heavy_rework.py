from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any, Mapping

from .candidate_rework import (
    train_embedding_candidate_v2,
    train_lora_candidate_v2,
    train_yolo_candidate_v2,
)
from .heavy_federation import (
    CANDIDATE_TASKS,
    _digest,
    _frontier_entry,
    _normalise_candidate,
    build_dataset_bundle,
    discover_candidate_packs,
)
from .review_board import CandidateReviewBoard, ShadowRollout, _clip, _digest as _review_digest, _finite


HEAVY_REWORK_VERSION = "heavy-runtime-federation-v2"


class RelativeUpliftRollout:
    """Synthetic rollout using task-normalised uplift rather than raw scale."""

    def simulate(self, pack: Mapping[str, Any], cohorts: int = 6, decisions_per_cohort: int = 40) -> ShadowRollout:
        evidence = pack.get("evidence", pack)
        candidate_id = str(evidence.get("candidate_id", "unresolved"))
        metrics = dict(evidence.get("metrics") or {})
        baseline = dict(evidence.get("baseline_metrics") or {})
        safety = dict(evidence.get("safety_results") or {})
        task = str(evidence.get("task", "unknown"))

        if task == "language_model":
            candidate = _finite(metrics.get("test_perplexity"), 1e9)
            reference = _finite(baseline.get("test_perplexity"), 1e9)
            uplift = _clip((reference - candidate) / max(reference, 1e-9))
        elif task == "embedding":
            uplift = _finite(metrics.get("retrieval_mrr")) - _finite(baseline.get("retrieval_mrr"))
        elif task == "vision":
            candidate_quality = 0.50 * _finite(metrics.get("map50")) + 0.25 * _finite(metrics.get("precision")) + 0.25 * _finite(metrics.get("recall"))
            uplift = candidate_quality - _finite(baseline.get("map50"))
        else:
            uplift = _finite(metrics.get("primary_score")) - _finite(baseline.get("primary_score"))

        safety_pass_rate = sum(bool(value) for value in safety.values()) / max(1, len(safety))
        overfit_gap = max(0.0, _finite(metrics.get("validation_loss")) - _finite(metrics.get("train_loss")))
        quant_loss = _finite((evidence.get("quantization_metrics") or {}).get("relative_quality_loss"))
        calibration = _finite(metrics.get("expected_calibration_error"), 0.10)
        disagreement = _clip(0.34 - uplift * 0.45 + overfit_gap * 0.35 + quant_loss * 0.50 + calibration * 0.20)
        abstention = _clip(0.08 + disagreement * 0.45 + (1.0 - safety_pass_rate) * 0.35)
        incident = _clip((1.0 - safety_pass_rate) * 0.60 + max(0.0, overfit_gap - 0.20) * 0.50 + quant_loss * 0.40)
        rollback = 1.0 if safety.get("rollback_verified", False) and evidence.get("rollback_artifact") else _clip(0.30 - incident)
        stable = uplift > 0.0 and disagreement <= 0.28 and incident <= 0.05 and rollback >= 0.95
        payload = {
            "candidate_id": candidate_id,
            "cohorts": int(cohorts),
            "decisions": int(cohorts * decisions_per_cohort),
            "disagreement": round(disagreement, 8),
            "abstention": round(abstention, 8),
            "incident": round(incident, 8),
            "rollback": round(rollback, 8),
            "stable": stable,
            "uplift": round(uplift, 8),
        }
        return ShadowRollout(
            candidate_id=candidate_id,
            cohort_count=int(cohorts),
            simulated_decisions=int(cohorts * decisions_per_cohort),
            disagreement_rate=disagreement,
            abstention_rate=abstention,
            incident_rate=incident,
            rollback_recovery_rate=rollback,
            stable=stable,
            digest=_review_digest(payload),
        )


def run_heavy_candidate(candidate: str, workspace: str | Path, seed: int = 130) -> dict[str, Any]:
    if candidate not in CANDIDATE_TASKS:
        raise ValueError(f"unsupported heavy candidate: {candidate}")
    workspace = Path(workspace)
    dataset_root = workspace / "datasets"
    if not (dataset_root / "MANIFEST.json").exists():
        raise FileNotFoundError("governed dataset bundle is missing")
    candidate_dir = workspace / "candidates" / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if candidate == "embedding":
        result = train_embedding_candidate_v2(dataset_root, candidate_dir, seed=seed, epochs=60)
    elif candidate == "lora":
        result = train_lora_candidate_v2(dataset_root, candidate_dir, seed=seed, epochs=8)
    else:
        result = train_yolo_candidate_v2(dataset_root, candidate_dir, seed=seed, epochs=18)
    return _normalise_candidate(candidate, result, candidate_dir, time.perf_counter() - started)


def federate_heavy_evidence(candidates_root: str | Path, reference_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    candidates_root = Path(candidates_root)
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    packs, missing = discover_candidate_packs(candidates_root)
    board_engine = CandidateReviewBoard(rollout=RelativeUpliftRollout())
    board = board_engine.compare(packs) if packs else {
        "candidate_count": 0,
        "cards": [],
        "board_digest": _digest({"empty": True}),
        "promotion_permitted": False,
        "human_review_required": True,
    }
    frontier = [_frontier_entry(pack, reference) for pack in packs]
    gate_ready = all(bool(pack.get("gate", {}).get("eligible_for_human_review")) for pack in packs)
    extended_shadow_ready = bool(board.get("cards")) and all(card.get("decision") == "eligible_for_extended_shadow" for card in board.get("cards", []))
    report = {
        "schema_version": 2,
        "version": HEAVY_REWORK_VERSION,
        "candidate_count": len(packs),
        "missing_tasks": missing,
        "complete_candidate_set": not missing,
        "review_board": board,
        "microcandidate_reference": {
            "reference_id": reference["reference_id"],
            "source_pr": reference["source_pr"],
            "direct_comparability": False,
        },
        "frontier": frontier,
        "eligible_for_human_review": bool(packs) and not missing and gate_ready,
        "eligible_for_extended_shadow": bool(packs) and not missing and gate_ready and extended_shadow_ready,
        "promotion_permitted": False,
        "human_review_required": True,
        "production_deployment": False,
        "crm_decision_use": False,
        "external_communication": False,
    }
    report["federation_digest"] = _digest(report)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
