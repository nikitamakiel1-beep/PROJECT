#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_fabric import MultiDimensionalConvEncoder, TensorContract  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture():
    return {
        "tabular": [0.84, 0.65, 1.0, 1.0, 1.0, 0.149, 0.55, 0.10, 0.20, 0.03, 0.0, 0.82],
        "text": [0.12, -0.33, 0.41, 0.28, -0.17, 0.22, 0.38, -0.09],
        "activities": [
            [0.72, 1.0, 1.0, 0.0, 1.0, 0.30],
            [0.88, 1.0, 1.0, 1.0, 1.0, 0.58],
            [0.95, 1.0, 0.0, 1.0, 1.0, 0.42],
        ],
        "graph": [
            [1.0, 0.0, 0.0, 0.0, 0.82, 1.0],
            [0.0, 1.0, 0.0, 0.0, 0.65, 1.0],
            [0.0, 0.0, 1.0, 0.0, 0.84, 1.0],
            [0.0, 0.0, 0.0, 1.0, 0.149, 0.55],
        ],
    }


def run():
    evidence = []

    def case(name, function):
        function()
        evidence.append({"case": name, "result": "passed"})

    def shape_and_output():
        data = fixture()
        encoder = MultiDimensionalConvEncoder(random.Random(42), 12, 8, 6, 6)
        tensor = encoder.build_tensor(data["tabular"], data["text"], data["activities"], data["graph"])
        require(len(tensor) == 4, "tensor depth is not four modalities")
        require(all(len(plane) == 4 for plane in tensor), "tensor height mismatch")
        require(all(len(row) == 4 for plane in tensor for row in plane), "tensor width mismatch")
        output = encoder.encode(data["tabular"], data["text"], data["activities"], data["graph"])
        require(len(output) == TensorContract().output_size, "latent output size mismatch")
        require(all(isinstance(value, float) for value in output), "latent output contains non-floats")
        require(all(value == value for value in output), "latent output contains NaN")

    case("four-modal 4x4 tensor and multiscale output", shape_and_output)

    def deterministic():
        data = fixture()
        first = MultiDimensionalConvEncoder(random.Random(77), 12, 8, 6, 6)
        second = MultiDimensionalConvEncoder(random.Random(77), 12, 8, 6, 6)
        first_output = first.encode(data["tabular"], data["text"], data["activities"], data["graph"])
        second_output = second.encode(data["tabular"], data["text"], data["activities"], data["graph"])
        require(first_output == second_output, "same-seed multidimensional inference is not deterministic")

    case("same-seed tensor inference is deterministic", deterministic)

    def cross_modal_sensitivity():
        data = fixture()
        encoder = MultiDimensionalConvEncoder(random.Random(91), 12, 8, 6, 6)
        baseline = encoder.encode(data["tabular"], data["text"], data["activities"], data["graph"])

        altered_activity = fixture()
        altered_activity["activities"] = [[0.02, 0.0, 0.0, 0.0, 0.0, 0.0]]
        activity_output = encoder.encode(
            altered_activity["tabular"], altered_activity["text"], altered_activity["activities"], altered_activity["graph"]
        )
        require(activity_output != baseline, "activity axis did not affect latent state")

        altered_graph = fixture()
        altered_graph["graph"][2] = [0.0, 0.0, 1.0, 0.0, 0.15, 0.0]
        graph_output = encoder.encode(altered_graph["tabular"], altered_graph["text"], altered_graph["activities"], altered_graph["graph"])
        require(graph_output != baseline, "graph axis did not affect latent state")

        altered_semantic = fixture()
        altered_semantic["text"] = [-value for value in altered_semantic["text"]]
        semantic_output = encoder.encode(
            altered_semantic["tabular"], altered_semantic["text"], altered_semantic["activities"], altered_semantic["graph"]
        )
        require(semantic_output != baseline, "semantic axis did not affect latent state")

    case("activity semantic and graph axes alter the latent state", cross_modal_sensitivity)

    def multiscale_contract():
        contract = TensorContract()
        require(contract.kernel_shapes == ((2, 2, 2), (3, 2, 2)), "multiscale kernels changed unexpectedly")
        require(contract.channels_per_scale == 4, "channel contract changed unexpectedly")
        require(contract.output_size == 36, "expected 36-dimensional shared latent output")

    case("two 3D kernel scales produce 36 latent dimensions", multiscale_contract)

    def invalid_dimensions_fail():
        data = fixture()
        encoder = MultiDimensionalConvEncoder(random.Random(12), 12, 8, 6, 6)
        try:
            encoder.encode(data["tabular"][:-1], data["text"], data["activities"], data["graph"])
        except ValueError as error:
            require("tabular" in str(error), "wrong tabular-dimension error")
        else:
            raise AssertionError("invalid tabular dimension was accepted")

        bad_graph = [row[:-1] for row in data["graph"]]
        try:
            encoder.encode(data["tabular"], data["text"], data["activities"], bad_graph)
        except ValueError as error:
            require("graph" in str(error), "wrong graph-dimension error")
        else:
            raise AssertionError("invalid graph dimension was accepted")

    case("dimension mismatches fail closed", invalid_dimensions_fail)

    print(json.dumps({
        "ok": True,
        "architecture": "four-modal multiscale 3D convolutional fabric",
        "tests": evidence,
    }, indent=2))


if __name__ == "__main__":
    run()
