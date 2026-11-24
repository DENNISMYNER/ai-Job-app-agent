"""Job ingestion, de-duplication and filtered listing."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.jobs import http
from app.jobs.sources import ADAPTERS, RawJob
from app.matching.extract import extract_requirements
from app.models import JobListing, JobMatch, JobRequirement, JobSource
from app.security.untrusted import detect_injection, normalise_text
from app.services.activity import log_activity

log = logging.getLogger(__name__)
SOURCE_KINDS = set(ADAPTERS)


def create_source(db: Session, name: str, kind: str, identifier: str, config: dict | None = None) -> JobSource:
    if kind not in SOURCE_KINDS:
        raise ValidationFailed(f"kind must be one of {sorted(SOURCE_KINDS)}")
    if kind in {"rss", "career_page", "manual"}:
        http.assert_public_url(identifier)
    exists = db.scalar(select(JobSource).where(JobSource.kind == kind, JobSource.identifier == identifier))
    if exists:
        raise ValidationFailed("This source already exists.")
    src = JobSource(name=name, kind=kind, identifier=identifier, config=config or {})
    db.add(src)
    db.flush()
    return src


def _salary_from_text(text: str) -> tuple[int | None, int | None, str]:
    m = re.search(r"(\$|€|£|USD|EUR|GBP|KES)\s?(\d{2,3}(?:[,.]\d{3})*|\d+k)\s*(?:-|–|to)\s*(?:\$|€|£)?\s?(\d{2,3}(?:[,.]\d{3})*|\d+k)", text)
    if not m:
        return None, None, ""

    def num(s: str) -> int:
        return int(float(s[:-1]) * 1000) if s.endswith("k") else int(re.sub(r"[,.]", "", s))

    cur = {"$": "USD", "€": "EUR", "£": "GBP"}.get(m.group(1), m.group(1))
    return num(m.group(2)), num(m.group(3)), cur


def upsert_listing(db: Session, raw: RawJob, source: JobSource | None) -> tuple[JobListing, bool]:
    """Insert a normalised job. Returns (listing, created). Duplicates are never re-inserted."""
    url = raw.get("url", "")
    if not url or not raw.get("title"):
        raise ValidationFailed("Job is missing a title or URL.")
    canon = http.canonical_url(url)
    desc = normalise_text(raw.get("description", ""))
    existing = db.scalar(select(JobListing).where(JobListing.canonical_url == canon))
    if existing is None and source is not None and raw.get("external_id"):
        existing = db.scalar(
            select(JobListing).where(JobListing.source_id == source.id, JobListing.external_id == raw["external_id"])
        )
    content_hash = hashlib.sha256(f"{raw['title']}|{desc}".encode()).hexdigest()
    if existing:
        if existing.content_hash != content_hash:  # description changed -> refresh
            existing.description_text, existing.content_hash = desc, content_hash
            _apply_extraction(existing, raw)
        return existing, False

    smin, smax, scur = raw.get("salary_min"), raw.get("salary_max"), raw.get("salary_currency", "")
    if smin is None:
        smin, smax, scur = _salary_from_text(desc)
    listing = JobListing(
        source_id=source.id if source else None,
        external_id=str(raw.get("external_id", ""))[:200],
        title=normalise_text(raw["title"], 300),
        company=normalise_text(raw.get("company", ""), 200),
        location=normalise_text(raw.get("location", ""), 300),
        employment_type=(raw.get("employment_type") or "")[:30],
        salary_min=smin, salary_max=smax, salary_currency=scur or "",
        url=url[:1000], canonical_url=canon[:1000], description_text=desc,
        posted_at=raw.get("posted_at"), content_hash=content_hash,
        injection_flags=detect_injection(desc),
    )
    _apply_extraction(listing, raw)
    db.add(listing)
    db.flush()
    if listing.injection_flags:
        log_activity(db, "discovery", "injection_flagged", f"Job {listing.id} contains instruction-like text", level="warning")
    return listing, True


def _apply_extraction(listing: JobListing, raw: RawJob) -> None:
    ex = extract_requirements(listing.title, listing.description_text, listing.location)
    listing.experience_level = ex.level
    listing.remote_type = ex.remote_type
    listing.technologies = ex.technologies
    if not listing.employment_type:
        m = re.search(r"\b(full[- ]time|part[- ]time|contract|internship|freelance)\b", listing.description_text, re.I)
        listing.employment_type = m.group(1).lower().replace(" ", "-") if m else ""
    listing.requirements = (
        [JobRequirement(kind="required", text=t, skill=s) for t, s in ex.required]
        + [JobRequirement(kind="preferred", text=t, skill=s) for t, s in ex.preferred]
        + [JobRequirement(kind="experience", text=t) for t in ex.experience]
    )


def run_source(db: Session, source: JobSource) -> dict:
    adapter = ADAPTERS[source.kind]
    company = source.config.get("company", "") if source.config else ""
    try:
        raws = adapter(source.identifier, company)
        created = 0
        for raw in raws:
            try:
                _, was_new = upsert_listing(db, raw, source)
                created += was_new
            except ValidationFailed:
                continue
        source.last_run_at = datetime.now(timezone.utc)
        source.last_status = f"ok: {len(raws)} found, {created} new"
        return {"source": source.name, "found": len(raws), "new": created, "error": None}
    except Exception as exc:  # a failing source must never break the whole run
        source.last_run_at = datetime.now(timezone.utc)
        source.last_status = f"error: {getattr(exc, 'message', type(exc).__name__)}"[:300]
        log.warning("Source %s failed: %s", source.id, type(exc).__name__)
        return {"source": source.name, "found": 0, "new": 0, "error": source.last_status}


def import_url(db: Session, url: str, company: str = "") -> tuple[JobListing, bool]:
    raw = ADAPTERS["manual"](url, company)[0]
    return upsert_listing(db, raw, None)


def import_text(db: Session, title: str, company: str, description: str, url: str = "") -> tuple[JobListing, bool]:
    """Manual paste fallback for sites that forbid automation."""
    url = url or f"manual://{hashlib.sha1((title + company + description).encode()).hexdigest()[:16]}"
    raw = RawJob(external_id=url, title=title, company=company, description=description, url=url)
    return upsert_listing(db, raw, None)


def query_listings(
    *, q: str | None = None, title: str | None = None, technology: str | None = None,
    level: str | None = None, location: str | None = None, remote: str | None = None,
    employment_type: str | None = None, salary_min: int | None = None, salary_max: int | None = None,
    posted_after: datetime | None = None, min_score: int | None = None, profile_id: int | None = None,
    include_dismissed: bool = False, sort: str = "newest",
) -> Select:
    stmt = select(JobListing)
    if not include_dismissed:
        stmt = stmt.where(JobListing.dismissed.is_(False))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(JobListing.title.ilike(like), JobListing.company.ilike(like), JobListing.description_text.ilike(like)))
    if title:
        stmt = stmt.where(JobListing.title.ilike(f"%{title}%"))
    if technology:
        stmt = stmt.where(func.lower(cast(JobListing.technologies, String)).like(f'%"{technology.lower()}"%'))
    if level:
        stmt = stmt.where(JobListing.experience_level == level)
    if location:
        stmt = stmt.where(JobListing.location.ilike(f"%{location}%"))
    if remote:
        stmt = stmt.where(JobListing.remote_type == remote)
    if employment_type:
        stmt = stmt.where(JobListing.employment_type.ilike(f"%{employment_type}%"))
    if salary_min is not None:
        stmt = stmt.where(or_(JobListing.salary_max.is_(None), JobListing.salary_max >= salary_min))
    if salary_max is not None:
        stmt = stmt.where(or_(JobListing.salary_min.is_(None), JobListing.salary_min <= salary_max))
    if posted_after:
        stmt = stmt.where(JobListing.posted_at >= posted_after)
    if min_score is not None and profile_id is not None:
        stmt = stmt.join(JobMatch, (JobMatch.listing_id == JobListing.id) & (JobMatch.profile_id == profile_id)).where(
            JobMatch.score >= min_score
        )
    if sort == "score" and profile_id is not None:
        if min_score is None:
            stmt = stmt.outerjoin(JobMatch, (JobMatch.listing_id == JobListing.id) & (JobMatch.profile_id == profile_id))
        stmt = stmt.order_by(JobMatch.score.desc().nulls_last(), JobListing.id.desc())
    elif sort == "company":
        stmt = stmt.order_by(JobListing.company, JobListing.title)
    else:
        stmt = stmt.order_by(JobListing.posted_at.desc().nulls_last(), JobListing.id.desc())
    return stmt


def get_listing(db: Session, listing_id: int) -> JobListing:
    obj = db.get(JobListing, listing_id)
    if not obj:
        raise NotFoundError("Job not found")
    return obj
