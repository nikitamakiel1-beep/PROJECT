"""Neural venture operating brain.

The planner selects the next bounded internal work package from evidence and
produces an n→n+1 instruction. It does not execute external communication,
financial actions, deployments or model promotion.
"""

from .planner import AutonomousVenturePlanner, PlannerDecision

__all__ = ["AutonomousVenturePlanner", "PlannerDecision"]
