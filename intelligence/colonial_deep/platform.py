from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .adapters import OptionalRuntimeAdapter, TransformerFineTuneConfig, YOLOFineTuneConfig
from .core import MixtureOfExperts
from .data import DatasetRegistry, EntityGraph, GovernedFeatureStore
from .reinforcement import GovernedRLRouter, SafeRewardModel
from .retrieval import RetrievalAugmentedGenerator, VectorIndex
from .training import HyperParameters, HyperparameterAutotuner, model_card
from .vision_cards import FloatingCardFabric, YOLOStyleDetector


@dataclass(frozen=True)
class ColonyExpert:
    expert_id: str
    name: str
    domain: str
    capabilities: tuple[str, ...]
    vetoes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TradeRoute:
    route_id: str
    source: str
    target: str
    payload: tuple[str, ...]
    acknowledgement_required: bool
    failure_mode: str


class ColonialExpertMesh:
    """Specialised expert colonies with safety vetoes and explicit trade routes."""

    def __init__(self):
        self.experts = {
            expert.expert_id: expert
            for expert in (
                ColonyExpert("EXP-VISION", "Argus", "vision", ("yolo_decode", "media_cards", "visual_quality")),
                ColonyExpert("EXP-RAG", "Mnemosyne", "retrieval", ("embedding", "rag", "grounded_generation", "perplexity")),
                ColonyExpert("EXP-CRM", "Hermes", "crm", ("lead_graph", "opportunity", "follow_up", "b2b")),
                ColonyExpert("EXP-B2C", "Hestia", "b2c", ("consumer_intent", "consent_scope", "personalisation")),
                ColonyExpert("EXP-TRAIN", "Daedalus", "training", ("backprop", "lora", "autotuning", "quantisation")),
                ColonyExpert("EXP-RL", "Janus", "reinforcement", ("dqn", "policy_gradient", "reward_governance")),
                ColonyExpert("EXP-CARDS", "Atlas", "interface", ("floating_cards", "latent_layout", "handoffs")),
                ColonyExpert("EXP-AUDIT", "Pallas", "safety", ("privacy", "overfit", "drift", "promotion"), ("unsafe_action", "insufficient_evidence", "privacy_leak")),
            )
        }
        self.routes = (
            TradeRoute("ROUTE-01", "EXP-VISION", "EXP-CARDS", ("detections", "confidence", "source_refs"), True, "media is displayed without reviewed classification"),
            TradeRoute("ROUTE-02", "EXP-RAG", "EXP-CRM", ("citations", "retrieved_context", "uncertainty"), True, "CRM advice becomes ungrounded"),
            TradeRoute("ROUTE-03", "EXP-CRM", "EXP-RL", ("bounded_state", "permitted_actions", "outcome_evidence"), True, "policy optimises unsafe proxy metrics"),
            TradeRoute("ROUTE-04", "EXP-TRAIN", "EXP-AUDIT", ("model_card", "holdout_metrics", "overfit_gap", "rollback"), True, "candidate model is promoted without evidence"),
            TradeRoute("ROUTE-05", "EXP-B2C", "EXP-AUDIT", ("consent_scope", "feature_minimisation", "segment_metrics"), True, "consumer personalisation violates consent"),
            TradeRoute("ROUTE-06", "EXP-CARDS", "EXP-CRM", ("selected_card", "human_action", "record_reference"), True, "floating UI silently mutates CRM"),
        )

    def route_health(self, acknowledgements: Mapping[str, bool]):
        debt = [route.route_id for route in self.routes if route.acknowledgement_required and not acknowledgements.get(route.route_id, False)]
        return {"healthy": not debt, "route_debt": debt, "release_blocked": bool(debt)}


class SegmentExpertRouter:
    SEGMENTS = ("b2b", "b2c", "crm_operations", "delivery", "knowledge", "media")

    def __init__(self):
        self.moe = MixtureOfExperts(8, len(self.SEGMENTS), expert_count=6, top_k=2, seed=331)

    def route(self, state):
        if len(state) != 8:
            raise ValueError("segment router expects eight bounded features")
        output, route = self.moe([max(0.0, min(1.0, float(value))) for value in state])
        ranked = sorted(zip(self.SEGMENTS, output), key=lambda item: (-item[1], item[0]))
        return {"primary": ranked[0][0], "scores": dict(ranked), "experts": route}


class ColonialDeepLearningPlatform:
    """Integrated reference platform for the whole venture network.

    All stateful or externally visible actions remain proposals. The platform
    produces evidence, cards, routes and model plans; it does not contact clients,
    deploy models, charge money or overwrite production databases.
    """

    MODEL_VERSION = "colonial-deep-platform-shadow-v0.1"

    def __init__(self):
        self.features = GovernedFeatureStore()
        self.graph = EntityGraph()
        self.datasets = DatasetRegistry()
        self.index = VectorIndex()
        self.rag = RetrievalAugmentedGenerator(self.index)
        self.vision = YOLOStyleDetector()
        self.cards = FloatingCardFabric()
        self.rl = GovernedRLRouter()
        self.rewards = SafeRewardModel()
        self.adapters = OptionalRuntimeAdapter()
        self.expert_mesh = ColonialExpertMesh()
        self.segment_router = SegmentExpertRouter()
        self.audit_log = []

    @staticmethod
    def _digest(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def ingest_knowledge(self, chunks):
        for chunk in chunks:
            self.index.add(chunk["chunk_id"], chunk["text"], chunk.get("metadata"))
        return {"indexed": len(chunks), "index_digest": self._digest([chunk["chunk_id"] for chunk in chunks])}

    def ingest_features(self, records, salt):
        stored = []
        for record in records:
            entity_ref = self.features.pseudonymise(record["identifier"], salt)
            stored.append(self.features.upsert(
                entity_ref,
                record["entity_type"],
                record["segment"],
                record["features"],
                record["source_digest"],
                record["consent_scope"],
                record["created_at"],
            ))
        return {"stored": len(stored), "feature_store_digest": self.features.digest(), "entity_refs": [item.entity_ref for item in stored]}

    def analyse_multimedia(self, grid_predictions, source_id):
        detections = self.vision.decode(grid_predictions, source_id)
        cards = self.cards.assign_multimedia(detections, "Neural media card")
        return {
            "detections": [asdict(item) for item in detections],
            "cards": [asdict(item) for item in cards],
            "human_review_required": True,
            "automatic_database_write": False,
        }

    def answer(self, question, audience="internal", filters=None):
        result = self.rag.grounded_answer(question, audience, filters=filters)
        result["external_send_allowed"] = False
        result["human_review_required"] = True
        return result

    def decide_internal_action(self, state, mode="dqn"):
        result = self.rl.choose(state, mode)
        result["decision_digest"] = self._digest({"state": state, "mode": mode, "result": result})
        result["execution"] = "proposal_only"
        return result

    def build_floating_workspace(self, records, knowledge_question=None):
        cards = []
        for record in records:
            cards.append(self.cards.build(
                record["card_type"], record["title"], record["summary"],
                tuple(record.get("source_refs", ())), record.get("confidence", 0.7), tuple(record.get("actions", ("review",))),
            ))
        connected = self.cards.connect(cards)
        rag = self.answer(knowledge_question) if knowledge_question else None
        return {
            "model_version": self.MODEL_VERSION,
            "cards": [asdict(card) for card in connected],
            "rag": rag,
            "floating_layers": sorted({card.layer for card in connected}),
            "automatic_actions": False,
        }

    def training_programme(self, base_model, task, output_dir, yolo_dataset=None):
        transformer = self.adapters.transformer_plan(TransformerFineTuneConfig(base_model, task, output_dir))
        yolo = self.adapters.yolo_plan(YOLOFineTuneConfig(dataset_yaml=yolo_dataset or "datasets/cards/data.yaml"))
        return {
            "transformer_peft": transformer,
            "vision_yolo": yolo,
            "reference_hyperparameters": asdict(HyperParameters()),
            "autotuning": "offline_evidence_gated",
            "online_learning": False,
            "automatic_promotion": False,
        }

    def full_cycle(self, request):
        segment = self.segment_router.route(request["segment_state"])
        workspace = self.build_floating_workspace(request.get("cards", []), request.get("question"))
        action = self.decide_internal_action(request["rl_state"], request.get("rl_mode", "dqn"))
        route_health = self.expert_mesh.route_health(request.get("acknowledgements", {}))
        release_blocked = route_health["release_blocked"] or action["external"]
        evidence = {
            "model_version": self.MODEL_VERSION,
            "segment": segment,
            "workspace": workspace,
            "internal_action": action,
            "route_health": route_health,
            "release_blocked": release_blocked,
            "human_review_required": True,
        }
        evidence["cycle_digest"] = self._digest(evidence)
        self.audit_log.append({"cycle_digest": evidence["cycle_digest"], "release_blocked": release_blocked})
        return evidence
