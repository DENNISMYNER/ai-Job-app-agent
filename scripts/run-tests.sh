#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/python -m pytest -q)
(cd frontend && npm test && npm run build)
echo "Optional browser e2e: cd frontend && npx playwright install chromium && npm run e2e"
