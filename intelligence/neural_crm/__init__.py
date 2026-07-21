"""Governed neural CRM intelligence.

The package provides deterministic shadow-mode inference for CRM decisions. It
combines a 1D convolutional activity encoder, graph message passing, dense
feature fusion, uncertainty calibration and policy gates. It does not send
messages or mutate production CRM data.
"""

from .engine import NeuralCRMEngine
from .policy import AutonomyMode, DecisionPolicy

__all__ = ["NeuralCRMEngine", "AutonomyMode", "DecisionPolicy"]
