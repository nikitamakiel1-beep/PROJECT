from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Iterable, Sequence

from .core import Embedding, SelfAttention, MixtureOfExperts, cosine_similarity, perplexity


def tokenize(text):
    return re.findall(r"[a-zA-ZÀ-ÿ0-9_'-]+", str(text).lower())


class HashedTextEncoder:
    def __init__(self, dimensions=32):
        self.dimensions = dimensions

    def encode(self, text):
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            for offset in range(0, min(8, len(digest)), 2):
                bucket = int.from_bytes(digest[offset : offset + 2], "big") % self.dimensions
                sign = -1.0 if digest[(offset + 1) % len(digest)] & 1 else 1.0
                vector[bucket] += sign * (1.0 + min(len(token), 16) / 16.0)
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    metadata: dict
    embedding: tuple[float, ...]


class VectorIndex:
    def __init__(self, encoder=None):
        self.encoder = encoder or HashedTextEncoder()
        self._chunks = []

    def add(self, chunk_id, text, metadata=None):
        if any(chunk.chunk_id == chunk_id for chunk in self._chunks):
            raise ValueError("duplicate chunk_id")
        metadata = dict(metadata or {})
        self._chunks.append(DocumentChunk(str(chunk_id), str(text), metadata, tuple(self.encoder.encode(text))))

    def search(self, query, top_k=4, filters=None):
        query_vector = self.encoder.encode(query)
        filters = filters or {}
        candidates = []
        for chunk in self._chunks:
            if any(chunk.metadata.get(key) != value for key, value in filters.items()):
                continue
            score = cosine_similarity(query_vector, chunk.embedding)
            candidates.append((score, chunk))
        candidates.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            {"chunk_id": chunk.chunk_id, "text": chunk.text, "metadata": dict(chunk.metadata), "score": score}
            for score, chunk in candidates[:top_k]
        ]


class RetrievalAugmentedGenerator:
    """Evidence-first RAG pack builder.

    Generation is intentionally template-bound in the dependency-free runtime.
    An optional reviewed LLM adapter may consume the returned prompt pack later.
    """

    def __init__(self, index):
        self.index = index

    def build_prompt(self, question, audience="internal", top_k=4, filters=None):
        evidence = self.index.search(question, top_k=top_k, filters=filters)
        context = "\n\n".join(f"[{item['chunk_id']}] {item['text']}" for item in evidence)
        prompt = (
            "Use only the cited context. State uncertainty and do not invent client facts.\n"
            f"Audience: {audience}\nQuestion: {question}\nContext:\n{context}"
        )
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        return {"question": question, "audience": audience, "evidence": evidence, "prompt": prompt, "prompt_digest": digest}

    def grounded_answer(self, question, audience="internal", top_k=4, filters=None):
        pack = self.build_prompt(question, audience, top_k, filters)
        if not pack["evidence"]:
            return {**pack, "answer": "Insufficient indexed evidence.", "citations": [], "grounded": False}
        strongest = pack["evidence"][:2]
        answer = " ".join(item["text"] for item in strongest)
        return {**pack, "answer": answer, "citations": [item["chunk_id"] for item in strongest], "grounded": True}


class TinyAutoregressiveDecoder:
    """Causal attention decoder for deterministic synthetic validation."""

    def __init__(self, vocabulary, dimensions=16, seed=251):
        self.vocabulary = tuple(vocabulary)
        self.token_to_id = {token: index for index, token in enumerate(self.vocabulary)}
        self.embedding = Embedding(len(self.vocabulary), dimensions, seed)
        self.attention = SelfAttention(dimensions, heads=2, seed=seed + 1)
        self.experts = MixtureOfExperts(dimensions, len(self.vocabulary), expert_count=4, top_k=2, seed=seed + 2)

    def logits(self, tokens):
        ids = [self.token_to_id.get(token, 0) for token in tokens]
        sequence = self.embedding(ids)
        attended = self.attention(sequence, causal=True)
        output, route = self.experts(attended[-1])
        return output, route

    @staticmethod
    def _softmax(values, temperature=1.0):
        temperature = max(0.05, float(temperature))
        maximum = max(values)
        exp = [math.exp((value - maximum) / temperature) for value in values]
        total = sum(exp) or 1.0
        return [value / total for value in exp]

    def decode(self, prefix, max_new_tokens=8, temperature=0.8):
        tokens = list(prefix)
        routes = []
        for _ in range(max_new_tokens):
            logits, route = self.logits(tokens)
            probabilities = self._softmax(logits, temperature)
            token_index = max(range(len(probabilities)), key=lambda index: probabilities[index])
            tokens.append(self.vocabulary[token_index])
            routes.append(route)
            if self.vocabulary[token_index] == "<eos>":
                break
        return {"tokens": tokens, "routes": routes}

    def evaluate_perplexity(self, sequences: Iterable[Sequence[str]]):
        losses = []
        for sequence in sequences:
            for index in range(1, len(sequence)):
                logits, _ = self.logits(sequence[:index])
                probabilities = self._softmax(logits, 1.0)
                target = self.token_to_id.get(sequence[index], 0)
                losses.append(-math.log(max(probabilities[target], 1e-12)))
        return perplexity(losses)


@dataclass(frozen=True)
class LLMRuntimeContract:
    provider: str = "disabled"
    model_id: str = "unset"
    quantization: str = "int8-reference"
    peft_adapter: str = "none"
    maximum_context_tokens: int = 2048
    maximum_new_tokens: int = 256
    temperature: float = 0.2
    top_p: float = 0.9
    external_data_allowed: bool = False
    automatic_action_allowed: bool = False
