# Testing Guide

| Layer | Tool | Command | Count (at build) |
|---|---|---|---|
| Backend unit/API/integration | pytest | `cd backend && .venv/bin/python -m pytest -q` | 92 |
| Backend browser (real Chromium vs mock site) | pytest marker `browser` | included; deselect with `-m "not browser"` | included |
| Frontend components/pages | Vitest + Testing Library | `cd frontend && npm test` | 35 |
| UI end-to-end | Playwright | `cd frontend && npx playwright install chromium && npm run e2e` | 3 |
| Types / build | tsc, Vite | `npm run build` | — |

## Principles
- **No network, no real sites, no real submissions.** An autouse fixture makes Ollama connections fail unless a test supplies `httpx.MockTransport`. Browser tests use the local `mocksite.py` server.
- Safety rules have dedicated tests: submit blocked without approval, approval single-use, CAPTCHA pause, sensitive questions → `needs_user`, fact guard rejects invented skills, prompt-injection text does not alter scores, upload/path traversal rejection, host/origin guard.
- Frontend tests assert that no `/submit` request is made until the confirmation dialog is confirmed.

## E2E notes
The e2e config starts the real backend on port 8000 with a throw-away data directory (`/tmp/jobagent-e2e`), AI disabled and the scheduler off; it needs `frontend/dist` built. To reuse an installed Chromium: `E2E_CHROMIUM=/path/to/chrome npm run e2e`.

## What is not covered
Real Ollama models, real job sites, real IMAP/SMTP, Docker, PostgreSQL, Windows scripts. Test these manually with throw-away data.
