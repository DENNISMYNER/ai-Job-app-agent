# Browser Automation

## Process
1. **Prepare** opens the job URL in a persistent, **headed** Chromium profile (`data/browser_profile`), so sign-ins persist and you can intervene.
2. **Detect** (`detector.py`): injected JS inventories visible form controls (label, type, required, options) and tags each with `data-ja-id`; site-agnostic.
3. **Map** (`mapper.py`): each field → a `FieldPlan` (fill from profile, upload CV/letter, answer from Q&A engine, or `ask_user`). Sensitive questions are always `ask_user`.
4. **Fill** (`filler.py`): fills field by field, verifies the value stuck, advances multi-page forms by "Next/Continue" (never "Submit"), and produces a **fill report**.
5. **Review**: the report shows every field and its source. Nothing is submitted.
6. **Submit** (`runner.submit_application`): only with `approved_at` + `confirm=true`; re-detects and re-validates required fields; clicks submit once; success only if a confirmation is detected.

## Pauses for a human
CAPTCHA, bot checks, login walls and MFA → status `intervention_required`. The agent never solves or bypasses them. Complete the step in the open browser window, then use **Rescan**.

## Duplicate protection
Before creating an application: normalised company+position hash and canonical URL are checked; duplicates return 409.

## Auto-submit (optional, off by default)
Enable in Automation Settings: `auto_submit_enabled` plus `require_approval=false`. Without the opt-in, `require_approval:false` is coerced back to `true`. Even then submission only happens at the explicit Submit step; scheduled tasks never apply.

## Politeness and safety
`robots.txt` is honoured for discovery, per-host throttling, private/loopback addresses blocked (SSRF), redirects re-validated. Check each site's terms before automating.

## Testing
Tests run real Chromium against a **local mock job site** (`backend/tests/mocksite.py`); they never touch real sites and never submit real applications. Headless mode (`JOBAGENT_BROWSER_HEADLESS=true`) is used in CI/Docker, where CAPTCHA pauses cannot be resolved interactively.
