@echo off
REM Starts the Job Application Agent and opens the browser. Run scripts\install.ps1 first.
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
  echo Not installed yet. Run: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  pause & exit /b 1
)
start "" http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
