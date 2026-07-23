from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable, Iterable, Sequence


def _shape(data):
    if not isinstance(data, (list, tuple)):
        return ()
    if not data:
        return (0,)
    child = _shape(data[0])
    if any(_shape(item) != child for item in data):
        raise ValueError("ragged tensor")
    return (len(data),) + child


def _flatten(data):
    if not isinstance(data, (list, tuple)):
        return [float(data)]
    out = []
    for item in data:
        out.extend(_flatten(item))
    return out


def _product(values):
    result = 1
    for value in values:
        result *= value
    return result


def _unflatten(values, shape):
    iterator = iter(values)

    def build(axis):
        if axis == len(shape):
            return next(iterator)
        return [build(axis + 1) for _ in range(shape[axis])]

    return build(0)


@dataclass(frozen=True)
class Tensor:
    data: object

    def __post_init__(self):
        _shape(self.data)

    @property
    def shape(self):
        return _shape(self.data)

    def flatten(self):
        return _flatten(self.data)

    def reshape(self, *shape):
        if _product(shape) != len(self.flatten()):
            raise ValueError("reshape element count mismatch")
        return Tensor(_unflatten(self.flatten(), shape))

    def quantize_int8(self):
        values = self.flatten()
        maximum = max((abs(value) for value in values), default=0.0)
        scale = maximum / 127.0 if maximum else 1.0
        quantized = [max(-127, min(127, int(round(value / scale)))) for value in values]
        return QuantizedTensor(tuple(quantized), self.shape, scale)


@dataclass(frozen=True)
class QuantizedTensor:
    values: tuple[int, ...]
    shape: tuple[int, ...]
    scale: float

    def dequantize(self):
        return Tensor(_unflatten([value * self.scale for value in self.values], self.shape))


class Scalar:
    """Tiny reverse-mode autodiff scalar used to verify backpropagation."""

    def __init__(self, data, children=(), operation=""):
        self.data = float(data)
        self.grad = 0.0
        self._previous = set(children)
        self._operation = operation
        self._backward = lambda: None

    def __add__(self, other):
        other = other if isinstance(other, Scalar) else Scalar(other)
        out = Scalar(self.data + other.data, (self, other), "+")

        def backward():
            self.grad += out.grad
            other.grad += out.grad

        out._backward = backward
        return out

    __radd__ = __add__

    def __mul__(self, other):
        other = other if isinstance(other, Scalar) else Scalar(other)
        out = Scalar(self.data * other.data, (self, other), "*")

        def backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad

        out._backward = backward
        return out

    __rmul__ = __mul__

    def __neg__(self):
        return self * -1.0

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return other + (-self)

    def __truediv__(self, other):
        return self * (other if isinstance(other, Scalar) else Scalar(other)).pow(-1.0)

    def pow(self, power):
        out = Scalar(self.data ** power, (self,), f"pow({power})")

        def backward():
            self.grad += power * (self.data ** (power - 1.0)) * out.grad

        out._backward = backward
        return out

    def exp(self):
        value = math.exp(max(-40.0, min(40.0, self.data)))
        out = Scalar(value, (self,), "exp")
        out._backward = lambda: setattr(self, "grad", self.grad + value * out.grad)
        return out

    def log(self):
        out = Scalar(math.log(max(self.data, 1e-12)), (self,), "log")
        out._backward = lambda: setattr(self, "grad", self.grad + out.grad / max(self.data, 1e-12))
        return out

    def tanh(self):
        value = math.tanh(self.data)
        out = Scalar(value, (self,), "tanh")
        out._backward = lambda: setattr(self, "grad", self.grad + (1.0 - value * value) * out.grad)
        return out

    def relu(self):
        out = Scalar(max(0.0, self.data), (self,), "relu")
        out._backward = lambda: setattr(self, "grad", self.grad + (1.0 if self.data > 0 else 0.0) * out.grad)
        return out

    def backward(self):
        topology = []
        visited = set()

        def build(node):
            if node not in visited:
                visited.add(node)
                for child in node._previous:
                    build(child)
                topology.append(node)

        build(self)
        self.grad = 1.0
        for node in reversed(topology):
            node._backward()


class Embedding:
    def __init__(self, vocabulary_size, dimensions, seed=101):
        rng = random.Random(seed)
        self.vocabulary_size = int(vocabulary_size)
        self.dimensions = int(dimensions)
        self.weights = [
            [rng.uniform(-0.25, 0.25) for _ in range(self.dimensions)]
            for _ in range(self.vocabulary_size)
        ]

    def __call__(self, token_ids):
        return [list(self.weights[int(token) % self.vocabulary_size]) for token in token_ids]


class SelfAttention:
    def __init__(self, dimensions, heads=2, seed=131):
        if dimensions % heads:
            raise ValueError("dimensions must be divisible by heads")
        self.dimensions = dimensions
        self.heads = heads
        rng = random.Random(seed)
        scale = 1.0 / math.sqrt(dimensions)
        self.q = [[rng.uniform(-scale, scale) for _ in range(dimensions)] for _ in range(dimensions)]
        self.k = [[rng.uniform(-scale, scale) for _ in range(dimensions)] for _ in range(dimensions)]
        self.v = [[rng.uniform(-scale, scale) for _ in range(dimensions)] for _ in range(dimensions)]

    @staticmethod
    def _project(vector, matrix):
        return [sum(vector[i] * matrix[i][j] for i in range(len(vector))) for j in range(len(matrix[0]))]

    @staticmethod
    def _softmax(values):
        maximum = max(values)
        exp = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in values]
        total = sum(exp) or 1.0
        return [value / total for value in exp]

    def __call__(self, sequence, causal=False):
        queries = [self._project(vector, self.q) for vector in sequence]
        keys = [self._project(vector, self.k) for vector in sequence]
        values = [self._project(vector, self.v) for vector in sequence]
        head_size = self.dimensions // self.heads
        output = [[0.0] * self.dimensions for _ in sequence]
        for row in range(len(sequence)):
            for head in range(self.heads):
                start = head * head_size
                stop = start + head_size
                scores = []
                for column in range(len(sequence)):
                    if causal and column > row:
                        scores.append(-1e9)
                    else:
                        dot = sum(queries[row][i] * keys[column][i] for i in range(start, stop))
                        scores.append(dot / math.sqrt(head_size))
                attention = self._softmax(scores)
                for i in range(start, stop):
                    output[row][i] = sum(attention[column] * values[column][i] for column in range(len(sequence)))
        return output


class MixtureOfExperts:
    def __init__(self, input_size, output_size, expert_count=4, top_k=2, seed=173):
        self.input_size = input_size
        self.output_size = output_size
        self.expert_count = expert_count
        self.top_k = min(top_k, expert_count)
        rng = random.Random(seed)
        self.router = [[rng.uniform(-0.3, 0.3) for _ in range(expert_count)] for _ in range(input_size)]
        self.experts = [
            [[rng.uniform(-0.25, 0.25) for _ in range(output_size)] for _ in range(input_size)]
            for _ in range(expert_count)
        ]

    def __call__(self, vector):
        logits = [sum(vector[i] * self.router[i][expert] for i in range(self.input_size)) for expert in range(self.expert_count)]
        chosen = sorted(range(self.expert_count), key=lambda index: logits[index], reverse=True)[: self.top_k]
        maximum = max(logits[index] for index in chosen)
        weights = [math.exp(logits[index] - maximum) for index in chosen]
        total = sum(weights) or 1.0
        weights = [value / total for value in weights]
        output = [0.0] * self.output_size
        for route_weight, expert in zip(weights, chosen):
            expert_output = [sum(vector[i] * self.experts[expert][i][j] for i in range(self.input_size)) for j in range(self.output_size)]
            for j in range(self.output_size):
                output[j] += route_weight * expert_output[j]
        return output, {"experts": chosen, "weights": weights}


def gradient_clip(parameters: Iterable[Scalar], max_norm=1.0):
    parameters = list(parameters)
    norm = math.sqrt(sum(parameter.grad * parameter.grad for parameter in parameters))
    scale = min(1.0, float(max_norm) / max(norm, 1e-12))
    for parameter in parameters:
        parameter.grad *= scale
    return norm, scale


def cross_entropy(logits: Sequence[float], target: int):
    maximum = max(logits)
    exp = [math.exp(value - maximum) for value in logits]
    probabilities = [value / sum(exp) for value in exp]
    return -math.log(max(probabilities[target], 1e-12))


def perplexity(losses: Sequence[float]):
    return math.exp(min(40.0, sum(losses) / max(len(losses), 1)))


def cosine_similarity(left: Sequence[float], right: Sequence[float]):
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    return dot / max(norm_left * norm_right, 1e-12)


def contrastive_loss(anchor, positive, negatives, margin=0.25):
    positive_score = cosine_similarity(anchor, positive)
    penalties = [max(0.0, margin - positive_score + cosine_similarity(anchor, negative)) for negative in negatives]
    return sum(penalties) / max(len(penalties), 1)
