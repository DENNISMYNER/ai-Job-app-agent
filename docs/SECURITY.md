# Security

## Threat model
Single user, local machine. Threats: malicious job ads/web pages/emails (prompt injection), other websites attacking the local API (CSRF, DNS rebinding), malicious uploads, secrets leaking to disk/logs, and the agent itself acting without consent.

| Threat | Control |
|---|---|
| Prompt injection in job text/emails | Untrusted-data delimiting + injection scan + deterministic decisions; LLM output never triggers actions |
| Agent submits without consent | Server-side single-use approval + `confirm=true` + UI confirmation dialog; auto-submit opt-in only |
| CAPTCHA/MFA bypass | Never attempted; agent pauses (`intervention_required`) |
| Fabricated qualifications | Fact guard rejects unsupported skills/numbers/years in CVs and letters |
| Guessing sensitive answers | Classified `needs_user`, never auto-answered |
| CSRF / DNS rebinding | `LocalOnlyGuard`: Host allow-list, Origin check on state-changing requests; CORS restricted; binds 127.0.0.1 |
| SSRF via job URLs | Private/loopback/link-local blocked, redirects re-validated, scheme limited to http(s) |
| Malicious uploads | Extension allow-list + magic-byte check + size limit; safe filenames; `resolve_inside` prevents path traversal |
| Credential storage | Email settings encrypted with Fernet; key in `data/secret.key` (or `JOBAGENT_SECRET_KEY`); never returned by the API |
| Secrets in logs | JSON logger redacts emails and phone numbers; request bodies are not logged |
| Data lifetime | Export, retention setting, and *Delete all* (type DELETE) |
| Browser session theft | Persistent profile lives in `data/browser_profile` — treat `data/` as sensitive |
| Headers / XSS | Security headers; React escapes output; no `dangerouslySetInnerHTML` |

## Email
IMAP is opened read-only (`BODY.PEEK`, so mail is not marked read). SMTP sends only an approved draft. Use an **app password**, not your main password.

## Operating guidance
- Do not expose port 8000 to a network. Docker publishes to `127.0.0.1` only.
- Do not commit `.env` or `data/` (both in `.gitignore`; the ZIP excludes them).
- Back up `data/secret.key` together with the DB, or encrypted email settings become unreadable.
- There is no login: anyone with access to your OS account can use the app. Use disk encryption.

## Known limitations
No multi-user auth by design; no third-party security audit; Docker and PostgreSQL paths were not exercised in the build environment.
