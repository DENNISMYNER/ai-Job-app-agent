"""Application lifecycle: duplicates, status/events, prepare, approve, submit."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApprovalRequiredError, ConflictError, NotFoundError, ValidationFailed
from app.jobs.http import canonical_url
from app.models import STATUSES, ApplicationEvent, CoverLetter, GeneratedCV, JobApplication, JobListing, JobMatch, Profile
from app.services import settings_service as ss
from app.services.activity import log_activity, notify

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def make_dedupe_key(company: str, position: str) -> str:
    return hashlib.sha256(f"{_norm(company)}|{_norm(position)}".encode()).hexdigest()


def find_duplicate(db: Session, company: str, position: str, url: str = "") -> JobApplication | None:
    app = db.scalar(select(JobApplication).where(JobApplication.dedupe_key == make_dedupe_key(company, position)))
    if app or not url:
        return app
    canon = canonical_url(url)
    for a in db.scalars(select(JobApplication)):
        if canonical_url(a.job_url) == canon:
            return a
    return None


def add_event(db: Session, app: JobApplication, type_: str, detail: str = "") -> None:
    db.add(ApplicationEvent(application_id=app.id, type=type_, detail=detail[:2000]))
    db.flush()


def create_application(db: Session, *, listing: JobListing | None = None, company: str = "", position: str = "", url: str = "", status: str = "discovered") -> JobApplication:
    if listing:
        company, position, url = listing.company, listing.title, listing.url
    if not (company and position and url):
        raise ValidationFailed("company, position and url are required.")
    if status not in STATUSES:
        raise ValidationFailed(f"status must be one of {STATUSES}")
    if (dup := find_duplicate(db, company, position, url)):
        raise ConflictError(
            f"You already have an application for '{dup.position}' at '{dup.company}' (status: {dup.status}).",
            detail={"existing_id": dup.id, "status": dup.status},
        )
    app = JobApplication(listing_id=listing.id if listing else None, company=company, position=position, job_url=url,
                         dedupe_key=make_dedupe_key(company, position), status=status)
    db.add(app)
    db.flush()
    add_event(db, app, "created", f"Status: {status}")
    return app


def get_application(db: Session, app_id: int) -> JobApplication:
    a = db.get(JobApplication, app_id)
    if not a:
        raise NotFoundError("Application not found")
    return a


def set_status(db: Session, app: JobApplication, status: str, detail: str = "") -> None:
    if status not in STATUSES:
        raise ValidationFailed(f"status must be one of {STATUSES}")
    if status == app.status:
        return
    old, app.status = app.status, status
    if status == "applied" and app.applied_at is None:
        app.applied_at = datetime.now(timezone.utc)
        if app.follow_up_date is None:
            app.follow_up_date = app.applied_at + timedelta(days=7)
    add_event(db, app, "status_changed", f"{old} -> {status}. {detail}".strip())


# ------------------------------------------------------------- preparation
def prepare(db: Session, app: JobApplication, p: Profile, *, use_ai: bool = True, headless: bool | None = None) -> dict:
    from app.automation import runner
    from app.documents import cv as cvmod
    from app.documents import letters

    job = db.get(JobListing, app.listing_id) if app.listing_id else None
    if app.status in {"applied", "interview", "assessment", "offer", "rejected", "withdrawn"}:
        raise ConflictError("This application is already past the preparation stage.")
    set_status(db, app, "preparing")
    app.approved_at = None
    if app.cv_id is None:
        app.cv_id = cvmod.generate_cv(db, p, job=job, use_ai=use_ai).id
    if app.cover_letter_id is None and job is not None:
        app.cover_letter_id = letters.generate_letter(db, p, job, use_ai=use_ai)[0].id
    db.flush()
    report = runner.prepare_form(db, app, p, job, use_ai=use_ai, headless=headless)
    return _record_report(db, app, report)


def rescan(db: Session, app: JobApplication, p: Profile, *, use_ai: bool = True) -> dict:
    from app.automation import runner

    job = db.get(JobListing, app.listing_id) if app.listing_id else None
    app.approved_at = None  # anything changed since approval invalidates it
    return _record_report(db, app, runner.rescan(db, app, p, job, use_ai=use_ai))


def _record_report(db: Session, app: JobApplication, report: dict) -> dict:
    app.fill_report = report
    st = report["status"]
    if st == "ready_for_review":
        set_status(db, app, "awaiting_approval", "Form filled; waiting for your review")
        notify(db, "approval", f"Ready for review: {app.position} @ {app.company}", "Open the Application Assistant to review and approve.", application_id=app.id)
    else:
        add_event(db, app, "fill_" + st, report.get("reason") or ", ".join(report.get("needs_user", [])))
    log_activity(db, "automation", "prepare", f"Application {app.id}: {st}")
    return report


# -------------------------------------------------------- approval / submit
def approve(db: Session, app: JobApplication) -> None:
    if app.status != "awaiting_approval":
        raise ConflictError("Only applications that are awaiting approval (form filled and validated) can be approved.")
    if app.fill_report.get("status") != "ready_for_review":
        raise ConflictError("The last form check found missing information. Fix it and re-scan first.")
    app.approved_at = datetime.now(timezone.utc)
    add_event(db, app, "approved_by_user", "User approved final submission")


def auto_submit_allowed(db: Session, app: JobApplication) -> bool:
    """Optional policy. Disabled by default; explicit approval is the default workflow."""
    cfg = ss.get_setting(db, "automation")
    if cfg.get("require_approval", True) or not cfg.get("auto_submit_enabled", False):
        return False
    m = db.scalar(select(JobMatch).where(JobMatch.listing_id == app.listing_id)) if app.listing_id else None
    if m is None or m.score < cfg.get("auto_submit_min_score", 85):
        return False
    since = datetime.now(timezone.utc) - timedelta(days=1)
    today = db.scalar(select(func.count()).select_from(ApplicationEvent).where(ApplicationEvent.type == "auto_approved_by_policy", ApplicationEvent.created_at >= since)) or 0
    return today < cfg.get("auto_submit_daily_limit", 5)


def submit(db: Session, app: JobApplication) -> dict:
    from app.automation import runner

    if app.status != "awaiting_approval":
        raise ConflictError("Application is not awaiting approval.")
    if app.approved_at is None:
        if auto_submit_allowed(db, app):
            app.approved_at = datetime.now(timezone.utc)
            add_event(db, app, "auto_approved_by_policy", "Automation policy allowed submission")
        else:
            raise ApprovalRequiredError("Final submission requires your explicit approval. Review the form, then approve.")
    result = runner.submit_application(db, app)
    app.approved_at = None  # approval is single-use
    outcome = result["result"]
    add_event(db, app, "submit_" + outcome, result.get("reason") or result.get("confirmation", "")[:200])
    if outcome == "success":
        app.submission_result, app.confirmation = "success", result.get("confirmation", "")
        set_status(db, app, "applied", "Submission confirmed by the site")
        runner.close_browser_page(app.id)
        notify(db, "info", f"Applied: {app.position} @ {app.company}", app.confirmation[:200], application_id=app.id)
    elif outcome == "failed":
        app.submission_result = "failed"
    else:  # incomplete / unconfirmed: keep the window open so the user can finish
        app.submission_result = "incomplete"
        if outcome == "unconfirmed":
            app.confirmation = "Submitted but unconfirmed - verify on the site."
    return result


def dashboard_stats(db: Session, profile_id: int | None) -> dict:
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    by_status = dict(db.execute(select(JobApplication.status, func.count()).group_by(JobApplication.status)).all())
    min_score = ss.get_setting(db, "matching")["min_apply_score"]
    now = datetime.now(timezone.utc)
    upcoming = db.scalars(
        select(JobApplication).where(JobApplication.follow_up_date.is_not(None), JobApplication.follow_up_date >= now - timedelta(days=1),
                                     JobApplication.status.in_(["applied", "interview", "assessment"]))
        .order_by(JobApplication.follow_up_date).limit(5)
    ).all()
    from app.models import AgentActivityLog

    recent = db.scalars(select(AgentActivityLog).order_by(AgentActivityLog.id.desc()).limit(8)).all()
    return {
        "discovered_jobs": count(JobListing),
        "matching_jobs": count(JobMatch, JobMatch.score >= min_score, *( [JobMatch.profile_id == profile_id] if profile_id else [])),
        "submitted": by_status.get("applied", 0) + by_status.get("interview", 0) + by_status.get("assessment", 0) + by_status.get("offer", 0) + by_status.get("rejected", 0),
        "awaiting_approval": by_status.get("awaiting_approval", 0),
        "interviews": by_status.get("interview", 0),
        "rejections": by_status.get("rejected", 0),
        "offers": by_status.get("offer", 0),
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "follow_ups": [{"id": a.id, "company": a.company, "position": a.position, "date": a.follow_up_date.isoformat()} for a in upcoming],
        "recent_activity": [{"actor": r.actor, "action": r.action, "message": r.message, "at": r.created_at.isoformat()} for r in recent],
    }
