#!/usr/bin/env python3
"""Windows-only header-aware writer for Maumer_Capital-Oportunidades_USANDO.

Usage:
    python scripts/windows_usando_excel_adapter.py PLAN.json
    python scripts/windows_usando_excel_adapter.py PLAN.json --execute

The adapter locates the CODI header, updates one project row, sets B3, forces a
full rebuild, saves, closes and returns an evidence receipt. It never downloads,
uploads or opens a network connection.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("plan_type") != "usando_excel_com_update":
        raise ValueError("invalid USANDO update plan")
    return plan


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    workbook_path = Path(str(plan.get("workbook_path") or ""))
    if not workbook_path.is_absolute():
        errors.append("workbook path is not absolute")
    elif not workbook_path.is_file():
        errors.append("workbook does not exist")
    elif workbook_path.suffix.casefold() not in {".xlsx", ".xlsm"}:
        errors.append("workbook is not XLSX or XLSM")
    if "USANDO" not in workbook_path.stem.upper():
        warnings.append("workbook filename does not contain USANDO")
    if plan.get("sheet") != "#Pre-analisis":
        errors.append("unexpected primary sheet")
    if plan.get("key_header") != "CODI":
        errors.append("unexpected key header")
    if plan.get("selected_project_cell") != "B3":
        errors.append("unexpected selected-project cell")
    if plan.get("formula_recalculation") != "CalculateFullRebuild":
        errors.append("full calculation rebuild is not configured")
    values = plan.get("field_values")
    if not isinstance(values, dict) or values.get("CODI") != plan.get("project_code"):
        errors.append("field values do not contain the bound project code")
    if plan.get("manual_transfer_tax_binding_required"):
        warnings.append(
            "transfer-tax rate is reviewed but not mapped to a confirmed workbook header"
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "plan_digest": plan.get("plan_digest"),
        "manual_transfer_tax_binding_required": bool(
            plan.get("manual_transfer_tax_binding_required")
        ),
    }


def find_header_row(sheet: Any, key_header: str, max_rows: int) -> int:
    width = min(int(sheet.UsedRange.Columns.Count), 300)
    for row in range(1, max_rows + 1):
        for column in range(1, width + 1):
            value = sheet.Cells(row, column).Value
            if str(value or "").strip() == key_header:
                return row
    raise RuntimeError(f"header {key_header!r} not found")


def build_header_map(sheet: Any, header_row: int) -> dict[str, int]:
    width = min(int(sheet.UsedRange.Columns.Count), 500)
    result: dict[str, int] = {}
    duplicates: set[str] = set()
    for column in range(1, width + 1):
        value = str(sheet.Cells(header_row, column).Value or "").strip()
        if not value:
            continue
        if value in result:
            duplicates.add(value)
        result[value] = column
    if duplicates:
        raise RuntimeError(f"duplicate USANDO headers: {sorted(duplicates)}")
    return result


def find_target_row(sheet: Any, header_row: int, key_column: int, code: str) -> int:
    last = max(int(sheet.UsedRange.Rows.Count), header_row + 1)
    first_empty = None
    for row in range(header_row + 1, last + 2):
        value = str(sheet.Cells(row, key_column).Value or "").strip()
        if value.casefold() == code.casefold():
            return row
        if not value and first_empty is None:
            first_empty = row
    return first_empty or last + 1


def execute(plan: dict[str, Any]) -> dict[str, Any]:
    validation = validate_plan(plan)
    if not validation["valid"]:
        raise RuntimeError(f"invalid USANDO plan: {validation['errors']}")
    if os.name != "nt":
        raise RuntimeError("this adapter requires Windows and Microsoft Excel")
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pywin32 is required") from exc

    workbook_path = Path(plan["workbook_path"])
    before = file_sha256(workbook_path)
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False
    workbook = None
    target_row = None
    written_headers: list[str] = []
    try:
        workbook = excel.Workbooks.Open(
            str(workbook_path),
            UpdateLinks=0,
            ReadOnly=False,
            IgnoreReadOnlyRecommended=True,
        )
        if bool(workbook.ReadOnly):
            raise RuntimeError("USANDO workbook opened read-only; close other copies")
        sheet = workbook.Worksheets(plan["sheet"])
        header_row = find_header_row(
            sheet,
            plan["key_header"],
            int(plan["header_search_rows"]),
        )
        header_map = build_header_map(sheet, header_row)
        if plan["key_header"] not in header_map:
            raise RuntimeError("CODI header missing after header discovery")
        target_row = find_target_row(
            sheet,
            header_row,
            header_map[plan["key_header"]],
            plan["project_code"],
        )
        missing_headers = sorted(
            header for header in plan["field_values"] if header not in header_map
        )
        if missing_headers:
            raise RuntimeError(f"USANDO headers not found: {missing_headers}")
        for header, value in plan["field_values"].items():
            sheet.Cells(target_row, header_map[header]).Value = value
            written_headers.append(header)
        sheet.Range(plan["selected_project_cell"]).Value = plan["project_code"]
        excel.CalculateFullRebuild()
        workbook.Save()
        workbook.Close(SaveChanges=True)
        workbook = None
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        excel.Quit()

    after = file_sha256(workbook_path)
    receipt = {
        "schema_version": 2,
        "project_code": plan["project_code"],
        "workbook_path": str(workbook_path),
        "plan_digest": plan["plan_digest"],
        "before_sha256": before,
        "after_sha256": after,
        "workbook_changed": before != after,
        "target_row": target_row,
        "written_headers": sorted(written_headers),
        "full_recalculation_executed": True,
        "selected_project_cell": f"{plan['sheet']}!{plan['selected_project_cell']}",
        "reviewed_assumptions": dict(plan.get("reviewed_assumptions") or {}),
        "manual_transfer_tax_binding_required": bool(
            plan.get("manual_transfer_tax_binding_required")
        ),
        "financial_review_ready": not bool(
            plan.get("manual_transfer_tax_binding_required")
        ),
        "network_access": False,
    }
    receipt["receipt_digest"] = "sha256:" + sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = load_plan(Path(args.plan))
    validation = validate_plan(plan)
    if not args.execute:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["valid"] else 1
    print(json.dumps(execute(plan), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
