from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Sequence

from .core import cosine_similarity
from .retrieval import HashedTextEncoder


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    confidence: float
    class_id: str
    source_id: str = ""

    def clipped(self):
        x = max(0.0, min(1.0, self.x))
        y = max(0.0, min(1.0, self.y))
        width = max(0.0, min(1.0 - x, self.width))
        height = max(0.0, min(1.0 - y, self.height))
        return BoundingBox(x, y, width, height, max(0.0, min(1.0, self.confidence)), self.class_id, self.source_id)


def iou(left: BoundingBox, right: BoundingBox):
    lx2, ly2 = left.x + left.width, left.y + left.height
    rx2, ry2 = right.x + right.width, right.y + right.height
    intersection_width = max(0.0, min(lx2, rx2) - max(left.x, right.x))
    intersection_height = max(0.0, min(ly2, ry2) - max(left.y, right.y))
    intersection = intersection_width * intersection_height
    union = left.width * left.height + right.width * right.height - intersection
    return intersection / max(union, 1e-12)


def non_max_suppression(boxes: Sequence[BoundingBox], threshold=0.45):
    ordered = sorted((box.clipped() for box in boxes), key=lambda box: (-box.confidence, box.class_id, box.source_id))
    kept = []
    while ordered:
        candidate = ordered.pop(0)
        kept.append(candidate)
        ordered = [box for box in ordered if box.class_id != candidate.class_id or iou(candidate, box) < threshold]
    return kept


class YOLOStyleDetector:
    """Grid/anchor detector contract for card-worthy multimedia regions.

    This dependency-free runtime decodes model outputs and performs NMS. Actual
    image feature extraction and trained weights belong to an optional reviewed
    Ultralytics/ONNX adapter; the reference code never claims trained detection.
    """

    def __init__(self, classes=("person", "product", "document", "chart", "logo", "landscape"), threshold=0.35):
        self.classes = tuple(classes)
        self.threshold = threshold

    def decode(self, grid_predictions, source_id="synthetic"):
        boxes = []
        for row_index, row in enumerate(grid_predictions):
            for column_index, cell in enumerate(row):
                objectness = float(cell.get("objectness", 0.0))
                class_scores = list(cell.get("classes", []))
                if not class_scores:
                    continue
                class_index = max(range(min(len(class_scores), len(self.classes))), key=lambda index: class_scores[index])
                confidence = objectness * float(class_scores[class_index])
                if confidence < self.threshold:
                    continue
                grid_height = len(grid_predictions)
                grid_width = len(row)
                x = (column_index + float(cell.get("x", 0.5))) / max(grid_width, 1)
                y = (row_index + float(cell.get("y", 0.5))) / max(grid_height, 1)
                width = float(cell.get("width", 0.25))
                height = float(cell.get("height", 0.25))
                boxes.append(BoundingBox(x - width / 2, y - height / 2, width, height, confidence, self.classes[class_index], source_id))
        return non_max_suppression(boxes)

    @staticmethod
    def training_contract():
        return {
            "framework_adapter": "ultralytics_or_onnx_disabled",
            "dataset_required": True,
            "annotation_format": "YOLO normalized xywh",
            "metrics": ["mAP50", "mAP50-95", "precision", "recall", "class_error"],
            "augmentation": ["resize", "letterbox", "limited_flip", "colour_jitter"],
            "anti_overfit": ["train_validation_test_split", "early_stopping", "weight_decay", "augmentation_audit"],
            "promotion": "human_review_required",
        }


@dataclass(frozen=True)
class NeuralCard:
    card_id: str
    card_type: str
    title: str
    summary: str
    source_refs: tuple[str, ...]
    confidence: float
    layer: int
    position: tuple[float, float]
    related_cards: tuple[str, ...]
    actions: tuple[str, ...]
    human_review: bool = True


class CardEmbeddingSpace:
    def __init__(self, dimensions=32):
        self.encoder = HashedTextEncoder(dimensions)

    def encode(self, title, summary, card_type):
        return self.encoder.encode(f"{card_type} {title} {summary}")


class FloatingCardFabric:
    CARD_TYPES = ("lead", "company", "service", "opportunity", "activity", "document", "media", "insight", "task", "risk")

    def __init__(self, dimensions=32):
        self.space = CardEmbeddingSpace(dimensions)

    @staticmethod
    def _card_id(card_type, source_refs, title):
        payload = f"{card_type}|{'|'.join(sorted(source_refs))}|{title}".encode()
        return "CARD-" + hashlib.sha256(payload).hexdigest()[:12].upper()

    def build(self, card_type, title, summary, source_refs, confidence=0.7, actions=()):
        if card_type not in self.CARD_TYPES:
            raise ValueError("unsupported card type")
        card_id = self._card_id(card_type, tuple(source_refs), title)
        digest = int(hashlib.sha256(card_id.encode()).hexdigest()[:8], 16)
        layer = 1 + digest % 5
        angle = (digest % 360) * math.pi / 180.0
        radius = 0.18 + (digest % 29) / 100.0
        position = (0.5 + math.cos(angle) * radius, 0.5 + math.sin(angle) * radius)
        return NeuralCard(card_id, card_type, title, summary, tuple(source_refs), max(0.0, min(1.0, confidence)), layer, position, (), tuple(actions), True)

    def connect(self, cards: Sequence[NeuralCard], threshold=0.20, maximum_links=4):
        embeddings = {card.card_id: self.space.encode(card.title, card.summary, card.card_type) for card in cards}
        result = []
        for card in cards:
            candidates = []
            for other in cards:
                if card.card_id == other.card_id:
                    continue
                score = cosine_similarity(embeddings[card.card_id], embeddings[other.card_id])
                shared_source = bool(set(card.source_refs).intersection(other.source_refs))
                score += 0.20 if shared_source else 0.0
                if score >= threshold:
                    candidates.append((score, other.card_id))
            candidates.sort(key=lambda item: (-item[0], item[1]))
            related = tuple(card_id for _, card_id in candidates[:maximum_links])
            result.append(NeuralCard(**{**card.__dict__, "related_cards": related}))
        return result

    def assign_multimedia(self, detections: Iterable[BoundingBox], source_title="Media evidence"):
        cards = []
        for index, detection in enumerate(detections):
            card_type = "media" if detection.class_id not in {"document", "chart"} else "document"
            cards.append(self.build(
                card_type,
                f"{source_title}: {detection.class_id}",
                f"Detected {detection.class_id} region at confidence {detection.confidence:.2f}.",
                (detection.source_id or f"region-{index}",),
                detection.confidence,
                actions=("review", "attach_to_relevant_record"),
            ))
        return self.connect(cards)


@dataclass(frozen=True)
class VisionRuntimeContract:
    provider: str = "disabled"
    model_id: str = "yolo-unset"
    quantization: str = "int8_or_fp16_candidate"
    device: str = "cpu"
    automatic_upload: bool = False
    automatic_client_claim: bool = False
    human_review_required: bool = True
