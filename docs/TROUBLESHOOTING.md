# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Ollama is not running" | Start it (`ollama serve` or the desktop app). Check `JOBAGENT_OLLAMA_BASE_URL`. AI Settings shows status. |
| "Model not found" | `ollama pull qwen3:4b` and `ollama pull nomic-embed-text` (or choose an installed model in AI Settings). |
| "AI features are turned off" | Enable in AI Settings. |
| UI shows "Cannot reach the local backend" | Backend not running or wrong port. Start `scripts/start.sh` / `start-windows.bat`. |
| 403 "forbidden_host / forbidden_origin" | Access via `127.0.0.1`/`localhost` and an allowed origin; add custom ports via `JOBAGENT_ALLOWED_ORIGINS` (JSON list). |
| Blank page at :8000 | Frontend not built: `cd frontend && npm install && npm run build`. |
| Playwright "Executable doesn't exist" | `python -m playwright install chromium` (inside the venv). Linux: `playwright install-deps chromium`. |
| Browser opens but fill stops ("intervention required") | CAPTCHA/login/MFA: complete it in the browser window, then Rescan. The agent will never bypass it. |
| Fields left empty / "needs your input" | Sensitive or unknown question: answer it in Application Assistant, approve the answer, rescan. |
| "You already have an application…" (409) | Duplicate protection; open the existing one in the Tracker. |
| Submit button disabled | Needs: fill report ready, no pending questions, approval given. |
| Email poll fails | Use an app password, IMAP enabled, correct host/port. |
| Email settings unreadable after restore | `data/secret.key` was not restored with the DB; re-enter the email settings. |
| `database is locked` | Close other processes using `data/jobagent.db`. |
| Port 8000 in use | `JOBAGENT_PORT=8001` and use `--port 8001` (add the origin if using Vite). |
| PowerShell blocks scripts | Use the `-ExecutionPolicy Bypass -File` form shown in INSTALLATION. |
| Slow AI responses | Use a smaller model (`qwen3:1.7b`, `llama3.2:3b`) or raise `JOBAGENT_AI_TIMEOUT_SECONDS`. |

Logs: `logs/`. Reset everything: System Settings → Delete all data, or delete `data/` while the app is stopped.
