from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from .candidate_rework import train_lora_candidate_v2, train_yolo_candidate_v2
from .embedding_rework import train_embedding_candidate_v3
from .heavy_federation import CANDIDATE_TASKS, _normalise_candidate, build_dataset_bundle
from .heavy_rework import federate_heavy_evidence


def run_heavy_candidate(candidate: str, workspace: str | Path, seed: int = 130) -> dict[str, Any]:
    if candidate not in CANDIDATE_TASKS:
        raise ValueError(f"unsupported heavy candidate: {candidate}")
    workspace = Path(workspace)
    dataset_root = workspace / "datasets"
    if not (dataset_root / "MANIFEST.json").exists():
        raise FileNotFoundError("governed dataset bundle is missing")
    candidate_dir = workspace / "candidates" / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if candidate == "embedding":
        result = train_embedding_candidate_v3(dataset_root, candidate_dir, seed=seed, epochs=60)
    elif candidate == "lora":
        result = train_lora_candidate_v2(dataset_root, candidate_dir, seed=seed, epochs=8)
    else:
        result = train_yolo_candidate_v2(dataset_root, candidate_dir, seed=seed, epochs=18)
    return _normalise_candidate(candidate, result, candidate_dir, time.perf_counter() - started)


__all__ = ["build_dataset_bundle", "federate_heavy_evidence", "run_heavy_candidate"]
