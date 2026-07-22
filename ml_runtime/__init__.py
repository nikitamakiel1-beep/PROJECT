"""Governed optional-model candidate laboratory.

The package generates synthetic or explicitly approved datasets, validates
privacy and split isolation, runs shadow candidate training, and emits evidence
packs. It never promotes a model or connects to production systems.
"""

from .governance import DatasetBundleBuilder, DatasetPolicyError
from .evidence import CandidateEvidence, EvidenceGate

__all__ = ["DatasetBundleBuilder", "DatasetPolicyError", "CandidateEvidence", "EvidenceGate"]
