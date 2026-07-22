from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


EXPERT_ROUTES = {
    "performance": "Daedalus→Pallas",
    "generalisation": "Daedalus→Pallas",
    "calibration": "Hermes→Pallas",
    "retrieval": "Mnemosyne→Pallas",
    "vision": "Argus→Pallas",
    "privacy": "Hestia→Pallas",
    "robustness": "Janus→Pallas",
    "efficiency": "Daedalus→Atlas",
    "rollback": "Pallas→Atlas",
    "reproducibility": "Daedalus→Pallas",
}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ReviewAxis:
    name: str
    score: float
    weight: float
    status: str
    reasons: tuple[str, ...]
    route: str


@dataclass(frozen=True)
class ShadowRollout:
    candidate_id: str
    cohort_count: int
    simulated_decisions: int
    disagreement_rate: float
    abstention_rate: float
    incident_rate: float
    rollback_recovery_rate: float
    stable: bool
    digest: str


@dataclass(frozen=True)
class ReviewCard:
    candidate_id: str
    task: str
    framework: str
    evidence_digest: str
    board_score: float
    decision: str
    promotion_permitted: bool
    human_review_required: bool
    axes: tuple[ReviewAxis, ...]
    route_debt: tuple[str, ...]
    blockers: tuple[str, ...]
    rollback_status: str
    shadow_rollout: ShadowRollout
    card_digest: str


class ShadowRolloutSimulator:
    """Deterministic, synthetic-only rollout and rollback drill.

    This does not use client data or execute candidate actions. It converts the
    evidence pack into bounded synthetic cohorts and tests disagreement,
    abstention, incident and rollback behaviour against a transparent baseline.
    """

    def simulate(self, pack: Mapping[str, Any], cohorts: int = 6, decisions_per_cohort: int = 40) -> ShadowRollout:
        evidence = pack.get("evidence", pack)
        candidate_id = str(evidence.get("candidate_id", "unresolved"))
        metrics = dict(evidence.get("metrics") or {})
        baseline = dict(evidence.get("baseline_metrics") or {})
        safety = dict(evidence.get("safety_results") or {})
        task = str(evidence.get("task", "unknown"))

        if task == "language_model":
            candidate_quality = 1.0 / max(_finite(metrics.get("test_perplexity"), 1e6), 1.0)
            baseline_quality = 1.0 / max(_finite(baseline.get("test_perplexity"), 1e6), 1.0)
        elif task == "embedding":
            candidate_quality = _finite(metrics.get("retrieval_mrr"))
            baseline_quality = _finite(baseline.get("retrieval_mrr"))
        elif task == "vision":
            candidate_quality = 0.50 * _finite(metrics.get("map50")) + 0.25 * _finite(metrics.get("precision")) + 0.25 * _finite(metrics.get("recall"))
            baseline_quality = _finite(baseline.get("map50"))
        else:
            candidate_quality = _finite(metrics.get("primary_score"))
            baseline_quality = _finite(baseline.get("primary_score"))

        uplift = candidate_quality - baseline_quality
        safety_pass_rate = sum(bool(value) for value in safety.values()) / max(1, len(safety))
        overfit_gap = max(0.0, _finite(metrics.get("validation_loss")) - _finite(metrics.get("train_loss")))
        quant_loss = _finite((evidence.get("quantization_metrics") or {}).get("relative_quality_loss"))

        disagreement = _clip(0.34 - uplift * 0.45 + overfit_gap * 0.35 + quant_loss * 0.50)
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
            digest=_digest(payload),
        )


class CandidateReviewBoard:
    """Multi-axis evidence adjudicator with fail-closed release custody."""

    WEIGHTS = {
        "performance": 0.20,
        "generalisation": 0.13,
        "calibration": 0.10,
        "privacy": 0.15,
        "robustness": 0.14,
        "efficiency": 0.08,
        "rollback": 0.10,
        "reproducibility": 0.10,
    }

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

    def __init__(self, rollout: ShadowRolloutSimulator | None = None) -> None:
        self.rollout = rollout or ShadowRolloutSimulator()

    @staticmethod
    def _axis(name: str, score: float, reasons: Iterable[str]) -> ReviewAxis:
        score = _clip(score)
        reasons = tuple(sorted(set(str(reason) for reason in reasons if reason)))
        status = "pass" if score >= 0.80 and not reasons else "review" if score >= 0.60 else "fail"
        return ReviewAxis(name, score, CandidateReviewBoard.WEIGHTS[name], status, reasons, EXPERT_ROUTES.get(name, "Pallas"))

    def evaluate(self, pack: Mapping[str, Any]) -> ReviewCard:
        evidence = dict(pack.get("evidence") or pack)
        candidate_id = str(evidence.get("candidate_id", "unresolved"))
        task = str(evidence.get("task", "unknown"))
        framework = str(evidence.get("framework", "unknown"))
        metrics = dict(evidence.get("metrics") or {})
        baseline = dict(evidence.get("baseline_metrics") or {})
        segments = dict(evidence.get("segment_metrics") or {})
        quant = dict(evidence.get("quantization_metrics") or {})
        safety = dict(evidence.get("safety_results") or {})
        limitations = tuple(str(item) for item in evidence.get("limitations") or ())
        rollback_artifact = str(evidence.get("rollback_artifact") or "")

        performance_reasons: list[str] = []
        if task == "language_model":
            candidate = _finite(metrics.get("test_perplexity"), 1e9)
            reference = _finite(baseline.get("test_perplexity"), 1e9)
            uplift = (reference - candidate) / max(reference, 1e-9)
            if uplift <= 0:
                performance_reasons.append("perplexity_does_not_beat_baseline")
            performance_score = _clip(0.55 + uplift * 2.0)
        elif task == "embedding":
            candidate = _finite(metrics.get("retrieval_mrr"))
            reference = _finite(baseline.get("retrieval_mrr"))
            uplift = candidate - reference
            if uplift <= 0:
                performance_reasons.append("retrieval_does_not_beat_baseline")
            performance_score = _clip(0.55 + uplift * 1.8)
        elif task == "vision":
            map50 = _finite(metrics.get("map50"))
            precision = _finite(metrics.get("precision"))
            recall = _finite(metrics.get("recall"))
            uplift = map50 - _finite(baseline.get("map50"))
            if uplift <= 0:
                performance_reasons.append("map50_does_not_beat_baseline")
            if min(precision, recall) < 0.50:
                performance_reasons.append("vision_precision_or_recall_below_floor")
            performance_score = _clip(0.30 * map50 + 0.35 * precision + 0.35 * recall)
        else:
            candidate = _finite(metrics.get("primary_score"))
            reference = _finite(baseline.get("primary_score"))
            uplift = candidate - reference
            if uplift <= 0:
                performance_reasons.append("primary_metric_does_not_beat_baseline")
            performance_score = _clip(0.55 + uplift)

        segment_values = [
            _finite(value)
            for values in segments.values()
            for value in values.values()
            if isinstance(value, (int, float)) and math.isfinite(float(value))
        ]
        segment_gap = max(segment_values) - min(segment_values) if len(segment_values) >= 2 else 1.0
        generalisation_reasons = [] if segments else ["missing_segment_metrics"]
        if segment_gap > 0.20:
            generalisation_reasons.append("segment_gap_above_limit")
        overfit_gap = max(0.0, _finite(metrics.get("validation_loss")) - _finite(metrics.get("train_loss")))
        if overfit_gap > 0.35:
            generalisation_reasons.append("overfit_gap_above_limit")
        generalisation_score = _clip(1.0 - segment_gap * 1.5 - max(0.0, overfit_gap - 0.10))

        ece = _finite(metrics.get("expected_calibration_error"), 0.10)
        brier = _finite(metrics.get("brier_score"), 0.20)
        calibration_reasons = []
        if ece > 0.10:
            calibration_reasons.append("calibration_error_above_limit")
        calibration_score = _clip(1.0 - ece * 4.0 - brier * 0.5)

        privacy_missing = [key for key in ("pii_scan_passed", "memorisation_test_passed", "model_extraction_test_passed") if not safety.get(key, False)]
        privacy_score = _clip(1.0 - len(privacy_missing) / 3.0)
        privacy_reasons = [f"missing_or_failed:{key}" for key in privacy_missing]

        robustness_missing = [key for key in ("prompt_injection_test_passed", "reward_hacking_test_passed") if not safety.get(key, False)]
        robustness_score = _clip(1.0 - len(robustness_missing) / 2.0)
        robustness_reasons = [f"missing_or_failed:{key}" for key in robustness_missing]

        quality_loss = _finite(quant.get("relative_quality_loss"))
        speedup = _finite(quant.get("speedup"), 1.0)
        efficiency_reasons = []
        if quality_loss > 0.05:
            efficiency_reasons.append("quantization_quality_loss_above_limit")
        if quant and speedup < 1.0:
            efficiency_reasons.append("quantized_runtime_not_faster")
        efficiency_score = _clip(0.75 + min(max(speedup - 1.0, 0.0), 1.0) * 0.20 - quality_loss * 2.0) if quant else 0.60

        rollback_ok = bool(safety.get("rollback_verified")) and bool(rollback_artifact)
        rollback_score = 1.0 if rollback_ok else 0.0
        rollback_reasons = [] if rollback_ok else ["rollback_not_verified"]

        reproducible = all(
            evidence.get(key) not in (None, "")
            for key in ("dataset_digest", "code_commit", "seed")
        ) and bool(pack.get("pack_digest") or evidence.get("evidence_digest"))
        reproducibility_score = 1.0 if reproducible else 0.35
        reproducibility_reasons = [] if reproducible else ["incomplete_reproducibility_chain"]

        axes = (
            self._axis("performance", performance_score, performance_reasons),
            self._axis("generalisation", generalisation_score, generalisation_reasons),
            self._axis("calibration", calibration_score, calibration_reasons),
            self._axis("privacy", privacy_score, privacy_reasons),
            self._axis("robustness", robustness_score, robustness_reasons),
            self._axis("efficiency", efficiency_score, efficiency_reasons),
            self._axis("rollback", rollback_score, rollback_reasons),
            self._axis("reproducibility", reproducibility_score, reproducibility_reasons),
        )
        board_score = sum(axis.score * axis.weight for axis in axes)
        rollout = self.rollout.simulate(pack)

        route_debt = sorted({axis.route for axis in axes if axis.status != "pass"})
        blockers = sorted({reason for axis in axes for reason in axis.reasons})
        if not rollout.stable:
            blockers.append("shadow_rollout_not_stable")
            route_debt.append("Janus→Pallas")
        if limitations:
            blockers.extend(f"declared_limitation:{item}" for item in limitations)
        blockers = sorted(set(blockers))
        route_debt = sorted(set(route_debt))

        if blockers:
            decision = "reject_or_rework"
        elif board_score >= 0.85 and rollout.stable:
            decision = "eligible_for_extended_shadow"
        else:
            decision = "human_review_required"

        card_payload = {
            "candidate_id": candidate_id,
            "task": task,
            "framework": framework,
            "evidence_digest": str(pack.get("pack_digest") or _digest(evidence)),
            "board_score": round(board_score, 8),
            "decision": decision,
            "axes": [asdict(axis) for axis in axes],
            "route_debt": route_debt,
            "blockers": blockers,
            "rollout": asdict(rollout),
        }
        return ReviewCard(
            candidate_id=candidate_id,
            task=task,
            framework=framework,
            evidence_digest=card_payload["evidence_digest"],
            board_score=board_score,
            decision=decision,
            promotion_permitted=False,
            human_review_required=True,
            axes=axes,
            route_debt=tuple(route_debt),
            blockers=tuple(blockers),
            rollback_status="verified" if rollback_ok else "blocked",
            shadow_rollout=rollout,
            card_digest=_digest(card_payload),
        )

    def compare(self, packs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        cards = [self.evaluate(pack) for pack in packs]
        ordered = sorted(cards, key=lambda card: (-card.board_score, card.candidate_id))
        return {
            "board_version": "candidate-review-board-v1",
            "candidate_count": len(ordered),
            "cards": [asdict(card) for card in ordered],
            "eligible_for_extended_shadow": [card.candidate_id for card in ordered if card.decision == "eligible_for_extended_shadow"],
            "rejected_or_rework": [card.candidate_id for card in ordered if card.decision == "reject_or_rework"],
            "promotion_permitted": False,
            "human_review_required": True,
            "board_digest": _digest([asdict(card) for card in ordered]),
        }
