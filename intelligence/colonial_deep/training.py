from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import random
from typing import Callable, Iterable, Sequence

from .core import Scalar, gradient_clip


@dataclass(frozen=True)
class HyperParameters:
    learning_rate: float = 0.01
    weight_decay: float = 0.001
    dropout: float = 0.10
    batch_size: int = 8
    epochs: int = 40
    patience: int = 6
    gradient_clip_norm: float = 1.0
    lora_rank: int = 4
    lora_alpha: float = 8.0
    label_smoothing: float = 0.02
    seed: int = 211

    def validate(self):
        if not 0 < self.learning_rate <= 1:
            raise ValueError("learning_rate outside range")
        if not 0 <= self.weight_decay < 1:
            raise ValueError("weight_decay outside range")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout outside range")
        if self.batch_size < 1 or self.epochs < 1 or self.patience < 1:
            raise ValueError("training counts must be positive")
        if self.lora_rank < 1 or self.lora_alpha <= 0:
            raise ValueError("LoRA configuration invalid")
        return self


class DenseLayer:
    def __init__(self, inputs, outputs, seed=223):
        rng = random.Random(seed)
        scale = math.sqrt(2.0 / max(inputs, 1))
        self.weights = [[Scalar(rng.uniform(-scale, scale)) for _ in range(outputs)] for _ in range(inputs)]
        self.bias = [Scalar(0.0) for _ in range(outputs)]

    def parameters(self):
        return [item for row in self.weights for item in row] + self.bias

    def __call__(self, vector):
        output = []
        for column in range(len(self.bias)):
            value = self.bias[column]
            for row, feature in enumerate(vector):
                value = value + feature * self.weights[row][column]
            output.append(value)
        return output


class LoRAAdapter:
    """Low-rank adapter that leaves the base matrix frozen."""

    def __init__(self, inputs, outputs, rank=4, alpha=8.0, seed=227):
        rng = random.Random(seed)
        self.inputs = inputs
        self.outputs = outputs
        self.rank = rank
        self.alpha = alpha
        self.a = [[Scalar(rng.uniform(-0.05, 0.05)) for _ in range(rank)] for _ in range(inputs)]
        self.b = [[Scalar(0.0) for _ in range(outputs)] for _ in range(rank)]

    @property
    def scale(self):
        return self.alpha / self.rank

    def parameters(self):
        return [value for row in self.a for value in row] + [value for row in self.b for value in row]

    def delta(self, vector):
        low_rank = []
        for hidden in range(self.rank):
            value = Scalar(0.0)
            for index, feature in enumerate(vector):
                value = value + feature * self.a[index][hidden]
            low_rank.append(value)
        output = []
        for column in range(self.outputs):
            value = Scalar(0.0)
            for hidden in range(self.rank):
                value = value + low_rank[hidden] * self.b[hidden][column]
            output.append(value * self.scale)
        return output


class PEFTDense:
    def __init__(self, base_weights, base_bias, rank=4, alpha=8.0, seed=229):
        self.base_weights = [[float(value) for value in row] for row in base_weights]
        self.base_bias = [float(value) for value in base_bias]
        self.adapter = LoRAAdapter(len(base_weights), len(base_bias), rank, alpha, seed)

    def parameters(self):
        return self.adapter.parameters()

    def __call__(self, vector):
        base = [
            self.base_bias[column] + sum(float(vector[row].data if isinstance(vector[row], Scalar) else vector[row]) * self.base_weights[row][column] for row in range(len(vector)))
            for column in range(len(self.base_bias))
        ]
        delta = self.adapter.delta(vector)
        return [Scalar(base[index]) + delta[index] for index in range(len(base))]


class AdamW:
    def __init__(self, parameters: Iterable[Scalar], learning_rate=0.01, weight_decay=0.001, beta1=0.9, beta2=0.999):
        self.parameters = list(parameters)
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.beta1 = beta1
        self.beta2 = beta2
        self.m = [0.0] * len(self.parameters)
        self.v = [0.0] * len(self.parameters)
        self.step_index = 0

    def zero_grad(self):
        for parameter in self.parameters:
            parameter.grad = 0.0

    def step(self):
        self.step_index += 1
        for index, parameter in enumerate(self.parameters):
            gradient = parameter.grad + self.weight_decay * parameter.data
            self.m[index] = self.beta1 * self.m[index] + (1 - self.beta1) * gradient
            self.v[index] = self.beta2 * self.v[index] + (1 - self.beta2) * gradient * gradient
            m_hat = self.m[index] / (1 - self.beta1 ** self.step_index)
            v_hat = self.v[index] / (1 - self.beta2 ** self.step_index)
            parameter.data -= self.learning_rate * m_hat / (math.sqrt(v_hat) + 1e-8)


@dataclass
class TrainingHistory:
    train_loss: list[float] = field(default_factory=list)
    validation_loss: list[float] = field(default_factory=list)
    gradient_norm: list[float] = field(default_factory=list)
    best_epoch: int = -1
    stopped_early: bool = False


class EarlyStopping:
    def __init__(self, patience=6, minimum_delta=1e-5):
        self.patience = patience
        self.minimum_delta = minimum_delta
        self.best = float("inf")
        self.wait = 0

    def update(self, value):
        if value < self.best - self.minimum_delta:
            self.best = value
            self.wait = 0
            return False, True
        self.wait += 1
        return self.wait >= self.patience, False


def deterministic_split(items, validation_fraction=0.2):
    if not items:
        return [], []
    split = max(1, min(len(items) - 1, int(round(len(items) * (1 - validation_fraction))))) if len(items) > 1 else 1
    return list(items[:split]), list(items[split:])


def dropout(vector, probability, rng):
    if probability <= 0:
        return list(vector)
    scale = 1.0 / (1.0 - probability)
    return [value * scale if rng.random() >= probability else Scalar(0.0) if isinstance(value, Scalar) else 0.0 for value in vector]


def mse_loss(prediction, target):
    losses = [(prediction[index] - float(target[index])).pow(2.0) for index in range(len(target))]
    total = Scalar(0.0)
    for loss in losses:
        total = total + loss
    return total / len(losses)


def train_peft_regressor(model: PEFTDense, train_rows, validation_rows, hyperparameters=HyperParameters()):
    hp = hyperparameters.validate()
    optimiser = AdamW(model.parameters(), hp.learning_rate, hp.weight_decay)
    stopping = EarlyStopping(hp.patience)
    history = TrainingHistory()
    rng = random.Random(hp.seed)
    best_snapshot = [parameter.data for parameter in model.parameters()]

    def evaluate(rows):
        if not rows:
            return 0.0
        total = 0.0
        for features, target in rows:
            prediction = model([Scalar(value) for value in features])
            total += sum((prediction[index].data - target[index]) ** 2 for index in range(len(target))) / len(target)
        return total / len(rows)

    for epoch in range(hp.epochs):
        shuffled = list(train_rows)
        rng.shuffle(shuffled)
        epoch_loss = 0.0
        for features, target in shuffled:
            optimiser.zero_grad()
            vector = dropout([Scalar(value) for value in features], hp.dropout, rng)
            prediction = model(vector)
            loss = mse_loss(prediction, target)
            loss.backward()
            norm, _ = gradient_clip(model.parameters(), hp.gradient_clip_norm)
            optimiser.step()
            epoch_loss += loss.data
        train_loss = epoch_loss / max(len(shuffled), 1)
        validation_loss = evaluate(validation_rows)
        history.train_loss.append(train_loss)
        history.validation_loss.append(validation_loss)
        history.gradient_norm.append(norm if shuffled else 0.0)
        stop, improved = stopping.update(validation_loss)
        if improved:
            history.best_epoch = epoch
            best_snapshot = [parameter.data for parameter in model.parameters()]
        if stop:
            history.stopped_early = True
            break

    for parameter, value in zip(model.parameters(), best_snapshot):
        parameter.data = value
    return history


@dataclass(frozen=True)
class TrialResult:
    trial_id: str
    hyperparameters: HyperParameters
    score: float
    overfit_gap: float


class HyperparameterAutotuner:
    def __init__(self, seed=233):
        self.seed = seed

    def search(self, evaluator: Callable[[HyperParameters], tuple[float, float]], trials=8):
        rng = random.Random(self.seed)
        results = []
        for index in range(trials):
            hp = HyperParameters(
                learning_rate=10 ** rng.uniform(-3.0, -1.2),
                weight_decay=10 ** rng.uniform(-5.0, -2.0),
                dropout=rng.uniform(0.0, 0.35),
                batch_size=rng.choice([4, 8, 16]),
                epochs=rng.choice([20, 30, 40]),
                patience=rng.choice([4, 6, 8]),
                gradient_clip_norm=rng.choice([0.5, 1.0, 2.0]),
                lora_rank=rng.choice([2, 4, 8]),
                lora_alpha=rng.choice([4.0, 8.0, 16.0]),
                label_smoothing=rng.choice([0.0, 0.02, 0.05]),
                seed=self.seed + index,
            )
            validation_loss, train_loss = evaluator(hp)
            gap = max(0.0, validation_loss - train_loss)
            score = validation_loss + gap * 0.75
            digest = hashlib.sha256(json.dumps(hp.__dict__, sort_keys=True).encode()).hexdigest()[:12].upper()
            results.append(TrialResult(f"HTUNE-{digest}", hp, score, gap))
        return sorted(results, key=lambda item: item.score)


def model_card(model_name, hyperparameters, history, dataset_digest, limitations):
    payload = {
        "model_name": model_name,
        "hyperparameters": hyperparameters.__dict__,
        "dataset_digest": dataset_digest,
        "best_epoch": history.best_epoch,
        "stopped_early": history.stopped_early,
        "final_train_loss": history.train_loss[-1] if history.train_loss else None,
        "final_validation_loss": history.validation_loss[-1] if history.validation_loss else None,
        "limitations": list(limitations),
        "promotion": "human_review_required",
    }
    payload["card_digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
