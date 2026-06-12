#!/usr/bin/env bash
# Start FastAPI + Vite dev server together. Usage: run_stack.sh [replay|live]
set -euo pipefail

MODE="${1:-replay}"
export DEMO_MODE="$MODE"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Missing .venv - run 'make install' first." >&2
  exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "Missing frontend deps - running 'make ui-install'..." >&2
  (cd frontend && npm install)
fi

echo "[run_stack] DEMO_MODE=$MODE"
"$PY" -m uvicorn app.main:app --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

# Give the API a moment to bind before the UI starts proxying to it.
sleep 2
echo "[run_stack] UI dev server: http://localhost:5173"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}" npm --prefix frontend run dev
