#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/synergy-poc"
BWS_ENV="/home/aswin/.config/aios/env"
TARGET="${APP_DIR}/.env.production"
DOMAIN="${1:-}"

if [ -z "${DOMAIN}" ]; then
  echo "Usage: $0 <domain>" >&2
  exit 2
fi
if ! [[ "${DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || [[ "${DOMAIN}" == .* ]] || [[ "${DOMAIN}" == *. ]]; then
  echo "Domain must be a DNS hostname without a scheme or path." >&2
  exit 2
fi
if [ -e "${TARGET}" ]; then
  echo "Refusing to overwrite ${TARGET}. Move it aside deliberately before regenerating." >&2
  exit 1
fi
if [ ! -r "${BWS_ENV}" ]; then
  echo "Cannot read ${BWS_ENV}. Run this script as the aswin user." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "${BWS_ENV}"
set +a

OPENROUTER_API_KEY="$(
  bws secret list --output json \
    | jq -er '[.[] | select((.key | ascii_downcase) == "openrouter api key")] | if length == 1 then .[0].value else error("Expected exactly one Openrouter API Key") end'
)"
AUTH_SECRET="$(openssl rand -hex 32)"

umask 077
{
  printf 'APP_DOMAIN=%s\n' "${DOMAIN}"
  printf 'APP_VERSION=main\n'
  printf 'OPENROUTER_API_KEY=%s\n' "${OPENROUTER_API_KEY}"
  printf 'OPENROUTER_MODEL=openai/gpt-5.6-luna\n'
  printf 'AUTH_SECRET=%s\n' "${AUTH_SECRET}"
  printf 'AUTH_TOKEN_TTL_HOURS=12\n'
  printf 'AUTH_COOKIE_SECURE=true\n'
  printf 'EXCEL_PATH=/app/input/learning.xlsx\n'
  printf 'HEADCOUNT_EXCEL_PATH=/app/input/headcount.xlsx\n'
  printf 'DATABASE_PATH=/app/data/learning_chat.db\n'
  printf 'EXPORTS_PATH=/app/data/exports\n'
} > "${TARGET}"
chmod 600 "${TARGET}"

echo "Created ${TARGET} with mode 0600. Secret values were not printed."
