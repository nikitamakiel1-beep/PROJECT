#!/usr/bin/env python3
"""Windows-only header-aware writer for Maumer_Capital-Oportunidades_USANDO.

Usage:
    python scripts/windows_usando_excel_adapter.py PLAN.json --execute

The adapter locates the CODI header in the first configured rows, updates the
matching project row or the first empty row, sets #Pre-analisis!B3, forces a full
Excel recalculation and saves. It never downloads or uploads files.
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


def find_header_row(sheet: Any, key_header: str, max_rows: int) -> int:
    for row in range(1, max_rows + 1):
        for column in range(1, min(int(sheet.UsedRange.Columns.Count), 300) + 1):
            value = sheet.Cells(row, column).Value
            if str(value or "").strip() == key_header:
                return row
    raise RuntimeError(f"header {key_header!r} not found")


def build_header_map(sheet: Any, header_row: int) -> dict[str, int]:
    width = min(int(sheet.UsedRange.Columns.Count), 500)
    result: dict[str, int] = {}
    for column in range(1, width + 1):
        value = str(sheet.Cells(header_row, column).Value or "").strip()
        if value:
            result[value] = column
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
    workbook = None
    try:
        workbook = excel.Workbooks.Open(str(workbook_path))
        sheet = workbook.Worksheets(plan["sheet"])
        header_row = find_header_row(sheet, plan["key_header"], int(plan["header_search_rows"]))
        header_map = build_header_map(sheet, header_row)
        if plan["key_header"] not in header_map:
            raise RuntimeError("CODI header missing after header discovery")
        target_row = find_target_row(
            sheet,
            header_row,
            header_map[plan["key_header"]],
            plan["project_code"],
        )
        missing_headers: list[str] = []
        for header, value in plan["field_values"].items():
            column = header_map.get(header)
            if column is None:
                missing_headers.append(header)
                continue
            sheet.Cells(target_row, column).Value = value
        if missing_headers:
            raise RuntimeError(f"USANDO headers not found: {missing_headers}")
        sheet.Range(plan["selected_project_cell"]).Value = plan["project_code"]
        excel.CalculateFullRebuild()
        workbook.Save()
        workbook.Close(SaveChanges=True)
        workbook = None
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        excel.Quit()

    receipt = {
        "project_code": plan["project_code"],
        "workbook_path": str(workbook_path),
        "before_sha256": before,
        "after_sha256": file_sha256(workbook_path),
        "full_recalculation_executed": True,
        "selected_project_cell": f"{plan['sheet']}!{plan['selected_project_cell']}",
        "network_access": False,
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = load_plan(Path(args.plan))
    if not args.execute:
        print(json.dumps({"valid": True, "execute": False, "plan_digest": plan["plan_digest"]}, indent=2))
        return 0
    print(json.dumps(execute(plan), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
