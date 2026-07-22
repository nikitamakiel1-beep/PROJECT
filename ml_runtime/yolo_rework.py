from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import traceback
from typing import Any

from .candidate_rework import _ece_brier, _generate_yolo_dataset_v2
from .candidates import _dataset_digest, _require, _safety_results
from .evidence import CandidateEvidence, EvidenceGate


def _numeric_vector(value: Any) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (int, float)):
        return [float(value)]
    return [float(item) for item in value]


def train_yolo_candidate_v3(dataset_root: str | Path, output_dir: str | Path, seed: int = 130, epochs: int = 18) -> dict[str, Any]:
    ultralytics = _require("ultralytics")["ultralytics"]
    dataset_root, output_dir = Path(dataset_root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
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
            name="yolo_candidate_v3",
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
        maps = _numeric_vector(getattr(metrics.box, "maps", None))
        classes = ["document", "chart", "logo", "product", "landscape", "person"]
        segment_metrics = {
            name: {"map50": maps[index] if index < len(maps) else map50}
            for index, name in enumerate(classes)
        }

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
            best = int(result.boxes.conf.argmax().item())
            confidences.append(float(result.boxes.conf[best].item()))
            correctness.append(int(int(result.boxes.cls[best].item()) == expected_class))
        ece, brier = _ece_brier(confidences, correctness)
        save_dir = Path(getattr(train_result, "save_dir", output_dir / "yolo_candidate_v3"))
        weights = save_dir / "weights" / "best.pt"
        if not weights.exists():
            fallback = output_dir / "yolo_candidate_v3" / "weights" / "best.pt"
            weights = fallback if fallback.exists() else weights

        evidence = CandidateEvidence(
            candidate_id="yolo-geometric-cards-shadow-v3",
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
    except Exception as error:
        failure = {
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "promotion_permitted": False,
            "production_deployment": False,
        }
        (output_dir / "ERROR.json").write_text(json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8")
        raise
