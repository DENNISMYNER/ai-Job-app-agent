# API Documentation
Base path `/api`. Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`. JSON in/out. Local origins only.

## Errors
`{"error": "<code>", "message": "<human text>", "detail": ...}` with status 400/403/404/409/422/503. Examples: `approval_required` (403), `conflict` (409, duplicate application), `ai_unavailable` (503), `validation_failed` (422).

## Endpoints
**System** — `GET /health` · `GET /ai/status` · `GET|PUT /settings/{ai|automation|system|...}` · `GET /data/export` · `POST /data/apply-retention` · `POST /data/delete-all {"confirm":"DELETE"}`

**Profile & documents** — `GET|PUT /profile` · `POST /import-cv` (PDF/DOCX upload, returns a draft for review; nothing is saved until you save the profile) · `GET /documents`, `POST /documents`, `GET /documents/{id}/download`, `DELETE /documents/{id}`

**Jobs** — `GET /jobs` (search, filters, sort, pagination) · `GET /jobs/recommended` · `GET /jobs/{id}` · `POST /jobs/discover` · `POST /jobs/import-url` · `POST /jobs/import-text` · `POST /jobs/{id}/match` · `POST /jobs/{id}/dismiss` · `POST /matching/run` · `GET|POST /job-sources`, `PATCH|DELETE /job-sources/{id}`

**Generation** — `GET|POST /cvs`, `GET|PUT|DELETE /cvs/{id}`, `GET /cvs/{id}/download/{pdf|docx}` · `GET|POST /cover-letters`, `POST /cover-letters/templates`, `PUT|DELETE /cover-letters/{id}`, `GET /cover-letters/{id}/download`

**Applications** — `GET|POST /applications` · `GET /applications/check-duplicate` · `GET|PATCH|DELETE /applications/{id}` · `POST /applications/{id}/prepare` (open browser, fill, stop before submit) · `/rescan` · `/approve` · `/submit {"confirm": true}` · `/close-browser` · `/follow-up-draft` · `/interview-prep` · `/interviews` · `/recruiters` · `GET /dashboard`

**Q&A** — `GET|POST /answers` · `POST /answers/ask` · `PATCH|DELETE /answers/{id}`

**Interviews / recruiters** — `GET /interviews`, `PATCH|DELETE /interviews/{id}`, `DELETE /recruiters/{id}`

**Email** — `GET|PUT|DELETE /email/config` · `POST /email/poll` · `GET /email/drafts` · `POST /email/suggest-reply` · `POST /email/drafts/{id}/approve` · `POST /email/drafts/{id}/send` (only after approval) · `DELETE /email/drafts/{id}`

**Automation** — `GET /automation/status` · `GET|POST /automation/schedules` · `PUT|DELETE /automation/schedules/{id}` · `POST /automation/schedules/{id}/{run|pause|resume}` · `POST /automation/pause-all|resume-all`

**Notifications** — `GET /notifications` · `POST /notifications/read-all` · `POST /notifications/{id}/read`

## Submission contract
`POST /applications/{id}/submit` succeeds only if: the application was approved (`approved_at`), the body has `confirm: true`, the form passes deterministic re-validation (required fields filled), and no CAPTCHA/MFA is pending. Result is one of `success`, `incomplete`, `failed`, `intervention_required`. A success is reported only when the site shows a confirmation. Approval is consumed by the attempt.
