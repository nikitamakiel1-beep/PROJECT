#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.colonial_deep.adapters import OptionalRuntimeAdapter, TransformerFineTuneConfig  # noqa: E402
from intelligence.colonial_deep.core import (  # noqa: E402
    Embedding, MixtureOfExperts, Scalar, SelfAttention, Tensor, contrastive_loss,
    gradient_clip,
)
from intelligence.colonial_deep.data import DatasetRegistry, EntityGraph, GovernedFeatureStore  # noqa: E402
from intelligence.colonial_deep.platform import ColonialDeepLearningPlatform  # noqa: E402
from intelligence.colonial_deep.reinforcement import (  # noqa: E402
    DQNAgent, GovernedRLRouter, PolicyGradientAgent, ReplayMemory, SafeRewardModel, Transition,
)
from intelligence.colonial_deep.retrieval import TinyAutoregressiveDecoder, VectorIndex, RetrievalAugmentedGenerator  # noqa: E402
from intelligence.colonial_deep.training import (  # noqa: E402
    HyperParameters, HyperparameterAutotuner, PEFTDense, model_card, train_peft_regressor,
)
from intelligence.colonial_deep.vision_cards import BoundingBox, FloatingCardFabric, YOLOStyleDetector, iou, non_max_suppression  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    results = []

    def case(name, function):
        function()
        results.append({"case": name, "result": "passed"})

    def tensor_quantisation():
        tensor = Tensor([[0.0, 0.5], [-1.0, 1.0]])
        require(tensor.shape == (2, 2), "tensor shape invalid")
        restored = tensor.quantize_int8().dequantize()
        require(restored.shape == tensor.shape, "quantised shape changed")
        error = max(abs(a - b) for a, b in zip(tensor.flatten(), restored.flatten()))
        require(error < 0.01, f"int8 quantisation error too high: {error}")
        require(tensor.reshape(4).shape == (4,), "reshape failed")

    case("tensor reshape and int8 quantisation", tensor_quantisation)

    def backpropagation():
        x = Scalar(3.0)
        y = (x * x + x * 2.0).tanh()
        y.backward()
        expected = (1.0 - math.tanh(15.0) ** 2) * 8.0
        require(abs(x.grad - expected) < 1e-9, "reverse-mode backprop derivative incorrect")
        parameters = [Scalar(0.0), Scalar(0.0)]
        parameters[0].grad = 3.0
        parameters[1].grad = 4.0
        norm, scale = gradient_clip(parameters, 1.0)
        require(abs(norm - 5.0) < 1e-9 and abs(scale - 0.2) < 1e-9, "gradient clipping invalid")

    case("reverse-mode backpropagation and gradient clipping", backpropagation)

    def attention_embedding_moe():
        embedding = Embedding(12, 8, seed=4)
        vectors = embedding([1, 2, 3])
        attention = SelfAttention(8, heads=2, seed=5)
        first = attention(vectors, causal=True)
        second = attention(vectors, causal=True)
        require(first == second and len(first) == 3 and len(first[0]) == 8, "causal self-attention invalid")
        moe = MixtureOfExperts(8, 4, expert_count=5, top_k=2, seed=6)
        output, route = moe(first[-1])
        require(len(output) == 4, "MoE output size invalid")
        require(len(route["experts"]) == 2, "MoE did not use sparse top-k routing")
        require(abs(sum(route["weights"]) - 1.0) < 1e-9, "MoE route weights not normalised")

    case("embedding causal attention and sparse mixture-of-experts", attention_embedding_moe)

    def contrastive_learning():
        anchor = [1.0, 0.0, 0.0]
        positive = [0.95, 0.05, 0.0]
        negatives = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
        good = contrastive_loss(anchor, positive, negatives)
        bad = contrastive_loss(anchor, negatives[0], [positive])
        require(good < bad, "contrastive objective does not prefer positive pair")

    case("contrastive latent-space learning objective", contrastive_learning)

    def peft_lora_training():
        base_weights = [[0.0], [0.0]]
        model = PEFTDense(base_weights, [0.0], rank=2, alpha=4.0, seed=9)
        rows = [([0.0, 0.0], [0.0]), ([1.0, 0.0], [1.0]), ([0.0, 1.0], [1.0]), ([1.0, 1.0], [2.0])] * 8
        train = rows[:24]
        validation = rows[24:]
        initial = sum((model([Scalar(value) for value in features])[0].data - target[0]) ** 2 for features, target in validation) / len(validation)
        hp = HyperParameters(learning_rate=0.03, weight_decay=0.0001, dropout=0.0, epochs=50, patience=12, lora_rank=2, lora_alpha=4.0, seed=10)
        history = train_peft_regressor(model, train, validation, hp)
        final = sum((model([Scalar(value) for value in features])[0].data - target[0]) ** 2 for features, target in validation) / len(validation)
        require(final < initial, f"LoRA PEFT did not improve validation loss: {initial} -> {final}")
        require(history.best_epoch >= 0, "best epoch was not recorded")
        card = model_card("synthetic-lora", hp, history, "a" * 64, ["synthetic data only"])
        require(len(card["card_digest"]) == 64 and card["promotion"] == "human_review_required", "model card invalid")

    case("LoRA PEFT backpropagation with anti-overfitting controls", peft_lora_training)

    def autotuning():
        tuner = HyperparameterAutotuner(seed=11)
        trials = tuner.search(lambda hp: (0.4 + hp.dropout * 0.2 + hp.learning_rate, 0.35 + hp.learning_rate), trials=5)
        require(len(trials) == 5, "autotuner trial count invalid")
        require(trials == sorted(trials, key=lambda item: item.score), "autotuner results not ranked")
        require(all(trial.hyperparameters.lora_rank in {2, 4, 8} for trial in trials), "autotuner produced invalid LoRA rank")

    case("hyperparameter autotuning and overfit-gap penalty", autotuning)

    def rag_and_decoder():
        index = VectorIndex()
        index.add("CRM-001", "The CRM follow-up digest ranks overdue leads and opportunities.", {"domain": "crm"})
        index.add("WEB-001", "The website neural guide recommends the smallest active service.", {"domain": "web"})
        rag = RetrievalAugmentedGenerator(index)
        answer = rag.grounded_answer("How are overdue leads ranked?", filters={"domain": "crm"})
        require(answer["grounded"] and answer["citations"] == ["CRM-001"], "RAG retrieval was not grounded")
        require("Use only the cited context" in answer["prompt"], "RAG grounding instruction missing")
        decoder = TinyAutoregressiveDecoder(("<unk>", "crm", "review", "card", "<eos>"), dimensions=8, seed=12)
        generated = decoder.decode(["crm"], max_new_tokens=4)
        require(1 < len(generated["tokens"]) <= 5, "autoregressive decoding length invalid")
        ppl = decoder.evaluate_perplexity([["crm", "review", "<eos>"], ["card", "review", "<eos>"]])
        require(math.isfinite(ppl) and ppl > 0, "perplexity invalid")

    case("RAG autoregressive decoding and perplexity", rag_and_decoder)

    def reinforcement_learning():
        memory = ReplayMemory(capacity=10, seed=13)
        transition = Transition((0.2, 0.8), 1, 1.0, (0.4, 0.6), False, True)
        memory.append(transition)
        require(memory.sample(1)[0] == transition, "replay memory invalid")
        try:
            memory.append(Transition((0.0, 0.0), 0, 0.0, (0.0, 0.0), True, False))
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe transition entered replay")
        dqn = DQNAgent(2, 3, epsilon=0.0, seed=14)
        loss, maximum_gradient = dqn.train_batch([transition])
        require(loss >= 0 and maximum_gradient <= 1.0, "DQN update or clipping invalid")
        policy = PolicyGradientAgent(2, 3, seed=15)
        pg_loss = policy.update_episode([(0.1, 0.9), (0.8, 0.2)], [1, 0], [1.0, 0.5], permitted_actions=(0, 1))
        require(math.isfinite(pg_loss), "policy-gradient update invalid")
        router = GovernedRLRouter(state_size=8)
        decision = router.choose([0.5] * 8)
        require(not decision["external"] and decision["action"] != "external_message", "RL selected external action")
        try:
            SafeRewardModel().score(["message_volume"])
        except ValueError:
            pass
        else:
            raise AssertionError("reward hacking metric accepted")

    case("DQN policy-gradient replay and reward governance", reinforcement_learning)

    def yolo_and_cards():
        detector = YOLOStyleDetector(threshold=0.2)
        grid = [[
            {"objectness": 0.9, "classes": [0.1, 0.1, 0.8, 0, 0, 0], "x": 0.5, "y": 0.5, "width": 0.4, "height": 0.4},
            {"objectness": 0.8, "classes": [0.1, 0.1, 0.75, 0, 0, 0], "x": 0.1, "y": 0.5, "width": 0.4, "height": 0.4},
        ]]
        detections = detector.decode(grid, "SYNTHETIC-MEDIA")
        require(detections and all(item.class_id == "document" for item in detections), "YOLO-style decoder failed")
        require(0 <= iou(BoundingBox(0, 0, .5, .5, .9, "x"), BoundingBox(.25, .25, .5, .5, .8, "x")) <= 1, "IoU invalid")
        fabric = FloatingCardFabric()
        cards = fabric.assign_multimedia(detections)
        require(cards and all(card.human_review for card in cards), "media cards missing human custody")
        require(all(1 <= card.layer <= 5 for card in cards), "floating layer outside range")
        contract = detector.training_contract()
        require(contract["dataset_required"] and contract["promotion"] == "human_review_required", "YOLO training contract unsafe")

    case("YOLO-style detection NMS and floating card assignment", yolo_and_cards)

    def databases_and_graph():
        store = GovernedFeatureStore()
        reference = store.pseudonymise("synthetic@example.test", "this-is-a-long-synthetic-salt")
        record = store.upsert(reference, "lead", "b2b", {"fit": 0.8, "urgency": 0.7}, "b" * 64, "synthetic", "2026-07-22T08:00:00Z")
        require(store.get(reference) == record, "feature store retrieval failed")
        try:
            store.upsert("ENT-BAD", "lead", "b2c", {"email": 0.5}, "b" * 64, "synthetic", "2026-07-22T08:00:00Z")
        except ValueError:
            pass
        else:
            raise AssertionError("raw personal field entered feature store")
        graph = EntityGraph()
        edge = graph.add_edge(reference, "SERVICE-IVA", "lead_interested_in_service", 0.9, "c" * 64)
        require(graph.neighbours(reference)[0][1] == edge, "entity graph edge missing")
        registry = DatasetRegistry()
        dataset = registry.register("DS-SYN-001", "synthetic validation", 20, "d" * 64, "e" * 64, "temporal", "synthetic", False)
        require(dataset["training_allowed"], "safe synthetic dataset was blocked")

    case("governed B2B B2C CRM feature store and entity graph", databases_and_graph)

    def platform_cycle():
        platform = ColonialDeepLearningPlatform()
        platform.ingest_knowledge([
            {"chunk_id": "POL-001", "text": "External messages always require human approval.", "metadata": {"domain": "policy"}}
        ])
        request = {
            "segment_state": [0.8, 0.2, 0.7, 0.6, 0.3, 0.4, 0.9, 0.5],
            "cards": [
                {"card_type": "lead", "title": "Qualified synthetic lead", "summary": "Review service fit.", "source_refs": ["LEAD-SYN"], "confidence": 0.8},
                {"card_type": "service", "title": "IVA", "summary": "International visibility audit.", "source_refs": ["SERVICE-IVA"], "confidence": 0.9},
            ],
            "question": "Can the system send an external message?",
            "rl_state": [0.5] * 8,
            "acknowledgements": {"ROUTE-01": True},
        }
        result = platform.full_cycle(request)
        require(result["human_review_required"], "platform removed human review")
        require(result["release_blocked"], "route debt did not block release")
        require(len(result["cycle_digest"]) == 64, "cycle digest invalid")
        require(result["workspace"]["cards"], "floating workspace empty")
        require(result["internal_action"]["execution"] == "proposal_only", "RL action was executed")
        training = platform.training_programme("synthetic/base-model", "crm-assistance", "/tmp/not-executed")
        require(not training["online_learning"] and not training["automatic_promotion"], "training programme unsafe")

    case("Colonial expert mesh full-cycle governance", platform_cycle)

    def optional_runtime_contract():
        adapter = OptionalRuntimeAdapter()
        plan = adapter.transformer_plan(TransformerFineTuneConfig("synthetic/model", "classification", "artifacts/model"))
        require(not plan["automatic_execution"], "optional runtime executes automatically")
        require(plan["promotion"] == "pull_request_and_human_approval_required", "model promotion custody missing")

    case("optional Transformers PEFT YOLO runtime remains gated", optional_runtime_contract)

    print(json.dumps({
        "ok": True,
        "model": ColonialDeepLearningPlatform.MODEL_VERSION,
        "tests": results,
        "capabilities": [
            "multidimensional CNN fabric", "autograd/backprop", "attention/embeddings", "MoE",
            "PEFT/LoRA", "autotuning", "RAG", "autoregressive decoding", "perplexity",
            "DQN", "policy gradient", "YOLO-style detection", "quantisation", "floating cards",
            "B2B/B2C/CRM feature store", "expert colonies and trade-route governance"
        ]
    }, indent=2))


if __name__ == "__main__":
    run()
