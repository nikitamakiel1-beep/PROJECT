from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class AgentEvidence:
    agent: str
    role: str
    claim: str
    confidence: float
    evidence_refs: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class EvidenceLedger:
    """Append-only provenance bundle for one inference cycle."""

    def __init__(self, cycle_id: str, model_version: str) -> None:
        self.cycle_id = cycle_id
        self.model_version = model_version
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._entries: list[AgentEvidence] = []

    def append(self, evidence: AgentEvidence) -> None:
        if not 0.0 <= evidence.confidence <= 1.0:
            raise ValueError("agent confidence must be between zero and one")
        self._entries.append(evidence)

    @property
    def entries(self) -> tuple[AgentEvidence, ...]:
        return tuple(self._entries)

    def digest(self) -> str:
        payload = {
            "cycle_id": self.cycle_id,
            "model_version": self.model_version,
            "created_at": self.created_at,
            "entries": [asdict(entry) for entry in self._entries],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "model_version": self.model_version,
            "created_at": self.created_at,
            "entries": [asdict(entry) for entry in self._entries],
            "ledger_digest": self.digest(),
        }


class CognitiveColony:
    """Named internal roles inspired by the governed Colonial-AI pattern."""

    ROLES = {
        "Scout": "extracts market, service and lead signals",
        "Cartographer": "constructs the relationship and evidence graph",
        "Analyst": "runs convolutional, graph and fusion inference",
        "Strategist": "compares next-best-action candidates and counterfactuals",
        "Auditor": "checks calibration, drift, provenance and policy conflicts",
        "Custodian": "enforces human custody and bounded autonomy",
    }

    @classmethod
    def evidence(
        cls,
        agent: str,
        claim: str,
        confidence: float,
        evidence_refs: Iterable[str],
        warnings: Iterable[str] = (),
    ) -> AgentEvidence:
        if agent not in cls.ROLES:
            raise ValueError(f"unknown cognitive agent: {agent}")
        return AgentEvidence(
            agent=agent,
            role=cls.ROLES[agent],
            claim=claim,
            confidence=max(0.0, min(1.0, float(confidence))),
            evidence_refs=tuple(str(reference) for reference in evidence_refs),
            warnings=tuple(str(warning) for warning in warnings),
        )
