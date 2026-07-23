"""La Vanguardia address-to-zone evidence contracts.

This module does not scrape or download La Vanguardia. It prepares a supervised
capture plan and validates an operator-confirmed evidence bundle containing the
exact address match, the census-section map screenshot, the displayed household
income, the selected 1-5 legend bucket, and surrounding-area captures.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


class ZoneEvidenceError(ValueError):
    """Raised when zone evidence is incomplete or not trustworthy enough."""


DEFAULT_SOURCE_URL = (
    "https://stories.lavanguardia.com/sociedad/20221007/58738/"
    "ganas-mas-o-menos-que-tu-vecino-consulta-tu-calle-en-este-mapa"
)

ALLOWED_ZONE_MEDIA_RIGHTS = {
    "owned",
    "licensed",
    "client_authorised",
    "public_source_capture",
    "streetview_capture",
}


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def normalize_address(address: str) -> str:
    normalized = re.sub(r"\s+", " ", str(address or "").strip())
    if len(normalized) < 8:
        raise ZoneEvidenceError("a sufficiently specific property address is required")
    return normalized


def _validate_lavanguardia_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ZoneEvidenceError("La Vanguardia evidence URL must use HTTPS")
    host = parsed.netloc.casefold()
    if host not in {"stories.lavanguardia.com", "www.lavanguardia.com"}:
        raise ZoneEvidenceError("zone evidence must point to La Vanguardia")


def build_zone_capture_plan(
    *,
    project_code: str,
    exact_address: str,
    operator_token: str,
    source_url: str = DEFAULT_SOURCE_URL,
) -> dict[str, Any]:
    """Build a supervised browser-capture plan.

    The operator searches the exact address in the interactive map, confirms the
    census-section polygon, records the displayed household income and legend
    bucket, and captures one map screenshot plus at least two surroundings images.
    """
    if not re.fullmatch(r"[A-Z0-9_\-]{4,80}", project_code):
        raise ZoneEvidenceError("invalid project code")
    address = normalize_address(exact_address)
    if not operator_token.startswith("restricted://operator/"):
        raise ZoneEvidenceError("restricted operator token required")
    _validate_lavanguardia_url(source_url)

    plan = {
        "schema_version": 1,
        "plan_type": "supervised_lavanguardia_zone_capture",
        "project_code": project_code,
        "exact_address": address,
        "source_url": source_url,
        "source_title": "¿Ganas más o menos que tu vecino? Consulta tu calle en este mapa",
        "source_dataset": "INE Atlas de Distribución de Renta de los Hogares",
        "source_data_year_expected": 2020,
        "operator_token": operator_token,
        "steps": [
            "Open the configured La Vanguardia interactive page in a normal browser.",
            "Search the exact property address and select the matching result.",
            "Confirm that the marker falls inside the intended census-section polygon.",
            "Record the household-income value displayed by the interactive.",
            "Record the visible legend colour/range and select Zone 1-5.",
            "Capture the map with address/marker, polygon, legend and income visible.",
            "Capture at least two surroundings images with source and attribution.",
            "Save all files in the restricted project workspace.",
        ],
        "required_capture_fields": [
            "matched_address",
            "latitude",
            "longitude",
            "address_match_confidence",
            "household_income_eur",
            "source_data_year",
            "selected_zone",
            "legend_label",
            "legend_version",
            "map_screenshot_path",
            "surroundings",
            "manual_confirmation",
        ],
        "automation_boundary": {
            "page_scraping_permitted": False,
            "captcha_or_access_bypass_permitted": False,
            "manual_browser_capture_required": True,
        },
    }
    plan["plan_digest"] = canonical_digest(plan)
    return plan


def classify_zone_from_thresholds(
    household_income_eur: float,
    thresholds: Sequence[float],
) -> int:
    """Classify income into five zones when a reviewed legend has four cut points."""
    if household_income_eur <= 0:
        raise ZoneEvidenceError("household income must be positive")
    if len(thresholds) != 4:
        raise ZoneEvidenceError("exactly four reviewed thresholds are required")
    ordered = [float(item) for item in thresholds]
    if ordered != sorted(ordered) or len(set(ordered)) != 4:
        raise ZoneEvidenceError("zone thresholds must be unique and ascending")
    for index, threshold in enumerate(ordered, start=1):
        if household_income_eur < threshold:
            return index
    return 5


def _validate_capture_file(path_value: str, label: str) -> tuple[str, str]:
    path = Path(path_value)
    if not path.is_absolute():
        raise ZoneEvidenceError(f"{label} path must be absolute")
    if not path.is_file() or path.stat().st_size == 0:
        raise ZoneEvidenceError(f"{label} file is missing or empty")
    return str(path), file_sha256(path)


def build_zone_evidence(
    *,
    capture_plan: Mapping[str, Any],
    capture_record: Mapping[str, Any],
    reviewed_thresholds: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Validate and digest one exact-address zone evidence bundle."""
    if capture_plan.get("plan_type") != "supervised_lavanguardia_zone_capture":
        raise ZoneEvidenceError("invalid capture plan")
    _validate_lavanguardia_url(str(capture_plan.get("source_url") or ""))

    exact = normalize_address(str(capture_plan["exact_address"]))
    matched = normalize_address(str(capture_record.get("matched_address") or ""))
    confidence = float(capture_record.get("address_match_confidence", 0))
    if confidence < 0.8:
        raise ZoneEvidenceError("address match confidence must be at least 0.80")
    if capture_record.get("manual_confirmation") is not True:
        raise ZoneEvidenceError("manual confirmation of the exact census section is required")

    latitude = float(capture_record.get("latitude"))
    longitude = float(capture_record.get("longitude"))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ZoneEvidenceError("invalid latitude or longitude")

    income = float(capture_record.get("household_income_eur"))
    if income <= 0:
        raise ZoneEvidenceError("displayed household income is required")
    source_year = int(capture_record.get("source_data_year"))
    if source_year < 2015 or source_year > 2030:
        raise ZoneEvidenceError("invalid source data year")

    selected_zone = int(capture_record.get("selected_zone"))
    if selected_zone not in {1, 2, 3, 4, 5}:
        raise ZoneEvidenceError("selected zone must be between 1 and 5")
    legend_label = str(capture_record.get("legend_label") or "").strip()
    legend_version = str(capture_record.get("legend_version") or "").strip()
    if not legend_label or not legend_version:
        raise ZoneEvidenceError("legend label and version are required")

    derived_zone = None
    if reviewed_thresholds is not None:
        derived_zone = classify_zone_from_thresholds(income, reviewed_thresholds)
        if selected_zone != derived_zone:
            raise ZoneEvidenceError("selected zone conflicts with reviewed legend thresholds")

    screenshot_path, screenshot_sha = _validate_capture_file(
        str(capture_record.get("map_screenshot_path") or ""),
        "map screenshot",
    )

    surroundings = capture_record.get("surroundings")
    if not isinstance(surroundings, list) or len(surroundings) < 2:
        raise ZoneEvidenceError("at least two surroundings captures are required")
    validated_surroundings: list[dict[str, Any]] = []
    for index, item in enumerate(surroundings, start=1):
        if not isinstance(item, Mapping):
            raise ZoneEvidenceError("surroundings items must be objects")
        rights = str(item.get("rights_status") or "")
        if rights not in ALLOWED_ZONE_MEDIA_RIGHTS:
            raise ZoneEvidenceError(f"unsupported surroundings rights status: {rights}")
        source_url = str(item.get("source_url") or "")
        if not source_url.startswith("https://"):
            raise ZoneEvidenceError("surroundings source URL must use HTTPS")
        path, digest = _validate_capture_file(
            str(item.get("path") or ""),
            f"surroundings image {index}",
        )
        validated_surroundings.append(
            {
                "media_id": str(item.get("media_id") or f"ZONE-{index:02d}"),
                "path": path,
                "sha256": digest,
                "source_url": source_url,
                "source_type": str(item.get("source_type") or "web_capture"),
                "rights_status": rights,
                "attribution": str(item.get("attribution") or ""),
                "watermark_removal_permitted": False,
            }
        )

    evidence = {
        "schema_version": 1,
        "evidence_type": "lavanguardia_census_income_zone",
        "project_code": capture_plan["project_code"],
        "requested_address": exact,
        "matched_address": matched,
        "latitude": latitude,
        "longitude": longitude,
        "address_match_confidence": confidence,
        "source_url": capture_plan["source_url"],
        "source_title": capture_plan["source_title"],
        "source_dataset": capture_plan["source_dataset"],
        "source_data_year": source_year,
        "household_income_eur": income,
        "zone": selected_zone,
        "derived_zone": derived_zone,
        "legend_label": legend_label,
        "legend_version": legend_version,
        "map_screenshot_path": screenshot_path,
        "map_screenshot_sha256": screenshot_sha,
        "surroundings": validated_surroundings,
        "manual_confirmation": True,
        "stale_data_warning_required": True,
        "watermark_removal_permitted_for_map": False,
        "report_placement": {
            "slide": 8,
            "fields": ["zone", "household_income_eur", "map_screenshot_path"],
        },
    }
    evidence["evidence_digest"] = canonical_digest(evidence)
    return evidence
