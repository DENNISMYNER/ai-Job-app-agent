# Local-First AI Job Application Agent

A privacy-first assistant that finds jobs, scores them against **your real profile**, tailors your CV and cover letters, fills application forms in a real browser, and tracks everything — while **you stay in control of every submission**.

- Runs entirely on your computer. No paid AI, no cloud, no API keys: language models come from [Ollama](https://ollama.com) (open-source).
- Works without Ollama too: matching, tracking, templates and form filling are deterministic; only wording and embeddings degrade.
- Backend: Python FastAPI + SQLAlchemy + Alembic (SQLite, PostgreSQL-ready). Frontend: React + TypeScript + Vite + Tailwind. Browser automation: Playwright.

## Safety rules the code enforces
| Rule | Where enforced |
|---|---|
| Never invent skills/employment/qualifications | Fact guard in `documents/cv.py`, `documents/letters.py` (rejects unsupported skills/numbers/years, falls back to a template) |
| Never click final submit without your approval | `automation/runner.py::submit_application` requires `approved_at` **and** `confirm=true`; the UI needs a confirmation dialog; approval is single-use |
| Never bypass CAPTCHA / MFA / bot checks | Detector reports `intervention_required`; the agent pauses for you |
| Never guess sensitive/legal/eligibility/demographic answers | `applications/answers.py` classifies these as `needs_user` |
| Job ads are untrusted (prompt injection) | `security/untrusted.py` delimits and scans all web text; scores are deterministic, the LLM only words explanations |
| Email credentials encrypted; sending needs approval | Fernet in `security/crypto.py`; drafts must be approved before SMTP send |
| Auto-submit off by default | Needs an explicit opt-in in Automation Settings; never runs from scheduled tasks |

## Quick start
**Windows** (details in [docs/INSTALLATION.md](docs/INSTALLATION.md)):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
start-windows.bat
```
**Linux / macOS**
```bash
bash scripts/install.sh
bash scripts/start.sh        # http://127.0.0.1:8000
```
**Docker (optional):** `docker compose up --build`

## Documentation
| Doc | Purpose |
|---|---|
| [PROJECT_BLUEPRINT](docs/PROJECT_BLUEPRINT.md) | Requirements, stack decisions, diagrams |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Modules, layers, data flow |
| [DATABASE_DESIGN](docs/DATABASE_DESIGN.md) | ER diagram and tables |
| [API_DOCUMENTATION](docs/API_DOCUMENTATION.md) | REST endpoints |
| [AI_AGENT_WORKFLOW](docs/AI_AGENT_WORKFLOW.md) | Matching, generation, Q&A pipeline |
| [BROWSER_AUTOMATION](docs/BROWSER_AUTOMATION.md) | Form detection/filling/submission |
| [SECURITY](docs/SECURITY.md) | Threat model and controls |
| [INSTALLATION](docs/INSTALLATION.md) | Setup per OS |
| [DEVELOPMENT_GUIDE](docs/DEVELOPMENT_GUIDE.md) | Contributing, conventions |
| [TESTING_GUIDE](docs/TESTING_GUIDE.md) | Running and writing tests |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Common problems |

## Honest status and limitations
- Verified by automated tests: backend (92 pytest tests, incl. real Chromium against a **local mock job site**), frontend (35 Vitest tests), UI end-to-end (3 Playwright tests).
- **Not verified in the build environment:** a real Ollama model (AI paths are tested against a mocked Ollama), real job sites (none were contacted), real IMAP/SMTP servers (tested with fakes), Docker builds, and the Windows scripts. Expect to adjust for site-specific forms.
- Application forms vary enormously; the filler is site-agnostic and conservative. Fields it cannot map confidently are left for you.
- Check each site's terms of service before automating. You are responsible for what you submit.
