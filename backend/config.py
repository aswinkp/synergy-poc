from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def find_workbook() -> Path:
    configured = os.getenv("EXCEL_PATH")
    if configured:
        return _resolve_path(configured, ROOT)
    workbooks = sorted(ROOT.glob("*.xlsx"))
    if not workbooks:
        raise FileNotFoundError("Place an .xlsx workbook in the project folder or set EXCEL_PATH.")
    return workbooks[0]


DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH"), ROOT / "data" / "learning_chat.db")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-5.6-luna")
