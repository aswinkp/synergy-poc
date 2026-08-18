from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .config import EXPORTS_PATH

SUPPORTED_EXPORTS = {"csv", "xlsx"}


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _safe_cell(value: Any) -> Any:
    """Prevent spreadsheet software from treating source text as a formula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _safe_name(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", title.strip()).strip("-").lower()
    return cleaned[:60] or "synergy-export"


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        if columns:
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _safe_cell(row.get(key)) for key in columns})


def _write_xlsx(path: Path, rows: list[dict[str, Any]], columns: list[str], title: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (_safe_name(title).replace("-", " ").title() or "Export")[:31]

    if columns:
        sheet.append(columns)
        header_fill = PatternFill("solid", fgColor="173245")
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(vertical="center")

        for row in rows:
            sheet.append([_safe_cell(row.get(key)) for key in columns])

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(columns, start=1):
            longest = max(
                len(str(column)),
                *(len(str(_safe_cell(row.get(column)) or "")) for row in rows),
            )
            sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 12), 42)

    workbook.save(path)
    workbook.close()


def create_export(rows: list[dict[str, Any]], title: str, export_format: str) -> dict[str, Any]:
    if export_format not in SUPPORTED_EXPORTS:
        raise ValueError(f"Unsupported export format: {export_format}")

    EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
    export_id = str(uuid.uuid4())
    path = EXPORTS_PATH / f"{export_id}.{export_format}"
    columns = _columns(rows)
    if export_format == "csv":
        _write_csv(path, rows, columns)
    else:
        _write_xlsx(path, rows, columns, title)

    display_name = f"{_safe_name(title)}.{export_format}"
    return {
        "id": export_id,
        "format": export_format,
        "filename": display_name,
        "url": f"/api/exports/{export_id}",
        "row_count": len(rows),
        "size_bytes": path.stat().st_size,
        "title": title,
    }


def attachment_path(attachment: dict[str, Any]) -> Path | None:
    try:
        export_id = str(uuid.UUID(str(attachment["id"])))
        export_format = str(attachment["format"])
    except (KeyError, TypeError, ValueError):
        return None
    if export_format not in SUPPORTED_EXPORTS:
        return None
    return EXPORTS_PATH / f"{export_id}.{export_format}"
