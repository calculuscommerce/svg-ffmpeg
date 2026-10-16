#!/usr/bin/env bash
# Start backend (FastAPI :8010) and frontend (Vite :5173) for local development.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f backend/.env ]; then
  echo "backend/.env missing — copy backend/.env.example and fill in your keys"; exit 1
fi
if [ ! -d backend/.venv ]; then
  echo "Creating Python venv…"; (cd backend && uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r requirements.txt)
fi
[ -d node_modules ] || npm install
[ -d frontend/node_modules ] || (cd frontend && npm install)
npx playwright install chromium >/dev/null 2>&1 || true

trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload) &
(cd frontend && npm run dev) &
wait
