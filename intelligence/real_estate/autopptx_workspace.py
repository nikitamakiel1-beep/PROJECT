"""Project workspace and fail-closed USANDO workbook plans."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping


class AutoPPTXPipelineError(ValueError):
    pass


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def validate_project_code(project_code: str) -> str:
    code = str(project_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,12}_[A-Z0-9]{2,16}_[A-Z0-9]{2,20}\d{2}", code):
        raise AutoPPTXPipelineError(
            "project code must follow PROVINCE_MUNICIPALITY_NEIGHBOURHOOD##"
        )
    return code


def create_project_workspace(root: str | Path, project_code: str) -> dict[str, str]:
    root_path = Path(root)
    if not root_path.is_absolute():
        raise AutoPPTXPipelineError("workspace root must be absolute")
    code = validate_project_code(project_code)
    project = root_path / code
    folders = {
        "project": project,
        "source": project / "01 Source",
        "property_data": project / "02 Property Data",
        "cadastral_legal": project / "03 Catastro and Legal",
        "financial_inputs": project / "04 Financial Inputs",
        "comparables": project / "05 Comparables",
        "visit_photos": project / "06 Visit and Photos",
        "underwriting": project / "07 Underwriting",
        "report_output": project / "08 Report Output",
        "approvals": project / "09 Approvals",
        "autopptx_piso": project / "AutoPPTX" / "Piso" / code,
        "autopptx_zona": project / "AutoPPTX" / "Zona" / code,
        "autopptx_proyectos": project / "AutoPPTX" / "Proyectos" / code,
        "original_media": project / "06 Visit and Photos" / "Originals",
        "authorised_clean_media": project / "06 Visit and Photos" / "Authorised Clean",
    }
    for path in folders.values():
        path.mkdir(parents=True, exist_ok=True)
    return {name: str(path) for name, path in folders.items()}


def build_usando_update_plan(
    *,
    project_code: str,
    workbook_path: str | Path,
    field_values: Mapping[str, Any],
    source_profile: str,
    explicit_transfer_tax_rate: float,
    transfer_tax_workbook_header: str | None = None,
) -> dict[str, Any]:
    code = validate_project_code(project_code)
    workbook = Path(workbook_path)
    if not workbook.is_absolute() or not workbook.is_file():
        raise AutoPPTXPipelineError("USANDO workbook must be an existing absolute file")
    if workbook.suffix.casefold() not in {".xlsx", ".xlsm"}:
        raise AutoPPTXPipelineError("USANDO workbook must be XLSX or XLSM")
    transfer_tax_rate = float(explicit_transfer_tax_rate)
    if not (0 <= transfer_tax_rate <= 0.20):
        raise AutoPPTXPipelineError("explicit transfer-tax rate is invalid")
    if "CODI" in field_values and str(field_values["CODI"]).strip().upper() != code:
        raise AutoPPTXPipelineError("CODI value conflicts with project code")
    if transfer_tax_workbook_header is not None and not transfer_tax_workbook_header.strip():
        raise AutoPPTXPipelineError("transfer-tax workbook header cannot be blank")

    values = dict(field_values)
    values["CODI"] = code
    values["Transfer Tax Rate"] = transfer_tax_rate
    header = transfer_tax_workbook_header.strip() if transfer_tax_workbook_header else None
    metadata_only_fields: list[str] = []
    if header:
        if header != "Transfer Tax Rate":
            values[header] = transfer_tax_rate
            metadata_only_fields.append("Transfer Tax Rate")
    else:
        metadata_only_fields.append("Transfer Tax Rate")
    plan = {
        "schema_version": 2,
        "plan_type": "usando_excel_com_update",
        "project_code": code,
        "workbook_path": str(workbook),
        "workbook_name_expected": "Maumer_Capital-Oportunidades_USANDO",
        "sheet": "#Pre-analisis",
        "header_search_rows": 30,
        "key_header": "CODI",
        "selected_project_cell": "B3",
        "field_values": values,
        "metadata_only_fields": metadata_only_fields,
        "reviewed_assumptions": {
            "transfer_tax_rate": transfer_tax_rate,
        },
        "transfer_tax_workbook_header": header,
        "manual_transfer_tax_binding_required": header is None,
        "source_profile": source_profile,
        "formula_recalculation": "CalculateFullRebuild",
        "save_required": True,
        "close_required": True,
        "manual_formula_review_required": True,
        "monthly_loan_convention_required": True,
        "stale_cached_values_permitted": False,
        "network_access_permitted": False,
    }
    plan["plan_digest"] = canonical_digest(plan)
    return plan
