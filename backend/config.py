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
    workbooks = [path for path in sorted(ROOT.glob("*.xlsx")) if "headcount" not in path.name.casefold()]
    if not workbooks:
        raise FileNotFoundError("Set EXCEL_PATH or place the learning-report .xlsx workbook in the project folder.")
    return workbooks[0]


def find_headcount_workbook() -> Path | None:
    configured = os.getenv("HEADCOUNT_EXCEL_PATH")
    if configured:
        return _resolve_path(configured, ROOT)
    workbooks = [path for path in sorted(ROOT.glob("*.xlsx")) if "headcount" in path.name.casefold()]
    return workbooks[0] if workbooks else None


DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH"), ROOT / "data" / "learning_chat.db")
EXPORTS_PATH = _resolve_path(os.getenv("EXPORTS_PATH"), ROOT / "data" / "exports")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-5.6-luna")
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_TOKEN_TTL_HOURS = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").casefold() in {"1", "true", "yes", "on"}
