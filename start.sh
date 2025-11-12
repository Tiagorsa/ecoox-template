#!/usr/bin/env bash
set -euo pipefail

# Opção: permitir configurar host/port por env
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "[INFO] Iniciando Template Sender API em ${HOST}:${PORT}"
echo "[INFO] BASE_URL=${BASE_URL:-unset}"
echo "[INFO] TEMPLATE_TOKEN set? $([ -n "${TEMPLATE_TOKEN:-}" ] && echo yes || echo no)"
echo "[INFO] APP_ROOT_PATH='${APP_ROOT_PATH:-}' (prefixo reverso)"

exec uvicorn main:app --host "$HOST" --port "$PORT"
