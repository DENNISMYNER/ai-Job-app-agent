from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import DB, PageParams
from app.applications import service as svc
from app.core.errors import NotFoundError, ValidationFailed
from app.jobs.service import get_listing
from app.models import (STATUSES, ApplicationEvent, Interview, JobApplication, Notification, RecruiterContact)
from app.schemas.common import ORM, Message, Page
from app.services import profile_service as ps

router = APIRouter(tags=["applications"])


class EventOut(ORM):
    type: str
    detail: str
    created_at: datetime


class InterviewOut(ORM):
    id: int
    application_id: int
    scheduled_at: datetime | None
    kind: str
    location: str
    notes: str
    prep: dict


class RecruiterOut(ORM):
    id: int
    application_id: int | None
    name: str
    email: str
    phone: str
    company: str
    notes: str


class AppOut(ORM):
    id: int
    listing_id: int | None
    company: str
    position: str
    job_url: str
    status: str
    applied_at: datetime | None
    cv_id: int | None
    cover_letter_id: int | None
    confirmation: str
    follow_up_date: datetime | None
    notes: str
    submission_result: str
    approved_at: datetime | None
    created_at: datetime


class AppDetail(AppOut):
    fill_report: dict
    events: list[EventOut] = []
    interviews: list[InterviewOut] = []
    recruiters: list[RecruiterOut] = []


class AppCreate(BaseModel):
    listing_id: int | None = None
    company: str = ""
    position: str = ""
    url: str = ""
    status: str = "shortlisted"


class AppPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(None, max_length=5000)
    follow_up_date: datetime | None = None
    confirmation: str | None = Field(None, max_length=2000)
    cv_id: int | None = None
    cover_letter_id: int | None = None
    applied_at: datetime | None = None


@router.get("/applications", response_model=Page[AppOut])
def list_applications(db: DB, pp: PageParams = Depends(), status: str | None = None, q: str | None = None, sort: str = "newest"):
    stmt = select(JobApplication)
    if status:
        stmt = stmt.where(JobApplication.status == status)
    if q:
        stmt = stmt.where(or_(JobApplication.company.ilike(f"%{q}%"), JobApplication.position.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {"company": JobApplication.company, "status": JobApplication.status, "follow_up": JobApplication.follow_up_date}.get(sort)
    stmt = stmt.order_by(order if order is not None else JobApplication.id.desc())
    return Page(items=db.scalars(stmt.offset(pp.offset).limit(pp.page_size)).all(), total=total, page=pp.page, page_size=pp.page_size)


@router.post("/applications", response_model=AppOut, status_code=201)
def create_application(body: AppCreate, db: DB):
    listing = get_listing(db, body.listing_id) if body.listing_id else None
    return svc.create_application(db, listing=listing, company=body.company, position=body.position, url=body.url, status=body.status)


@router.get("/applications/check-duplicate")
def check_duplicate(company: str, position: str, db: DB, url: str = ""):
    d = svc.find_duplicate(db, company, position, url)
    return {"duplicate": d is not None, "existing_id": d.id if d else None, "status": d.status if d else None}


@router.get("/applications/{app_id}", response_model=AppDetail)
def get_application(app_id: int, db: DB):
    return svc.get_application(db, app_id)


@router.patch("/applications/{app_id}", response_model=AppOut)
def patch_application(app_id: int, body: AppPatch, db: DB):
    app = svc.get_application(db, app_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        if data["status"] == "applied" and app.status != "applied":
            # Manual marking is allowed (user applied elsewhere) but is recorded as such.
            svc.add_event(db, app, "marked_applied_manually", "Status set by the user")
        svc.set_status(db, app, data.pop("status"), "set manually")
    for k, v in data.items():
        setattr(app, k, v)
    return app


@router.delete("/applications/{app_id}", response_model=Message)
def delete_application(app_id: int, db: DB):
    app = svc.get_application(db, app_id)
    db.delete(app)
    return Message(message="Application deleted")


# ---------------------------------------------------------- automation flow
class PrepareBody(BaseModel):
    use_ai: bool = True
    headless: bool | None = None


@router.post("/applications/{app_id}/prepare")
def prepare(app_id: int, body: PrepareBody, db: DB):
    app = svc.get_application(db, app_id)
    return svc.prepare(db, app, ps.require_profile(db), use_ai=body.use_ai, headless=body.headless)


@router.post("/applications/{app_id}/rescan")
def rescan(app_id: int, db: DB, use_ai: bool = True):
    return svc.rescan(db, svc.get_application(db, app_id), ps.require_profile(db), use_ai=use_ai)


@router.post("/applications/{app_id}/approve", response_model=AppOut)
def approve(app_id: int, db: DB):
    app = svc.get_application(db, app_id)
    svc.approve(db, app)
    return app


class SubmitBody(BaseModel):
    confirm: bool = False


@router.post("/applications/{app_id}/submit")
def submit(app_id: int, body: SubmitBody, db: DB):
    if not body.confirm:
        raise ValidationFailed("Set confirm=true to submit. Final submission is always an explicit action.")
    return svc.submit(db, svc.get_application(db, app_id))


@router.post("/applications/{app_id}/close-browser", response_model=Message)
def close_browser(app_id: int, db: DB):
    from app.automation import runner

    svc.get_application(db, app_id)
    runner.close_browser_page(app_id)
    return Message(message="Browser window closed")


# ------------------------------------------------------ interviews/recruiters
class InterviewIn(BaseModel):
    scheduled_at: datetime | None = None
    kind: str = "general"
    location: str = ""
    notes: str = Field("", max_length=8000)


@router.post("/applications/{app_id}/interviews", response_model=InterviewOut, status_code=201)
def add_interview(app_id: int, body: InterviewIn, db: DB):
    app = svc.get_application(db, app_id)
    iv = Interview(application_id=app.id, **body.model_dump())
    db.add(iv)
    db.flush()
    if app.status in {"applied", "shortlisted", "preparing", "awaiting_approval", "discovered"}:
        svc.set_status(db, app, "interview", "Interview added")
    svc.add_event(db, app, "interview_added", body.kind)
    return iv


@router.get("/interviews", response_model=list[InterviewOut])
def list_interviews(db: DB, upcoming: bool = False):
    q = select(Interview).order_by(Interview.scheduled_at)
    if upcoming:
        q = q.where(Interview.scheduled_at >= datetime.now(timezone.utc))
    return db.scalars(q).all()


@router.patch("/interviews/{iid}", response_model=InterviewOut)
def edit_interview(iid: int, body: InterviewIn, db: DB):
    iv = db.get(Interview, iid)
    if not iv:
        raise NotFoundError("Interview not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(iv, k, v)
    return iv


@router.delete("/interviews/{iid}", response_model=Message)
def delete_interview(iid: int, db: DB):
    iv = db.get(Interview, iid)
    if not iv:
        raise NotFoundError("Interview not found")
    db.delete(iv)
    return Message(message="Interview deleted")


class RecruiterIn(BaseModel):
    name: str = Field("", max_length=200)
    email: str = Field("", max_length=320)
    phone: str = Field("", max_length=50)
    company: str = Field("", max_length=200)
    notes: str = Field("", max_length=3000)


@router.post("/applications/{app_id}/recruiters", response_model=RecruiterOut, status_code=201)
def add_recruiter(app_id: int, body: RecruiterIn, db: DB):
    app = svc.get_application(db, app_id)
    r = RecruiterContact(application_id=app.id, **body.model_dump())
    db.add(r)
    db.flush()
    return r


@router.delete("/recruiters/{rid}", response_model=Message)
def delete_recruiter(rid: int, db: DB):
    r = db.get(RecruiterContact, rid)
    if not r:
        raise NotFoundError("Contact not found")
    db.delete(r)
    return Message(message="Contact deleted")


# ------------------------------------------------- notifications / dashboard
class NotificationOut(ORM):
    id: int
    kind: str
    title: str
    body: str
    read: bool
    payload: dict
    created_at: datetime


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(db: DB, unread: bool = False):
    q = select(Notification).order_by(Notification.id.desc()).limit(100)
    if unread:
        q = q.where(Notification.read.is_(False))
    return db.scalars(q).all()


@router.post("/notifications/{nid}/read", response_model=Message)
def mark_read(nid: int, db: DB):
    n = db.get(Notification, nid)
    if n:
        n.read = True
    return Message(message="ok")


@router.post("/notifications/read-all", response_model=Message)
def read_all(db: DB):
    for n in db.scalars(select(Notification).where(Notification.read.is_(False))):
        n.read = True
    return Message(message="ok")


@router.get("/dashboard")
def dashboard(db: DB):
    p = ps.get_profile(db)
    return svc.dashboard_stats(db, p.id if p else None)


# ---------------------------------------------------------- interview prep
class PrepBody(BaseModel):
    use_ai: bool = True
    interview_id: int | None = None


@router.post("/applications/{app_id}/interview-prep")
def interview_prep(app_id: int, body: PrepBody, db: DB):
    from app.models import JobListing
    from app.services import interview_service as iss

    app = svc.get_application(db, app_id)
    job = db.get(JobListing, app.listing_id) if app.listing_id else None
    prep = iss.generate_prep(db, app, ps.require_profile(db), job, use_ai=body.use_ai)
    iv = iss.save_prep(db, app, prep, body.interview_id)
    return {"interview_id": iv.id, "prep": prep}
