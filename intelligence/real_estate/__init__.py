"""Governed real-estate CRM vertical."""
from .engine import (
    MODEL_VERSION,
    RealEstateGovernanceError,
    InvestorMandate,
    assert_rights_gate,
    build_crm_merge_plan,
    build_scenarios,
    calculate_metrics,
    detect_sensitive_fields,
    normalise_property_row,
    score_match,
)

__all__ = [
    "MODEL_VERSION", "RealEstateGovernanceError", "InvestorMandate",
    "assert_rights_gate", "build_crm_merge_plan", "build_scenarios",
    "calculate_metrics", "detect_sensitive_fields", "normalise_property_row",
    "score_match",
]
