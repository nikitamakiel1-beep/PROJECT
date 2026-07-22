"""Dependency-free multidimensional convolutional fabric.

The package encodes static, semantic, temporal and relational CRM evidence into
one bounded latent representation. It is deterministic and shadow-oriented;
training and promotion remain separate governed processes.
"""

from .multidimensional import MultiDimensionalConvEncoder, TensorContract

__all__ = ["MultiDimensionalConvEncoder", "TensorContract"]
