#!/usr/bin/env bash
# Development: backend with reload (8000) + Vite dev server (5173)
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
BACK=$!; trap "kill $BACK" EXIT
cd frontend && npm run dev
