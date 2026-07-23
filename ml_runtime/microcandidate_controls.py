from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import random
from typing import Any, Sequence

from . import micro_candidates as base
from .evidence import CandidateEvidence, EvidenceGate
from .review_board import CandidateReviewBoard


CONTROL_VERSION = "autonomous-microcandidate-lane-v2"


def _power_row(row: Sequence[float], gamma: float) -> list[float]:
    values = [max(float(value), 1e-12) ** gamma for value in row]
    total = sum(values) or 1.0
    return [value / total for value in values]


def _fit_power_calibration(probabilities: Sequence[Sequence[float]], targets: Sequence[int]) -> float:
    candidates = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0)
    best_gamma, best_ece = 1.0, float("inf")
    for gamma in candidates:
        calibrated = [_power_row(row, gamma) for row in probabilities]
        _, ece = base._calibration(calibrated, targets)
        if ece < best_ece:
            best_gamma, best_ece = gamma, ece
    return best_gamma


def _apply_power_calibration(probabilities: Sequence[Sequence[float]], gamma: float) -> list[list[float]]:
    return [_power_row(row, gamma) for row in probabilities]


def _scaled_clip(groups: Sequence[Any], ceiling: float = 1.0) -> float:
    values: list[float] = []
    for group in groups:
        for row in group:
            if isinstance(row, list):
                values.extend(float(value) for value in row)
            else:
                values.append(float(row))
    norm = math.sqrt(sum(value * value for value in values))
    return 1.0 if norm == 0.0 or norm <= ceiling else ceiling / norm


def _train_low_rank(self: Any, sequences: Sequence[Sequence[int]], epochs: int = 600, learning_rate: float = 1.0) -> list[float]:
    history: list[float] = []
    transitions = [(current, target) for sequence in sequences for current, target in zip(sequence, sequence[1:])]
    scale = 1.0 / max(1, len(transitions))
    for _ in range(epochs):
        grad_a = [[0.0] * self.rank for _ in range(self.vocab_size)]
        grad_b = [[0.0] * self.vocab_size for _ in range(self.rank)]
        loss = 0.0
        for current, target in transitions:
            probabilities = self.probabilities(current)
            loss += base._cross_entropy(probabilities, target)
            grad_logits = [value - (1.0 if index == target else 0.0) for index, value in enumerate(probabilities)]
            for rank in range(self.rank):
                grad_a[current][rank] += sum(grad_logits[index] * self.b[rank][index] for index in range(self.vocab_size))
                for index in range(self.vocab_size):
                    grad_b[rank][index] += self.a[current][rank] * grad_logits[index]
        scaled_a = [[value * scale for value in row] for row in grad_a]
        scaled_b = [[value * scale for value in row] for row in grad_b]
        clip = _scaled_clip((scaled_a, scaled_b), 1.0)
        for token in range(self.vocab_size):
            for rank in range(self.rank):
                self.a[token][rank] -= learning_rate * clip * (scaled_a[token][rank] + 0.001 * self.a[token][rank])
        for rank in range(self.rank):
            for target in range(self.vocab_size):
                self.b[rank][target] -= learning_rate * clip * (scaled_b[rank][target] + 0.001 * self.b[rank][target])
        history.append(loss * scale)
    return history


def _train_projection(self: Any, rows: Sequence[tuple[str, list[float], int]], epochs: int = 180, learning_rate: float = 0.22) -> list[float]:
    history: list[float] = []
    scale = 1.0 / max(1, len(rows))
    for _ in range(epochs):
        grad_w = [[0.0] * len(self.bias) for _ in range(len(self.weights))]
        grad_b = [0.0] * len(self.bias)
        loss = 0.0
        for _, features, target in rows:
            probabilities = self.probabilities(features)
            loss += base._cross_entropy(probabilities, target)
            for output, probability in enumerate(probabilities):
                gradient = probability - (1.0 if output == target else 0.0)
                grad_b[output] += gradient
                for index, feature in enumerate(features):
                    grad_w[index][output] += feature * gradient
        scaled_w = [[value * scale for value in row] for row in grad_w]
        scaled_b = [value * scale for value in grad_b]
        clip = _scaled_clip((scaled_w, scaled_b), 1.0)
        for index in range(len(self.weights)):
            for output in range(len(self.bias)):
                self.weights[index][output] -= learning_rate * clip * (scaled_w[index][output] + 0.001 * self.weights[index][output])
        for output in range(len(self.bias)):
            self.bias[output] -= learning_rate * clip * scaled_b[output]
        history.append(loss * scale)
    return history


def _train_vision(self: Any, rows: Sequence[tuple[str, list[list[float]], int]], epochs: int = 180, learning_rate: float = 0.50) -> list[float]:
    history: list[float] = []
    scale = 1.0 / max(1, len(rows))
    for _ in range(epochs):
        grad_filters = [[[0.0] * 3 for _ in range(3)] for _ in range(3)]
        grad_bias = [0.0] * 3
        loss = 0.0
        for _, image, target in rows:
            logits, caches = self.logits_and_cache(image)
            probabilities = base._softmax(logits)
            loss += base._cross_entropy(probabilities, target)
            for class_index, probability in enumerate(probabilities):
                gradient = probability - (1.0 if class_index == target else 0.0)
                grad_bias[class_index] += gradient
                for row, column, pre_activation in caches[class_index]:
                    if pre_activation <= 0.0:
                        continue
                    for kernel_row in range(3):
                        for kernel_column in range(3):
                            grad_filters[class_index][kernel_row][kernel_column] += gradient * image[row + kernel_row][column + kernel_column] / 36.0
        scaled_filters = [[[value * scale for value in row] for row in kernel] for kernel in grad_filters]
        scaled_bias = [value * scale for value in grad_bias]
        flat_filters = [[value for row in kernel for value in row] for kernel in scaled_filters]
        clip = _scaled_clip((flat_filters, scaled_bias), 1.0)
        for class_index in range(3):
            for kernel_row in range(3):
                for kernel_column in range(3):
                    self.filters[class_index][kernel_row][kernel_column] -= learning_rate * clip * (
                        scaled_filters[class_index][kernel_row][kernel_column] + 0.001 * self.filters[class_index][kernel_row][kernel_column]
                    )
            self.bias[class_index] -= learning_rate * clip * scaled_bias[class_index]
        history.append(loss * scale)
    return history


def _balanced_language_data(seed: int) -> dict[str, list[tuple[str, list[int]]]]:
    rng = random.Random(seed)
    patterns = {
        "visibility": [1, 2, 3, 4, 1, 2, 3, 4],
        "crm": [5, 6, 7, 8, 5, 6, 7, 8],
        "sales": [9, 10, 11, 12, 9, 10, 11, 12],
    }
    result: dict[str, list[tuple[str, list[int]]]] = {"train": [], "validation": [], "test": []}
    for split, count in (("train", 36), ("validation", 12), ("test", 15)):
        for segment, pattern in patterns.items():
            for _ in range(count):
                offset = rng.randrange(len(pattern))
                result[split].append((segment, pattern[offset:] + pattern[:offset]))
    return result


def _train_balanced_lora(output_dir: Path, seed: int, dataset_digest: str) -> dict[str, Any]:
    data = _balanced_language_data(seed)
    model = base.LowRankAutoregressiveAdapter(vocab_size=13, rank=4, seed=seed)
    history = _train_low_rank(model, [sequence for _, sequence in data["train"]])
    validation_loss = model.loss([sequence for _, sequence in data["validation"]])
    test_loss = model.loss([sequence for _, sequence in data["test"]])

    def probability_rows(rows: Sequence[tuple[str, list[int]]]) -> tuple[list[list[float]], list[int]]:
        probabilities: list[list[float]] = []
        targets: list[int] = []
        for _, sequence in rows:
            for current, target in zip(sequence, sequence[1:]):
                probabilities.append(model.probabilities(current))
                targets.append(target)
        return probabilities, targets

    validation_probabilities, validation_targets = probability_rows(data["validation"])
    gamma = _fit_power_calibration(validation_probabilities, validation_targets)
    test_probabilities, test_targets = probability_rows(data["test"])
    calibrated = _apply_power_calibration(test_probabilities, gamma)
    brier, ece = base._calibration(calibrated, test_targets)

    segment_metrics: dict[str, dict[str, float]] = {}
    for segment in sorted({name for name, _ in data["test"]}):
        correct = 0
        total = 0
        for name, sequence in data["test"]:
            if name != segment:
                continue
            for current, target in zip(sequence, sequence[1:]):
                prediction = max(range(model.vocab_size), key=lambda index: model.probabilities(current)[index])
                correct += int(prediction == target)
                total += 1
        segment_metrics[segment] = {"quality": correct / max(1, total)}

    artifact = output_dir / "micro_lora_adapter.json"
    artifact.write_text(json.dumps(model.state(), sort_keys=True), encoding="utf-8")
    evidence = CandidateEvidence(
        candidate_id="micro-lora-autoregressive-shadow-v1",
        task="language_model",
        framework="python-low-rank-backprop",
        dataset_id="microcandidate-synthetic-v1",
        dataset_digest=dataset_digest,
        code_commit=base._code_commit(),
        seed=seed,
        metrics={
            "train_loss": history[-1],
            "validation_loss": validation_loss,
            "test_loss": test_loss,
            "test_perplexity": math.exp(min(test_loss, 20.0)),
            "expected_calibration_error": ece,
            "brier_score": brier,
            "minimum_segment_token_accuracy": min(values["quality"] for values in segment_metrics.values()),
            "trainable_parameters": float(13 * 4 + 4 * 13),
        },
        baseline_metrics={"test_perplexity": 13.0},
        segment_metrics=segment_metrics,
        quantization_metrics={},
        safety_results=base._safety_results(),
        limitations=("balanced synthetic transition language", "microcandidate smoke lane", "not a transformer replacement", "shadow only"),
        rollback_artifact="lora/micro_lora_adapter.json",
    )
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "pack": pack, "history": history}


def _canonicalise_candidate(name: str, candidate: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    evidence_dict = dict(candidate["evidence"])
    artifact_names = {
        "embedding": "micro_embedding_projection.json",
        "vision": "micro_convolutional_vision_proxy.json",
    }
    evidence_dict["rollback_artifact"] = f"{name}/{artifact_names[name]}"
    evidence_dict["limitations"] = tuple(evidence_dict.get("limitations") or ())
    evidence = CandidateEvidence(**evidence_dict)
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(output_dir / name / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "pack": pack, "history": candidate.get("history", [])}


def run_controlled_microcandidate_lane(output_dir: str | Path, seed: int = 129) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("lora", "embedding", "vision"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)

    base.VERSION = CONTROL_VERSION
    base._temperature_mix = _fit_power_calibration
    base._mix_probabilities = _apply_power_calibration
    base.LowRankAutoregressiveAdapter.train = _train_low_rank
    base.LatentProjection.train = _train_projection
    base.ConvolutionalVisionProxy.train = _train_vision

    initial = base.run_microcandidate_lane(output_dir, seed=seed)
    candidates = {
        "lora": _train_balanced_lora(output_dir / "lora", seed, initial["summary"]["dataset_digest"]),
        "embedding": _canonicalise_candidate("embedding", initial["candidates"]["embedding"], output_dir),
        "vision": _canonicalise_candidate("vision", initial["candidates"]["vision"], output_dir),
    }
    packs = [candidates[name]["pack"] for name in ("lora", "embedding", "vision")]
    board = CandidateReviewBoard().compare(packs)
    (output_dir / "candidate-review-board.json").write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "version": CONTROL_VERSION,
        "seed": seed,
        "dataset_digest": initial["summary"]["dataset_digest"],
        "candidate_ids": [pack["evidence"]["candidate_id"] for pack in packs],
        "board_digest": board["board_digest"],
        "promotion_permitted": False,
        "human_review_required": True,
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return {"summary": summary, "candidates": candidates, "board": board}
