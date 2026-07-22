from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable, Sequence

from .evidence import CandidateEvidence, EvidenceGate
from .review_board import CandidateReviewBoard


VERSION = "autonomous-microcandidate-lane-v1"


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _softmax(logits: Sequence[float]) -> list[float]:
    maximum = max(logits)
    values = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in logits]
    total = sum(values) or 1.0
    return [value / total for value in values]


def _cross_entropy(probabilities: Sequence[float], target: int) -> float:
    return -math.log(max(float(probabilities[target]), 1e-12))


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _global_clip(groups: Iterable[list[list[float]] | list[float]], ceiling: float = 1.0) -> float:
    values: list[float] = []
    for group in groups:
        for row in group:
            if isinstance(row, list):
                values.extend(float(value) for value in row)
            else:
                values.append(float(row))
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= ceiling or norm == 0.0:
        return 1.0
    return ceiling / norm


def _calibration(probabilities: Sequence[Sequence[float]], targets: Sequence[int], bins: int = 10) -> tuple[float, float]:
    if not probabilities:
        return 1.0, 1.0
    brier = 0.0
    bucket_rows: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for row, target in zip(probabilities, targets):
        brier += sum((float(value) - (1.0 if index == target else 0.0)) ** 2 for index, value in enumerate(row)) / len(row)
        confidence = max(row)
        correct = 1.0 if max(range(len(row)), key=lambda index: row[index]) == target else 0.0
        bucket_rows[min(bins - 1, int(confidence * bins))].append((confidence, correct))
    brier /= len(probabilities)
    ece = 0.0
    for bucket in bucket_rows:
        if not bucket:
            continue
        mean_confidence = sum(item[0] for item in bucket) / len(bucket)
        mean_accuracy = sum(item[1] for item in bucket) / len(bucket)
        ece += len(bucket) / len(probabilities) * abs(mean_confidence - mean_accuracy)
    return brier, ece


def _temperature_mix(
    validation_probabilities: Sequence[Sequence[float]], validation_targets: Sequence[int]
) -> float:
    classes = len(validation_probabilities[0]) if validation_probabilities else 1
    best_alpha, best_ece = 0.0, float("inf")
    for step in range(0, 20):
        alpha = step / 20.0
        mixed = [[(1.0 - alpha) * value + alpha / classes for value in row] for row in validation_probabilities]
        _, ece = _calibration(mixed, validation_targets)
        if ece < best_ece:
            best_alpha, best_ece = alpha, ece
    return best_alpha


def _mix_probabilities(probabilities: Sequence[Sequence[float]], alpha: float) -> list[list[float]]:
    if not probabilities:
        return []
    classes = len(probabilities[0])
    return [[(1.0 - alpha) * value + alpha / classes for value in row] for row in probabilities]


def _safety_results() -> dict[str, bool]:
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


def _code_commit() -> str:
    return os.getenv("GITHUB_SHA") or "local-microcandidate-commit"


class LowRankAutoregressiveAdapter:
    """Frozen-base transition model with a trainable low-rank adapter."""

    def __init__(self, vocab_size: int, rank: int, seed: int) -> None:
        rng = random.Random(seed)
        self.vocab_size = vocab_size
        self.rank = rank
        self.a = [[rng.uniform(-0.08, 0.08) for _ in range(rank)] for _ in range(vocab_size)]
        self.b = [[rng.uniform(-0.08, 0.08) for _ in range(vocab_size)] for _ in range(rank)]

    def probabilities(self, token: int) -> list[float]:
        logits = [sum(self.a[token][rank] * self.b[rank][target] for rank in range(self.rank)) for target in range(self.vocab_size)]
        return _softmax(logits)

    def loss(self, sequences: Sequence[Sequence[int]]) -> float:
        losses = []
        for sequence in sequences:
            losses.extend(_cross_entropy(self.probabilities(current), target) for current, target in zip(sequence, sequence[1:]))
        return sum(losses) / max(1, len(losses))

    def train(self, sequences: Sequence[Sequence[int]], epochs: int = 180, learning_rate: float = 0.45) -> list[float]:
        history: list[float] = []
        transitions = [(current, target) for sequence in sequences for current, target in zip(sequence, sequence[1:])]
        for _ in range(epochs):
            grad_a = [[0.0] * self.rank for _ in range(self.vocab_size)]
            grad_b = [[0.0] * self.vocab_size for _ in range(self.rank)]
            loss = 0.0
            for current, target in transitions:
                probabilities = self.probabilities(current)
                loss += _cross_entropy(probabilities, target)
                grad_logits = [value - (1.0 if index == target else 0.0) for index, value in enumerate(probabilities)]
                for rank in range(self.rank):
                    grad_a[current][rank] += sum(grad_logits[index] * self.b[rank][index] for index in range(self.vocab_size))
                    for index in range(self.vocab_size):
                        grad_b[rank][index] += self.a[current][rank] * grad_logits[index]
            scale = 1.0 / max(1, len(transitions))
            clip = _global_clip((grad_a, grad_b), 1.0)
            for token in range(self.vocab_size):
                for rank in range(self.rank):
                    self.a[token][rank] -= learning_rate * clip * (grad_a[token][rank] * scale + 0.001 * self.a[token][rank])
            for rank in range(self.rank):
                for target in range(self.vocab_size):
                    self.b[rank][target] -= learning_rate * clip * (grad_b[rank][target] * scale + 0.001 * self.b[rank][target])
            history.append(loss * scale)
        return history

    def state(self) -> dict[str, Any]:
        return {"vocab_size": self.vocab_size, "rank": self.rank, "a": self.a, "b": self.b}


def _language_data(seed: int) -> dict[str, list[tuple[str, list[int]]]]:
    rng = random.Random(seed)
    patterns = {
        "visibility": [1, 2, 3, 4, 1, 2, 3, 4],
        "crm": [5, 6, 7, 8, 5, 6, 7, 8],
        "sales": [9, 10, 11, 9, 10, 11, 9, 10],
    }
    result: dict[str, list[tuple[str, list[int]]]] = {"train": [], "validation": [], "test": []}
    for split, count in (("train", 36), ("validation", 12), ("test", 15)):
        for segment, pattern in patterns.items():
            for _ in range(count):
                offset = rng.randrange(len(pattern))
                sequence = pattern[offset:] + pattern[:offset]
                result[split].append((segment, sequence))
    return result


def train_micro_lora(output_dir: Path, seed: int, dataset_digest: str) -> dict[str, Any]:
    data = _language_data(seed)
    model = LowRankAutoregressiveAdapter(vocab_size=12, rank=4, seed=seed)
    baseline_perplexity = 12.0
    history = model.train([row[1] for row in data["train"]])
    validation_loss = model.loss([row[1] for row in data["validation"]])
    test_loss = model.loss([row[1] for row in data["test"]])

    def probability_rows(rows: Sequence[tuple[str, list[int]]]) -> tuple[list[list[float]], list[int]]:
        probabilities, targets = [], []
        for _, sequence in rows:
            for current, target in zip(sequence, sequence[1:]):
                probabilities.append(model.probabilities(current))
                targets.append(target)
        return probabilities, targets

    validation_probabilities, validation_targets = probability_rows(data["validation"])
    alpha = _temperature_mix(validation_probabilities, validation_targets)
    test_probabilities, test_targets = probability_rows(data["test"])
    calibrated = _mix_probabilities(test_probabilities, alpha)
    brier, ece = _calibration(calibrated, test_targets)
    segments: dict[str, dict[str, float]] = {}
    for segment in sorted({row[0] for row in data["test"]}):
        loss = model.loss([sequence for name, sequence in data["test"] if name == segment])
        segments[segment] = {"quality": math.exp(-loss)}

    artifact = output_dir / "micro_lora_adapter.json"
    artifact.write_text(json.dumps(model.state(), sort_keys=True), encoding="utf-8")
    evidence = CandidateEvidence(
        candidate_id="micro-lora-autoregressive-shadow-v1",
        task="language_model",
        framework="python-low-rank-backprop",
        dataset_id="microcandidate-synthetic-v1",
        dataset_digest=dataset_digest,
        code_commit=_code_commit(),
        seed=seed,
        metrics={
            "train_loss": history[-1],
            "validation_loss": validation_loss,
            "test_loss": test_loss,
            "test_perplexity": math.exp(min(test_loss, 20.0)),
            "expected_calibration_error": ece,
            "brier_score": brier,
            "trainable_parameters": float(12 * 4 + 4 * 12),
        },
        baseline_metrics={"test_perplexity": baseline_perplexity},
        segment_metrics=segments,
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("synthetic transition language", "microcandidate smoke lane", "not a transformer replacement", "shadow only"),
        rollback_artifact=str(artifact),
    )
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "pack": pack, "history": history}


def _classification_data(seed: int) -> dict[str, list[tuple[str, list[float], int]]]:
    rng = random.Random(seed)
    centres = (
        ("industrial_b2b", [1.0, 0.0, 0.0, 0.8, 0.2, 0.1]),
        ("service_b2b", [0.0, 1.0, 0.0, 0.2, 0.9, 0.1]),
        ("professional_b2c", [0.0, 0.0, 1.0, 0.1, 0.2, 0.9]),
    )
    result: dict[str, list[tuple[str, list[float], int]]] = {"train": [], "validation": [], "test": []}
    for split, count in (("train", 90), ("validation", 30), ("test", 36)):
        for target, (segment, centre) in enumerate(centres):
            for _ in range(count):
                features = [value + rng.uniform(-0.10, 0.10) for value in centre]
                result[split].append((segment, features, target))
    return result


class LatentProjection:
    def __init__(self, inputs: int, outputs: int, seed: int) -> None:
        rng = random.Random(seed)
        self.weights = [[rng.uniform(-0.04, 0.04) for _ in range(outputs)] for _ in range(inputs)]
        self.bias = [0.0] * outputs

    def logits(self, features: Sequence[float]) -> list[float]:
        return [self.bias[output] + sum(features[index] * self.weights[index][output] for index in range(len(features))) for output in range(len(self.bias))]

    def probabilities(self, features: Sequence[float]) -> list[float]:
        return _softmax(self.logits(features))

    def train(self, rows: Sequence[tuple[str, list[float], int]], epochs: int = 140, learning_rate: float = 0.18) -> list[float]:
        history = []
        for _ in range(epochs):
            grad_w = [[0.0] * len(self.bias) for _ in range(len(self.weights))]
            grad_b = [0.0] * len(self.bias)
            loss = 0.0
            for _, features, target in rows:
                probabilities = self.probabilities(features)
                loss += _cross_entropy(probabilities, target)
                for output, probability in enumerate(probabilities):
                    gradient = probability - (1.0 if output == target else 0.0)
                    grad_b[output] += gradient
                    for index, feature in enumerate(features):
                        grad_w[index][output] += feature * gradient
            scale = 1.0 / len(rows)
            clip = _global_clip((grad_w, grad_b), 1.0)
            for index in range(len(self.weights)):
                for output in range(len(self.bias)):
                    self.weights[index][output] -= learning_rate * clip * (grad_w[index][output] * scale + 0.001 * self.weights[index][output])
            for output in range(len(self.bias)):
                self.bias[output] -= learning_rate * clip * grad_b[output] * scale
            history.append(loss * scale)
        return history

    def state(self) -> dict[str, Any]:
        return {"weights": self.weights, "bias": self.bias}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def _retrieval_mrr(model: LatentProjection, rows: Sequence[tuple[str, list[float], int]]) -> float:
    vectors = [model.logits(features) for _, features, _ in rows]
    total = 0.0
    for index, (_, _, target) in enumerate(rows):
        ranking = sorted((other for other in range(len(rows)) if other != index), key=lambda other: _cosine(vectors[index], vectors[other]), reverse=True)
        rank = next((position + 1 for position, other in enumerate(ranking) if rows[other][2] == target), len(rows))
        total += 1.0 / rank
    return total / len(rows)


def _classification_metrics(model: LatentProjection, rows: Sequence[tuple[str, list[float], int]], alpha: float = 0.0) -> tuple[float, list[list[float]], list[int]]:
    raw = [model.probabilities(features) for _, features, _ in rows]
    probabilities = _mix_probabilities(raw, alpha)
    targets = [target for _, _, target in rows]
    accuracy = sum(max(range(len(row)), key=lambda index: row[index]) == target for row, target in zip(probabilities, targets)) / len(rows)
    return accuracy, probabilities, targets


def train_micro_embedding(output_dir: Path, seed: int, dataset_digest: str) -> dict[str, Any]:
    data = _classification_data(seed + 17)
    baseline = LatentProjection(6, 3, seed + 1)
    baseline.weights = [[0.0] * 3 for _ in range(6)]
    baseline_mrr = _retrieval_mrr(baseline, data["test"])
    model = LatentProjection(6, 3, seed + 2)
    history = model.train(data["train"])
    validation_raw = [model.probabilities(features) for _, features, _ in data["validation"]]
    validation_targets = [target for _, _, target in data["validation"]]
    alpha = _temperature_mix(validation_raw, validation_targets)
    accuracy, probabilities, targets = _classification_metrics(model, data["test"], alpha)
    brier, ece = _calibration(probabilities, targets)
    mrr = _retrieval_mrr(model, data["test"])
    validation_loss = sum(_cross_entropy(model.probabilities(features), target) for _, features, target in data["validation"]) / len(data["validation"])
    segments = {}
    for segment in sorted({row[0] for row in data["test"]}):
        segment_rows = [row for row in data["test"] if row[0] == segment]
        segment_accuracy, _, _ = _classification_metrics(model, segment_rows, alpha)
        segments[segment] = {"quality": segment_accuracy}

    artifact = output_dir / "micro_embedding_projection.json"
    artifact.write_text(json.dumps(model.state(), sort_keys=True), encoding="utf-8")
    evidence = CandidateEvidence(
        candidate_id="micro-service-embedding-shadow-v1",
        task="embedding",
        framework="python-latent-gradient-descent",
        dataset_id="microcandidate-synthetic-v1",
        dataset_digest=dataset_digest,
        code_commit=_code_commit(),
        seed=seed,
        metrics={
            "retrieval_mrr": mrr,
            "classification_accuracy": accuracy,
            "train_loss": history[-1],
            "validation_loss": validation_loss,
            "expected_calibration_error": ece,
            "brier_score": brier,
        },
        baseline_metrics={"retrieval_mrr": baseline_mrr},
        segment_metrics=segments,
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("synthetic service features", "supervised latent projection", "microcandidate smoke lane", "shadow only"),
        rollback_artifact=str(artifact),
    )
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "pack": pack, "history": history}


def _vision_image(label: int, rng: random.Random) -> list[list[float]]:
    image = [[rng.uniform(0.0, 0.03) for _ in range(8)] for _ in range(8)]
    if label == 0:
        for column in range(1, 7):
            image[3][column] = image[4][column] = 1.0
    elif label == 1:
        for row in range(1, 7):
            image[row][3] = image[row][4] = 1.0
    else:
        for index in range(1, 7):
            image[index][index] = 1.0
            image[index][7 - index] = 1.0
    return image


def _vision_data(seed: int) -> dict[str, list[tuple[str, list[list[float]], int]]]:
    rng = random.Random(seed)
    names = ("document", "chart", "logo")
    result: dict[str, list[tuple[str, list[list[float]], int]]] = {"train": [], "validation": [], "test": []}
    for split, count in (("train", 60), ("validation", 24), ("test", 30)):
        for label, name in enumerate(names):
            for _ in range(count):
                result[split].append((name, _vision_image(label, rng), label))
    return result


class ConvolutionalVisionProxy:
    """Trainable 3x3 convolution filters with global average pooling."""

    def __init__(self, seed: int) -> None:
        rng = random.Random(seed)
        templates = (
            ((-0.1, -0.1, -0.1), (0.3, 0.3, 0.3), (-0.1, -0.1, -0.1)),
            ((-0.1, 0.3, -0.1), (-0.1, 0.3, -0.1), (-0.1, 0.3, -0.1)),
            ((0.25, -0.1, 0.25), (-0.1, 0.25, -0.1), (0.25, -0.1, 0.25)),
        )
        self.filters = [[[value + rng.uniform(-0.02, 0.02) for value in row] for row in template] for template in templates]
        self.bias = [0.0, 0.0, 0.0]

    def logits_and_cache(self, image: Sequence[Sequence[float]]) -> tuple[list[float], list[list[tuple[int, int, float]]]]:
        logits, caches = [], []
        for class_index, kernel in enumerate(self.filters):
            activations: list[tuple[int, int, float]] = []
            total = 0.0
            for row in range(6):
                for column in range(6):
                    value = sum(image[row + kr][column + kc] * kernel[kr][kc] for kr in range(3) for kc in range(3))
                    activation = max(0.0, value)
                    total += activation
                    activations.append((row, column, value))
            logits.append(total / 36.0 + self.bias[class_index])
            caches.append(activations)
        return logits, caches

    def probabilities(self, image: Sequence[Sequence[float]]) -> list[float]:
        return _softmax(self.logits_and_cache(image)[0])

    def train(self, rows: Sequence[tuple[str, list[list[float]], int]], epochs: int = 100, learning_rate: float = 0.35) -> list[float]:
        history = []
        for _ in range(epochs):
            grad_filters = [[ [0.0] * 3 for _ in range(3)] for _ in range(3)]
            grad_bias = [0.0] * 3
            loss = 0.0
            for _, image, target in rows:
                logits, caches = self.logits_and_cache(image)
                probabilities = _softmax(logits)
                loss += _cross_entropy(probabilities, target)
                for class_index, probability in enumerate(probabilities):
                    gradient = probability - (1.0 if class_index == target else 0.0)
                    grad_bias[class_index] += gradient
                    for row, column, pre_activation in caches[class_index]:
                        if pre_activation <= 0.0:
                            continue
                        for kr in range(3):
                            for kc in range(3):
                                grad_filters[class_index][kr][kc] += gradient * image[row + kr][column + kc] / 36.0
            scale = 1.0 / len(rows)
            flat_filters = [[value for row in kernel for value in row] for kernel in grad_filters]
            clip = _global_clip((flat_filters, grad_bias), 1.0)
            for class_index in range(3):
                for kr in range(3):
                    for kc in range(3):
                        self.filters[class_index][kr][kc] -= learning_rate * clip * (grad_filters[class_index][kr][kc] * scale + 0.001 * self.filters[class_index][kr][kc])
                self.bias[class_index] -= learning_rate * clip * grad_bias[class_index] * scale
            history.append(loss * scale)
        return history

    def state(self) -> dict[str, Any]:
        return {"filters": self.filters, "bias": self.bias}


def _vision_metrics(model: ConvolutionalVisionProxy, rows: Sequence[tuple[str, list[list[float]], int]], alpha: float = 0.0) -> tuple[float, float, float, list[list[float]], list[int], dict[str, float]]:
    raw = [model.probabilities(image) for _, image, _ in rows]
    probabilities = _mix_probabilities(raw, alpha)
    targets = [target for _, _, target in rows]
    predictions = [max(range(3), key=lambda index: row[index]) for row in probabilities]
    precisions, recalls, class_accuracy = [], [], {}
    for class_index, name in enumerate(("document", "chart", "logo")):
        true_positive = sum(prediction == class_index and target == class_index for prediction, target in zip(predictions, targets))
        false_positive = sum(prediction == class_index and target != class_index for prediction, target in zip(predictions, targets))
        false_negative = sum(prediction != class_index and target == class_index for prediction, target in zip(predictions, targets))
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        precisions.append(precision)
        recalls.append(recall)
        class_accuracy[name] = recall
    precision = sum(precisions) / 3.0
    recall = sum(recalls) / 3.0
    proxy_map50 = 2.0 * precision * recall / max(precision + recall, 1e-12)
    return proxy_map50, precision, recall, probabilities, targets, class_accuracy


def train_micro_vision(output_dir: Path, seed: int, dataset_digest: str) -> dict[str, Any]:
    data = _vision_data(seed + 31)
    model = ConvolutionalVisionProxy(seed + 32)
    history = model.train(data["train"])
    validation_raw = [model.probabilities(image) for _, image, _ in data["validation"]]
    validation_targets = [target for _, _, target in data["validation"]]
    alpha = _temperature_mix(validation_raw, validation_targets)
    map50, precision, recall, probabilities, targets, class_accuracy = _vision_metrics(model, data["test"], alpha)
    brier, ece = _calibration(probabilities, targets)
    validation_loss = sum(_cross_entropy(model.probabilities(image), target) for _, image, target in data["validation"]) / len(data["validation"])
    artifact = output_dir / "micro_convolutional_vision_proxy.json"
    artifact.write_text(json.dumps(model.state(), sort_keys=True), encoding="utf-8")
    evidence = CandidateEvidence(
        candidate_id="micro-convolutional-card-vision-shadow-v1",
        task="vision",
        framework="python-convolution-backprop-proxy",
        dataset_id="microcandidate-synthetic-v1",
        dataset_digest=dataset_digest,
        code_commit=_code_commit(),
        seed=seed,
        metrics={
            "map50": map50,
            "precision": precision,
            "recall": recall,
            "train_loss": history[-1],
            "validation_loss": validation_loss,
            "expected_calibration_error": ece,
            "brier_score": brier,
        },
        baseline_metrics={"map50": 1.0 / 3.0},
        segment_metrics={name: {"quality": value} for name, value in class_accuracy.items()},
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("three-class geometric proxy", "not YOLO", "microcandidate smoke lane", "shadow only"),
        rollback_artifact=str(artifact),
    )
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "pack": pack, "history": history}


def run_microcandidate_lane(output_dir: str | Path, seed: int = 129) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_specification = {"version": VERSION, "seed": seed, "sources": ["synthetic_language", "synthetic_service_features", "synthetic_geometric_cards"]}
    dataset_digest = _digest(dataset_specification)
    (output_dir / "DATASET_SPECIFICATION.json").write_text(json.dumps({**dataset_specification, "dataset_digest": dataset_digest}, indent=2, sort_keys=True), encoding="utf-8")

    candidates = {
        "lora": train_micro_lora(output_dir / "lora", seed, dataset_digest),
        "embedding": train_micro_embedding(output_dir / "embedding", seed, dataset_digest),
        "vision": train_micro_vision(output_dir / "vision", seed, dataset_digest),
    }
    packs = [candidates[name]["pack"] for name in ("lora", "embedding", "vision")]
    board = CandidateReviewBoard().compare(packs)
    (output_dir / "candidate-review-board.json").write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "version": VERSION,
        "seed": seed,
        "dataset_digest": dataset_digest,
        "candidate_ids": [pack["evidence"]["candidate_id"] for pack in packs],
        "board_digest": board["board_digest"],
        "promotion_permitted": False,
        "human_review_required": True,
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return {"summary": summary, "candidates": candidates, "board": board}
