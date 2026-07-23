from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AutonomyMode(str, Enum):
    SHADOW = "shadow"
    ASSIST = "assist"
    BOUNDED_AUTO = "bounded_auto"


class ActionClass(str, Enum):
    ANALYSIS = "analysis"
    INTERNAL_REVERSIBLE = "internal_reversible"
    INTERNAL_MATERIAL = "internal_material"
    EXTERNAL_COMMUNICATION = "external_communication"
    FINANCIAL = "financial"
    IRREVERSIBLE = "irreversible"
    MODEL_PROMOTION = "model_promotion"


@dataclass(frozen=True)
class PolicyDecision:
    permitted: bool
    execution: str
    reason: str
    requires_human: bool
    confidence_threshold: float
    uncertainty_ceiling: float


class DecisionPolicy:
    """Custodian policy for neural CRM decisions.

    Internal analysis is always permitted. Material CRM changes, outbound
    communication, financial changes, irreversible operations and model
    promotion remain under explicit human custody.
    """

    DEFAULT_THRESHOLDS: Mapping[ActionClass, tuple[float, float]] = {
        ActionClass.ANALYSIS: (0.0, 1.0),
        ActionClass.INTERNAL_REVERSIBLE: (0.72, 0.28),
        ActionClass.INTERNAL_MATERIAL: (0.84, 0.16),
        ActionClass.EXTERNAL_COMMUNICATION: (1.0, 0.0),
        ActionClass.FINANCIAL: (1.0, 0.0),
        ActionClass.IRREVERSIBLE: (1.0, 0.0),
        ActionClass.MODEL_PROMOTION: (1.0, 0.0),
    }

    def __init__(self, mode: AutonomyMode = AutonomyMode.SHADOW) -> None:
        self.mode = AutonomyMode(mode)

    def decide(
        self,
        action_class: ActionClass,
        confidence: float,
        uncertainty: float,
        human_approved: bool = False,
        synthetic_only: bool = True,
    ) -> PolicyDecision:
        action_class = ActionClass(action_class)
        minimum_confidence, maximum_uncertainty = self.DEFAULT_THRESHOLDS[action_class]
        confidence = max(0.0, min(1.0, float(confidence)))
        uncertainty = max(0.0, min(1.0, float(uncertainty)))

        if action_class == ActionClass.ANALYSIS:
            return PolicyDecision(True, "execute", "analysis_is_non_mutating", False, minimum_confidence, maximum_uncertainty)

        if synthetic_only and action_class not in {ActionClass.INTERNAL_REVERSIBLE, ActionClass.INTERNAL_MATERIAL}:
            return PolicyDecision(False, "hold", "synthetic_stage_blocks_external_or_irreversible_action", True, minimum_confidence, maximum_uncertainty)

        if action_class in {
            ActionClass.EXTERNAL_COMMUNICATION,
            ActionClass.FINANCIAL,
            ActionClass.IRREVERSIBLE,
            ActionClass.MODEL_PROMOTION,
        }:
            if human_approved:
                return PolicyDecision(True, "execute_after_approval", "explicit_human_custody", True, minimum_confidence, maximum_uncertainty)
            return PolicyDecision(False, "request_approval", "human_custody_required", True, minimum_confidence, maximum_uncertainty)

        if self.mode == AutonomyMode.SHADOW:
            return PolicyDecision(False, "shadow_record", "shadow_mode_never_mutates", True, minimum_confidence, maximum_uncertainty)

        if self.mode == AutonomyMode.ASSIST:
            return PolicyDecision(False, "recommend", "assist_mode_requires_human_execution", True, minimum_confidence, maximum_uncertainty)

        if confidence < minimum_confidence:
            return PolicyDecision(False, "request_review", "confidence_below_threshold", True, minimum_confidence, maximum_uncertainty)
        if uncertainty > maximum_uncertainty:
            return PolicyDecision(False, "request_review", "uncertainty_above_ceiling", True, minimum_confidence, maximum_uncertainty)

        if action_class == ActionClass.INTERNAL_REVERSIBLE:
            return PolicyDecision(True, "execute_with_audit", "bounded_reversible_autonomy", False, minimum_confidence, maximum_uncertainty)

        return PolicyDecision(False, "request_approval", "material_internal_change_requires_human", True, minimum_confidence, maximum_uncertainty)
