from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
from typing import Any


@dataclass(frozen=True)
class RuntimeAvailability:
    torch: bool
    transformers: bool
    peft: bool
    ultralytics: bool
    onnxruntime: bool
    sentence_transformers: bool


def runtime_availability():
    return RuntimeAvailability(**{
        name.replace("-", "_"): importlib.util.find_spec(module) is not None
        for name, module in {
            "torch": "torch",
            "transformers": "transformers",
            "peft": "peft",
            "ultralytics": "ultralytics",
            "onnxruntime": "onnxruntime",
            "sentence-transformers": "sentence_transformers",
        }.items()
    })


@dataclass(frozen=True)
class TransformerFineTuneConfig:
    base_model: str
    task: str
    output_dir: str
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: tuple[str, ...] = ("q_proj", "k_proj", "v_proj", "o_proj")
    learning_rate: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_length: int = 1024
    gradient_clip_norm: float = 1.0
    quantization: str = "4bit_candidate"
    evaluation_strategy: str = "steps"
    save_strategy: str = "steps"
    early_stopping_patience: int = 3
    external_data_allowed: bool = False
    push_to_hub: bool = False


@dataclass(frozen=True)
class YOLOFineTuneConfig:
    base_model: str = "yolo11n.pt"
    dataset_yaml: str = "datasets/cards/data.yaml"
    epochs: int = 50
    image_size: int = 640
    batch_size: int = 8
    patience: int = 10
    device: str = "cpu"
    freeze_layers: int = 10
    close_mosaic_epochs: int = 10
    confidence_threshold: float = 0.35
    iou_threshold: float = 0.45
    export_format: str = "onnx"
    half_precision: bool = False
    int8_export: bool = True


class OptionalRuntimeAdapter:
    """Generates reviewed runtime plans without importing optional frameworks."""

    def __init__(self):
        self.availability = runtime_availability()

    def transformer_plan(self, config: TransformerFineTuneConfig):
        blockers = []
        for package in ("torch", "transformers", "peft"):
            if not getattr(self.availability, package):
                blockers.append(f"missing_optional_package:{package}")
        if config.external_data_allowed:
            blockers.append("external_data_requires_privacy_review")
        if config.push_to_hub:
            blockers.append("automatic_model_publishing_prohibited")
        return {
            "runtime": "transformers_peft",
            "config": asdict(config),
            "available": not blockers,
            "blockers": blockers,
            "commands": [
                "load tokenizer and causal/classification model",
                "load versioned minimised dataset",
                "apply BitsAndBytes quantisation only when hardware supports it",
                "attach LoRA adapters to reviewed target modules",
                "train with evaluation, gradient clipping and early stopping",
                "measure perplexity or task metrics on temporal holdout",
                "save adapter weights and signed model card locally",
            ],
            "automatic_execution": False,
            "promotion": "pull_request_and_human_approval_required",
        }

    def yolo_plan(self, config: YOLOFineTuneConfig):
        blockers = []
        if not self.availability.ultralytics:
            blockers.append("missing_optional_package:ultralytics")
        if not config.dataset_yaml:
            blockers.append("dataset_manifest_required")
        return {
            "runtime": "ultralytics_yolo",
            "config": asdict(config),
            "available": not blockers,
            "blockers": blockers,
            "commands": [
                "validate licence and dataset provenance",
                "verify train validation test split by source",
                "fine-tune frozen backbone then controlled unfreezing",
                "monitor mAP precision recall class imbalance and overfitting",
                "export ONNX candidate and benchmark fp32 fp16 int8",
                "run card-assignment regression suite",
            ],
            "automatic_execution": False,
            "promotion": "pull_request_and_human_approval_required",
        }

    def embedding_plan(self, model_id="sentence-transformers/all-MiniLM-L6-v2"):
        blockers = [] if self.availability.sentence_transformers else ["missing_optional_package:sentence_transformers"]
        return {
            "runtime": "sentence_transformers",
            "model_id": model_id,
            "available": not blockers,
            "blockers": blockers,
            "quantization_candidates": ["fp32", "fp16", "int8"],
            "contrastive_fine_tuning": "offline_reviewed_only",
            "external_data_allowed": False,
        }
