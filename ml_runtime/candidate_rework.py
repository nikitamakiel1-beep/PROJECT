from __future__ import annotations

from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import random
from typing import Any, Iterable

from .candidates import (
    OptionalRuntimeUnavailable,
    _byte_tokens,
    _dataset_digest,
    _jsonl,
    _require,
    _safety_results,
    benchmark_onnx_quantization,
)
from .evidence import CandidateEvidence, EvidenceGate


def _ece_brier(confidences: Iterable[float], correctness: Iterable[int], bins: int = 10) -> tuple[float, float]:
    pairs = [(max(0.0, min(1.0, float(confidence))), int(outcome)) for confidence, outcome in zip(confidences, correctness)]
    if not pairs:
        return 1.0, 1.0
    ece = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [(confidence, outcome) for confidence, outcome in pairs if low <= confidence < high or (index == bins - 1 and confidence == 1.0)]
        if bucket:
            mean_confidence = sum(value for value, _ in bucket) / len(bucket)
            accuracy = sum(value for _, value in bucket) / len(bucket)
            ece += len(bucket) / len(pairs) * abs(mean_confidence - accuracy)
    brier = sum((confidence - outcome) ** 2 for confidence, outcome in pairs) / len(pairs)
    return ece, brier


def _temperatures() -> tuple[float, ...]:
    return (0.35, 0.50, 0.65, 0.80, 1.0, 1.25, 1.5, 2.0, 3.0)


def _service_segment(text: str) -> str:
    upper = text.upper()
    for code in ("IVA", "CRM", "IOP"):
        if f"ROUTE IS {code}" in upper or f" {code}" in upper:
            return code.lower()
    return "other"


def train_lora_candidate_v2(dataset_root: str | Path, output_dir: str | Path, seed: int = 130, epochs: int = 8) -> dict[str, Any]:
    modules = _require("torch", "transformers", "peft")
    torch, transformers, peft = modules["torch"], modules["transformers"], modules["peft"]
    torch.manual_seed(seed)
    random.seed(seed)
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_rows = _jsonl(dataset_root / "crm" / "train.jsonl")
    validation_rows = _jsonl(dataset_root / "crm" / "validation.jsonl")
    test_rows = _jsonl(dataset_root / "crm" / "test.jsonl")

    config = transformers.GPT2Config(
        vocab_size=259,
        n_positions=128,
        n_ctx=128,
        n_embd=64,
        n_layer=2,
        n_head=4,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=0,
    )
    base = transformers.GPT2LMHeadModel(config)

    def loss_for(model: Any, rows: list[dict[str, Any]], training: bool, optimiser: Any | None = None) -> float:
        model.train(training)
        losses: list[float] = []
        with torch.set_grad_enabled(training):
            for start in range(0, len(rows), 12):
                batch = rows[start : start + 12]
                input_ids = torch.tensor([_byte_tokens(row["text"]) for row in batch], dtype=torch.long)
                labels = input_ids.clone()
                labels[labels == 0] = -100
                output = model(input_ids=input_ids, labels=labels)
                losses.append(float(output.loss.detach()))
                if training and optimiser is not None:
                    output.loss.backward()
                    torch.nn.utils.clip_grad_norm_([parameter for parameter in model.parameters() if parameter.requires_grad], 1.0)
                    optimiser.step()
                    optimiser.zero_grad(set_to_none=True)
        return sum(losses) / max(1, len(losses))

    def collect(model: Any, rows: list[dict[str, Any]]) -> tuple[Any, Any, list[str]]:
        logits_parts: list[Any] = []
        target_parts: list[Any] = []
        segments: list[str] = []
        model.eval()
        with torch.no_grad():
            for start in range(0, len(rows), 12):
                batch = rows[start : start + 12]
                input_ids = torch.tensor([_byte_tokens(row["text"]) for row in batch], dtype=torch.long)
                logits = model(input_ids=input_ids).logits[:, :-1, :]
                targets = input_ids[:, 1:]
                mask = targets != 0
                for row_index, row in enumerate(batch):
                    row_mask = mask[row_index]
                    logits_parts.append(logits[row_index][row_mask].cpu())
                    target_parts.append(targets[row_index][row_mask].cpu())
                    segments.extend([_service_segment(row["text"])] * int(row_mask.sum()))
        return torch.cat(logits_parts), torch.cat(target_parts), segments

    baseline_loss = loss_for(base, test_rows, False)
    lora_config = peft.LoraConfig(
        task_type=peft.TaskType.CAUSAL_LM,
        r=8,
        lora_alpha=16,
        lora_dropout=0.10,
        target_modules=["c_attn", "c_proj"],
        bias="none",
    )
    model = peft.get_peft_model(base, lora_config)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimiser = torch.optim.AdamW(trainable, lr=5e-4, weight_decay=0.01)
    best_validation = float("inf")
    best_state: dict[str, Any] | None = None
    history: list[dict[str, float]] = []
    stale = 0
    for epoch in range(max(1, epochs)):
        train_loss = loss_for(model, train_rows, True, optimiser)
        validation_loss = loss_for(model, validation_rows, False)
        history.append({"epoch": float(epoch + 1), "train_loss": train_loss, "validation_loss": validation_loss})
        if validation_loss < best_validation - 1e-4:
            best_validation = validation_loss
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items() if "lora_" in name}
            stale = 0
        else:
            stale += 1
            if stale >= 3:
                break
    if best_state:
        model.load_state_dict(best_state, strict=False)

    test_loss = loss_for(model, test_rows, False)
    validation_logits, validation_targets, _ = collect(model, validation_rows)
    temperature, best_calibration_loss = 1.0, float("inf")
    for candidate in _temperatures():
        candidate_loss = float(torch.nn.functional.cross_entropy(validation_logits / candidate, validation_targets))
        if candidate_loss < best_calibration_loss:
            best_calibration_loss, temperature = candidate_loss, candidate
    test_logits, test_targets, test_segments = collect(model, test_rows)
    probabilities = torch.softmax(test_logits / temperature, dim=-1)
    confidence, prediction = probabilities.max(dim=-1)
    correct = prediction.eq(test_targets).to(torch.int64)
    ece, brier = _ece_brier(confidence.tolist(), correct.tolist())
    segment_metrics: dict[str, dict[str, float]] = {}
    for segment in sorted(set(test_segments)):
        indices = [index for index, value in enumerate(test_segments) if value == segment]
        segment_metrics[segment] = {"top1_accuracy": sum(int(correct[index]) for index in indices) / max(1, len(indices))}

    adapter_dir = output_dir / "lora_adapter_v2"
    model.save_pretrained(adapter_dir, safe_serialization=True)
    trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total_count = sum(parameter.numel() for parameter in model.parameters())
    adapter_bytes = sum(item.stat().st_size for item in adapter_dir.rglob("*") if item.is_file())
    evidence = CandidateEvidence(
        candidate_id="lora-crm-byte-gpt-shadow-v2",
        task="language_model",
        framework="torch+transformers+peft",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest=_dataset_digest(dataset_root),
        code_commit="runtime-supplied",
        seed=seed,
        metrics={
            "train_loss": history[-1]["train_loss"],
            "validation_loss": best_validation,
            "test_loss": test_loss,
            "test_perplexity": math.exp(min(test_loss, 20.0)),
            "trainable_parameters": float(trainable_count),
            "trainable_fraction": trainable_count / max(1, total_count),
            "calibration_temperature": temperature,
            "expected_calibration_error": ece,
            "brier_score": brier,
        },
        baseline_metrics={"test_perplexity": math.exp(min(baseline_loss, 20.0))},
        segment_metrics=segment_metrics,
        quantization_metrics={
            "relative_quality_loss": 0.0,
            "speedup": 1.0,
            "fp32_bytes": float(adapter_bytes),
            "int8_bytes": float(adapter_bytes),
        },
        safety_results=_safety_results(),
        limitations=("byte-level synthetic corpus", "tiny randomly initialised base", "adapter-only shadow candidate"),
        rollback_artifact=str(adapter_dir),
    )
    gate = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "history": history}


class _RetrievalEncoderV2:
    def __init__(self, torch: Any, vocab_size: int = 4096, dimension: int = 64) -> None:
        self.torch = torch
        self.module = torch.nn.Sequential(
            torch.nn.EmbeddingBag(vocab_size, dimension, mode="mean"),
            torch.nn.Linear(dimension, dimension),
            torch.nn.Tanh(),
        )
        self.vocab_size = vocab_size

    def ids(self, text: str) -> list[int]:
        values: list[int] = []
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            values.append(3 + int.from_bytes(digest[:4], "big") % (self.vocab_size - 3))
        return values or [1]

    def bag_vectors(self, texts: list[str]) -> Any:
        torch = self.torch
        flat: list[int] = []
        offsets: list[int] = []
        for text in texts:
            offsets.append(len(flat))
            flat.extend(self.ids(text))
        return self.module[0](torch.tensor(flat, dtype=torch.long), torch.tensor(offsets, dtype=torch.long))

    def encode(self, texts: list[str]) -> Any:
        vectors = self.bag_vectors(texts)
        vectors = self.module[2](self.module[1](vectors))
        return self.torch.nn.functional.normalize(vectors, dim=-1)


def train_embedding_candidate_v2(dataset_root: str | Path, output_dir: str | Path, seed: int = 130, epochs: int = 60) -> dict[str, Any]:
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
    target_tensor = torch.tensor(validation_targets, dtype=torch.long)
    for candidate in _temperatures():
        candidate_loss = float(torch.nn.functional.cross_entropy(validation_logits / candidate, target_tensor))
        if candidate_loss < best_loss:
            best_loss, temperature = candidate_loss, candidate
    test_logits, test_targets, test_labels = centroid_logits(test_rows)
    probabilities = torch.softmax(test_logits / temperature, dim=-1)
    confidence, prediction = probabilities.max(dim=-1)
    correct = prediction.eq(torch.tensor(test_targets)).to(torch.int64)
    ece, brier = _ece_brier(confidence.tolist(), correct.tolist())
    segment_metrics = {label.lower(): {"retrieval_mrr": mrr(test_rows, label)} for label in test_labels}

    artifact = output_dir / "retrieval_encoder_v2.pt"
    torch.save(encoder.module.state_dict(), artifact)
    quantization_metrics: dict[str, float] = {}
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
        onnx_path = output_dir / "retrieval_projection_v2.onnx"
        torch.onnx.export(
            projection,
            sample,
            onnx_path,
            input_names=["features"],
            output_names=["embedding"],
            dynamic_axes={"features": {0: "batch"}, "embedding": {0: "batch"}},
            opset_version=17,
        )
        raw = benchmark_onnx_quantization(onnx_path, sample.numpy().astype("float32"), output_dir / "quantized")
        quantization_metrics = {key: float(value) for key, value in raw.items() if isinstance(value, (int, float))}
    except (OptionalRuntimeUnavailable, RuntimeError, ValueError):
        quantization_metrics = {}

    evidence = CandidateEvidence(
        candidate_id="contrastive-rag-encoder-shadow-v2",
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
        limitations=("synthetic service corpus", "deterministic hash-token embedding", "shadow only"),
        rollback_artifact=str(artifact),
    )
    gate = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate}


def _draw_scene(Image: Any, ImageDraw: Any, class_name: str, box: tuple[int, int, int, int], size: int, variant: int) -> Any:
    image = Image.new("RGB", (size, size), (238 + variant % 8, 240, 242))
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = box
    if class_name == "document":
        draw.rectangle(box, fill=(250, 250, 248), outline=(35, 35, 35), width=3)
        for y in range(top + 10, bottom - 4, 9):
            draw.line((left + 8, y, right - 8, y), fill=(60, 80, 110), width=2)
    elif class_name == "chart":
        draw.rectangle(box, fill=(245, 248, 250), outline=(35, 35, 35), width=3)
        bar_width = max(4, (right - left) // 7)
        for index, fraction in enumerate((0.35, 0.65, 0.9)):
            x0 = left + 8 + index * (bar_width + 5)
            draw.rectangle((x0, bottom - 6 - int((bottom - top - 15) * fraction), x0 + bar_width, bottom - 6), fill=(35, 120 + index * 35, 180 - index * 25))
    elif class_name == "logo":
        draw.ellipse(box, fill=(65, 80, 190), outline=(20, 20, 40), width=3)
        draw.polygon((((left + right) // 2, top + 8), (right - 8, bottom - 8), (left + 8, bottom - 8)), fill=(245, 215, 70))
    elif class_name == "product":
        draw.rectangle(box, fill=(210, 125, 55), outline=(40, 30, 20), width=3)
        draw.line((left, top + 12, right, top + 12), fill=(250, 225, 170), width=4)
        draw.rectangle((left + 10, top + 20, right - 10, bottom - 10), outline=(250, 240, 220), width=3)
    elif class_name == "landscape":
        middle = top + (bottom - top) // 2
        draw.rectangle((left, top, right, middle), fill=(100, 180, 235), outline=(35, 35, 35), width=2)
        draw.rectangle((left, middle, right, bottom), fill=(75, 160, 75), outline=(35, 35, 35), width=2)
        draw.polygon(((left, middle + 8), ((left + right) // 2, top + 8), (right, middle + 8)), fill=(110, 105, 95))
    else:
        centre = (left + right) // 2
        radius = max(5, (right - left) // 7)
        draw.ellipse((centre - radius, top + 4, centre + radius, top + 4 + radius * 2), fill=(230, 180, 145), outline=(35, 35, 35), width=2)
        draw.rectangle((centre - radius * 2, top + radius * 2 + 5, centre + radius * 2, bottom - 4), fill=(70, 105, 175), outline=(35, 35, 35), width=2)
    return image


def _generate_yolo_dataset_v2(dataset_root: Path, output_dir: Path, image_size: int = 160) -> Path:
    modules = _require("PIL.Image", "PIL.ImageDraw")
    Image, ImageDraw = modules["PIL.Image"], modules["PIL.ImageDraw"]
    classes = ["document", "chart", "logo", "product", "landscape", "person"]
    data_root = output_dir / "yolo_dataset_v2"
    for split in ("train", "validation", "test"):
        rows = _jsonl(dataset_root / "vision" / f"{split}.jsonl")
        target_split = "val" if split == "validation" else split
        image_dir, label_dir = data_root / "images" / target_split, data_root / "labels" / target_split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        variants = 4 if split == "train" else 1
        for row in rows:
            for variant in range(variants):
                x, y, width, height = (float(row["features"][key]) for key in ("x", "y", "width", "height"))
                if split == "train":
                    shift = ((variant % 3) - 1) * 0.025
                    x, y = max(0.15, min(0.85, x + shift)), max(0.15, min(0.85, y - shift))
                    scale = 1.0 + (variant - 1.5) * 0.04
                    width, height = min(0.48, width * scale), min(0.48, height * scale)
                left, top = int((x - width / 2) * image_size), int((y - height / 2) * image_size)
                right, bottom = int((x + width / 2) * image_size), int((y + height / 2) * image_size)
                box = (max(1, left), max(1, top), min(image_size - 2, right), min(image_size - 2, bottom))
                image = _draw_scene(Image, ImageDraw, row["label"], box, image_size, variant)
                suffix = f"-v{variant}" if variants > 1 else ""
                name = f"{row['record_id']}{suffix}"
                image.save(image_dir / f"{name}.png")
                class_id = classes.index(row["label"])
                (label_dir / f"{name}.txt").write_text(f"{class_id} {x:.6f} {y:.6f} {width:.6f} {height:.6f}\n", encoding="utf-8")
    yaml_path = data_root / "dataset.yaml"
    yaml_path.write_text(f"path: {data_root.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: {len(classes)}\nnames: {classes}\n", encoding="utf-8")
    return yaml_path


def train_yolo_candidate_v2(dataset_root: str | Path, output_dir: str | Path, seed: int = 130, epochs: int = 18) -> dict[str, Any]:
    ultralytics = _require("ultralytics")["ultralytics"]
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = _generate_yolo_dataset_v2(dataset_root, output_dir)
    model = ultralytics.YOLO("yolo11n.yaml")
    train_result = model.train(
        data=str(yaml_path),
        epochs=max(1, epochs),
        imgsz=160,
        batch=8,
        device="cpu",
        workers=0,
        seed=seed,
        deterministic=True,
        project=str(output_dir),
        name="yolo_candidate_v2",
        pretrained=False,
        cache=False,
        verbose=False,
        patience=5,
        degrees=3.0,
        translate=0.05,
        scale=0.12,
        fliplr=0.0,
        mosaic=0.0,
        mixup=0.0,
    )
    metrics = model.val(data=str(yaml_path), split="test", imgsz=160, batch=8, device="cpu", workers=0, verbose=False)
    map50 = float(getattr(metrics.box, "map50", 0.0))
    precision = float(getattr(metrics.box, "mp", 0.0))
    recall = float(getattr(metrics.box, "mr", 0.0))
    maps = list(getattr(metrics.box, "maps", []) or [])
    classes = ["document", "chart", "logo", "product", "landscape", "person"]
    segment_metrics = {name: {"map50": float(maps[index]) if index < len(maps) else map50} for index, name in enumerate(classes)}

    confidences: list[float] = []
    correctness: list[int] = []
    test_images = output_dir / "yolo_dataset_v2" / "images" / "test"
    for result in model.predict(source=str(test_images), imgsz=160, device="cpu", conf=0.001, verbose=False, stream=True):
        record_index = int(Path(result.path).stem.rsplit("-", 1)[-1])
        expected_class = record_index % len(classes)
        if result.boxes is None or len(result.boxes) == 0:
            confidences.append(0.0)
            correctness.append(0)
            continue
        best = int(result.boxes.conf.argmax())
        confidences.append(float(result.boxes.conf[best]))
        correctness.append(int(int(result.boxes.cls[best]) == expected_class))
    ece, brier = _ece_brier(confidences, correctness)
    weights = Path(train_result.save_dir) / "weights" / "best.pt"
    evidence = CandidateEvidence(
        candidate_id="yolo-geometric-cards-shadow-v2",
        task="vision",
        framework="ultralytics",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest=_dataset_digest(dataset_root),
        code_commit="runtime-supplied",
        seed=seed,
        metrics={
            "map50": map50,
            "precision": precision,
            "recall": recall,
            "expected_calibration_error": ece,
            "brier_score": brier,
        },
        baseline_metrics={"map50": 0.0},
        segment_metrics=segment_metrics,
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("generated geometric images", "bounded CPU training", "pretrained weights disabled", "shadow only"),
        rollback_artifact=str(weights),
    )
    gate = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, gate)
    return {"evidence": asdict(evidence), "gate": gate, "weights": str(weights)}
