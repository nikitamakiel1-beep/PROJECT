from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import random
from typing import Any

from .candidate_rework import _RetrievalEncoderV2, _ece_brier, _temperatures
from .candidates import _dataset_digest, _jsonl, _require, _safety_results, benchmark_onnx_quantization
from .evidence import CandidateEvidence, EvidenceGate


def train_embedding_candidate_v3(dataset_root: str | Path, output_dir: str | Path, seed: int = 130, epochs: int = 60) -> dict[str, Any]:
    torch = _require("torch")["torch"]
    torch.manual_seed(seed)
    random.seed(seed)
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_rows = _jsonl(dataset_root / "rag" / "train.jsonl")
    validation_rows = _jsonl(dataset_root / "rag" / "validation.jsonl")
    test_rows = _jsonl(dataset_root / "rag" / "test.jsonl")
    encoder = _RetrievalEncoderV2(torch)
    optimiser = torch.optim.AdamW(encoder.module.parameters(), lr=3e-3, weight_decay=0.01)

    def mrr(rows: list[dict[str, Any]], label_filter: str | None = None) -> float:
        vectors = encoder.encode([row["text"] for row in rows]).detach()
        scores = vectors @ vectors.T
        values: list[float] = []
        for index, row in enumerate(rows):
            if label_filter and row["label"] != label_filter:
                continue
            ranking = sorted((other for other in range(len(rows)) if other != index), key=lambda other: float(scores[index, other]), reverse=True)
            rank = next((position + 1 for position, other in enumerate(ranking) if rows[other]["label"] == row["label"]), len(rows))
            values.append(1.0 / rank)
        return sum(values) / max(1, len(values))

    def centroid_logits(rows: list[dict[str, Any]]) -> tuple[Any, list[int], list[str]]:
        labels = sorted({row["label"] for row in train_rows})
        reference = encoder.encode([row["text"] for row in train_rows])
        centroids = []
        for label in labels:
            indices = [index for index, row in enumerate(train_rows) if row["label"] == label]
            centroids.append(torch.nn.functional.normalize(reference[indices].mean(dim=0), dim=0))
        vectors = encoder.encode([row["text"] for row in rows])
        return vectors @ torch.stack(centroids).T, [labels.index(row["label"]) for row in rows], labels

    baseline = mrr(test_rows)
    labels = [row["label"] for row in train_rows]
    for _ in range(max(1, epochs)):
        vectors = encoder.encode([row["text"] for row in train_rows])
        similarity = vectors @ vectors.T / 0.08
        similarity = similarity.masked_fill(torch.eye(len(train_rows), dtype=torch.bool), -1e9)
        losses = []
        for index, label in enumerate(labels):
            positives = torch.tensor([other != index and other_label == label for other, other_label in enumerate(labels)], dtype=torch.bool)
            if positives.any():
                log_probability = similarity[index] - torch.logsumexp(similarity[index], dim=0)
                losses.append(-log_probability[positives].mean())
        loss = torch.stack(losses).mean()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(encoder.module.parameters(), 1.0)
        optimiser.step()
        optimiser.zero_grad(set_to_none=True)

    score = mrr(test_rows)
    validation_logits, validation_targets, _ = centroid_logits(validation_rows)
    temperature, best_loss = 1.0, float("inf")
    validation_target_tensor = torch.tensor(validation_targets, dtype=torch.long)
    for candidate in _temperatures():
        candidate_loss = float(torch.nn.functional.cross_entropy(validation_logits / candidate, validation_target_tensor))
        if candidate_loss < best_loss:
            best_loss, temperature = candidate_loss, candidate
    test_logits, test_targets, test_labels = centroid_logits(test_rows)
    probabilities = torch.softmax(test_logits / temperature, dim=-1)
    confidence, prediction = probabilities.max(dim=-1)
    correct = prediction.eq(torch.tensor(test_targets)).to(torch.int64)
    ece, brier = _ece_brier(confidence.tolist(), correct.tolist())
    segment_metrics = {label.lower(): {"retrieval_mrr": mrr(test_rows, label)} for label in test_labels}

    artifact = output_dir / "retrieval_encoder_v3.pt"
    torch.save(encoder.module.state_dict(), artifact)
    quantization_metrics: dict[str, float]
    quantization_failed = False
    try:
        _require("onnx", "onnxruntime", "onnxruntime.quantization", "numpy")

        class Projection(torch.nn.Module):
            def __init__(self, linear: Any, activation: Any) -> None:
                super().__init__()
                self.linear = linear
                self.activation = activation

            def forward(self, value: Any) -> Any:
                return torch.nn.functional.normalize(self.activation(self.linear(value)), dim=-1)

        projection = Projection(encoder.module[1], encoder.module[2]).eval()
        sample = encoder.bag_vectors([row["text"] for row in test_rows]).detach()
        onnx_path = output_dir / "retrieval_projection_v3.onnx"
        torch.onnx.export(
            projection,
            sample,
            onnx_path,
            input_names=["features"],
            output_names=["embedding"],
            dynamic_axes={"features": {0: "batch"}, "embedding": {0: "batch"}},
            opset_version=17,
            dynamo=False,
        )
        raw = benchmark_onnx_quantization(onnx_path, sample.numpy().astype("float32"), output_dir / "quantized")
        quantization_metrics = {key: float(value) for key, value in raw.items() if isinstance(value, (int, float))}
    except Exception:
        quantization_failed = True
        quantization_metrics = {
            "relative_quality_loss": 1.0,
            "speedup": 0.0,
            "fp32_bytes": 0.0,
            "int8_bytes": 0.0,
        }

    limitations = ["synthetic service corpus", "deterministic hash-token embedding", "shadow only"]
    if quantization_failed:
        limitations.append("ONNX/int8 exporter failed; candidate remains blocked")
    evidence = CandidateEvidence(
        candidate_id="contrastive-rag-encoder-shadow-v3",
        task="embedding",
        framework="torch+onnxruntime",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest=_dataset_digest(dataset_root),
        code_commit="runtime-supplied",
        seed=seed,
        metrics={
            "retrieval_mrr": score,
            "classification_accuracy": float(correct.float().mean()),
            "calibration_temperature": temperature,
            "expected_calibration_error": ece,
            "brier_score": brier,
        },
        baseline_metrics={"retrieval_mrr": baseline},
        segment_metrics=segment_metrics,
        quantization_metrics=quantization_metrics,
        safety_results=_safety_results(),
        limitations=tuple(limitations),
        rollback_artifact=str(artifact),
    )
    gate = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "quantization_failed": quantization_failed}
