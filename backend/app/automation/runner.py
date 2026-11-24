"""Application runner: prepare/fill (never submits) and submit (approval-gated).

Workflow
--------
``prepare_form``  open URL -> detect -> map -> fill -> next page ... -> validate -> review report
``submit_application``  only after explicit user approval: re-validate, click submit, record result.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.automation import detector, filler, mapper
from app.automation.session import BrowserWorker, get_worker
from app.core.config import get_settings
from app.core.errors import ApprovalRequiredError, ConflictError, UserInterventionRequired
from app.documents.render import generated_file
from app.jobs.http import assert_public_url
from app.models import CoverLetter, GeneratedCV, JobApplication, JobListing, Profile
from app.services import settings_service as ss

log = logging.getLogger(__name__)
MAX_PAGES = 8
CONFIRM_RE = re.compile(r"(thank you for (applying|your application)|application (has been )?(received|submitted|sent)|successfully submitted|we('ve| have) received your application)", re.I)
ERROR_RE = re.compile(r"(please (correct|fix|complete)|required field|there (was|were) (an )?error|invalid)", re.I)


def _files(db: Session, app: JobApplication) -> dict[str, Path | None]:
    cv = db.get(GeneratedCV, app.cv_id) if app.cv_id else None
    letter = db.get(CoverLetter, app.cover_letter_id) if app.cover_letter_id else None
    return {
        "cv": generated_file(cv.pdf_path) if cv and cv.pdf_path else None,
        "letter": generated_file(letter.pdf_path) if letter and letter.pdf_path else None,
    }


def prepare_form(db: Session, app: JobApplication, p: Profile, job: JobListing | None, *, use_ai: bool = True, headless: bool | None = None) -> dict:
    """Open the application, fill everything it safely can, and return a review report.

    Never clicks the final submit button. Pauses (``intervention``) on CAPTCHA/MFA/login.
    """
    assert_public_url(app.job_url)
    files = _files(db, app)
    has_cv, has_letter = bool(files["cv"]), bool(files["letter"])
    cfg = ss.get_setting(db, "automation")
    headless = cfg.get("headless", False) if headless is None else headless

    # Plans need the DB session, which is not thread-safe -> gather plans on the worker via a callback
    # that only touches the DB from this (calling) thread is impossible, so we do detect -> plan -> fill
    # in small worker calls and keep DB work in this thread.
    worker = get_worker()
    pages_report: list[dict] = []

    def open_page(w: BrowserWorker):
        page = w.new_page(app.id, headless)
        page.goto(app.job_url, wait_until="domcontentloaded")
        page.wait_for_timeout(300)
        return detector.scan_page(page)

    scan = worker.call(open_page)

    def intervention(scan: detector.PageScan) -> dict | None:
        reason = scan.blocking
        if reason:
            return {"status": "intervention_required", "reason": reason, "pages": pages_report, "url": scan.url}
        return None

    if (r := intervention(scan)):
        return r

    # Landing page with just a description: follow the single 'Apply' entry point once.
    if not scan.fields and (entry := detector.find_apply_entry(scan)):
        def click_entry(w: BrowserWorker):
            page = w.page(app.id)
            page.locator(f'[data-ja-id="{entry["id"]}"]').click()
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(300)
            return detector.scan_page(page)

        scan = worker.call(click_entry)
        if (r := intervention(scan)):
            return r

    if not scan.fields:
        return {"status": "no_form_found", "reason": "No application form was detected. Use the browser window to navigate to the form, then press 'Re-scan', or apply manually.", "pages": pages_report, "url": scan.url}

    for page_no in range(1, MAX_PAGES + 1):
        plans = mapper.plan_page(scan.fields, p, db, job, has_cv=has_cv, has_letter=has_letter, use_ai=use_ai)
        results = worker.call(lambda w, plans=plans: filler.apply_plan(w.page(app.id), plans, files))
        pages_report.append({"page": page_no, "url": scan.url, "fields": results,
                             "has_submit": detector.find_submit_button(scan) is not None})
        nxt = detector.find_next_button(scan)
        if not nxt:
            break
        # Do not advance while required fields on this page still need the user.
        if any(f["status"] == "needs_user" and f["required"] and not f["filled"] for f in results):
            break

        def go_next(w: BrowserWorker):
            filler.advance(w.page(app.id))
            return detector.scan_page(w.page(app.id))

        scan = worker.call(go_next)
        if (r := intervention(scan)):
            return r | {"pages": pages_report}

    return summarise(pages_report, scan.url, worker, app.id)


def summarise(pages_report: list[dict], url: str, worker: BrowserWorker, app_id: int) -> dict:
    missing = worker.call(lambda w: filler.missing_required(w.page(app_id))) if worker.call(lambda w: w.page(app_id) is not None) else []
    needs_user = [f for pg in pages_report for f in pg["fields"] if f["status"] == "needs_user" and not f["filled"]]
    review = [f for pg in pages_report for f in pg["fields"] if f["status"] == "review" and f["filled"]]
    return {
        "status": "ready_for_review" if not missing and not [f for f in needs_user if f["required"]] else "needs_input",
        "url": url, "pages": pages_report, "missing_required": missing,
        "needs_user": [f["label"] for f in needs_user], "review": [f["label"] for f in review],
        "filled": sum(1 for pg in pages_report for f in pg["fields"] if f["filled"]),
    }


def rescan(db: Session, app: JobApplication, p: Profile, job: JobListing | None, *, use_ai: bool = True) -> dict:
    """After the user manually fixed things in the browser: fill remaining blanks and re-validate."""
    worker = get_worker()
    if not worker.call(lambda w: w.page(app.id) is not None):
        raise ConflictError("The browser window for this application is closed. Run 'Prepare application' again.")
    files = _files(db, app)
    scan = worker.call(lambda w: detector.scan_page(w.page(app.id)))
    if scan.blocking:
        return {"status": "intervention_required", "reason": scan.blocking, "pages": [], "url": scan.url}
    plans = mapper.plan_page(scan.fields, p, db, job, has_cv=bool(files["cv"]), has_letter=bool(files["letter"]), use_ai=use_ai)
    # Do not overwrite anything the user already typed.
    current = worker.call(lambda w: filler.read_values(w.page(app.id)))
    todo = [pl for pl in plans if not current.get(pl.field_id, {}).get("filled")]
    results = worker.call(lambda w: filler.apply_plan(w.page(app.id), todo, files))
    return summarise([{"page": 1, "url": scan.url, "fields": results, "has_submit": detector.find_submit_button(scan) is not None}], scan.url, worker, app.id)


def submit_application(db: Session, app: JobApplication) -> dict:
    """Click the final submit button. Requires prior explicit approval (checked by the caller AND here)."""
    if app.approved_at is None:
        raise ApprovalRequiredError("Final submission requires your explicit approval.")
    worker = get_worker()
    if not worker.call(lambda w: w.page(app.id) is not None):
        raise ConflictError("The browser window for this application is closed. Run 'Prepare application' again.")

    def do_submit(w: BrowserWorker):
        page = w.page(app.id)
        scan = detector.scan_page(page)
        if scan.blocking:
            return {"result": "incomplete", "reason": scan.blocking}
        missing = filler.missing_required(page)  # deterministic re-validation immediately before submit
        if missing:
            return {"result": "incomplete", "reason": "Required fields are empty: " + ", ".join(missing)}
        btn = detector.find_submit_button(scan)
        if not btn:
            return {"result": "incomplete", "reason": "No submit button was found on this page. Submit it yourself in the browser window."}
        page.locator(f'[data-ja-id="{btn["id"]}"]').click()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(600)
        text = page.evaluate("document.body.innerText || ''")
        if CONFIRM_RE.search(text):
            m = CONFIRM_RE.search(text)
            return {"result": "success", "confirmation": text.strip()[:400], "matched": m.group(0)}
        if ERROR_RE.search(text):
            return {"result": "failed", "reason": "The site reported a validation problem after submission."}
        after = detector.scan_page(page)
        if after.blocking:
            return {"result": "incomplete", "reason": after.blocking}
        return {"result": "unconfirmed", "reason": "Submitted, but no confirmation message was recognised. Check the browser window."}

    return worker.call(do_submit)


def close_browser_page(app_id: int) -> None:
    get_worker().call(lambda w: w.close_page(app_id))
