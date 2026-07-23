from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping


PROHIBITED_RAW_FIELDS = {
    "email", "phone", "telephone", "contact_name", "first_name", "last_name",
    "address", "street", "personal_notes", "password", "token", "secret",
}


@dataclass(frozen=True)
class FeatureRecord:
    entity_ref: str
    entity_type: str
    segment: str
    features: dict[str, float]
    source_digest: str
    consent_scope: str
    created_at: str


class GovernedFeatureStore:
    """Pseudonymous bounded feature store for B2B, B2C and CRM entities."""

    ENTITY_TYPES = ("b2b_company", "b2b_contact", "b2c_person", "lead", "opportunity", "service", "activity", "document", "media")

    def __init__(self):
        self._records = {}

    @staticmethod
    def pseudonymise(identifier, salt):
        if not salt or len(salt) < 16:
            raise ValueError("pseudonym salt must contain at least 16 characters")
        return "ENT-" + hashlib.sha256(f"{salt}|{identifier}".encode()).hexdigest()[:20].upper()

    @staticmethod
    def validate_features(features: Mapping[str, Any]):
        clean = {}
        for key, value in features.items():
            normalised = str(key).strip().lower()
            if normalised in PROHIBITED_RAW_FIELDS or any(token in normalised for token in ("email", "phone", "name", "address", "secret", "token")):
                raise ValueError(f"raw personal or secret field prohibited: {key}")
            number = float(value)
            if not 0.0 <= number <= 1.0:
                raise ValueError(f"feature outside [0,1]: {key}")
            clean[str(key)] = number
        return clean

    def upsert(self, entity_ref, entity_type, segment, features, source_digest, consent_scope, created_at):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("unsupported entity type")
        clean = self.validate_features(features)
        if len(str(source_digest)) != 64:
            raise ValueError("source digest must be SHA-256")
        record = FeatureRecord(str(entity_ref), entity_type, str(segment), clean, str(source_digest), str(consent_scope), str(created_at))
        self._records[record.entity_ref] = record
        return record

    def get(self, entity_ref):
        return self._records.get(entity_ref)

    def query(self, entity_type=None, segment=None):
        result = list(self._records.values())
        if entity_type:
            result = [record for record in result if record.entity_type == entity_type]
        if segment:
            result = [record for record in result if record.segment == segment]
        return tuple(sorted(result, key=lambda record: record.entity_ref))

    def digest(self):
        payload = [record.__dict__ for record in self.query()]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float
    evidence_digest: str


class EntityGraph:
    RELATIONS = (
        "company_has_contact", "contact_created_lead", "lead_interested_in_service",
        "lead_became_opportunity", "opportunity_requires_delivery", "document_supports_entity",
        "media_supports_card", "card_related_to_card", "partner_refers_company",
        "b2c_person_interested_in_service", "activity_updates_entity",
    )

    def __init__(self):
        self.nodes = set()
        self.edges = []

    def add_node(self, entity_ref):
        self.nodes.add(str(entity_ref))

    def add_edge(self, source, target, relation, weight, evidence_digest):
        if relation not in self.RELATIONS:
            raise ValueError("unsupported relation")
        if not 0.0 <= float(weight) <= 1.0:
            raise ValueError("edge weight outside range")
        if len(str(evidence_digest)) != 64:
            raise ValueError("edge evidence digest must be SHA-256")
        self.add_node(source)
        self.add_node(target)
        edge = GraphEdge(str(source), str(target), relation, float(weight), str(evidence_digest))
        self.edges.append(edge)
        return edge

    def neighbours(self, entity_ref, minimum_weight=0.0):
        linked = []
        for edge in self.edges:
            if edge.weight < minimum_weight:
                continue
            if edge.source == entity_ref:
                linked.append((edge.target, edge))
            elif edge.target == entity_ref:
                linked.append((edge.source, edge))
        return tuple(sorted(linked, key=lambda item: (-item[1].weight, item[0])))


class DatasetRegistry:
    def __init__(self):
        self._datasets = {}

    def register(self, dataset_id, purpose, row_count, schema_digest, data_digest, split_policy, consent_scope, contains_personal_data=False):
        if dataset_id in self._datasets:
            raise ValueError("dataset already registered")
        item = {
            "dataset_id": dataset_id,
            "purpose": purpose,
            "row_count": int(row_count),
            "schema_digest": schema_digest,
            "data_digest": data_digest,
            "split_policy": split_policy,
            "consent_scope": consent_scope,
            "contains_personal_data": bool(contains_personal_data),
            "training_allowed": not contains_personal_data and bool(consent_scope),
            "promotion": "human_review_required",
        }
        self._datasets[dataset_id] = item
        return dict(item)

    def list(self):
        return tuple(dict(self._datasets[key]) for key in sorted(self._datasets))
