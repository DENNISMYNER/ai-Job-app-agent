# Development Guide

## Layout
```
backend/   FastAPI app (app/), Alembic (migrations/), tests/
frontend/  Vite + React + TS (src/), Vitest tests beside code, e2e/ (Playwright)
docs/  scripts/  docker/  docker-compose.yml  start-windows.bat
```

## Setup
`bash scripts/install.sh`, then `bash scripts/dev.sh`. Vite proxies `/api` to 127.0.0.1:8000.

## Conventions
- Routers validate and delegate; rules live in domain packages. Raise `AppError` subclasses (`NotFoundError`, `ConflictError`, `ValidationFailed`, `ApprovalRequiredError`, …) — handlers shape the JSON.
- Anything touching AI must catch `AIUnavailableError` and fall back. Anything built from web text must pass through `security/untrusted`.
- **Never** add a code path that clicks submit outside `runner.submit_application`, or answers sensitive questions automatically. Tests guard these.
- Frontend: server state via TanStack Query; mutations via `useAction` (toast + invalidate); destructive/irreversible actions via `ConfirmDialog`; forms via React Hook Form + Zod.
- TypeScript strict; Python typed with `from __future__ import annotations`.

## Database changes
```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "describe change"
.venv/bin/alembic upgrade head
```
Review the generated migration (SQLite batch mode); migrations also run at app startup.

## Adding a job source
Add an adapter in `jobs/sources.py` returning normalised listings, register it in the source-type map, add a mocked-HTTP test in `tests/test_jobs_matching.py`.

## Commits
Small, conventional commits (`feat:`, `fix:`, `test:`, `docs:`). Run `bash scripts/run-tests.sh` first.

## Resuming work
Read `DEVELOPMENT_PROGRESS.md`, `IMPLEMENTATION_CHECKLIST.md`, `NEXT_STEPS.md`.
