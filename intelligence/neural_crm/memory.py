from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import random
from typing import Any, Iterable, Mapping, Sequence


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OutcomeEvent:
    event_id: str
    occurred_at: str
    entity_id: str
    model_version: str
    prediction: float
    outcome: int
    segment: str
    decision: str
    feature_digest: str
    evidence_digest: str

    def __post_init__(self) -> None:
        if not self.event_id or not self.entity_id or not self.model_version:
            raise ValueError("outcome event identifiers are required")
        if not 0.0 <= float(self.prediction) <= 1.0:
            raise ValueError("prediction must be between zero and one")
        if int(self.outcome) not in (0, 1):
            raise ValueError("outcome must be binary")
        datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        for name, value in (("feature_digest", self.feature_digest), ("evidence_digest", self.evidence_digest)):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
                raise ValueError(f"{name} must be a SHA-256 hex digest")


@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    brier_score: float
    expected_calibration_error: float
    log_loss: float
    positive_rate: float
    bins: tuple[dict[str, float], ...]


@dataclass(frozen=True)
class DriftReport:
    baseline_count: int
    current_count: int
    feature_scores: dict[str, float]
    maximum_score: float
    mean_score: float
    drift_detected: bool
    threshold: float


@dataclass(frozen=True)
class PromotionDecision:
    permitted: bool
    status: str
    reasons: tuple[str, ...]
    requires_human: bool
    active_model: str
    candidate_model: str


class OutcomeLedger:
    """Append-only pseudonymous outcome memory.

    Raw personal data and free text are prohibited. The ledger stores only stable
    pseudonymous entity IDs, bounded outcomes and cryptographic digests of the
    feature/evidence packages used by the inference cycle.
    """

    def __init__(self, events: Iterable[OutcomeEvent] = ()) -> None:
        self._events: list[OutcomeEvent] = []
        self._ids: set[str] = set()
        for event in events:
            self.append(event)

    def append(self, event: OutcomeEvent) -> None:
        if event.event_id in self._ids:
            raise ValueError("duplicate outcome event")
        self._ids.add(event.event_id)
        self._events.append(event)

    @property
    def events(self) -> tuple[OutcomeEvent, ...]:
        return tuple(self._events)

    def by_model(self, model_version: str) -> tuple[OutcomeEvent, ...]:
        return tuple(event for event in self._events if event.model_version == model_version)

    def by_segment(self, segment: str) -> tuple[OutcomeEvent, ...]:
        return tuple(event for event in self._events if event.segment == segment)

    def digest(self) -> str:
        return _digest([asdict(event) for event in self._events])

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_count": len(self._events),
            "ledger_digest": self.digest(),
            "events": [asdict(event) for event in self._events],
        }


class ReplayBuffer:
    """Deterministic, segment-aware replay selection for offline evaluation."""

    def __init__(self, capacity: int = 5000, seed: int = 120) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self.seed = int(seed)

    def select(self, events: Sequence[OutcomeEvent], limit: int) -> tuple[OutcomeEvent, ...]:
        if limit < 1:
            return ()
        ordered = sorted(events, key=lambda event: (event.segment, event.occurred_at, event.event_id))[-self.capacity :]
        grouped: dict[str, list[OutcomeEvent]] = {}
        for event in ordered:
            grouped.setdefault(event.segment or "unsegmented", []).append(event)
        rng = random.Random(self.seed + len(ordered) + limit)
        for group in grouped.values():
            rng.shuffle(group)
        selected: list[OutcomeEvent] = []
        keys = sorted(grouped)
        while keys and len(selected) < min(limit, len(ordered)):
            next_keys: list[str] = []
            for key in keys:
                group = grouped[key]
                if group and len(selected) < limit:
                    selected.append(group.pop())
                if group:
                    next_keys.append(key)
            keys = next_keys
        return tuple(selected)


class CalibrationMonitor:
    @staticmethod
    def evaluate(events: Sequence[OutcomeEvent], bins: int = 10) -> CalibrationReport:
        if not events:
            return CalibrationReport(0, 0.0, 0.0, 0.0, 0.0, ())
        bins = max(2, min(50, int(bins)))
        brier = sum((event.prediction - event.outcome) ** 2 for event in events) / len(events)
        log_loss = -sum(
            event.outcome * math.log(max(event.prediction, 1e-12))
            + (1 - event.outcome) * math.log(max(1.0 - event.prediction, 1e-12))
            for event in events
        ) / len(events)
        positive_rate = sum(event.outcome for event in events) / len(events)
        buckets: list[list[OutcomeEvent]] = [[] for _ in range(bins)]
        for event in events:
            index = min(bins - 1, int(event.prediction * bins))
            buckets[index].append(event)
        ece = 0.0
        report_bins: list[dict[str, float]] = []
        for index, bucket in enumerate(buckets):
            if not bucket:
                continue
            mean_prediction = sum(event.prediction for event in bucket) / len(bucket)
            outcome_rate = sum(event.outcome for event in bucket) / len(bucket)
            weight = len(bucket) / len(events)
            ece += weight * abs(mean_prediction - outcome_rate)
            report_bins.append(
                {
                    "lower": index / bins,
                    "upper": (index + 1) / bins,
                    "count": float(len(bucket)),
                    "mean_prediction": mean_prediction,
                    "outcome_rate": outcome_rate,
                    "absolute_gap": abs(mean_prediction - outcome_rate),
                }
            )
        return CalibrationReport(
            sample_count=len(events),
            brier_score=brier,
            expected_calibration_error=ece,
            log_loss=log_loss,
            positive_rate=positive_rate,
            bins=tuple(report_bins),
        )


class DriftMonitor:
    """Distribution drift using standardised mean and variance change.

    Input rows must contain bounded numeric features only. Raw identifiers and
    personal data are neither required nor accepted by the API contract.
    """

    @staticmethod
    def _stats(rows: Sequence[Mapping[str, float]], feature: str) -> tuple[float, float]:
        values = [float(row.get(feature, 0.0)) for row in rows]
        if not values:
            return 0.0, 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return mean, math.sqrt(max(variance, 0.0))

    @classmethod
    def compare(
        cls,
        baseline: Sequence[Mapping[str, float]],
        current: Sequence[Mapping[str, float]],
        threshold: float = 0.35,
    ) -> DriftReport:
        features = sorted({key for row in baseline for key in row} | {key for row in current for key in row})
        scores: dict[str, float] = {}
        for feature in features:
            base_mean, base_std = cls._stats(baseline, feature)
            current_mean, current_std = cls._stats(current, feature)
            scale = max(base_std, current_std, 0.05)
            mean_shift = abs(current_mean - base_mean) / scale
            variance_shift = abs(current_std - base_std) / max(base_std + current_std, 0.05)
            scores[feature] = _clip(0.72 * (mean_shift / 3.0) + 0.28 * variance_shift)
        maximum = max(scores.values(), default=0.0)
        mean_score = sum(scores.values()) / len(scores) if scores else 0.0
        threshold = _clip(threshold)
        return DriftReport(
            baseline_count=len(baseline),
            current_count=len(current),
            feature_scores=scores,
            maximum_score=maximum,
            mean_score=mean_score,
            drift_detected=maximum >= threshold or mean_score >= threshold * 0.65,
            threshold=threshold,
        )


class IncidentMemory:
    """Append-only record of neural incidents and mitigations."""

    def __init__(self) -> None:
        self._incidents: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def record(
        self,
        category: str,
        severity: str,
        model_version: str,
        evidence_digest: str,
        mitigation: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
        incident_id = "NINC-" + _digest([category, severity, model_version, evidence_digest, occurred_at])[:12].upper()
        if incident_id in self._ids:
            raise ValueError("duplicate incident")
        item = {
            "incident_id": incident_id,
            "occurred_at": occurred_at,
            "category": str(category),
            "severity": str(severity),
            "model_version": str(model_version),
            "evidence_digest": str(evidence_digest),
            "mitigation": str(mitigation),
            "status": "open",
        }
        self._ids.add(incident_id)
        self._incidents.append(item)
        return dict(item)

    def resolve(self, incident_id: str, resolution: str) -> dict[str, Any]:
        for item in self._incidents:
            if item["incident_id"] == incident_id:
                item["status"] = "resolved"
                item["resolution"] = str(resolution)
                item["resolved_at"] = datetime.now(timezone.utc).isoformat()
                return dict(item)
        raise KeyError("incident not found")

    @property
    def incidents(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._incidents)


class ModelPromotionGate:
    """Fail-closed model promotion custody.

    No code in this module changes active weights. It only evaluates whether a
    candidate is eligible for a human-reviewed promotion pull request.
    """

    def evaluate(
        self,
        active_model: str,
        candidate_model: str,
        calibration: CalibrationReport,
        drift: DriftReport,
        baseline_brier: float,
        red_team_passed: bool,
        rollback_verified: bool,
        temporal_split_verified: bool,
        segment_review_passed: bool,
        human_approved: bool = False,
        minimum_samples: int = 100,
    ) -> PromotionDecision:
        reasons: list[str] = []
        if candidate_model == active_model:
            reasons.append("candidate_equals_active_model")
        if calibration.sample_count < minimum_samples:
            reasons.append("insufficient_labelled_outcomes")
        if calibration.brier_score >= float(baseline_brier):
            reasons.append("candidate_does_not_beat_baseline_brier")
        if calibration.expected_calibration_error > 0.10:
            reasons.append("calibration_error_above_limit")
        if drift.drift_detected:
            reasons.append("unresolved_distribution_drift")
        if not red_team_passed:
            reasons.append("red_team_incomplete")
        if not rollback_verified:
            reasons.append("rollback_not_verified")
        if not temporal_split_verified:
            reasons.append("temporal_split_not_verified")
        if not segment_review_passed:
            reasons.append("segment_review_incomplete")
        if not human_approved:
            reasons.append("human_approval_required")
        return PromotionDecision(
            permitted=not reasons,
            status="approved_for_reviewed_promotion" if not reasons else "blocked",
            reasons=tuple(reasons),
            requires_human=True,
            active_model=str(active_model),
            candidate_model=str(candidate_model),
        )


def outcome_event(
    entity_id: str,
    model_version: str,
    prediction: float,
    outcome: int,
    segment: str,
    decision: str,
    features: Mapping[str, float],
    evidence: Mapping[str, Any],
    occurred_at: str,
) -> OutcomeEvent:
    event_id = "NOUT-" + _digest([entity_id, model_version, occurred_at, decision])[:12].upper()
    return OutcomeEvent(
        event_id=event_id,
        occurred_at=occurred_at,
        entity_id=str(entity_id),
        model_version=str(model_version),
        prediction=_clip(prediction),
        outcome=int(outcome),
        segment=str(segment or "unsegmented"),
        decision=str(decision),
        feature_digest=_digest(dict(features)),
        evidence_digest=_digest(dict(evidence)),
    )
