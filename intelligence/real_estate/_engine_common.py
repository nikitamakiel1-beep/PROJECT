"""Shared governance and parsing primitives for the real-estate runtime."""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping

MODEL_VERSION = "real-estate-underwriting-v0.1"
STATUS_MAP = {
    "excel": "discovered",
    "wip": "analysis_in_progress",
    "validat": "validated",
    "validado": "validated",
    "ppt": "presentation_ready",
    "compartit": "shared",
    "compartido": "shared",
    "reservat": "reserved",
    "reservado": "reserved",
    "descartat": "rejected",
    "descartado": "rejected",
}
STRATEGIES = {
    "traditional_rental": {
        "enabled_field": "Tradicional",
        "renovation_field": "REFORMA ESTIMADA TRADICIONAL",
        "rent_fields": {
            "downside": "Downside Tradicional",
            "base": "Base Tradicional",
            "upside": "Upside Tradicional",
        },
        "maintenance_field": "MANTENIMIENTO TRADICIONAL",
    },
    "room_rental": {
        "enabled_field": "Habitacional",
        "renovation_field": "REFORMA ESTIMADA HABITACIONES",
        "rent_fields": {
            "downside": "Downside Habitacions",
            "base": "Base Habitacions",
            "upside": "Upside Habitacions",
        },
        "maintenance_field": "MANTENIMIENTO HABITACIONAL",
    },
    "temporary_rental": {
        "enabled_field": "Temporal",
        "renovation_field": "REFORMA ESTIMADA TEMPORAL",
        "rent_fields": {
            "downside": "Downside Temporal",
            "base": "Base Temporal",
            "upside": "Upside Temporal",
        },
        "maintenance_field": "MANTENIMIENTO TEMPORAL",
    },
}
QUARANTINED_FIELDS = {
    "Responsable",
    "Clientes potenciales",
    "CARACTERISTIQUES PIS",
}
PRIVATE_TOKEN_FIELDS = {
    "Ref.Catastral": "cadastral_reference_token",
    "Link": "listing_url_token",
}
PII_MARKERS = {
    "email",
    "phone",
    "telefono",
    "teléfono",
    "full name",
    "contact name",
    "client name",
    "cliente",
    "clientes potenciales",
    "responsable",
}


class RealEstateGovernanceError(ValueError):
    """Raised when source data or authority violates the import boundary."""


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any, length: int) -> str:
    source = "|".join("" if part is None else str(part) for part in parts)
    digest = sha256(source.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:length].upper()}"


def private_token(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return stable_id("TOKEN", str(value).strip(), length=16)


def owner_alias(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return stable_id("OWNER", str(value).strip().casefold(), length=12)


def number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        result = float(value)
    elif isinstance(value, (int, float)):
        result = float(value)
    else:
        text = (
            str(value)
            .strip()
            .replace("€", "")
            .replace("%", "")
            .replace(" ", "")
        )
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            text = text.replace(",", "")
        try:
            result = float(text)
        except ValueError as exc:
            raise RealEstateGovernanceError(
                f"non-numeric value: {value!r}"
            ) from exc
    if not math.isfinite(result):
        raise RealEstateGovernanceError("numeric values must be finite")
    return result


def optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return number(value)


def integer(value: Any) -> int | None:
    parsed = optional_number(value)
    return None if parsed is None else int(round(parsed))


def yes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {
        "si",
        "sí",
        "yes",
        "true",
        "1",
        "x",
    }


def normalise_status(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return STATUS_MAP.get(
        text,
        "analysis_in_progress" if text else "discovered",
    )


def normalise_text(value: Any, max_length: int = 120) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:max_length] or None


def monthly_payment(
    principal: float,
    annual_rate: float,
    years: float,
) -> float:
    if principal <= 0 or years <= 0:
        return 0.0
    periods = int(round(years * 12))
    if periods <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate <= 0:
        return principal / periods
    factor = (1 + monthly_rate) ** periods
    return principal * monthly_rate * factor / (factor - 1)


def confidence(
    row: Mapping[str, Any],
    required: Iterable[str],
) -> float:
    fields = list(required)
    if not fields:
        return 0.0
    present = sum(
        1 for field in fields if row.get(field) not in (None, "")
    )
    return round(present / len(fields), 6)


def first_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def assert_rights_gate(rights_status: str) -> None:
    if rights_status not in {
        "owned",
        "licensed",
        "client_authorised",
        "public_source",
    }:
        raise RealEstateGovernanceError(
            "row-level import blocked: source rights must be owned, "
            "licensed, client_authorised or public_source"
        )


def detect_sensitive_fields(row: Mapping[str, Any]) -> list[str]:
    found: set[str] = set()
    for key, value in row.items():
        lowered = str(key).casefold()
        if value in (None, ""):
            continue
        if (
            any(marker in lowered for marker in PII_MARKERS)
            or str(key) in PRIVATE_TOKEN_FIELDS
            or str(key) in QUARANTINED_FIELDS
        ):
            found.add(str(key))
    return sorted(found)
