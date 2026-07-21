from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _softmax(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    maximum = max(values)
    exponents = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in values]
    total = sum(exponents) or 1.0
    return [value / total for value in exponents]


def _relu(value: float) -> float:
    return value if value > 0.0 else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    centre = _mean(values)
    return sum((value - centre) ** 2 for value in values) / len(values)


def _matvec(vector: Sequence[float], weights: Sequence[Sequence[float]], bias: Sequence[float]) -> list[float]:
    if len(weights) != len(vector):
        raise ValueError("matrix input dimension mismatch")
    output_size = len(bias)
    result = [float(bias[index]) for index in range(output_size)]
    for input_index, input_value in enumerate(vector):
        row = weights[input_index]
        if len(row) != output_size:
            raise ValueError("matrix output dimension mismatch")
        for output_index in range(output_size):
            result[output_index] += float(input_value) * float(row[output_index])
    return result


def _weights(rng: random.Random, inputs: int, outputs: int, scale: float = 0.35) -> list[list[float]]:
    return [[rng.uniform(-scale, scale) for _ in range(outputs)] for _ in range(inputs)]


def _bias(rng: random.Random, outputs: int, scale: float = 0.08) -> list[float]:
    return [rng.uniform(-scale, scale) for _ in range(outputs)]


@dataclass(frozen=True)
class NeuralPrediction:
    conversion_probability: float
    relationship_strength: float
    urgency_probability: float
    churn_risk: float
    action_probabilities: dict[str, float]
    confidence: float
    uncertainty: float
    ensemble_size: int


class Conv1DEncoder:
    """Small 1D CNN for ordered CRM activity sequences.

    Input shape is ``timesteps x feature_count``. Convolution is followed by
    ReLU and global max pooling. The implementation is dependency-free so the
    shadow contract can run in standard CI and Apps-adjacent environments.
    """

    def __init__(self, rng: random.Random, feature_count: int, channels: int = 4, kernel_width: int = 3) -> None:
        self.feature_count = feature_count
        self.channels = channels
        self.kernel_width = kernel_width
        self.kernels = [
            [
                [rng.uniform(-0.28, 0.28) for _ in range(feature_count)]
                for _ in range(kernel_width)
            ]
            for _ in range(channels)
        ]
        self.bias = _bias(rng, channels, 0.04)

    def encode(self, sequence: Sequence[Sequence[float]]) -> list[float]:
        if not sequence:
            return [0.0] * self.channels
        for step in sequence:
            if len(step) != self.feature_count:
                raise ValueError("activity sequence feature dimension mismatch")
        padded = [list(map(float, step)) for step in sequence]
        while len(padded) < self.kernel_width:
            padded.insert(0, [0.0] * self.feature_count)
        pooled = [-float("inf")] * self.channels
        for start in range(0, len(padded) - self.kernel_width + 1):
            for channel in range(self.channels):
                activation = self.bias[channel]
                for offset in range(self.kernel_width):
                    for feature in range(self.feature_count):
                        activation += padded[start + offset][feature] * self.kernels[channel][offset][feature]
                pooled[channel] = max(pooled[channel], _relu(activation))
        return [0.0 if value == -float("inf") else value for value in pooled]


class GraphNeuralEncoder:
    """Two message-passing layers over the CRM relationship graph."""

    def __init__(self, rng: random.Random, feature_count: int, hidden: int = 6, output: int = 5) -> None:
        self.feature_count = feature_count
        self.hidden = hidden
        self.output = output
        self.first = _weights(rng, feature_count, hidden, 0.30)
        self.first_bias = _bias(rng, hidden, 0.04)
        self.second = _weights(rng, hidden, output, 0.30)
        self.second_bias = _bias(rng, output, 0.04)

    @staticmethod
    def _aggregate(features: Sequence[Sequence[float]], adjacency: Sequence[Sequence[float]]) -> list[list[float]]:
        size = len(features)
        if len(adjacency) != size or any(len(row) != size for row in adjacency):
            raise ValueError("graph adjacency dimension mismatch")
        aggregated: list[list[float]] = []
        for node in range(size):
            weights = [max(0.0, float(value)) for value in adjacency[node]]
            weights[node] += 1.0
            total = sum(weights) or 1.0
            vector = [0.0] * len(features[node])
            for neighbour, edge_weight in enumerate(weights):
                for feature_index, feature_value in enumerate(features[neighbour]):
                    vector[feature_index] += edge_weight * float(feature_value) / total
            aggregated.append(vector)
        return aggregated

    def encode(self, node_features: Sequence[Sequence[float]], adjacency: Sequence[Sequence[float]], focus_index: int) -> list[float]:
        if not node_features:
            return [0.0] * self.output
        if focus_index < 0 or focus_index >= len(node_features):
            raise ValueError("graph focus index is invalid")
        for node in node_features:
            if len(node) != self.feature_count:
                raise ValueError("graph node feature dimension mismatch")
        first_messages = self._aggregate(node_features, adjacency)
        first_hidden = [[math.tanh(value) for value in _matvec(node, self.first, self.first_bias)] for node in first_messages]
        second_messages = self._aggregate(first_hidden, adjacency)
        second_hidden = [[math.tanh(value) for value in _matvec(node, self.second, self.second_bias)] for node in second_messages]
        return second_hidden[focus_index]


class FusionMember:
    ACTIONS = ("research", "request_review", "prepare_discovery", "create_opportunity", "nurture")

    def __init__(self, seed: int, tabular_size: int, text_size: int, activity_features: int, graph_features: int) -> None:
        rng = random.Random(seed)
        self.cnn = Conv1DEncoder(rng, activity_features)
        self.gnn = GraphNeuralEncoder(rng, graph_features)
        fused_size = tabular_size + text_size + self.cnn.channels + self.gnn.output
        hidden_a = 18
        hidden_b = 10
        outputs = 4 + len(self.ACTIONS)
        self.layer_a = _weights(rng, fused_size, hidden_a, 0.20)
        self.bias_a = _bias(rng, hidden_a, 0.05)
        self.layer_b = _weights(rng, hidden_a, hidden_b, 0.24)
        self.bias_b = _bias(rng, hidden_b, 0.05)
        self.output = _weights(rng, hidden_b, outputs, 0.28)
        self.output_bias = _bias(rng, outputs, 0.06)

    def infer(
        self,
        tabular: Sequence[float],
        text_vector: Sequence[float],
        activity_sequence: Sequence[Sequence[float]],
        graph_nodes: Sequence[Sequence[float]],
        adjacency: Sequence[Sequence[float]],
        focus_index: int,
    ) -> tuple[list[float], list[float]]:
        activity = self.cnn.encode(activity_sequence)
        graph = self.gnn.encode(graph_nodes, adjacency, focus_index)
        fused = [float(value) for value in tabular] + [float(value) for value in text_vector] + activity + graph
        hidden_a = [_relu(value) for value in _matvec(fused, self.layer_a, self.bias_a)]
        hidden_b = [_relu(value) for value in _matvec(hidden_a, self.layer_b, self.bias_b)]
        raw = _matvec(hidden_b, self.output, self.output_bias)
        scalars = [_sigmoid(value) for value in raw[:4]]
        actions = _softmax(raw[4:])
        return scalars, actions


class NeuralCRMModel:
    """Neural-symbolic ensemble used in shadow mode.

    The committed model pack is intentionally synthetic and untrained on real
    people. Transparent business priors are blended with the neural ensemble so
    behaviour is stable while outcome evidence is still insufficient.
    """

    ACTIONS = FusionMember.ACTIONS

    def __init__(
        self,
        seeds: Iterable[int] = (17, 31, 47, 71, 89),
        tabular_size: int = 12,
        text_size: int = 8,
        activity_features: int = 6,
        graph_features: int = 6,
    ) -> None:
        self.tabular_size = tabular_size
        self.text_size = text_size
        self.activity_features = activity_features
        self.graph_features = graph_features
        self.members = [FusionMember(seed, tabular_size, text_size, activity_features, graph_features) for seed in seeds]
        if not self.members:
            raise ValueError("neural ensemble must contain at least one member")

    def predict(
        self,
        tabular: Sequence[float],
        text_vector: Sequence[float],
        activity_sequence: Sequence[Sequence[float]],
        graph_nodes: Sequence[Sequence[float]],
        adjacency: Sequence[Sequence[float]],
        focus_index: int,
        priors: dict[str, float] | None = None,
    ) -> NeuralPrediction:
        if len(tabular) != self.tabular_size:
            raise ValueError("tabular feature dimension mismatch")
        if len(text_vector) != self.text_size:
            raise ValueError("text feature dimension mismatch")
        priors = priors or {}
        member_scalars: list[list[float]] = []
        member_actions: list[list[float]] = []
        for member in self.members:
            scalars, actions = member.infer(tabular, text_vector, activity_sequence, graph_nodes, adjacency, focus_index)
            member_scalars.append(scalars)
            member_actions.append(actions)

        scalar_columns = list(zip(*member_scalars))
        neural_conversion, neural_relationship, neural_urgency, neural_churn = [_mean(list(column)) for column in scalar_columns]
        action_columns = list(zip(*member_actions))
        neural_actions = [_mean(list(column)) for column in action_columns]

        blend = 0.35
        conversion = blend * neural_conversion + (1.0 - blend) * float(priors.get("conversion", neural_conversion))
        relationship = blend * neural_relationship + (1.0 - blend) * float(priors.get("relationship", neural_relationship))
        urgency = blend * neural_urgency + (1.0 - blend) * float(priors.get("urgency", neural_urgency))
        churn = blend * neural_churn + (1.0 - blend) * float(priors.get("churn", neural_churn))

        action_prior = priors.get("actions")
        if isinstance(action_prior, (list, tuple)) and len(action_prior) == len(self.ACTIONS):
            blended_actions = [blend * neural_actions[index] + (1.0 - blend) * float(action_prior[index]) for index in range(len(self.ACTIONS))]
            action_values = _softmax([math.log(max(value, 1e-9)) for value in blended_actions])
        else:
            action_values = neural_actions

        scalar_variance = _mean([_variance(list(column)) for column in scalar_columns])
        action_variance = _mean([_variance(list(column)) for column in action_columns])
        uncertainty = max(0.0, min(1.0, math.sqrt(max(0.0, scalar_variance + action_variance)) * 4.0))
        confidence = max(0.0, min(1.0, 1.0 - uncertainty))

        return NeuralPrediction(
            conversion_probability=max(0.0, min(1.0, conversion)),
            relationship_strength=max(0.0, min(1.0, relationship)),
            urgency_probability=max(0.0, min(1.0, urgency)),
            churn_risk=max(0.0, min(1.0, churn)),
            action_probabilities={name: action_values[index] for index, name in enumerate(self.ACTIONS)},
            confidence=confidence,
            uncertainty=uncertainty,
            ensemble_size=len(self.members),
        )
