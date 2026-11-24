from __future__ import annotations

import shutil

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.ai.ollama import get_ai
from app.api.deps import DB
from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.models import (
    AgentActivityLog, ApplicationAnswer, CoverLetter, Document, GeneratedCV, JobApplication,
    JobListing, JobSource, Notification, Profile, UserSetting,
)
from app.schemas.common import Message
from app.services import profile_service as ps
from app.services import settings_service as ss

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ai/status")
def ai_status(db: DB):
    cfg = ss.get_setting(db, "ai")
    from app.ai.ollama import configure_runtime

    configure_runtime(cfg)
    st = get_ai().status()
    return {**st.__dict__, "enabled": cfg.get("enabled", True)}


@router.get("/settings/{key}")
def read_setting(key: str, db: DB):
    if key not in ss.DEFAULTS:
        raise ValidationFailed("Unknown settings group")
    return ss.get_setting(db, key)


@router.put("/settings/{key}")
def write_setting(key: str, patch: dict, db: DB):
    if key not in ss.DEFAULTS:
        raise ValidationFailed("Unknown settings group")
    if key == "automation" and patch.get("require_approval") is False and not patch.get("auto_submit_enabled", False):
        # Turning off approval only makes sense together with an explicit auto-submit opt-in.
        patch["require_approval"] = True
    saved = ss.update_setting(db, key, patch)
    if key == "ai":
        from app.ai.ollama import configure_runtime

        configure_runtime(saved)  # takes effect immediately, no restart
    return saved


@router.post("/data/apply-retention")
def run_retention(db: DB):
    from app.services.retention import apply_retention

    return {"removed": apply_retention(db)}


@router.get("/data/export")
def export_data(db: DB):
    """Export all personal data as JSON (data portability)."""
    p = ps.get_profile(db)

    def rows(model, fields):
        return [{f: getattr(r, f) for f in fields} for r in db.scalars(select(model)).all()]

    return {
        "profile": ps.facts_snapshot(p) if p else None,
        "applications": rows(JobApplication, ["id", "company", "position", "job_url", "status", "notes", "confirmation"]),
        "answers": rows(ApplicationAnswer, ["question", "answer", "approved"]),
        "cover_letters": rows(CoverLetter, ["title", "content", "version"]),
        "generated_cvs": rows(GeneratedCV, ["title", "category", "version", "content"]),
        "documents": rows(Document, ["filename", "kind", "size"]),
    }


class DeleteAll(BaseModel):
    confirm: str


@router.post("/data/delete-all", response_model=Message)
def delete_all(body: DeleteAll, db: DB):
    """Irreversibly delete every piece of personal data (requires typing DELETE)."""
    if body.confirm != "DELETE":
        raise ValidationFailed("Type DELETE to confirm.")
    for model in (JobApplication, GeneratedCV, CoverLetter, ApplicationAnswer, Document, Profile,
                  JobListing, Notification, AgentActivityLog):
        db.execute(delete(model))
    db.execute(delete(UserSetting).where(UserSetting.key.like("email%")))
    s = get_settings()
    for sub in ("uploads", "imports", "generated"):
        shutil.rmtree(s.documents_dir / sub, ignore_errors=True)
    return Message(message="All personal data deleted")
