"""Stable public façade for the governed real-estate runtime.

The implementation is split into governance, underwriting and matching modules
to keep the public API compatible while reducing corruption and review risk.
"""
from __future__ import annotations

from ._engine_common import (
    MODEL_VERSION,
    RealEstateGovernanceError,
    assert_rights_gate,
    detect_sensitive_fields,
)
from ._engine_matching import (
    InvestorMandate,
    build_crm_merge_plan,
    score_match,
)
from ._engine_underwriting import (
    build_scenarios,
    calculate_metrics,
    normalise_property_row,
)

__all__ = [
    "MODEL_VERSION",
    "RealEstateGovernanceError",
    "InvestorMandate",
    "assert_rights_gate",
    "build_crm_merge_plan",
    "build_scenarios",
    "calculate_metrics",
    "detect_sensitive_fields",
    "normalise_property_row",
    "score_match",
]
