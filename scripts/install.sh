#!/usr/bin/env bash
# Linux / macOS installer. Run from the project root: bash scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3 >/dev/null || { echo "Python 3.11+ is required"; exit 1; }
command -v node >/dev/null || { echo "Node.js 20+ is required"; exit 1; }
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -m playwright install chromium
(cd frontend && npm install && npm run build)
[ -f .env ] || cp .env.example .env
if command -v ollama >/dev/null; then
  ollama pull qwen3:4b || true
  ollama pull nomic-embed-text || true
else
  echo "Ollama not found: install it from https://ollama.com for AI features (the app works without it, with reduced features)."
fi
echo "Done. Start with: bash scripts/start.sh"
