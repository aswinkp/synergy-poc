#!/usr/bin/env bash
set -euo pipefail

cd /opt/synergy-poc
docker compose --env-file .env.production -f compose.production.yml exec app python -m backend.users "$@"
