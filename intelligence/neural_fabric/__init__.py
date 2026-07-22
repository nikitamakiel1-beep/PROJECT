"""Dependency-free multidimensional convolutional fabric.

The package encodes static, semantic, temporal and relational evidence into one
bounded latent representation and converts it into reviewable internal plans.
Training, external actions and model promotion remain separately governed.
"""

from .execution import ConnectedExecutionPlanner, ExecutionPlan
from .multidimensional import MultiDimensionalConvEncoder, TensorContract

__all__ = [
    "ConnectedExecutionPlanner",
    "ExecutionPlan",
    "MultiDimensionalConvEncoder",
    "TensorContract",
]
