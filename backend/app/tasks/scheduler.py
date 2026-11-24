"""Local background scheduler (APScheduler). Schedules live in the database; no external service."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.errors import ValidationFailed
from app.database.session import session_factory
from app.jobs import service as js
from app.matching import engine
from app.models import AutomationSchedule, JobApplication, JobListing, JobMatch, JobSource
from app.services import profile_service as ps
from app.services import settings_service as ss
from app.services.activity import log_activity, notify

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
TASKS = {"discover_match", "daily_report"}


def validate_cron(expr: str) -> None:
    try:
        CronTrigger.from_crontab(expr)
    except ValueError as exc:
        raise ValidationFailed(f"Invalid cron expression: {exc}") from exc


# ------------------------------------------------------------------ the tasks
def run_discover_match(db, params: dict) -> str:
    """Search sources, score new jobs, notify about high matches. Never applies automatically."""
    srcs = db.scalars(select(JobSource).where(JobSource.enabled.is_(True))).all()
    if params.get("source_ids"):
        srcs = [s for s in srcs if s.id in params["source_ids"]]
    before = {j for (j,) in db.execute(select(JobListing.id))}
    errors = sum(1 for r in (js.run_source(db, s) for s in srcs) if r["error"])
    p = ps.get_profile(db)
    new_ids = [j for (j,) in db.execute(select(JobListing.id)) if j not in before]
    high = 0
    if p and new_ids:
        threshold = params.get("min_score") or ss.get_setting(db, "automation")["notify_min_score"]
        words = [w.lower() for w in params.get("keywords", [])]
        for jid in new_ids:
            job = db.get(JobListing, jid)
            if words and not any(w in f"{job.title} {job.description_text}".lower() for w in words):
                continue
            if params.get("remote_only") and job.remote_type != "remote":
                continue
            m = engine.match_listing(db, job, p, use_ai=params.get("use_ai", True))
            if m.score >= threshold:
                high += 1
                notify(db, "high_match", f"{m.score}% match: {job.title} @ {job.company}", m.explanation[:300], listing_id=job.id, score=m.score)
    return f"{len(srcs)} sources ({errors} failed), {len(new_ids)} new jobs, {high} high matches"


def run_daily_report(db, params: dict) -> str:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    new_jobs = db.query(JobListing).filter(JobListing.discovered_at >= since).count()
    applied = db.query(JobApplication).filter(JobApplication.applied_at >= since).count()
    awaiting = db.query(JobApplication).filter(JobApplication.status == "awaiting_approval").count()
    top = db.scalars(select(JobMatch).join(JobListing).where(JobListing.discovered_at >= since).order_by(JobMatch.score.desc()).limit(3)).all()
    body = f"New jobs: {new_jobs}. Applications submitted: {applied}. Awaiting your approval: {awaiting}."
    if top:
        body += " Top matches: " + ", ".join(f"{m.listing.title} ({m.score})" for m in top)
    notify(db, "report", "Daily application report", body)
    return body


RUNNERS = {"discover_match": run_discover_match, "daily_report": run_daily_report}


def execute_schedule(schedule_id: int) -> str:
    """Run one schedule with its own DB session. Used by the scheduler and by 'Run now'."""
    db = session_factory()()
    try:
        sch = db.get(AutomationSchedule, schedule_id)
        if sch is None:
            return "missing"
        try:
            status = "ok: " + RUNNERS[sch.task_type](db, sch.params or {})
        except Exception as exc:  # noqa: BLE001 - a failing schedule must never kill the scheduler
            log.warning("Schedule %s failed: %s", schedule_id, type(exc).__name__)
            status = f"error: {type(exc).__name__}"
        sch.last_run_at, sch.last_status = datetime.now(timezone.utc), status[:300]
        log_activity(db, "scheduler", sch.task_type, f"{sch.name}: {status}")
        db.commit()
        return status
    finally:
        db.close()


# -------------------------------------------------------------- scheduler mgmt
def start_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        _scheduler.add_job(run_retention_job, CronTrigger(hour=3, minute=15), id="maintenance-retention", replace_existing=True)
    sync_schedules()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def sync_schedules() -> int:
    """(Re)register every enabled schedule from the database."""
    if _scheduler is None:
        return 0
    for j in _scheduler.get_jobs():
        if j.id.startswith("sched-"):  # leave built-in maintenance jobs alone
            _scheduler.remove_job(j.id)
    db = session_factory()()
    try:
        n = 0
        for s in db.scalars(select(AutomationSchedule).where(AutomationSchedule.enabled.is_(True))):
            _scheduler.add_job(execute_schedule, CronTrigger.from_crontab(s.cron), args=[s.id], id=f"sched-{s.id}", replace_existing=True, coalesce=True, max_instances=1)
            n += 1
        return n
    finally:
        db.close()


def run_retention_job() -> None:
    from app.services.retention import apply_retention

    db = session_factory()()
    try:
        apply_retention(db)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("Retention job failed: %s", type(exc).__name__)
    finally:
        db.close()


def scheduler_state() -> dict:
    if _scheduler is None:
        return {"running": False, "paused": False, "jobs": []}
    return {
        "running": _scheduler.running, "paused": _scheduler.state == 2,
        "jobs": [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                 for j in _scheduler.get_jobs() if j.id.startswith("sched-")],
    }


def pause_all() -> None:
    if _scheduler is not None:
        _scheduler.pause()


def resume_all() -> None:
    if _scheduler is not None:
        _scheduler.resume()
