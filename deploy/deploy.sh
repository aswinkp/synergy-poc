#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/synergy-poc"
COMPOSE=(docker compose --env-file .env.production -f compose.production.yml)

cd "${APP_DIR}"
test -f .env.production
test -r input/learning.xlsx
test -r input/headcount.xlsx

if [ -f data/learning_chat.db ]; then
  ./deploy/backup.sh
fi

git pull --ff-only origin main
export APP_VERSION="$(git rev-parse --short HEAD)"
"${COMPOSE[@]}" build --pull
"${COMPOSE[@]}" up -d --remove-orphans
"${COMPOSE[@]}" exec -T app python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5).read()"
"${COMPOSE[@]}" ps

echo "Deployment complete for ${APP_VERSION}."
