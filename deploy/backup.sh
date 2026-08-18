#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/synergy-poc"
BACKUP_DIR="${APP_DIR}/data/backups"
COMPOSE=(docker compose --env-file .env.production -f compose.production.yml)

cd "${APP_DIR}"
mkdir -p "${BACKUP_DIR}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="learning_chat-${timestamp}.db"

if "${COMPOSE[@]}" ps --services --status running app | grep -qx 'app'; then
  PYTHON=("${COMPOSE[@]}" exec -T app python)
  SOURCE="/app/data/learning_chat.db"
  DESTINATION="/app/data/backups/${filename}"
else
  PYTHON=(python3)
  SOURCE="${APP_DIR}/data/learning_chat.db"
  DESTINATION="${BACKUP_DIR}/${filename}"
fi

"${PYTHON[@]}" - "${SOURCE}" "${DESTINATION}" <<'PY'
import sqlite3
import sys
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
if not source.is_file():
    raise SystemExit(f"Database not found: {source}")
destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as backup_db:
    source_db.backup(backup_db)
print(destination.name)
PY

find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'learning_chat-*.db' -mtime +14 -delete
echo "Database backup completed: ${BACKUP_DIR}/${filename}"
