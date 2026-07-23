"""Local synthetic fixture reconciliation, mutation planning and rollback verification."""
from __future__ import annotations

import copy
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
import zipfile

from .synergy import SyntheticFixture, canonical_digest


class SyntheticReconciliationError(ValueError):
    """Raised when a synthetic snapshot, diff or mutation plan is invalid."""


ID_FIELDS = {
    "Properties": "Property ID",
    "Property Scenarios": "Scenario ID",
    "Investor Mandates": "Mandate ID",
    "Property Matches": "Match ID",
    "Viewings & Offers": "Event ID",
    "Due Diligence": "Check ID",
    "Transactions": "Transaction ID",
    "Tenancies": "Tenancy ID",
    "RE Import Staging": "Import ID",
    "Property Sources": "Source ID",
    "Partners & Captors": "Partner ID",
    "Visits": "Visit ID",
    "Evidence & Media": "Evidence ID",
    "Renovation Estimates": "Estimate ID",
    "Reports & Approvals": "Report ID",
    "Fee Arrangements": "Fee Arrangement ID",
    "Synergy Event Log": "Event ID",
    "Source Registry": "Source ID",
}


def _row_id(sheet: str, row: Mapping[str, Any]) -> str:
    preferred = ID_FIELDS.get(sheet)
    if preferred and row.get(preferred) not in (None, ""):
        return str(row[preferred])
    candidates = [
        key for key, value in row.items()
        if str(key).endswith(" ID") and value not in (None, "")
    ]
    if len(candidates) == 1:
        return str(row[candidates[0]])
    raise SyntheticReconciliationError(
        f"cannot resolve one stable ID for sheet {sheet!r}: {sorted(candidates)}"
    )


def _index_rows(sheet: str, rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        stable_id = _row_id(sheet, row)
        if stable_id in indexed:
            raise SyntheticReconciliationError(
                f"duplicate stable ID {stable_id!r} in sheet {sheet!r}"
            )
        indexed[stable_id] = row
    return indexed


def _quarantine_row(receipt: Mapping[str, Any]) -> dict[str, Any]:
    batch_id = str(receipt.get("batch_id") or "UNKNOWN-BATCH")
    source_row = str(receipt.get("source_row") or "UNKNOWN-ROW")
    quarantine_id = "QRT-SYN-" + sha256(
        f"{batch_id}|{source_row}".encode("utf-8")
    ).hexdigest()[:20].upper()
    return {
        "Quarantine ID": quarantine_id,
        "Batch ID": batch_id,
        "Source Row": source_row,
        "Status": str(receipt.get("status") or "quarantined"),
        "Reason": receipt.get("reason"),
        "Event ID": receipt.get("event_id"),
        "Plan Digest": receipt.get("plan_digest"),
        "Receipt Digest": receipt.get("receipt_digest"),
        "Details": copy.deepcopy(receipt.get("details", [])),
        "Real Writes Permitted": False,
        "External Communication Permitted": False,
        "Transaction Action Permitted": False,
    }


def _snapshot_body(
    sheets: Mapping[str, Iterable[Mapping[str, Any]]],
    quarantines: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    canonical_sheets: dict[str, list[dict[str, Any]]] = {}
    for sheet in sorted(sheets):
        indexed = _index_rows(sheet, sheets[sheet])
        canonical_sheets[sheet] = [indexed[key] for key in sorted(indexed)]

    quarantine_index = _index_rows("Quarantines", quarantines)
    canonical_quarantines = [
        quarantine_index[key] for key in sorted(quarantine_index)
    ]
    return {
        "schema_version": 1,
        "snapshot_type": "synthetic_crm_fixture",
        "sheets": canonical_sheets,
        "quarantines": canonical_quarantines,
        "synthetic_only": True,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
        "transaction_action_permitted": False,
    }


def build_snapshot(
    fixture: SyntheticFixture | Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    row_receipts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    sheets = fixture.rows if isinstance(fixture, SyntheticFixture) else fixture
    quarantines = [
        _quarantine_row(receipt)
        for receipt in row_receipts
        if receipt.get("status") == "quarantined"
    ]
    body = _snapshot_body(sheets, quarantines)
    return {**body, "snapshot_digest": canonical_digest(body)}


def snapshot_from_batch_result(batch_result: Mapping[str, Any]) -> dict[str, Any]:
    return build_snapshot(
        batch_result["fixture"],
        row_receipts=batch_result.get("row_receipts", []),
    )


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema_version") != 1:
        raise SyntheticReconciliationError("unsupported snapshot schema version")
    if snapshot.get("snapshot_type") != "synthetic_crm_fixture":
        raise SyntheticReconciliationError("unsupported snapshot type")
    if snapshot.get("synthetic_only") is not True:
        raise SyntheticReconciliationError("synthetic snapshot required")
    for flag in (
        "real_writes_permitted",
        "external_communication_permitted",
        "transaction_action_permitted",
    ):
        if snapshot.get(flag) is not False:
            raise SyntheticReconciliationError(f"forbidden snapshot flag: {flag}")
    body = _snapshot_body(
        snapshot.get("sheets", {}),
        snapshot.get("quarantines", []),
    )
    expected = canonical_digest(body)
    if snapshot.get("snapshot_digest") != expected:
        raise SyntheticReconciliationError("snapshot digest mismatch")


def _field_changes(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        {"field": field, "before": before.get(field), "after": after.get(field)}
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    ]


def _compare_collection(
    collection: str,
    before_rows: Iterable[Mapping[str, Any]],
    after_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    before = _index_rows(collection, before_rows)
    after = _index_rows(collection, after_rows)
    before_ids = set(before)
    after_ids = set(after)
    added = [
        {"row_id": row_id, "after": after[row_id]}
        for row_id in sorted(after_ids - before_ids)
    ]
    removed = [
        {"row_id": row_id, "before": before[row_id]}
        for row_id in sorted(before_ids - after_ids)
    ]
    changed = []
    unchanged = []
    for row_id in sorted(before_ids & after_ids):
        if before[row_id] == after[row_id]:
            unchanged.append(row_id)
        else:
            changed.append({
                "row_id": row_id,
                "before": before[row_id],
                "after": after[row_id],
                "field_changes": _field_changes(before[row_id], after[row_id]),
            })
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
    }


def compare_snapshots(
    before_snapshot: Mapping[str, Any],
    after_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    validate_snapshot(before_snapshot)
    validate_snapshot(after_snapshot)
    sheet_names = sorted(
        set(before_snapshot.get("sheets", {}))
        | set(after_snapshot.get("sheets", {}))
    )
    sheets = {
        sheet: _compare_collection(
            sheet,
            before_snapshot.get("sheets", {}).get(sheet, []),
            after_snapshot.get("sheets", {}).get(sheet, []),
        )
        for sheet in sheet_names
    }
    quarantines = _compare_collection(
        "Quarantines",
        before_snapshot.get("quarantines", []),
        after_snapshot.get("quarantines", []),
    )
    totals = {
        key: sum(item["counts"][key] for item in sheets.values())
        for key in ("added", "removed", "changed", "unchanged")
    }
    totals.update({
        "quarantines_introduced": quarantines["counts"]["added"],
        "quarantines_resolved": quarantines["counts"]["removed"],
        "quarantines_changed": quarantines["counts"]["changed"],
    })
    body = {
        "schema_version": 1,
        "diff_type": "synthetic_fixture_reconciliation",
        "before_snapshot_digest": before_snapshot["snapshot_digest"],
        "after_snapshot_digest": after_snapshot["snapshot_digest"],
        "sheets": sheets,
        "quarantines": quarantines,
        "totals": totals,
        "synthetic_only": True,
        "real_writes_permitted": False,
    }
    return {**body, "diff_digest": canonical_digest(body)}


def _operation(
    *,
    collection_type: str,
    collection_name: str,
    action: str,
    row_id: str,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, Any]:
    body = {
        "collection_type": collection_type,
        "collection_name": collection_name,
        "action": action,
        "row_id": row_id,
        "before": copy.deepcopy(before),
        "after": copy.deepcopy(after),
    }
    return {**body, "operation_digest": canonical_digest(body)}


def build_mutation_plan(diff: Mapping[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    for sheet, changes in sorted(diff.get("sheets", {}).items()):
        for item in changes["removed"]:
            operations.append(_operation(
                collection_type="sheet",
                collection_name=sheet,
                action="remove",
                row_id=item["row_id"],
                before=item["before"],
                after=None,
            ))
        for item in changes["changed"]:
            operations.append(_operation(
                collection_type="sheet",
                collection_name=sheet,
                action="update",
                row_id=item["row_id"],
                before=item["before"],
                after=item["after"],
            ))
        for item in changes["added"]:
            operations.append(_operation(
                collection_type="sheet",
                collection_name=sheet,
                action="add",
                row_id=item["row_id"],
                before=None,
                after=item["after"],
            ))

    quarantine = diff.get("quarantines", {})
    for item in quarantine.get("removed", []):
        operations.append(_operation(
            collection_type="quarantine",
            collection_name="Quarantines",
            action="remove",
            row_id=item["row_id"],
            before=item["before"],
            after=None,
        ))
    for item in quarantine.get("changed", []):
        operations.append(_operation(
            collection_type="quarantine",
            collection_name="Quarantines",
            action="update",
            row_id=item["row_id"],
            before=item["before"],
            after=item["after"],
        ))
    for item in quarantine.get("added", []):
        operations.append(_operation(
            collection_type="quarantine",
            collection_name="Quarantines",
            action="add",
            row_id=item["row_id"],
            before=None,
            after=item["after"],
        ))

    operations.sort(key=lambda item: (
        item["collection_type"],
        item["collection_name"],
        item["row_id"],
        item["action"],
    ))
    body = {
        "schema_version": 1,
        "plan_type": "synthetic_fixture_mutation",
        "source_snapshot_digest": diff["before_snapshot_digest"],
        "target_snapshot_digest": diff["after_snapshot_digest"],
        "diff_digest": diff["diff_digest"],
        "operations": operations,
        "synthetic_only": True,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
        "transaction_action_permitted": False,
    }
    return {**body, "plan_digest": canonical_digest(body)}


def invert_mutation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    reverse_actions = {"add": "remove", "remove": "add", "update": "update"}
    operations = [
        _operation(
            collection_type=item["collection_type"],
            collection_name=item["collection_name"],
            action=reverse_actions[item["action"]],
            row_id=item["row_id"],
            before=item.get("after"),
            after=item.get("before"),
        )
        for item in reversed(plan.get("operations", []))
    ]
    body = {
        "schema_version": 1,
        "plan_type": "synthetic_fixture_rollback",
        "source_snapshot_digest": plan["target_snapshot_digest"],
        "target_snapshot_digest": plan["source_snapshot_digest"],
        "diff_digest": plan["diff_digest"],
        "forward_plan_digest": plan["plan_digest"],
        "operations": operations,
        "synthetic_only": True,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
        "transaction_action_permitted": False,
    }
    return {**body, "plan_digest": canonical_digest(body)}


def _apply_operation(
    indexed: dict[str, dict[str, Any]],
    operation: Mapping[str, Any],
) -> None:
    row_id = str(operation["row_id"])
    action = str(operation["action"])
    before = operation.get("before")
    after = operation.get("after")
    current = indexed.get(row_id)
    if action == "add":
        if current is not None or after is None:
            raise SyntheticReconciliationError(f"invalid add for {row_id}")
        indexed[row_id] = copy.deepcopy(dict(after))
    elif action == "remove":
        if current is None or before is None or current != before:
            raise SyntheticReconciliationError(f"remove precondition failed for {row_id}")
        del indexed[row_id]
    elif action == "update":
        if current is None or before is None or after is None or current != before:
            raise SyntheticReconciliationError(f"update precondition failed for {row_id}")
        indexed[row_id] = copy.deepcopy(dict(after))
    else:
        raise SyntheticReconciliationError(f"unsupported mutation action: {action}")


def apply_mutation_plan(
    snapshot: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    validate_snapshot(snapshot)
    if snapshot["snapshot_digest"] != plan.get("source_snapshot_digest"):
        raise SyntheticReconciliationError("mutation source digest mismatch")
    if plan.get("synthetic_only") is not True or plan.get("real_writes_permitted") is not False:
        raise SyntheticReconciliationError("unsafe mutation plan")

    sheets = {
        sheet: _index_rows(sheet, rows)
        for sheet, rows in snapshot.get("sheets", {}).items()
    }
    quarantines = _index_rows("Quarantines", snapshot.get("quarantines", []))

    for operation in plan.get("operations", []):
        body = {key: operation.get(key) for key in (
            "collection_type", "collection_name", "action", "row_id", "before", "after"
        )}
        if operation.get("operation_digest") != canonical_digest(body):
            raise SyntheticReconciliationError("operation digest mismatch")
        if operation["collection_type"] == "sheet":
            sheet = str(operation["collection_name"])
            target = sheets.setdefault(sheet, {})
            _apply_operation(target, operation)
        elif operation["collection_type"] == "quarantine":
            _apply_operation(quarantines, operation)
        else:
            raise SyntheticReconciliationError("unsupported mutation collection")

    body = _snapshot_body(
        {
            sheet: [rows[key] for key in sorted(rows)]
            for sheet, rows in sorted(sheets.items())
            if rows
        },
        [quarantines[key] for key in sorted(quarantines)],
    )
    result = {**body, "snapshot_digest": canonical_digest(body)}
    if result["snapshot_digest"] != plan.get("target_snapshot_digest"):
        raise SyntheticReconciliationError("mutation target digest mismatch")
    return result


def verify_rollback(
    before_snapshot: Mapping[str, Any],
    forward_plan: Mapping[str, Any],
) -> dict[str, Any]:
    target = apply_mutation_plan(before_snapshot, forward_plan)
    rollback_plan = invert_mutation_plan(forward_plan)
    restored = apply_mutation_plan(target, rollback_plan)
    verified = restored["snapshot_digest"] == before_snapshot["snapshot_digest"]
    receipt = {
        "schema_version": 1,
        "forward_plan_digest": forward_plan["plan_digest"],
        "rollback_plan_digest": rollback_plan["plan_digest"],
        "original_snapshot_digest": before_snapshot["snapshot_digest"],
        "target_snapshot_digest": target["snapshot_digest"],
        "restored_snapshot_digest": restored["snapshot_digest"],
        "rollback_verified": verified,
        "synthetic_only": True,
        "real_writes_permitted": False,
    }
    return {**receipt, "receipt_digest": canonical_digest(receipt)}


def render_diff_markdown(diff: Mapping[str, Any]) -> str:
    lines = [
        "# Synthetic Fixture Reconciliation",
        "",
        f"- Before: `{diff['before_snapshot_digest']}`",
        f"- After: `{diff['after_snapshot_digest']}`",
        f"- Diff: `{diff['diff_digest']}`",
        "",
        "## Totals",
        "",
    ]
    for key, value in diff["totals"].items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    for sheet, changes in sorted(diff.get("sheets", {}).items()):
        if not any(changes["counts"][key] for key in ("added", "removed", "changed")):
            continue
        lines.extend(["", f"## {sheet}", ""])
        for label in ("added", "removed", "changed"):
            ids = [item["row_id"] for item in changes[label]]
            if ids:
                lines.append(f"- {label.title()}: {', '.join(ids)}")
    quarantine = diff.get("quarantines", {})
    if any(quarantine.get("counts", {}).get(key, 0) for key in ("added", "removed", "changed")):
        lines.extend(["", "## Quarantines", ""])
        for label in ("added", "removed", "changed"):
            ids = [item["row_id"] for item in quarantine.get(label, [])]
            if ids:
                lines.append(f"- {label.title()}: {', '.join(ids)}")
    lines.extend([
        "",
        "Real writes, external communication and transaction actions remain disabled.",
        "",
    ])
    return "\n".join(lines)


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    row_list = [dict(row) for row in rows]
    headers = sorted({field for row in row_list for field in row})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in row_list:
        writer.writerow({
            field: json.dumps(row.get(field), ensure_ascii=False, sort_keys=True)
            if isinstance(row.get(field), (dict, list))
            else row.get(field, "")
            for field in headers
        })
    return stream.getvalue().encode("utf-8")


def export_reconciliation_bundle(
    snapshot: Mapping[str, Any],
    *,
    destination: str | Path,
    diff: Mapping[str, Any] | None = None,
    forward_plan: Mapping[str, Any] | None = None,
    rollback_plan: Mapping[str, Any] | None = None,
    rollback_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validate_snapshot(snapshot)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "snapshot.json": json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
        "quarantines.csv": _csv_bytes(snapshot.get("quarantines", [])),
    }
    for sheet, rows in sorted(snapshot.get("sheets", {}).items()):
        files[f"sheets/{sheet.replace('/', '-')}.csv"] = _csv_bytes(rows)
    optional_json = {
        "reconciliation/diff.json": diff,
        "reconciliation/forward-plan.json": forward_plan,
        "reconciliation/rollback-plan.json": rollback_plan,
        "reconciliation/rollback-receipt.json": rollback_receipt,
    }
    for name, payload in optional_json.items():
        if payload is not None:
            files[name] = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    if diff is not None:
        files["reconciliation/diff.md"] = render_diff_markdown(diff).encode("utf-8")

    file_digests = {
        name: "sha256:" + sha256(body).hexdigest()
        for name, body in sorted(files.items())
    }
    manifest = {
        "schema_version": 1,
        "bundle_type": "synthetic_crm_reconciliation_bundle",
        "snapshot_digest": snapshot["snapshot_digest"],
        "file_digests": file_digests,
        "synthetic_only": True,
        "real_writes_permitted": False,
        "external_communication_permitted": False,
    }
    files["manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)
    bundle = path.read_bytes()
    return {
        "path": str(path),
        "bundle_digest": "sha256:" + sha256(bundle).hexdigest(),
        "files": sorted(files),
        "manifest": manifest,
        "synthetic_only": True,
        "real_writes_permitted": False,
    }


def load_reconciliation_bundle(path: str | Path) -> dict[str, Any]:
    with zipfile.ZipFile(Path(path), "r") as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "snapshot.json" not in names:
            raise SyntheticReconciliationError("bundle manifest or snapshot missing")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("bundle_type") != "synthetic_crm_reconciliation_bundle":
            raise SyntheticReconciliationError("unsupported bundle type")
        if manifest.get("synthetic_only") is not True or manifest.get("real_writes_permitted") is not False:
            raise SyntheticReconciliationError("unsafe bundle manifest")
        for name, expected in manifest.get("file_digests", {}).items():
            if name not in names:
                raise SyntheticReconciliationError(f"bundle file missing: {name}")
            actual = "sha256:" + sha256(archive.read(name)).hexdigest()
            if actual != expected:
                raise SyntheticReconciliationError(f"bundle file digest mismatch: {name}")
        snapshot = json.loads(archive.read("snapshot.json").decode("utf-8"))
    validate_snapshot(snapshot)
    if snapshot["snapshot_digest"] != manifest.get("snapshot_digest"):
        raise SyntheticReconciliationError("bundle snapshot digest mismatch")
    return snapshot


def compare_reconciliation_bundles(
    before_path: str | Path,
    after_path: str | Path,
) -> dict[str, Any]:
    return compare_snapshots(
        load_reconciliation_bundle(before_path),
        load_reconciliation_bundle(after_path),
    )
