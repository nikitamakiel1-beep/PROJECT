from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import re
from typing import Any, Iterable, Mapping


class DatasetPolicyError(ValueError):
    pass


PII_KEYS = {
    "name", "first_name", "last_name", "email", "phone", "telephone",
    "address", "postal_address", "password", "secret", "token", "api_key",
    "website", "url", "company_name", "contact_name",
}
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\s().-]*){9,}")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T.*)?$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 6)


def validate_no_pii(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalised in PII_KEYS:
                raise DatasetPolicyError(f"prohibited field at {path}.{key}")
            validate_no_pii(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_no_pii(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if EMAIL_PATTERN.search(value):
            raise DatasetPolicyError(f"email-like content at {path}")
        if URL_PATTERN.search(value):
            raise DatasetPolicyError(f"URL-like content at {path}")
        if not ISO_DATE_PATTERN.fullmatch(value) and PHONE_PATTERN.search(value):
            raise DatasetPolicyError(f"phone-like content at {path}")


@dataclass(frozen=True)
class DatasetRecord:
    record_id: str
    occurred_at: str
    segment: str
    task: str
    text: str
    features: dict[str, float]
    label: str | int
    source_class: str = "synthetic"

    def __post_init__(self) -> None:
        if self.source_class not in {"synthetic", "explicitly_approved"}:
            raise DatasetPolicyError("unapproved source class")
        validate_no_pii(asdict(self))
        for key, value in self.features.items():
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise DatasetPolicyError(f"feature {key} is not bounded")


@dataclass(frozen=True)
class DatasetSplit:
    name: str
    records: tuple[DatasetRecord, ...]

    @property
    def record_ids(self) -> set[str]:
        return {record.record_id for record in self.records}


class DatasetBundleBuilder:
    """Deterministic lawful dataset generator and evidence packager.

    The committed generator creates only fictional CRM/B2B/B2C, RAG and vision
    material. An explicitly approved dataset may be passed through the same
    validators later, but this module never reads production CRM data.
    """

    SERVICES = ("IVA", "CRM", "IOP")
    SEGMENTS = ("b2b_industrial", "b2b_services", "b2c_professional")
    INTENTS = (
        "clarify international visibility",
        "organise lead follow-up",
        "prepare a commercial message",
    )

    def __init__(self, seed: int = 126, signing_key: str | None = None) -> None:
        self.seed = int(seed)
        self.signing_key = signing_key if signing_key is not None else os.getenv("DATASET_SIGNING_KEY", "")

    def _crm_records(self, count: int = 240) -> list[DatasetRecord]:
        start = date(2025, 1, 1)
        records: list[DatasetRecord] = []
        for index in range(count):
            segment = self.SEGMENTS[index % len(self.SEGMENTS)]
            service = self.SERVICES[index % len(self.SERVICES)]
            intent = self.INTENTS[index % len(self.INTENTS)]
            fit = _bounded(0.25 + ((index * 17) % 70) / 100)
            activity = _bounded(0.10 + ((index * 11) % 80) / 100)
            urgency = _bounded(0.05 + ((index * 7) % 90) / 100)
            consent = 1.0 if index % 5 else 0.0
            relationship = _bounded(0.15 + ((index * 13) % 75) / 100)
            price_sensitivity = _bounded(((index * 19) % 100) / 100)
            outcome = int((fit * 0.40 + activity * 0.22 + relationship * 0.18 + consent * 0.10 + urgency * 0.10) >= 0.57)
            occurred = start + timedelta(days=index * 2)
            text = (
                f"Fictional {segment.replace('_', ' ')} case requests to {intent}. "
                f"The recommended catalogue route is {service}; evidence is synthetic and non-identifying."
            )
            records.append(
                DatasetRecord(
                    record_id=f"SYN-CRM-{index:04d}",
                    occurred_at=occurred.isoformat(),
                    segment=segment,
                    task="crm_conversion",
                    text=text,
                    features={
                        "fit": fit,
                        "activity": activity,
                        "urgency": urgency,
                        "consent": consent,
                        "relationship": relationship,
                        "price_sensitivity": price_sensitivity,
                        "service_iva": 1.0 if service == "IVA" else 0.0,
                        "service_crm": 1.0 if service == "CRM" else 0.0,
                        "service_iop": 1.0 if service == "IOP" else 0.0,
                    },
                    label=outcome,
                )
            )
        return records

    def _rag_records(self, count: int = 36) -> list[DatasetRecord]:
        start = date(2025, 2, 1)
        topics = (
            ("IVA", "audit value proposition, trust, mobile clarity and international readiness"),
            ("CRM", "define ownership, pipeline stages, follow-up dates and a management dashboard"),
            ("IOP", "select an audience, collect proof, address objections and produce a bilingual one-pager"),
        )
        records: list[DatasetRecord] = []
        for index in range(count):
            service, body = topics[index % len(topics)]
            records.append(
                DatasetRecord(
                    record_id=f"SYN-RAG-{index:04d}",
                    occurred_at=(start + timedelta(days=index)).isoformat(),
                    segment="internal_knowledge",
                    task="rag_retrieval",
                    text=f"Synthetic knowledge unit {index}: {service} should {body}. Human approval is required before external use.",
                    features={"service_index": (index % 3) / 2, "revision": _bounded(index / max(1, count - 1))},
                    label=service,
                )
            )
        return records

    def _vision_records(self, count: int = 72) -> list[DatasetRecord]:
        classes = ("document", "chart", "logo", "product", "landscape", "person")
        start = date(2025, 3, 1)
        records: list[DatasetRecord] = []
        for index in range(count):
            class_name = classes[index % len(classes)]
            x = _bounded(0.12 + ((index * 7) % 50) / 100)
            y = _bounded(0.10 + ((index * 9) % 50) / 100)
            width = _bounded(0.18 + ((index * 5) % 25) / 100)
            height = _bounded(0.18 + ((index * 3) % 25) / 100)
            records.append(
                DatasetRecord(
                    record_id=f"SYN-VIS-{index:04d}",
                    occurred_at=(start + timedelta(days=index)).isoformat(),
                    segment="synthetic_multimedia",
                    task="object_detection",
                    text=f"Synthetic geometric scene containing one reviewed {class_name} card object.",
                    features={"x": x, "y": y, "width": width, "height": height, "class_index": (index % len(classes)) / (len(classes) - 1)},
                    label=class_name,
                )
            )
        return records

    @staticmethod
    def temporal_split(records: Iterable[DatasetRecord], train_ratio: float = 0.70, validation_ratio: float = 0.15) -> dict[str, DatasetSplit]:
        ordered = sorted(records, key=lambda record: (record.occurred_at, record.record_id))
        if len(ordered) < 6:
            raise DatasetPolicyError("at least six records are required")
        train_end = max(1, int(len(ordered) * train_ratio))
        validation_end = max(train_end + 1, int(len(ordered) * (train_ratio + validation_ratio)))
        validation_end = min(validation_end, len(ordered) - 1)
        splits = {
            "train": DatasetSplit("train", tuple(ordered[:train_end])),
            "validation": DatasetSplit("validation", tuple(ordered[train_end:validation_end])),
            "test": DatasetSplit("test", tuple(ordered[validation_end:])),
        }
        ids = [split.record_ids for split in splits.values()]
        if ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2]:
            raise DatasetPolicyError("split leakage detected")
        if max(record.occurred_at for record in splits["train"].records) >= min(record.occurred_at for record in splits["validation"].records):
            raise DatasetPolicyError("train/validation temporal boundary invalid")
        if max(record.occurred_at for record in splits["validation"].records) >= min(record.occurred_at for record in splits["test"].records):
            raise DatasetPolicyError("validation/test temporal boundary invalid")
        return splits

    @staticmethod
    def _write_jsonl(path: Path, records: Iterable[DatasetRecord]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(json.dumps(asdict(record), sort_keys=True, ensure_ascii=False) + "\n" for record in records)
        path.write_text(payload, encoding="utf-8")
        return sha256(payload)

    def _signature(self, manifest: Mapping[str, Any]) -> dict[str, str]:
        digest = sha256(canonical_json(manifest))
        if not self.signing_key:
            return {"mode": "unsigned_synthetic", "manifest_digest": digest, "signature": ""}
        signature = hmac.new(self.signing_key.encode("utf-8"), canonical_json(manifest), hashlib.sha256).hexdigest()
        return {"mode": "hmac_sha256", "manifest_digest": digest, "signature": signature}

    def build(self, root: str | Path) -> dict[str, Any]:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        task_records = {
            "crm": self._crm_records(),
            "rag": self._rag_records(),
            "vision": self._vision_records(),
        }
        files: dict[str, dict[str, Any]] = {}
        split_summary: dict[str, Any] = {}
        for task, records in task_records.items():
            splits = self.temporal_split(records)
            split_summary[task] = {}
            for split_name, split in splits.items():
                relative = Path(task) / f"{split_name}.jsonl"
                digest = self._write_jsonl(root / relative, split.records)
                files[str(relative)] = {"sha256": digest, "records": len(split.records)}
                split_summary[task][split_name] = {
                    "records": len(split.records),
                    "first_date": split.records[0].occurred_at,
                    "last_date": split.records[-1].occurred_at,
                    "segments": sorted({record.segment for record in split.records}),
                }
        card = {
            "dataset_id": "colonial-candidate-lab-synthetic-v1",
            "source_class": "synthetic",
            "lawful_basis": "fictional generated data; no person or company represented",
            "intended_uses": ["shadow candidate training", "pipeline validation", "regression testing"],
            "prohibited_uses": ["production decisions", "external communication", "identity inference", "model promotion without reviewed evidence"],
            "tasks": sorted(task_records),
            "splits": split_summary,
            "pii_review": "passed_by_generator",
            "seed": self.seed,
        }
        card_path = root / "DATASET_CARD.json"
        card_path.write_text(json.dumps(card, indent=2, sort_keys=True), encoding="utf-8")
        files["DATASET_CARD.json"] = {"sha256": sha256(card_path.read_bytes()), "records": 1}
        manifest = {
            "schema_version": 1,
            "dataset_id": card["dataset_id"],
            "source_class": "synthetic",
            "files": files,
            "card_digest": files["DATASET_CARD.json"]["sha256"],
        }
        signature = self._signature(manifest)
        evidence = {"manifest": manifest, "signature": signature}
        (root / "MANIFEST.json").write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        return evidence
