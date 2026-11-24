"""Email assistant + automation scheduler endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB
from app.applications import service as svc
from app.automation.session import check_browser_setup
from app.core.errors import NotFoundError, ValidationFailed
from app.models import AutomationSchedule, EmailDraft
from app.notifications import email as em
from app.schemas.common import ORM, Message
from app.services import profile_service as ps
from app.tasks import scheduler as sch

router = APIRouter(tags=["integrations"])


# ------------------------------------------------------------------- email
class EmailConfig(BaseModel):
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 465
    username: str = ""
    password: str = Field("", repr=False)
    from_address: str = ""


@router.get("/email/config")
def email_config(db: DB):
    return em.get_config(db)


@router.put("/email/config")
def put_email_config(body: EmailConfig, db: DB):
    return em.save_config(db, body.model_dump())


@router.delete("/email/config", response_model=Message)
def remove_email_config(db: DB):
    em.delete_config(db)
    return Message(message="Email settings (including the stored password) deleted")


@router.post("/email/poll")
def poll(db: DB):
    return {"found": em.poll_inbox(db)}


class DraftOut(ORM):
    id: int
    application_id: int | None
    to_address: str
    subject: str
    body: str
    status: str
    error: str


class FollowUpBody(BaseModel):
    to: str = ""


@router.post("/applications/{app_id}/follow-up-draft", response_model=DraftOut, status_code=201)
def follow_up(app_id: int, body: FollowUpBody, db: DB):
    return em.follow_up_draft(db, svc.get_application(db, app_id), ps.require_profile(db), body.to)


class ReplyBody(BaseModel):
    label: str
    to: str
    sender_name: str = ""
    role: str = ""
    subject: str = ""
    application_id: int | None = None


@router.post("/email/suggest-reply", response_model=DraftOut, status_code=201)
def suggest(body: ReplyBody, db: DB):
    return em.suggest_reply(db, body.label, ps.require_profile(db), to=body.to, sender_name=body.sender_name, role=body.role, application_id=body.application_id, subject=body.subject)


@router.get("/email/drafts", response_model=list[DraftOut])
def drafts(db: DB):
    return db.scalars(select(EmailDraft).order_by(EmailDraft.id.desc())).all()


@router.post("/email/drafts/{did}/approve", response_model=DraftOut)
def approve_draft(did: int, db: DB, edits: dict | None = None):
    return em.approve_draft(db, did, edits)


@router.post("/email/drafts/{did}/send", response_model=DraftOut)
def send(did: int, db: DB):
    return em.send_draft(db, did)


@router.delete("/email/drafts/{did}", response_model=Message)
def delete_draft(did: int, db: DB):
    d = db.get(EmailDraft, did)
    if not d:
        raise NotFoundError("Draft not found")
    db.delete(d)
    return Message(message="Draft deleted")


# --------------------------------------------------------------- scheduler
class ScheduleIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task_type: str
    cron: str = "0 8 * * *"
    params: dict = Field(default_factory=dict)
    enabled: bool = True


class ScheduleOut(ORM):
    id: int
    name: str
    task_type: str
    cron: str
    params: dict
    enabled: bool
    last_run_at: datetime | None
    last_status: str


def _check(body: ScheduleIn) -> None:
    if body.task_type not in sch.TASKS:
        raise ValidationFailed(f"task_type must be one of {sorted(sch.TASKS)}")
    sch.validate_cron(body.cron)


@router.get("/automation/schedules", response_model=list[ScheduleOut])
def schedules(db: DB):
    return db.scalars(select(AutomationSchedule).order_by(AutomationSchedule.id)).all()


@router.post("/automation/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(body: ScheduleIn, db: DB):
    _check(body)
    s = AutomationSchedule(**body.model_dump())
    db.add(s)
    db.flush()
    db.commit()  # the scheduler thread reads from the DB
    sch.sync_schedules()
    return s


@router.put("/automation/schedules/{sid}", response_model=ScheduleOut)
def update_schedule(sid: int, body: ScheduleIn, db: DB):
    _check(body)
    s = db.get(AutomationSchedule, sid)
    if not s:
        raise NotFoundError("Schedule not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    sch.sync_schedules()
    return s


@router.post("/automation/schedules/{sid}/{action}", response_model=ScheduleOut)
def schedule_action(sid: int, action: str, db: DB):
    s = db.get(AutomationSchedule, sid)
    if not s:
        raise NotFoundError("Schedule not found")
    if action == "pause":
        s.enabled = False
    elif action == "resume":
        s.enabled = True
    elif action == "run-now":
        db.commit()
        sch.execute_schedule(sid)
        db.refresh(s)
        return s
    else:
        raise ValidationFailed("action must be pause, resume or run-now")
    db.commit()
    sch.sync_schedules()
    return s


@router.delete("/automation/schedules/{sid}", response_model=Message)
def delete_schedule(sid: int, db: DB):
    s = db.get(AutomationSchedule, sid)
    if not s:
        raise NotFoundError("Schedule not found")
    db.delete(s)
    db.commit()
    sch.sync_schedules()
    return Message(message="Schedule deleted")


@router.get("/automation/status")
def automation_status(check_browser: bool = False):
    out = {"scheduler": sch.scheduler_state()}
    if check_browser:
        out["browser"] = check_browser_setup()
    return out


@router.post("/automation/pause-all", response_model=Message)
def pause_all():
    sch.pause_all()
    return Message(message="All scheduled automation paused")


@router.post("/automation/resume-all", response_model=Message)
def resume_all():
    sch.resume_all()
    return Message(message="Scheduled automation resumed")
