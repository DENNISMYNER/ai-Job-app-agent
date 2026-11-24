"""Configurable data retention (``system.retention_days``; 0 keeps everything)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models import AgentActivityLog, JobApplication, JobListing, Notification
from app.services import settings_service as ss


def apply_retention(db: Session) -> dict[str, int]:
    """Delete old, low-value records. Applications, CVs, letters and the profile are never touched."""
    days = int(ss.get_setting(db, "system").get("retention_days", 0) or 0)
    if days <= 0:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    logs = db.execute(delete(AgentActivityLog).where(AgentActivityLog.created_at < cutoff)).rowcount
    notes = db.execute(delete(Notification).where(Notification.read.is_(True), Notification.created_at < cutoff)).rowcount
    # Dismissed jobs that were never turned into an application.
    old_jobs = db.scalars(
        select(JobListing).where(
            JobListing.dismissed.is_(True), JobListing.discovered_at < cutoff,
            ~exists().where(JobApplication.listing_id == JobListing.id),
        )
    ).all()
    for j in old_jobs:
        db.delete(j)
    db.flush()
    return {"activity_logs": logs or 0, "notifications": notes or 0, "dismissed_jobs": len(old_jobs)}
