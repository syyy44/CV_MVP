#!/usr/bin/env bash
# Stop FastAPI + Vite dev servers, then start them again.
# Usage: restart_stack.sh [replay|live]
set -euo pipefail

MODE="${1:-replay}"
export API_PORT="${API_PORT:-8000}"
export UI_PORT="${UI_PORT:-5173}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

stop_port() {
  local port=$1
  local pids
  pids=$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)
  if [ -z "$pids" ]; then
    return 0
  fi

  echo "[restart] stopping :${port} (pid: ${pids//$'\n'/ })"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.5

  pids=$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

echo "[restart] stopping existing stack..."
pkill -f "${ROOT}/scripts/run_stack.sh" 2>/dev/null || true
stop_port "$API_PORT"
stop_port "$UI_PORT"
sleep 0.5

echo "[restart] starting stack (mode=${MODE})..."
exec bash "${ROOT}/scripts/run_stack.sh" "$MODE"
