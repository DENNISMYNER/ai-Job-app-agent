from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DB, PageParams
from app.core.errors import NotFoundError
from app.jobs import service as js
from app.matching import engine
from app.models import JobMatch, JobSource
from app.schemas.common import Message, Page
from app.schemas.jobs import ImportText, ImportUrl, JobDetail, JobOut, MatchOut, SourceIn, SourceOut
from app.services import profile_service as ps
from app.services.activity import log_activity

router = APIRouter(tags=["jobs"])


def _with_match(db, job, profile_id):
    out = JobOut.model_validate(job)
    if profile_id:
        m = db.scalar(select(JobMatch).where(JobMatch.listing_id == job.id, JobMatch.profile_id == profile_id))
        out.match = MatchOut.model_validate(m) if m else None
    return out


# ---------------------------------------------------------------- sources
@router.get("/job-sources", response_model=list[SourceOut])
def list_sources(db: DB):
    return db.scalars(select(JobSource).order_by(JobSource.id)).all()


@router.post("/job-sources", response_model=SourceOut, status_code=201)
def add_source(body: SourceIn, db: DB):
    src = js.create_source(db, body.name, body.kind, body.identifier, body.config)
    src.enabled = body.enabled
    return src


@router.patch("/job-sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, patch: dict, db: DB):
    src = db.get(JobSource, source_id)
    if not src:
        raise NotFoundError("Source not found")
    for k in ("name", "enabled", "config"):
        if k in patch:
            setattr(src, k, patch[k])
    return src


@router.delete("/job-sources/{source_id}", response_model=Message)
def delete_source(source_id: int, db: DB):
    src = db.get(JobSource, source_id)
    if not src:
        raise NotFoundError("Source not found")
    db.delete(src)
    return Message(message="Source deleted")


@router.post("/jobs/discover")
def discover(db: DB, source_id: int | None = None):
    """Run discovery on one source or all enabled sources, then score new jobs."""
    q = select(JobSource).where(JobSource.enabled.is_(True))
    if source_id:
        q = q.where(JobSource.id == source_id)
    results = [js.run_source(db, s) for s in db.scalars(q).all()]
    matched = 0
    if (p := ps.get_profile(db)):
        matched = len(engine.match_all(db, p, only_new=True))
    log_activity(db, "discovery", "run", f"{sum(r['new'] for r in results)} new jobs")
    return {"results": results, "matched": matched}


@router.post("/jobs/import-url", response_model=JobOut, status_code=201)
def import_url(body: ImportUrl, db: DB):
    job, _ = js.import_url(db, body.url, body.company)
    p = ps.get_profile(db)
    if p:
        engine.match_listing(db, job, p)
    return _with_match(db, job, p.id if p else None)


@router.post("/jobs/import-text", response_model=JobOut, status_code=201)
def import_text(body: ImportText, db: DB):
    job, _ = js.import_text(db, body.title, body.company, body.description, body.url)
    p = ps.get_profile(db)
    if p:
        engine.match_listing(db, job, p)
    return _with_match(db, job, p.id if p else None)


# ------------------------------------------------------------------- jobs
@router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    db: DB, pp: PageParams = Depends(), q: str | None = None, title: str | None = None,
    technology: str | None = None, level: str | None = None, location: str | None = None,
    remote: str | None = None, employment_type: str | None = None, salary_min: int | None = None,
    salary_max: int | None = None, posted_after: datetime | None = None, min_score: int | None = None,
    sort: str = "newest", include_dismissed: bool = False,
):
    p = ps.get_profile(db)
    pid = p.id if p else None
    stmt = js.query_listings(
        q=q, title=title, technology=technology, level=level, location=location, remote=remote,
        employment_type=employment_type, salary_min=salary_min, salary_max=salary_max,
        posted_after=posted_after, min_score=min_score, profile_id=pid, sort=sort,
        include_dismissed=include_dismissed,
    )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.offset(pp.offset).limit(pp.page_size)).unique().all()
    return Page(items=[_with_match(db, j, pid) for j in rows], total=total, page=pp.page, page_size=pp.page_size)


@router.get("/jobs/recommended", response_model=Page[JobOut])
def recommended(db: DB, pp: PageParams = Depends(), min_score: int = 45):
    return list_jobs(db, pp, min_score=min_score, sort="score")


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: DB):
    job = js.get_listing(db, job_id)
    p = ps.get_profile(db)
    base = _with_match(db, job, p.id if p else None)
    return JobDetail(**base.model_dump(), description_text=job.description_text,
                     requirements=[{"kind": r.kind, "text": r.text, "skill": r.skill} for r in job.requirements])


@router.post("/jobs/{job_id}/dismiss", response_model=Message)
def dismiss(job_id: int, db: DB):
    js.get_listing(db, job_id).dismissed = True
    return Message(message="Job dismissed")


@router.post("/jobs/{job_id}/match", response_model=MatchOut)
def rematch(job_id: int, db: DB):
    return engine.match_listing(db, js.get_listing(db, job_id), ps.require_profile(db))


@router.post("/matching/run")
def run_matching(db: DB):
    matches = engine.match_all(db, ps.require_profile(db))
    return {"matched": len(matches)}
