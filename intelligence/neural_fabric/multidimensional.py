from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence


def _relu(value: float) -> float:
    return value if value > 0.0 else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    centre = _mean(values)
    return sum((value - centre) ** 2 for value in values) / len(values)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _pad(values: Sequence[float], size: int) -> list[float]:
    output = [float(value) for value in values[:size]]
    while len(output) < size:
        output.append(0.0)
    return output


@dataclass(frozen=True)
class TensorContract:
    depth: int = 4
    height: int = 4
    width: int = 4
    kernel_shapes: tuple[tuple[int, int, int], ...] = ((2, 2, 2), (3, 2, 2))
    channels_per_scale: int = 4

    @property
    def pooled_dimensions(self) -> int:
        channels = len(self.kernel_shapes) * self.channels_per_scale
        return channels * 3

    @property
    def axis_dimensions(self) -> int:
        return self.depth + self.height + self.width

    @property
    def output_size(self) -> int:
        return self.pooled_dimensions + self.axis_dimensions


class MultiDimensionalConvEncoder:
    """3D convolution over static, semantic, temporal and graph evidence.

    The input tensor has four modality planes, each represented as a 4×4 grid:

    1. static commercial/tabular evidence;
    2. semantic/text and cross-feature evidence;
    3. temporally binned activity evidence;
    4. graph-node evidence.

    Two kernel scales operate across modality depth, progression rows and
    feature groups. Global max, mean and standard-deviation pooling is followed
    by depth/row/column summaries. No external numeric dependency is required.
    """

    def __init__(
        self,
        rng: random.Random,
        tabular_size: int,
        text_size: int,
        activity_features: int,
        graph_features: int,
        contract: TensorContract | None = None,
    ) -> None:
        self.tabular_size = int(tabular_size)
        self.text_size = int(text_size)
        self.activity_features = int(activity_features)
        self.graph_features = int(graph_features)
        self.contract = contract or TensorContract()
        self.output_size = self.contract.output_size
        self._kernels: list[list[list[float]]] = []
        self._bias: list[list[float]] = []
        for depth, height, width in self.contract.kernel_shapes:
            kernel_size = depth * height * width
            self._kernels.append([
                [rng.uniform(-0.24, 0.24) for _ in range(kernel_size)]
                for _ in range(self.contract.channels_per_scale)
            ])
            self._bias.append([rng.uniform(-0.035, 0.035) for _ in range(self.contract.channels_per_scale)])

    @staticmethod
    def _rows(values: Sequence[float], height: int = 4, width: int = 4) -> list[list[float]]:
        padded = _pad(values, height * width)
        return [padded[row * width:(row + 1) * width] for row in range(height)]

    def _static_plane(self, tabular: Sequence[float], text: Sequence[float]) -> list[list[float]]:
        static = list(map(float, tabular)) + list(map(float, text[:4]))
        return self._rows(static)

    def _semantic_plane(self, tabular: Sequence[float], text: Sequence[float]) -> list[list[float]]:
        text_values = _pad(text, 8)
        tabular_values = _pad(tabular, 12)
        semantic = [
            *text_values,
            _mean(tabular_values[0:4]),
            _mean(tabular_values[4:8]),
            _mean(tabular_values[8:12]),
            math.sqrt(_variance(tabular_values)),
            _clip(tabular_values[0] * tabular_values[1]),
            _clip(tabular_values[2] * tabular_values[3]),
            _clip(tabular_values[4] * tabular_values[7]),
            _clip(tabular_values[8] * (1.0 - tabular_values[9])),
        ]
        return self._rows(semantic)

    def _activity_plane(self, sequence: Sequence[Sequence[float]]) -> list[list[float]]:
        if not sequence:
            return [[0.0] * 4 for _ in range(4)]
        for step in sequence:
            if len(step) != self.activity_features:
                raise ValueError("activity sequence feature dimension mismatch")
        bins: list[list[Sequence[float]]] = [[] for _ in range(4)]
        for index, step in enumerate(sequence):
            bin_index = min(3, int(index * 4 / max(1, len(sequence))))
            bins[bin_index].append(step)
        rows: list[list[float]] = []
        for bin_steps in bins:
            if not bin_steps:
                rows.append([0.0] * 4)
                continue
            feature_means = [
                _mean([float(step[feature]) for step in bin_steps])
                for feature in range(self.activity_features)
            ]
            rows.append([
                _mean(feature_means[0:2]),
                _mean(feature_means[2:4]),
                _mean(feature_means[4:6]),
                math.sqrt(_variance(feature_means)),
            ])
        return rows

    def _graph_plane(self, graph_nodes: Sequence[Sequence[float]]) -> list[list[float]]:
        if not graph_nodes:
            return [[0.0] * 4 for _ in range(4)]
        rows: list[list[float]] = []
        for node in graph_nodes[:4]:
            if len(node) != self.graph_features:
                raise ValueError("graph node feature dimension mismatch")
            values = [float(value) for value in node]
            rows.append([
                _mean(values[0:2]),
                _mean(values[2:4]),
                _mean(values[4:6]),
                math.sqrt(_variance(values)),
            ])
        while len(rows) < 4:
            rows.append([0.0] * 4)
        return rows

    def build_tensor(
        self,
        tabular: Sequence[float],
        text: Sequence[float],
        activity_sequence: Sequence[Sequence[float]],
        graph_nodes: Sequence[Sequence[float]],
    ) -> list[list[list[float]]]:
        if len(tabular) != self.tabular_size:
            raise ValueError("tabular feature dimension mismatch")
        if len(text) != self.text_size:
            raise ValueError("text feature dimension mismatch")
        tensor = [
            self._static_plane(tabular, text),
            self._semantic_plane(tabular, text),
            self._activity_plane(activity_sequence),
            self._graph_plane(graph_nodes),
        ]
        if len(tensor) != self.contract.depth:
            raise ValueError("tensor depth mismatch")
        return tensor

    def _convolve_scale(
        self,
        tensor: Sequence[Sequence[Sequence[float]]],
        scale_index: int,
    ) -> list[float]:
        kd, kh, kw = self.contract.kernel_shapes[scale_index]
        outputs: list[float] = []
        for channel in range(self.contract.channels_per_scale):
            kernel = self._kernels[scale_index][channel]
            bias = self._bias[scale_index][channel]
            activations: list[float] = []
            for depth in range(self.contract.depth - kd + 1):
                for row in range(self.contract.height - kh + 1):
                    for column in range(self.contract.width - kw + 1):
                        activation = bias
                        kernel_index = 0
                        for depth_offset in range(kd):
                            for row_offset in range(kh):
                                for column_offset in range(kw):
                                    activation += (
                                        float(tensor[depth + depth_offset][row + row_offset][column + column_offset])
                                        * kernel[kernel_index]
                                    )
                                    kernel_index += 1
                        activations.append(_relu(activation))
            outputs.extend([
                max(activations, default=0.0),
                _mean(activations),
                math.sqrt(_variance(activations)),
            ])
        return outputs

    def encode(
        self,
        tabular: Sequence[float],
        text: Sequence[float],
        activity_sequence: Sequence[Sequence[float]],
        graph_nodes: Sequence[Sequence[float]],
    ) -> list[float]:
        tensor = self.build_tensor(tabular, text, activity_sequence, graph_nodes)
        pooled: list[float] = []
        for scale_index in range(len(self.contract.kernel_shapes)):
            pooled.extend(self._convolve_scale(tensor, scale_index))
        depth_summary = [_mean([value for row in plane for value in row]) for plane in tensor]
        row_summary = [
            _mean([tensor[depth][row][column] for depth in range(self.contract.depth) for column in range(self.contract.width)])
            for row in range(self.contract.height)
        ]
        column_summary = [
            _mean([tensor[depth][row][column] for depth in range(self.contract.depth) for row in range(self.contract.height)])
            for column in range(self.contract.width)
        ]
        output = pooled + depth_summary + row_summary + column_summary
        if len(output) != self.output_size:
            raise ValueError("multidimensional encoder output mismatch")
        return output
