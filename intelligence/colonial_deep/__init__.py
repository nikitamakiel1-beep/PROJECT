"""Governed Colonial-style deep-learning platform for the venture network.

The package contains dependency-free reference implementations and contracts for
multidimensional CNNs, attention, embeddings, RAG, PEFT/LoRA, reinforcement
learning, vision/card routing, quantisation and evidence-gated training.
Production adapters and trained weights remain separate reviewed artefacts.
"""

from .core import Tensor, Scalar, Embedding, SelfAttention, MixtureOfExperts
from .platform import ColonialDeepLearningPlatform

__all__ = [
    "Tensor",
    "Scalar",
    "Embedding",
    "SelfAttention",
    "MixtureOfExperts",
    "ColonialDeepLearningPlatform",
]
