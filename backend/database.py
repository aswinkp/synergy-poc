from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from openpyxl import load_workbook

from .config import DATABASE_PATH
from .schema import COLUMNS


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _fingerprint(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    return hashlib.sha256(raw).hexdigest()


def initialize_database(workbook_path: Path) -> dict[str, Any]:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                visualization TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
            """
        )
        fingerprint = _fingerprint(workbook_path)
        stored = db.execute("SELECT value FROM app_meta WHERE key = 'workbook_fingerprint'").fetchone()
        has_records = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learning_records'"
        ).fetchone()
        if stored and stored["value"] == fingerprint and has_records:
            count = db.execute("SELECT COUNT(*) AS count FROM learning_records").fetchone()["count"]
            return {"records": count, "refreshed": False}

    count = _import_workbook(workbook_path, fingerprint)
    return {"records": count, "refreshed": True}


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    return value


def _import_workbook(path: Path, fingerprint: str) -> int:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows: list[tuple[Any, ...]] = []
    for raw in sheet.iter_rows(min_row=5, values_only=True):
        if not any(value is not None and str(value).strip() for value in raw):
            continue
        values = tuple(_clean_value(value) for value in raw[: len(COLUMNS)])
        rows.append(values)

    column_sql = ",\n".join(f'"{name}" {sql_type}' for name, _, sql_type in COLUMNS)
    names = ", ".join(f'"{name}"' for name, _, _ in COLUMNS)
    placeholders = ", ".join("?" for _ in COLUMNS)

    with connect() as db:
        db.execute("DROP TABLE IF EXISTS learning_records_next")
        db.execute(f"CREATE TABLE learning_records_next (row_id INTEGER PRIMARY KEY, {column_sql})")
        db.executemany(
            f"INSERT INTO learning_records_next ({names}) VALUES ({placeholders})",
            rows,
        )
        db.execute("DROP TABLE IF EXISTS learning_records")
        db.execute("ALTER TABLE learning_records_next RENAME TO learning_records")
        for column in ("employee_id", "status", "course_name", "company", "business_unit", "learning_category"):
            db.execute(f'CREATE INDEX IF NOT EXISTS idx_learning_{column} ON learning_records("{column}")')
        db.execute(
            "INSERT INTO app_meta(key, value) VALUES('workbook_fingerprint', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (fingerprint,),
        )
        db.execute(
            "INSERT INTO app_meta(key, value) VALUES('workbook_name', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (path.name,),
        )
    return len(rows)


def rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [{key: row[key] for key in row.keys()} for row in rows]


def load_visualization(value: str | None) -> dict[str, Any] | None:
    return json.loads(value) if value else None
