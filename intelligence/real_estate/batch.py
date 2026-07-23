"""Deterministic local batch adapter for the synthetic real-estate runtime."""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
import zipfile

from .synergy import (
    SyntheticFixture,
    SyntheticSynergyOrchestrator,
    build_synthetic_event,
    canonical_digest,
)


class SyntheticBatchError(ValueError):
    """Raised when a local synthetic batch violates the Stage 009r contract."""


def parse_synthetic_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parse a local CSV string into source-row envelopes.

    Values remain strings so the governed A30 parser remains authoritative for
    numeric and boolean interpretation.
    """
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    if not reader.fieldnames:
        raise SyntheticBatchError("CSV header is required")
    if "CODI" not in reader.fieldnames:
        raise SyntheticBatchError("CSV must contain CODI")

    records: list[dict[str, Any]] = []
    for offset, row in enumerate(reader, start=2):
        clean = {
            str(key): value
            for key, value in row.items()
            if key is not None and value not in (None, "")
        }
        if not clean:
            continue
        records.append({"source_row": offset, "row": clean})
    return records


def build_synthetic_batch(
    *,
    batch_id: str,
    source_profile: str,
    rights_status: str,
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "synthetic": True,
        "batch_id": batch_id,
        "source_profile": source_profile,
        "rights_status": rights_status,
        "records": [dict(record) for record in records],
    }


def _validate_batch(batch: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "synthetic",
        "batch_id",
        "source_profile",
        "rights_status",
        "records",
    }
    missing = sorted(required - set(batch))
    if missing:
        raise SyntheticBatchError(f"missing batch fields: {missing}")
    if batch["schema_version"] != 1:
        raise SyntheticBatchError("unsupported batch schema version")
    if batch["synthetic"] is not True:
        raise SyntheticBatchError("synthetic batch flag required")
    if not str(batch["batch_id"]).startswith("SYN-BATCH-"):
        raise SyntheticBatchError("synthetic batch ID required")
    if not str(batch["source_profile"]).startswith("SYNTHETIC_"):
        raise SyntheticBatchError("synthetic source profile required")
    if not isinstance(batch["records"], list):
        raise SyntheticBatchError("records must be a list")


def _row_receipt(
    *,
    batch_id: str,
    source_row: Any,
    status: str,
    reason: str | None = None,
    event_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = {
        "batch_id": batch_id,
        "source_row": source_row,
        "status": status,
        "reason": reason,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
        "transaction_action_permitted": False,
    }
    if event_receipt:
        receipt["event_id"] = event_receipt.get("event_id")
        receipt["plan_digest"] = event_receipt.get("plan_digest")
        receipt["details"] = event_receipt.get("details", [])
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def process_synthetic_batch(
    batch: Mapping[str, Any],
    *,
    orchestrator: SyntheticSynergyOrchestrator | None = None,
) -> dict[str, Any]:
    """Process a synthetic property batch into an in-memory fixture.

    One invalid row is quarantined without aborting valid rows. Reprocessing the
    same batch against the same orchestrator returns replay receipts and does not
    duplicate fixture rows.
    """
    _validate_batch(batch)
    runtime = orchestrator or SyntheticSynergyOrchestrator()
    batch_id = str(batch["batch_id"])
    source_profile = str(batch["source_profile"])
    default_rights = str(batch["rights_status"])
    correlation_id = "SYN-CORR-" + sha256(batch_id.encode("utf-8")).hexdigest()[:20].upper()

    row_receipts: list[dict[str, Any]] = []
    seen_external_codes: set[str] = set()

    for index, record_value in enumerate(batch["records"], start=1):
        if not isinstance(record_value, Mapping):
            row_receipts.append(
                _row_receipt(
                    batch_id=batch_id,
                    source_row=index,
                    status="quarantined",
                    reason="record_must_be_object",
                )
            )
            continue

        source_row = record_value.get("source_row", index)
        row = record_value.get("row")
        if not isinstance(row, Mapping):
            row_receipts.append(
                _row_receipt(
                    batch_id=batch_id,
                    source_row=source_row,
                    status="quarantined",
                    reason="row_must_be_object",
                )
            )
            continue

        external_code = str(row.get("CODI") or "").strip().casefold()
        if external_code and external_code in seen_external_codes:
            row_receipts.append(
                _row_receipt(
                    batch_id=batch_id,
                    source_row=source_row,
                    status="quarantined",
                    reason="duplicate_external_code_in_batch",
                )
            )
            continue
        if external_code:
            seen_external_codes.add(external_code)

        rights_status = str(record_value.get("rights_status", default_rights))
        payload = {
            "synthetic": True,
            "source_profile": source_profile,
            "source_row": source_row,
            "rights_status": rights_status,
            "row": dict(row),
        }
        row_digest = canonical_digest(payload)
        event = build_synthetic_event(
            "realestate.property_case.created",
            entity_type="property",
            entity_id=str(row.get("CODI") or f"SYN-ROW-{source_row}"),
            payload=payload,
            correlation_id=correlation_id,
            idempotency_key=(
                f"SYN-{batch_id}-{source_row}-{row_digest[-16:]}"
            ),
        )
        event_receipt = runtime.process(event, payload)
        row_receipts.append(
            _row_receipt(
                batch_id=batch_id,
                source_row=source_row,
                status=str(event_receipt["status"]),
                reason=event_receipt.get("reason"),
                event_receipt=event_receipt,
            )
        )

    counts = {
        status: sum(1 for receipt in row_receipts if receipt["status"] == status)
        for status in ("processed", "replayed", "quarantined")
    }
    summary = {
        "batch_id": batch_id,
        "batch_digest": canonical_digest(batch),
        "correlation_id": correlation_id,
        "records_received": len(batch["records"]),
        "counts": counts,
        "fixture_sheet_counts": {
            sheet: len(rows)
            for sheet, rows in sorted(runtime.fixture.rows.items())
        },
        "real_writes_permitted": False,
        "external_communication_permitted": False,
        "transaction_action_permitted": False,
    }
    result = {
        "schema_version": 1,
        "summary": summary,
        "row_receipts": row_receipts,
        "fixture": runtime.fixture,
    }
    result["result_digest"] = canonical_digest(
        {
            "summary": summary,
            "row_receipts": row_receipts,
        }
    )
    return result


def validate_fixture_contract(
    fixture: SyntheticFixture,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    sheets = contract.get("sheets", {})
    unknown_sheets: list[str] = []
    unknown_fields: dict[str, list[str]] = {}

    for sheet, rows in sorted(fixture.rows.items()):
        if sheet not in sheets:
            unknown_sheets.append(sheet)
            continue
        allowed = set(sheets[sheet])
        extras = sorted(
            {
                field
                for row in rows
                for field in row
                if field not in allowed
            }
        )
        if extras:
            unknown_fields[sheet] = extras

    return {
        "valid": not unknown_sheets and not unknown_fields,
        "unknown_sheets": unknown_sheets,
        "unknown_fields": unknown_fields,
    }


def _csv_bytes(rows: list[dict[str, Any]]) -> tuple[bytes, list[str]]:
    headers = sorted({field for row in rows for field in row})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=headers,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in headers})
    return stream.getvalue().encode("utf-8"), headers


def export_fixture_bundle(
    fixture: SyntheticFixture,
    *,
    batch_result: Mapping[str, Any],
    destination: str | Path,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Export a deterministic local ZIP containing one CSV per fixture sheet."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    files: dict[str, bytes] = {}
    headers_by_sheet: dict[str, list[str]] = {}
    for sheet, rows in sorted(fixture.rows.items()):
        body, headers = _csv_bytes(rows)
        safe_name = sheet.replace("/", "-")
        files[f"sheets/{safe_name}.csv"] = body
        headers_by_sheet[sheet] = headers

    contract_result = (
        validate_fixture_contract(fixture, contract)
        if contract is not None
        else None
    )
    file_digests = {
        name: "sha256:" + sha256(body).hexdigest()
        for name, body in sorted(files.items())
    }
    manifest = {
        "schema_version": 1,
        "bundle_type": "synthetic_crm_csv_workbook",
        "batch_id": batch_result["summary"]["batch_id"],
        "batch_result_digest": batch_result["result_digest"],
        "sheet_counts": {
            sheet: len(rows)
            for sheet, rows in sorted(fixture.rows.items())
        },
        "headers": headers_by_sheet,
        "file_digests": file_digests,
        "contract_validation": contract_result,
        "synthetic_only": True,
        "real_writes_permitted": False,
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    files["manifest.json"] = manifest_bytes

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)

    bundle_bytes = path.read_bytes()
    return {
        "path": str(path),
        "bundle_digest": "sha256:" + sha256(bundle_bytes).hexdigest(),
        "files": sorted(files),
        "manifest": manifest,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
    }
