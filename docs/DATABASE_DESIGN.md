# Database Design
SQLite by default (`data/jobagent.db`); schema is managed by Alembic (`backend/migrations`, revision `0001_initial_schema`) and applied automatically at startup. A deterministic naming convention and `render_as_batch` keep migrations portable to PostgreSQL.

```mermaid
erDiagram
  profiles ||--o{ education : has
  profiles ||--o{ employment : has
  profiles ||--o{ skills : has
  profiles ||--o{ certifications : has
  profiles ||--o{ languages : has
  job_sources ||--o{ job_listings : yields
  job_listings ||--o{ job_requirements : has
  job_listings ||--o| job_matches : scored_as
  job_listings ||--o{ job_applications : applied_via
  job_applications ||--o{ application_events : logs
  job_applications ||--o{ interviews : has
  job_applications ||--o{ recruiter_contacts : has
  job_applications }o--o| generated_cvs : uses
  job_applications }o--o| cover_letters : uses
  job_applications ||--o{ email_drafts : related
  profiles { int id PK  string full_name  string email  json verified_facts }
  job_listings { int id PK  string title  string company  string canonical_url  bool dismissed }
  job_matches { int id PK  int score  text explanation }
  job_applications { int id PK  string status  string dedupe_key  datetime approved_at  datetime applied_at }
  application_answers { int id PK  text question  text answer  bool approved }
```

## Tables (23)
profiles, education, employment, skills, certifications, languages · job_sources, job_listings, job_requirements, job_matches · job_applications, application_events, application_answers, interviews, recruiter_contacts · documents, generated_cvs, cover_letters · email_drafts, notifications · automation_schedules, agent_activity_logs, user_settings.

## Notable constraints
- `job_applications.dedupe_key` (normalised company+position hash) and canonical URL prevent duplicate applications.
- `profiles.verified_facts` (JSON) holds user-confirmed answers (e.g. work authorization) that the Q&A engine may reuse; nothing else is treated as a verified fact.
- `user_settings` is a key/value JSON store (`ai`, `automation`, `system`, `email*`). Email credentials are stored **encrypted**.
- Deleting data: *Delete all* (type `DELETE`) removes personal tables and files; retention removes old logs/read notifications/dismissed jobs without applications.

## PostgreSQL
`pip install "psycopg[binary]"`, then `JOBAGENT_DATABASE_URL=postgresql+psycopg://user:pass@host/db`. Migrations run on startup. *Not tested against PostgreSQL in this build* — only SQLite was exercised.
