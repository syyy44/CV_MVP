#!/usr/bin/env bash
# Start FastAPI + Vite dev server together. Usage: run_stack.sh [replay|live]
set -euo pipefail

MODE="${1:-replay}"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-5173}"
export DEMO_MODE="$MODE"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"

require_free_port() {
  local port=$1
  local owner
  owner=$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1 " pid=" $2}' || true)
  if [ -n "$owner" ]; then
    echo "[run_stack] port :${port} is already in use by ${owner}." >&2
    echo "[run_stack] Run 'make restart' to stop the old stack, or set API_PORT/UI_PORT." >&2
    exit 1
  fi
}

if [ ! -x "$PY" ]; then
  echo "Missing .venv - run 'make install' first." >&2
  exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "Missing frontend deps - running 'make ui-install'..." >&2
  (cd frontend && npm install)
fi

require_free_port "$API_PORT"
require_free_port "$UI_PORT"

echo "[run_stack] DEMO_MODE=$MODE API_PORT=$API_PORT UI_PORT=$UI_PORT"
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

# Give the API a moment to bind before the UI starts proxying to it.
sleep 2
echo "[run_stack] UI dev server: http://localhost:${UI_PORT}"
API_BASE_URL="${API_BASE_URL:-http://localhost:${API_PORT}}" \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port "$UI_PORT" --strictPort
