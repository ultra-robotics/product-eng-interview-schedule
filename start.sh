#!/usr/bin/env bash
# start.sh — build and/or run the app
#
# Usage:
#   ./start.sh          # dev: Vite dev server + FastAPI with --reload (default)
#   ./start.sh --prod   # prod: build frontend, run backend serving static files

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$REPO_ROOT/frontend"
BACKEND="$REPO_ROOT/backend"
MODE="dev"

for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod" ;;
    *) echo "Unknown argument: $arg"; echo "Usage: $0 [--prod]"; exit 1 ;;
  esac
done

# ── resolve python interpreter ──────────────────────────────────────────────

if command -v uv &>/dev/null; then
  PYTHON="uv run python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
else
  echo "Error: no Python interpreter found. Install Python 3.12+ or uv." >&2
  exit 1
fi

# ── install backend deps ────────────────────────────────────────────────────

cd "$BACKEND"
if command -v uv &>/dev/null; then
  echo "[backend] uv sync"
  uv sync
elif [ -f requirements.txt ]; then
  echo "[backend] pip install -r requirements.txt"
  pip install -r requirements.txt
fi

# ── seed the SQLite database (first run only) ───────────────────────────────
# Storage is a local SQLite file (backend/schedule.db) — no DB server to run.
# Tables auto-create on first use; here we load example schedule data for
# today + tomorrow once so the app has something to show.

cd "$BACKEND"
if [ ! -f schedule.db ]; then
  echo "[db] seeding schedule.db with example data"
  $PYTHON seed_data.py || echo "[db] seeding skipped (non-fatal)"
fi

# ── install frontend deps ───────────────────────────────────────────────────

cd "$FRONTEND"
if [ ! -d node_modules ] || [ package.json -nt node_modules ]; then
  echo "[frontend] npm install"
  npm install
fi

# ── prod: build then serve ──────────────────────────────────────────────────

if [ "$MODE" = "prod" ]; then
  echo "[frontend] building..."
  npm run build
  echo "[backend] starting (serves dist/)"
  cd "$BACKEND"
  exec $PYTHON main.py
fi

# ── dev: run both servers in parallel ──────────────────────────────────────

cleanup() {
  echo ""
  echo "shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM

echo "[backend] starting on :8000"
cd "$BACKEND"
$PYTHON main.py &
BACKEND_PID=$!

echo "[frontend] starting Vite dev server"
cd "$FRONTEND"
npm run dev &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
