"""Profile persistence and the canonical 'verified facts' snapshot."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import (
    Certification,
    Education,
    Employment,
    LanguageSkill,
    Profile,
    Skill,
)
from app.schemas.profile import ProfileIn

SCALAR_FIELDS = [
    "full_name", "email", "phone", "location", "country", "headline", "summary",
    "portfolio_url", "github_url", "linkedin_url", "salary_min", "salary_max",
    "salary_currency", "employment_types", "preferred_locations", "work_modes",
    "notice_period", "available_from", "verified_facts",
]


def get_profile(db: Session) -> Profile | None:
    return db.scalars(select(Profile).order_by(Profile.id).limit(1)).first()


def require_profile(db: Session) -> Profile:
    p = get_profile(db)
    if p is None:
        raise NotFoundError("No profile yet. Create your profile first.")
    return p


def upsert_profile(db: Session, data: ProfileIn) -> Profile:
    """Create or fully replace the (single, local) user's profile."""
    p = get_profile(db) or Profile()
    for f in SCALAR_FIELDS:
        setattr(p, f, getattr(data, f))
    db.add(p)
    # Remove old nested rows and flush FIRST: otherwise the unit of work inserts the new rows before
    # deleting the old ones and the (profile_id, name) unique constraint on skills fails.
    p.education, p.employment, p.skills, p.certifications, p.languages = [], [], [], [], []
    db.flush()
    p.education = [Education(**e.model_dump()) for e in data.education]
    p.employment = [Employment(**e.model_dump()) for e in data.employment]
    seen: set[str] = set()
    skills = []
    for s in data.skills:  # de-duplicate case-insensitively
        if s.name.lower() not in seen:
            seen.add(s.name.lower())
            skills.append(Skill(**s.model_dump()))
    p.skills = skills
    p.certifications = [Certification(**c.model_dump()) for c in data.certifications]
    p.languages = [LanguageSkill(**x.model_dump()) for x in data.languages]
    db.add(p)
    db.flush()
    return p


def delete_profile(db: Session) -> None:
    p = get_profile(db)
    if p:
        db.delete(p)
        db.flush()


def facts_snapshot(p: Profile) -> dict:
    """Plain-dict view of ONLY what the user has entered. Used by all AI features."""
    return {
        "full_name": p.full_name,
        "email": p.email,
        "phone": p.phone,
        "location": p.location,
        "country": p.country,
        "headline": p.headline,
        "summary": p.summary,
        "links": {"portfolio": p.portfolio_url, "github": p.github_url, "linkedin": p.linkedin_url},
        "salary": {"min": p.salary_min, "max": p.salary_max, "currency": p.salary_currency},
        "notice_period": p.notice_period,
        "available_from": p.available_from,
        "work_modes": p.work_modes,
        "employment_types": p.employment_types,
        "preferred_locations": p.preferred_locations,
        "verified_facts": p.verified_facts,
        "skills": [
            {"name": s.name, "category": s.category, "level": s.level, "years": s.years}
            for s in p.skills
        ],
        "employment": [
            {
                "company": e.company, "title": e.title, "location": e.location,
                "start_date": e.start_date, "end_date": "Present" if e.is_current else e.end_date,
                "description": e.description, "achievements": list(e.achievements or []),
            }
            for e in p.employment
        ],
        "education": [
            {
                "institution": e.institution, "degree": e.degree, "field": e.field_of_study,
                "start_date": e.start_date, "end_date": e.end_date,
            }
            for e in p.education
        ],
        "certifications": [
            {"name": c.name, "issuer": c.issuer, "issue_date": c.issue_date} for c in p.certifications
        ],
        "languages": [{"language": l.language, "proficiency": l.proficiency} for l in p.languages],
    }


def skill_names(p: Profile) -> set[str]:
    return {s.name.strip().lower() for s in p.skills}
