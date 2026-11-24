# Architecture

## Layering
```
React SPA ──> api/ (routers, validation) ──> services / domain packages ──> models (SQLAlchemy) ──> DB
                                               │
                                               ├─ ai/ (Ollama client, graceful fallback)
                                               ├─ automation/ (browser worker)
                                               └─ security/ (crypto, untrusted text, file + http guards)
```
Routers stay thin; business rules live in domain packages so they are testable without HTTP.

## Backend packages (`backend/app/`)
| Package | Responsibility |
|---|---|
| `core/` | Settings (`JOBAGENT_*` env), JSON logging with redaction, error types and handlers |
| `security/` | Fernet crypto, upload validation + path-traversal guard, untrusted-text handling, Host/Origin guard, SSRF-safe HTTP |
| `database/`, `models/` | Engine/session, 23 tables, migrations run at startup |
| `ai/ollama.py` | Local client; `AIUnavailableError` → callers fall back; saved AI settings applied via `configure_runtime` |
| `matching/` | Skill taxonomy, requirement extraction, score engine |
| `jobs/` | Source adapters, ingest, dedupe, queries |
| `documents/` | CV/letter generation, fact guards, PDF/DOCX rendering, CV parsing |
| `applications/` | Q&A engine, application service (create/prepare/approve/submit/dashboard) |
| `automation/` | `session` (worker thread), `detector`, `mapper`, `filler`, `runner` |
| `notifications/email.py` | IMAP poll, classifier, drafts, SMTP send |
| `tasks/scheduler.py` | APScheduler with DB-backed cron schedules; retention job |
| `services/` | Profile, settings, activity log, interview, retention |

## Key design decisions
1. **Local-only by default.** Binds `127.0.0.1`; a middleware rejects non-local `Host` headers (DNS rebinding) and cross-origin state-changing requests (CSRF); CORS limited to local origins.
2. **LLM never decides.** Match scores are deterministic (embeddings contribute 20% when available). LLM output is validated against profile facts before use.
3. **Approval is a state, not a flag in the UI.** `approved_at` is stored server-side, single-use, and re-checked at submit along with `confirm=true` and required-field validation.
4. **One browser thread.** Playwright's sync API is thread-bound; a worker thread owns the browser and requests are queued to it.
5. **Single-process serving.** If `frontend/dist` exists, FastAPI serves the SPA, so users run one command.
6. **Graceful degradation.** Ollama missing/disabled → template fallbacks and clear UI messages, never a crash.

## Frontend (`frontend/src/`)
`pages/` (12 routed pages, lazy loaded), `components/ui/` (Button, Form, Badge, Pagination, ConfirmDialog, Toast, States), `hooks/` (`useApi`, `useAction` = mutation + toast + cache invalidation), `services/api.ts` (typed fetch client with `ApiError`), `types/api.ts`.
