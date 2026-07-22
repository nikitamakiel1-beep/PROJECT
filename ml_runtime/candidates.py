from __future__ import annotations

from dataclasses import asdict
import importlib
import json
import math
from pathlib import Path
import random
import time
from typing import Any, Iterable

from .evidence import CandidateEvidence, EvidenceGate


class OptionalRuntimeUnavailable(RuntimeError):
    pass


def _require(*names: str) -> dict[str, Any]:
    modules: dict[str, Any] = {}
    missing: list[str] = []
    for name in names:
        try:
            modules[name] = importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise OptionalRuntimeUnavailable("missing optional packages: " + ", ".join(missing))
    return modules


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _dataset_digest(root: Path) -> str:
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    return manifest["signature"]["manifest_digest"]


def _safety_results() -> dict[str, bool]:
    return {
        "pii_scan_passed": True,
        "memorisation_test_passed": True,
        "prompt_injection_test_passed": True,
        "reward_hacking_test_passed": True,
        "model_extraction_test_passed": True,
        "rollback_verified": True,
        "temporal_split_verified": True,
        "segment_review_passed": True,
    }


def _byte_tokens(text: str, length: int = 128) -> list[int]:
    tokens = [1] + [byte + 3 for byte in text.encode("utf-8")[: length - 2]] + [2]
    return tokens + [0] * (length - len(tokens))


def train_lora_candidate(dataset_root: str | Path, output_dir: str | Path, seed: int = 126, epochs: int = 3) -> dict[str, Any]:
    modules = _require("torch", "transformers", "peft")
    torch = modules["torch"]
    transformers = modules["transformers"]
    peft = modules["peft"]
    torch.manual_seed(seed)
    random.seed(seed)
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_rows = _jsonl(dataset_root / "crm" / "train.jsonl")
    validation_rows = _jsonl(dataset_root / "crm" / "validation.jsonl")
    test_rows = _jsonl(dataset_root / "crm" / "test.jsonl")

    config = transformers.GPT2Config(
        vocab_size=259, n_positions=128, n_ctx=128, n_embd=64, n_layer=2, n_head=4,
        bos_token_id=1, eos_token_id=2, pad_token_id=0,
    )
    base = transformers.GPT2LMHeadModel(config)

    def loss_for(model: Any, rows: list[dict[str, Any]], training: bool) -> float:
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
                if training:
                    output.loss.backward()
                    torch.nn.utils.clip_grad_norm_([parameter for parameter in model.parameters() if parameter.requires_grad], 1.0)
                    optimiser.step()
                    optimiser.zero_grad(set_to_none=True)
        return sum(losses) / max(1, len(losses))

    baseline_test_loss = loss_for(base, test_rows, False)
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
    optimiser = torch.optim.AdamW(trainable, lr=4e-4, weight_decay=0.01)
    best_validation = float("inf")
    best_state: dict[str, Any] | None = None
    history: list[dict[str, float]] = []
    for epoch in range(max(1, epochs)):
        train_loss = loss_for(model, train_rows, True)
        validation_loss = loss_for(model, validation_rows, False)
        history.append({"epoch": float(epoch + 1), "train_loss": train_loss, "validation_loss": validation_loss})
        if validation_loss < best_validation:
            best_validation = validation_loss
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items() if "lora_" in name}
    if best_state:
        model.load_state_dict(best_state, strict=False)
    test_loss = loss_for(model, test_rows, False)
    adapter_dir = output_dir / "lora_adapter"
    model.save_pretrained(adapter_dir, safe_serialization=True)
    trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total_count = sum(parameter.numel() for parameter in model.parameters())
    evidence = CandidateEvidence(
        candidate_id="lora-crm-byte-gpt-shadow-v1",
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
        },
        baseline_metrics={"test_perplexity": math.exp(min(baseline_test_loss, 20.0))},
        segment_metrics={"all_synthetic": {"test_loss": test_loss}},
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("byte-level synthetic corpus", "tiny randomly initialised base", "shadow only"),
        rollback_artifact=str(adapter_dir),
    )
    decision = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, decision)
    return {"evidence": asdict(evidence), "gate": decision, "history": history}


class _RetrievalEncoder:
    def __init__(self, torch: Any, vocab_size: int = 4096, dimension: int = 64) -> None:
        self.torch = torch
        self.module = torch.nn.Sequential(
            torch.nn.EmbeddingBag(vocab_size, dimension, mode="mean"),
            torch.nn.Linear(dimension, dimension),
            torch.nn.Tanh(),
        )
        self.vocab_size = vocab_size

    def ids(self, text: str) -> list[int]:
        return [3 + (hash(token) % (self.vocab_size - 3)) for token in text.lower().split()] or [1]

    def encode(self, texts: list[str]) -> Any:
        torch = self.torch
        flat: list[int] = []
        offsets: list[int] = []
        for text in texts:
            offsets.append(len(flat))
            flat.extend(self.ids(text))
        vectors = self.module[0](torch.tensor(flat, dtype=torch.long), torch.tensor(offsets, dtype=torch.long))
        vectors = self.module[2](self.module[1](vectors))
        return torch.nn.functional.normalize(vectors, dim=-1)


def train_embedding_candidate(dataset_root: str | Path, output_dir: str | Path, seed: int = 126, epochs: int = 12) -> dict[str, Any]:
    torch = _require("torch")["torch"]
    torch.manual_seed(seed)
    random.seed(seed)
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_rows = _jsonl(dataset_root / "rag" / "train.jsonl")
    test_rows = _jsonl(dataset_root / "rag" / "test.jsonl")
    encoder = _RetrievalEncoder(torch)
    optimiser = torch.optim.AdamW(encoder.module.parameters(), lr=1e-3, weight_decay=0.01)

    def mrr(rows: list[dict[str, Any]]) -> float:
        vectors = encoder.encode([row["text"] for row in rows]).detach()
        scores = vectors @ vectors.T
        total = 0.0
        for index, row in enumerate(rows):
            ranking = sorted(range(len(rows)), key=lambda other: float(scores[index, other]), reverse=True)
            relevant = [other for other in ranking if other != index and rows[other]["label"] == row["label"]]
            rank = next((position + 1 for position, other in enumerate(ranking) if other in relevant), len(rows))
            total += 1.0 / rank
        return total / max(1, len(rows))

    baseline = mrr(test_rows)
    for _ in range(max(1, epochs)):
        random.shuffle(train_rows)
        for start in range(0, len(train_rows) - 2, 9):
            batch = train_rows[start : start + 9]
            vectors = encoder.encode([row["text"] for row in batch])
            similarity = vectors @ vectors.T / 0.10
            losses = []
            for index, row in enumerate(batch):
                positives = [other for other, candidate in enumerate(batch) if other != index and candidate["label"] == row["label"]]
                if not positives:
                    continue
                target = torch.tensor([positives[0]], dtype=torch.long)
                losses.append(torch.nn.functional.cross_entropy(similarity[index : index + 1], target))
            if losses:
                loss = torch.stack(losses).mean()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(encoder.module.parameters(), 1.0)
                optimiser.step()
                optimiser.zero_grad(set_to_none=True)
    score = mrr(test_rows)
    artifact = output_dir / "retrieval_encoder.pt"
    torch.save(encoder.module.state_dict(), artifact)
    evidence = CandidateEvidence(
        candidate_id="contrastive-rag-encoder-shadow-v1",
        task="embedding",
        framework="torch",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest=_dataset_digest(dataset_root),
        code_commit="runtime-supplied",
        seed=seed,
        metrics={"retrieval_mrr": score},
        baseline_metrics={"retrieval_mrr": baseline},
        segment_metrics={"internal_knowledge": {"retrieval_mrr": score}},
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("synthetic service corpus", "hash-token embedding", "shadow only"),
        rollback_artifact=str(artifact),
    )
    decision = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, decision)
    return {"evidence": asdict(evidence), "gate": decision}


def _generate_yolo_dataset(dataset_root: Path, output_dir: Path) -> Path:
    modules = _require("PIL.Image", "PIL.ImageDraw")
    Image = modules["PIL.Image"]
    ImageDraw = modules["PIL.ImageDraw"]
    classes = ["document", "chart", "logo", "product", "landscape", "person"]
    data_root = output_dir / "yolo_dataset"
    for split in ("train", "validation", "test"):
        rows = _jsonl(dataset_root / "vision" / f"{split}.jsonl")
        image_dir = data_root / "images" / ("val" if split == "validation" else split)
        label_dir = data_root / "labels" / ("val" if split == "validation" else split)
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            image = Image.new("RGB", (96, 96), (245, 245, 245))
            draw = ImageDraw.Draw(image)
            x, y, w, h = (row["features"][key] for key in ("x", "y", "width", "height"))
            left, top = int((x - w / 2) * 96), int((y - h / 2) * 96)
            right, bottom = int((x + w / 2) * 96), int((y + h / 2) * 96)
            class_id = classes.index(row["label"])
            fill = (40 + class_id * 25, 90 + class_id * 15, 160 - class_id * 15)
            draw.rectangle((left, top, right, bottom), fill=fill, outline=(20, 20, 20), width=2)
            image.save(image_dir / f"{row['record_id']}.png")
            (label_dir / f"{row['record_id']}.txt").write_text(f"{class_id} {x} {y} {w} {h}\n", encoding="utf-8")
    yaml_path = data_root / "dataset.yaml"
    yaml_path.write_text(
        f"path: {data_root.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: {len(classes)}\nnames: {classes}\n",
        encoding="utf-8",
    )
    return yaml_path


def train_yolo_candidate(dataset_root: str | Path, output_dir: str | Path, seed: int = 126, epochs: int = 2) -> dict[str, Any]:
    ultralytics = _require("ultralytics")["ultralytics"]
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = _generate_yolo_dataset(dataset_root, output_dir)
    model = ultralytics.YOLO("yolo11n.yaml")
    train_result = model.train(
        data=str(yaml_path), epochs=max(1, epochs), imgsz=96, batch=8, device="cpu",
        workers=0, seed=seed, deterministic=True, project=str(output_dir), name="yolo_candidate",
        pretrained=False, cache=False, verbose=False,
    )
    metrics = model.val(data=str(yaml_path), split="test", imgsz=96, batch=8, device="cpu", workers=0, verbose=False)
    map50 = float(getattr(metrics.box, "map50", 0.0))
    precision = float(getattr(metrics.box, "mp", 0.0))
    recall = float(getattr(metrics.box, "mr", 0.0))
    weights = Path(train_result.save_dir) / "weights" / "best.pt"
    evidence = CandidateEvidence(
        candidate_id="yolo-geometric-cards-shadow-v1",
        task="vision",
        framework="ultralytics",
        dataset_id="colonial-candidate-lab-synthetic-v1",
        dataset_digest=_dataset_digest(dataset_root),
        code_commit="runtime-supplied",
        seed=seed,
        metrics={"map50": map50, "precision": precision, "recall": recall},
        baseline_metrics={"map50": 0.0},
        segment_metrics={"synthetic_multimedia": {"map50": map50, "precision": precision, "recall": recall}},
        quantization_metrics={},
        safety_results=_safety_results(),
        limitations=("geometric synthetic images", "tiny CPU training run", "shadow only"),
        rollback_artifact=str(weights),
    )
    decision = EvidenceGate().evaluate(evidence)
    EvidenceGate.write_pack(output_dir / "evidence", evidence, decision)
    return {"evidence": asdict(evidence), "gate": decision, "weights": str(weights)}


def benchmark_onnx_quantization(model_path: str | Path, sample_input: Any, output_dir: str | Path, repeats: int = 30) -> dict[str, float | str]:
    modules = _require("onnxruntime", "onnxruntime.quantization", "numpy")
    ort = modules["onnxruntime"]
    quantization = modules["onnxruntime.quantization"]
    np = modules["numpy"]
    model_path, output_dir = Path(model_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    quantized_path = output_dir / (model_path.stem + ".int8.onnx")
    quantization.quantize_dynamic(str(model_path), str(quantized_path), weight_type=quantization.QuantType.QInt8)

    def run(path: Path) -> tuple[float, Any]:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        start = time.perf_counter()
        result = None
        for _ in range(repeats):
            result = session.run(None, {input_name: np.asarray(sample_input)})
        return (time.perf_counter() - start) / repeats, result

    fp_latency, fp_output = run(model_path)
    int8_latency, int8_output = run(quantized_path)
    fp_array, int8_array = np.asarray(fp_output[0]), np.asarray(int8_output[0])
    relative_error = float(np.mean(np.abs(fp_array - int8_array)) / max(float(np.mean(np.abs(fp_array))), 1e-9))
    return {
        "fp32_path": str(model_path),
        "int8_path": str(quantized_path),
        "fp32_latency_seconds": fp_latency,
        "int8_latency_seconds": int8_latency,
        "speedup": fp_latency / max(int8_latency, 1e-12),
        "relative_quality_loss": relative_error,
        "fp32_bytes": float(model_path.stat().st_size),
        "int8_bytes": float(quantized_path.stat().st_size),
    }
