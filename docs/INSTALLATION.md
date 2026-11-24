# Installation

## Prerequisites
- Python 3.11+ (3.12/3.13 tested: 3.13 in the build environment), Node.js 20+, Git (optional)
- [Ollama](https://ollama.com) for AI features (optional but recommended). ~3–4 GB disk/RAM for `qwen3:4b`.

## Windows 10/11
1. Install Python from python.org (**tick "Add python.exe to PATH"**), Node.js LTS, and Ollama for Windows.
2. Unzip `AI-Job-Application-Agent.zip`, open PowerShell in the folder:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
   This creates `backend\.venv`, installs dependencies, downloads Chromium for Playwright, builds the UI, copies `.env.example` to `.env`, and pulls the models if Ollama is installed.
3. Start: double-click `start-windows.bat` (opens http://127.0.0.1:8000).
Manual equivalent:
```powershell
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
backend\.venv\Scripts\python -m playwright install chromium
cd frontend; npm install; npm run build; cd ..
ollama pull qwen3:4b; ollama pull nomic-embed-text
cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8000
```

## Linux / macOS
```bash
bash scripts/install.sh
bash scripts/start.sh            # http://127.0.0.1:8000
```
On Linux, Chromium may need system libraries: `backend/.venv/bin/python -m playwright install-deps chromium`.

## Development mode (hot reload)
```bash
bash scripts/dev.sh              # API :8000 (reload) + UI http://localhost:5173
```

## Docker (optional)
```bash
docker compose up --build        # http://127.0.0.1:8000
```
Ollama stays on the host. The container runs Chromium **headless**, so CAPTCHA/login pauses cannot be solved there — use the local install for real applications. *Not built in the authoring environment; report issues.*

## Verify
```bash
curl http://127.0.0.1:8000/api/health        # {"status":"ok"}
```
Open **AI Settings** to check Ollama and model status. The app works without Ollama (reduced AI features).

## Configuration
Copy `.env.example` → `.env`; every variable is prefixed `JOBAGENT_`. Data lives in `data/` (DB, key, browser profile), `documents/`, `logs/`.

## PostgreSQL (optional)
`pip install "psycopg[binary]"` and set `JOBAGENT_DATABASE_URL`. Untested in this build.
