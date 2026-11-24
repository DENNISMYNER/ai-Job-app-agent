# Windows installer (PowerShell). Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ is required (https://www.python.org/downloads/ - tick 'Add to PATH')" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ is required (https://nodejs.org)" }
python -m venv backend\.venv
& backend\.venv\Scripts\pip install -r backend\requirements.txt
& backend\.venv\Scripts\python -m playwright install chromium
Push-Location frontend; npm install; npm run build; Pop-Location
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama pull qwen3:4b; ollama pull nomic-embed-text }
else { Write-Host "Ollama not found. Install from https://ollama.com for AI features (the app still works without it)." }
Write-Host "Done. Start with: start-windows.bat"
