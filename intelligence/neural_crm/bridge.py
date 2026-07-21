from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .model import NeuralCRMModel


PACKAGE_VERSION = "neural-provider-package-v1"
DECISION_VERSION = "neural-provider-decision-v1"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _probability(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}_must_be_numeric") from error
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name}_outside_probability_range")
    return number


def _vector(value: Any, size: int, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name}_dimension_mismatch")
    return [_probability(item, name) if name != "text_vector" else float(item) for item in value]


def _matrix(value: Any, columns: int, name: str, allow_empty: bool = False) -> list[list[float]]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{name}_must_be_matrix")
    matrix: list[list[float]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError(f"{name}_dimension_mismatch")
        matrix.append([float(item) for item in row])
    return matrix


def _safe_identifier(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 128:
        raise ValueError(f"{name}_invalid")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_:")
    if any(character not in allowed for character in text):
        raise ValueError(f"{name}_invalid")
    return text


def _reject_pii(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True).lower()
    forbidden_keys = (
        '"email"', '"phone"', '"full name"', '"contact name"', '"company name"',
        '"website"', '"notes"', '"linkedin"', '"role"', '"source urls"',
    )
    if any(marker in serialized for marker in forbidden_keys):
        raise ValueError("pii_or_free_text_field_detected")
    if "@" in serialized or "http://" in serialized or "https://" in serialized:
        raise ValueError("pii_or_provider_url_detected")


@dataclass(frozen=True)
class ValidatedProviderPackage:
    package_id: str
    lead_ref: str
    company_ref: str
    contact_ref: str
    service_code: str
    service_price_eur: float
    tabular: list[float]
    text_vector: list[float]
    activity_sequence: list[list[float]]
    graph_nodes: list[list[float]]
    adjacency: list[list[float]]
    focus_index: int
    priors: dict[str, Any]
    feature_digest: str


class NeuralProviderBridge:
    """Runs the repository neural model against a PII-free provider package."""

    def __init__(self, model: NeuralCRMModel | None = None) -> None:
        self.model = model or NeuralCRMModel()

    def validate(self, package: Mapping[str, Any]) -> ValidatedProviderPackage:
        if not isinstance(package, Mapping):
            raise ValueError("package_must_be_object")
        _reject_pii(package)
        if package.get("package_version") != PACKAGE_VERSION:
            raise ValueError("package_version_unsupported")
        if package.get("synthetic_only") is not True:
            raise ValueError("synthetic_gate_closed")

        package_id = _safe_identifier(package.get("package_id"), "package_id")
        lead_ref = _safe_identifier(package.get("lead_ref"), "lead_ref")
        company_ref = _safe_identifier(package.get("company_ref"), "company_ref")
        contact_ref = _safe_identifier(package.get("contact_ref"), "contact_ref")
        service_code = _safe_identifier(package.get("service_code"), "service_code").upper()
        try:
            price = float(package.get("service_price_eur"))
        except (TypeError, ValueError) as error:
            raise ValueError("service_price_invalid") from error
        if not 0.0 < price <= 1000000.0:
            raise ValueError("service_price_invalid")

        features = package.get("features")
        if not isinstance(features, Mapping):
            raise ValueError("features_missing")
        tabular = _vector(features.get("tabular"), self.model.tabular_size, "tabular")
        text_vector = _vector(features.get("text_vector"), self.model.text_size, "text_vector")
        activity_sequence = _matrix(features.get("activity_sequence"), self.model.activity_features, "activity_sequence", allow_empty=True)
        graph_nodes = _matrix(features.get("graph_nodes"), self.model.graph_features, "graph_nodes")
        adjacency = _matrix(features.get("adjacency"), len(graph_nodes), "adjacency")
        focus_index = int(features.get("focus_index", -1))
        if not 0 <= focus_index < len(graph_nodes):
            raise ValueError("focus_index_invalid")

        priors = package.get("priors")
        if not isinstance(priors, Mapping):
            raise ValueError("priors_missing")
        validated_priors: dict[str, Any] = {
            "conversion": _probability(priors.get("conversion"), "conversion_prior"),
            "relationship": _probability(priors.get("relationship"), "relationship_prior"),
            "urgency": _probability(priors.get("urgency"), "urgency_prior"),
            "churn": _probability(priors.get("churn"), "churn_prior"),
        }
        actions = priors.get("actions")
        if not isinstance(actions, list) or len(actions) != len(self.model.ACTIONS):
            raise ValueError("action_priors_dimension_mismatch")
        action_values = [_probability(value, "action_prior") for value in actions]
        total = sum(action_values)
        if total <= 0.0:
            raise ValueError("action_priors_empty")
        validated_priors["actions"] = [value / total for value in action_values]

        digest_payload = {
            "package_id": package_id,
            "lead_ref": lead_ref,
            "company_ref": company_ref,
            "contact_ref": contact_ref,
            "service_code": service_code,
            "service_price_eur": price,
            "features": {
                "tabular": tabular,
                "text_vector": text_vector,
                "activity_sequence": activity_sequence,
                "graph_nodes": graph_nodes,
                "adjacency": adjacency,
                "focus_index": focus_index,
            },
            "priors": validated_priors,
        }
        computed_digest = _digest(digest_payload)
        supplied_digest = str(package.get("feature_digest") or "")
        if supplied_digest and supplied_digest != computed_digest:
            raise ValueError("feature_digest_mismatch")

        return ValidatedProviderPackage(
            package_id=package_id,
            lead_ref=lead_ref,
            company_ref=company_ref,
            contact_ref=contact_ref,
            service_code=service_code,
            service_price_eur=price,
            tabular=tabular,
            text_vector=text_vector,
            activity_sequence=activity_sequence,
            graph_nodes=graph_nodes,
            adjacency=adjacency,
            focus_index=focus_index,
            priors=validated_priors,
            feature_digest=computed_digest,
        )

    def infer(self, package: Mapping[str, Any]) -> dict[str, Any]:
        validated = self.validate(package)
        prediction = self.model.predict(
            validated.tabular,
            validated.text_vector,
            validated.activity_sequence,
            validated.graph_nodes,
            validated.adjacency,
            validated.focus_index,
            validated.priors,
        )
        ranked = sorted(prediction.action_probabilities.items(), key=lambda item: item[1], reverse=True)
        bounded_auto_eligible = prediction.confidence >= 0.72 and prediction.uncertainty <= 0.28
        opportunity_id = "OPP-" + hashlib.sha256(
            f"{validated.lead_ref}|{validated.service_code}".encode("utf-8")
        ).hexdigest()[:12].upper()
        decision_core = {
            "decision_version": DECISION_VERSION,
            "package_id": validated.package_id,
            "feature_digest": validated.feature_digest,
            "lead_ref": validated.lead_ref,
            "company_ref": validated.company_ref,
            "contact_ref": validated.contact_ref,
            "service_code": validated.service_code,
            "model_version": "neural-crm-shadow-v0.1",
            "prediction": {
                **asdict(prediction),
                "ranked_actions": [{"action": action, "probability": probability} for action, probability in ranked],
            },
            "proposed_internal_action": {
                "type": "create_or_review_opportunity",
                "opportunity_ref": opportunity_id,
                "stage": "Qualified",
                "value_eur": round(validated.service_price_eur, 2),
                "probability_pct": round(prediction.conversion_probability * 100.0, 2),
                "weighted_value_eur": round(validated.service_price_eur * prediction.conversion_probability, 2),
                "next_step": "Human review of neural shadow evidence",
            },
            "execution_policy": {
                "mode": "shadow",
                "mutation_permitted": False,
                "bounded_auto_eligible": bounded_auto_eligible,
                "external_communication_permitted": False,
                "model_promotion_permitted": False,
            },
        }
        return {**decision_core, "decision_digest": _digest(decision_core)}
