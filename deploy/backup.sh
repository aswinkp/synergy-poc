#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/synergy-poc"
BACKUP_DIR="${APP_DIR}/data/backups"
COMPOSE=(docker compose --env-file .env.production -f compose.production.yml)

cd "${APP_DIR}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="learning_chat-${timestamp}.db"

if "${COMPOSE[@]}" ps --services --status running app | grep -qx 'app'; then
  PYTHON=("${COMPOSE[@]}" exec -T app python)
else
  PYTHON=("${COMPOSE[@]}" run --rm --no-deps app python)
fi
SOURCE="/app/data/learning_chat.db"
DESTINATION="/app/data/backups/${filename}"

"${PYTHON[@]}" - "${SOURCE}" "${DESTINATION}" <<'PY'
import sqlite3
import sys
import time
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
if not source.is_file():
    raise SystemExit(f"Database not found: {source}")
destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as backup_db:
    source_db.backup(backup_db)
cutoff = time.time() - (14 * 24 * 60 * 60)
for candidate in destination.parent.glob("learning_chat-*.db"):
    if candidate.stat().st_mtime < cutoff:
        candidate.unlink()
print(destination.name)
PY

echo "Database backup completed: ${BACKUP_DIR}/${filename}"
