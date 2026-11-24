"""CV content generation with a deterministic fact guard.

The CV is built from the user's profile only. The (optional) local LLM may re-word the
summary and bullets, but every rewritten line is checked and rejected if it introduces
a technology, number or claim that is not already in the user's own data.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.ollama import get_ai
from app.core.errors import AIUnavailableError
from app.matching.engine import profile_skill_set, total_years
from app.matching.extract import extract_requirements
from app.matching.skills import canonical, extract_skills
from app.models import GeneratedCV, JobListing, Profile
from app.security.untrusted import SYSTEM_GUARD, wrap_untrusted
from app.services import profile_service as ps

log = logging.getLogger(__name__)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _relevance(text: str, keywords: set[str]) -> int:
    low = text.lower()
    return sum(1 for k in keywords if k in low)


def build_cv_content(p: Profile, job: JobListing | None = None, category: str = "general") -> dict:
    """Deterministic, fact-only CV content. Job keywords only re-order what already exists."""
    keywords: set[str] = set()
    required_kw: set[str] = set()
    missing: list[str] = []
    if job is not None:
        ex = extract_requirements(job.title, job.description_text, job.location)
        wanted = [*ex.required_skills, *ex.preferred_skills]
        have = profile_skill_set(p)
        keywords = {s.lower() for s in wanted if s.lower() in have}
        required_kw = {s.lower() for s in ex.required_skills}
        missing = [s for s in wanted if s.lower() not in have]

    def rank(s) -> tuple:
        c = canonical(s.name).lower()  # required job skills first, then preferred, then the rest
        return (0 if c in required_kw else 1 if c in keywords else 2, s.name.lower())

    skills = sorted(p.skills, key=rank)
    exp = []
    for e in p.employment:
        bullets = list(e.achievements or [])
        if e.description and not bullets:
            bullets = [e.description]
        bullets.sort(key=lambda b: -_relevance(b, keywords))
        exp.append({
            "company": e.company, "title": e.title, "location": e.location,
            "start_date": e.start_date, "end_date": "Present" if e.is_current else e.end_date,
            "bullets": bullets,
        })
    # Most relevant role first only when tailoring; otherwise keep user's chronological order.
    if keywords:
        exp.sort(key=lambda r: -sum(_relevance(b, keywords) for b in r["bullets"]))

    summary = p.summary or ""
    return {
        "name": p.full_name, "headline": p.headline,
        "contact": {"email": p.email, "phone": p.phone, "location": ", ".join(x for x in [p.location, p.country] if x)},
        "links": {k: v for k, v in {"Portfolio": p.portfolio_url, "GitHub": p.github_url, "LinkedIn": p.linkedin_url}.items() if v},
        "summary": summary,
        "skills": [s.name for s in skills],
        "experience": exp,
        "education": [
            {"institution": e.institution, "degree": e.degree, "field": e.field_of_study,
             "start_date": e.start_date, "end_date": e.end_date} for e in p.education
        ],
        "certifications": [{"name": c.name, "issuer": c.issuer, "date": c.issue_date} for c in p.certifications],
        "languages": [{"language": l.language, "proficiency": l.proficiency} for l in p.languages],
        "_meta": {"category": category, "ats_keywords": sorted(keywords), "missing_keywords": missing},
    }


# --------------------------------------------------------------- fact guard
def _nums(text: str) -> set[str]:
    return set(_NUM.findall(text))


def guard_line(new: str, original: str, allowed_skills: set[str]) -> bool:
    """True if ``new`` adds no unsupported numbers or technologies compared to ``original``."""
    if not new.strip():
        return False
    if not _nums(new) <= _nums(original) | _nums(" ".join(allowed_skills)):
        return False
    return {s.lower() for s in extract_skills(new)} <= (allowed_skills | {s.lower() for s in extract_skills(original)})


def validate_cv(content: dict, p: Profile) -> list[str]:
    """Return a list of violations (empty = every claim traces back to the profile)."""
    facts = ps.facts_snapshot(p)
    problems: list[str] = []
    have_skills = {s["name"].lower() for s in facts["skills"]}
    for s in content.get("skills", []):
        if s.lower() not in have_skills:
            problems.append(f"skill not in profile: {s}")
    roles = {(e["company"], e["title"], e["start_date"]) for e in facts["employment"]}
    for e in content.get("experience", []):
        if (e["company"], e["title"], e["start_date"]) not in roles:
            problems.append(f"employment not in profile: {e['company']}")
    certs = {c["name"] for c in facts["certifications"]}
    for c in content.get("certifications", []):
        if c["name"] not in certs:
            problems.append(f"certification not in profile: {c['name']}")
    edu = {e["institution"] for e in facts["education"]}
    for e in content.get("education", []):
        if e["institution"] not in edu:
            problems.append(f"education not in profile: {e['institution']}")
    return problems


def _llm_polish(content: dict, p: Profile, job: JobListing | None) -> tuple[dict, list[str]]:
    """Ask the local model to improve wording only; reject any line that fails the guard."""
    warnings: list[str] = []
    allowed = profile_skill_set(p)
    payload = {"summary": content["summary"], "experience": [{"company": e["company"], "bullets": e["bullets"]} for e in content["experience"]]}
    task = (
        "Improve the wording of this candidate's CV summary and bullet points: concise, action verbs, ATS friendly. "
        "STRICT RULES: keep every fact; do not add skills, tools, numbers, employers, dates or achievements; "
        "keep the same number of bullets per company. Return JSON: "
        '{"summary": str, "experience": [{"company": str, "bullets": [str]}]}.\n'
        f"CANDIDATE PROFILE (JSON): {payload}\n"
    )
    if job is not None:
        task += wrap_untrusted("job_description", f"{job.title}\n{job.description_text}", 3000)
    try:
        out = get_ai().chat_json(SYSTEM_GUARD, task)
    except AIUnavailableError as exc:
        return content, [f"AI polish skipped: {exc.message}"]
    new_sum = str(out.get("summary", ""))
    if content["summary"] and guard_line(new_sum, content["summary"], allowed):
        content["summary"] = new_sum
    elif new_sum:
        warnings.append("AI summary rewrite rejected (added unsupported content); original kept.")
    by_company = {x.get("company"): x.get("bullets", []) for x in out.get("experience", []) if isinstance(x, dict)}
    for e in content["experience"]:
        new = by_company.get(e["company"])
        if not isinstance(new, list) or len(new) != len(e["bullets"]):
            continue
        merged = []
        for old_b, new_b in zip(e["bullets"], new):
            ok = isinstance(new_b, str) and guard_line(new_b, old_b, allowed)
            merged.append(new_b if ok else old_b)
            if not ok:
                warnings.append(f"A reworded bullet at {e['company']} was rejected by the fact guard.")
        e["bullets"] = merged
    return content, warnings


def generate_cv(
    db: Session, p: Profile, *, job: JobListing | None = None, category: str = "general",
    title: str = "", use_ai: bool = True,
) -> GeneratedCV:
    content = build_cv_content(p, job, category)
    warnings: list[str] = []
    method = "template"
    if use_ai:
        content, w = _llm_polish(content, p, job)
        warnings += w
        method = "template+llm" if not any("skipped" in x for x in w) else "template"
    problems = validate_cv(content, p)
    if problems:  # should be impossible, but never ship an unverifiable CV
        content = build_cv_content(p, job, category)
        warnings += [f"Fact guard reset content: {x}" for x in problems]
        method = "template"
    meta = content["_meta"]
    if meta["missing_keywords"]:
        warnings.append("Job asks for skills not in your profile (not added): " + ", ".join(meta["missing_keywords"]))

    job_id = job.id if job else None
    prev = db.scalar(
        select(GeneratedCV).where(GeneratedCV.profile_id == p.id, GeneratedCV.listing_id == job_id, GeneratedCV.category == category)
        .order_by(GeneratedCV.version.desc())
    )
    cv = GeneratedCV(
        profile_id=p.id, listing_id=job_id, category=category, version=(prev.version + 1) if prev else 1,
        parent_id=prev.id if prev else None, content=content, warnings=warnings, method=method,
        ats_keywords=meta["ats_keywords"],
        title=title or (f"{p.full_name} - {job.title} @ {job.company}" if job else f"{p.full_name} - {category} CV"),
    )
    db.add(cv)
    db.flush()
    from app.documents.render import render_cv

    render_cv(cv)
    return cv
