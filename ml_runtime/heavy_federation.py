from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping

from .candidates import (
    train_embedding_candidate,
    train_lora_candidate,
    train_yolo_candidate,
)
from .evidence import CandidateEvidence, EvidenceGate
from .governance import DatasetBundleBuilder
from .review_board import CandidateReviewBoard


HEAVY_FEDERATION_VERSION = "heavy-runtime-federation-v1"
CANDIDATE_TASKS = {
    "embedding": "embedding",
    "lora": "language_model",
    "yolo": "vision",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _recursive_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _relative_rollback(candidate: str, raw_path: str, candidate_dir: Path) -> tuple[str, Path]:
    raw = Path(raw_path)
    resolved = raw if raw.is_absolute() else candidate_dir / raw
    if not resolved.exists():
        direct = candidate_dir / raw.name
        resolved = direct if direct.exists() else resolved
    try:
        nested = resolved.relative_to(candidate_dir)
    except ValueError:
        nested = Path(resolved.name)
    return f"{candidate}/{nested.as_posix()}", resolved


def build_dataset_bundle(workspace: str | Path, seed: int = 130) -> dict[str, Any]:
    workspace = Path(workspace)
    dataset_root = workspace / "datasets"
    dataset_root.mkdir(parents=True, exist_ok=True)
    result = DatasetBundleBuilder(seed=seed).build(dataset_root)
    record_counts = {
        path: int(metadata.get("records", 0))
        for path, metadata in result["manifest"]["files"].items()
        if path.endswith(".jsonl")
    }
    summary = {
        "version": HEAVY_FEDERATION_VERSION,
        "seed": seed,
        "dataset_root": "datasets",
        "dataset_id": result["manifest"]["dataset_id"],
        "dataset_digest": result["signature"]["manifest_digest"],
        "record_counts": record_counts,
        "total_records": sum(record_counts.values()),
        "signature_mode": result["signature"]["mode"],
        "production_data_used": False,
        "model_downloads_used": False,
    }
    (workspace / "DATASET_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _normalise_candidate(
    candidate: str,
    result: Mapping[str, Any],
    candidate_dir: Path,
    runtime_seconds: float,
) -> dict[str, Any]:
    evidence_data = dict(result["evidence"])
    relative_rollback, resolved_rollback = _relative_rollback(
        candidate,
        str(evidence_data.get("rollback_artifact") or ""),
        candidate_dir,
    )
    metrics = dict(evidence_data.get("metrics") or {})
    metrics["runtime_seconds"] = float(runtime_seconds)
    metrics["rollback_artifact_bytes"] = float(_recursive_size(resolved_rollback))
    safety = dict(evidence_data.get("safety_results") or {})
    safety["rollback_verified"] = bool(resolved_rollback.exists() and _recursive_size(resolved_rollback) > 0)
    evidence_data.update(
        {
            "code_commit": os.getenv("GITHUB_SHA") or "local-heavy-runtime-commit",
            "metrics": metrics,
            "safety_results": safety,
            "rollback_artifact": relative_rollback,
            "limitations": tuple(evidence_data.get("limitations") or ())
            + (
                "synthetic governed dataset",
                "CPU-bounded candidate run",
                "not production-deployed",
            ),
        }
    )
    evidence = CandidateEvidence(**evidence_data)
    gate = EvidenceGate().evaluate(evidence)
    pack = EvidenceGate.write_pack(candidate_dir / "evidence", evidence, gate)
    runtime = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "candidate": candidate,
        "task": evidence.task,
        "runtime_seconds": runtime_seconds,
        "artifact_bytes": _recursive_size(resolved_rollback),
        "rollback_exists": resolved_rollback.exists(),
        "rollback_reference": relative_rollback,
        "offline_model_mode": os.getenv("HF_HUB_OFFLINE") == "1",
        "automatic_promotion": False,
    }
    payload = {
        "version": HEAVY_FEDERATION_VERSION,
        "candidate": candidate,
        "evidence": asdict(evidence),
        "gate": gate,
        "pack": pack,
        "runtime": runtime,
        "raw_result": {
            key: value
            for key, value in result.items()
            if key not in {"evidence", "gate"}
        },
    }
    (candidate_dir / "RESULT.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return payload


def run_heavy_candidate(
    candidate: str,
    workspace: str | Path,
    seed: int = 130,
) -> dict[str, Any]:
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
        result = train_embedding_candidate(dataset_root, candidate_dir, seed=seed, epochs=18)
    elif candidate == "lora":
        result = train_lora_candidate(dataset_root, candidate_dir, seed=seed, epochs=5)
    else:
        result = train_yolo_candidate(dataset_root, candidate_dir, seed=seed, epochs=3)
    runtime_seconds = time.perf_counter() - started
    return _normalise_candidate(candidate, result, candidate_dir, runtime_seconds)


def _load_pack(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "evidence" not in payload or "pack_digest" not in payload:
        raise ValueError(f"invalid candidate pack: {path}")
    expected = hashlib.sha256(
        json.dumps(
            {"evidence": payload["evidence"], "gate": payload["gate"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if expected != payload["pack_digest"]:
        raise ValueError(f"candidate pack digest mismatch: {path}")
    if payload["gate"].get("promotion_permitted") is not False:
        raise ValueError(f"candidate pack attempted promotion: {path}")
    return payload


def discover_candidate_packs(candidates_root: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    candidates_root = Path(candidates_root)
    packs: list[dict[str, Any]] = []
    discovered_tasks: set[str] = set()
    for path in sorted(candidates_root.rglob("*.json")):
        if path.name in {"RESULT.json", "SUMMARY.json", "candidate-review-board.json"}:
            continue
        try:
            pack = _load_pack(path)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        task = str(pack["evidence"].get("task") or "")
        if task in CANDIDATE_TASKS.values() and task not in discovered_tasks:
            packs.append(pack)
            discovered_tasks.add(task)
    missing = sorted(set(CANDIDATE_TASKS.values()) - discovered_tasks)
    return packs, missing


def _primary_metric(evidence: Mapping[str, Any]) -> tuple[str, float, str]:
    task = str(evidence.get("task"))
    metrics = dict(evidence.get("metrics") or {})
    if task == "language_model":
        return "test_perplexity", float(metrics.get("test_perplexity", math.inf)), "lower"
    if task == "embedding":
        return "retrieval_mrr", float(metrics.get("retrieval_mrr", 0.0)), "higher"
    if task == "vision":
        return "map50", float(metrics.get("map50", 0.0)), "higher"
    return "primary_score", float(metrics.get("primary_score", 0.0)), "higher"


def _frontier_entry(pack: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    evidence = dict(pack["evidence"])
    task = str(evidence["task"])
    metric, value, direction = _primary_metric(evidence)
    micro = dict(reference["candidates"].get(task) or {})
    micro_value = float(micro.get("value", math.nan))
    ratio = None
    if math.isfinite(micro_value):
        if direction == "lower":
            ratio = micro_value / max(value, 1e-12)
        else:
            ratio = value / max(micro_value, 1e-12)
    return {
        "task": task,
        "heavy_candidate_id": evidence["candidate_id"],
        "heavy_framework": evidence["framework"],
        "metric": metric,
        "direction": direction,
        "heavy_value": value,
        "micro_reference_id": micro.get("candidate_id"),
        "micro_reference_value": micro_value if math.isfinite(micro_value) else None,
        "reference_ratio": ratio,
        "directly_comparable": False,
        "comparison_note": reference["comparison_policy"],
        "heavy_runtime_seconds": float((evidence.get("metrics") or {}).get("runtime_seconds", 0.0)),
        "heavy_artifact_bytes": float((evidence.get("metrics") or {}).get("rollback_artifact_bytes", 0.0)),
    }


def federate_heavy_evidence(
    candidates_root: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    candidates_root = Path(candidates_root)
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    packs, missing = discover_candidate_packs(candidates_root)
    board = CandidateReviewBoard().compare(packs) if packs else {
        "candidate_count": 0,
        "cards": [],
        "board_digest": _digest({"empty": True}),
        "promotion_permitted": False,
        "human_review_required": True,
    }
    frontier = [_frontier_entry(pack, reference) for pack in packs]
    gate_ready = all(bool(pack.get("gate", {}).get("eligible_for_human_review")) for pack in packs)
    report = {
        "schema_version": 1,
        "version": HEAVY_FEDERATION_VERSION,
        "candidate_count": len(packs),
        "missing_tasks": missing,
        "complete_candidate_set": not missing,
        "review_board": board,
        "microcandidate_reference": {
            "reference_id": reference["reference_id"],
            "source_pr": reference["source_pr"],
            "direct_comparability": False,
        },
        "frontier": frontier,
        "eligible_for_human_review": bool(packs) and not missing and gate_ready,
        "promotion_permitted": False,
        "human_review_required": True,
        "production_deployment": False,
        "crm_decision_use": False,
        "external_communication": False,
    }
    report["federation_digest"] = _digest(report)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
