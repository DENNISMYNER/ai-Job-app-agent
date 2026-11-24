"""Job <-> profile suitability scoring.

The numeric score is ALWAYS computed deterministically from structured data so that it is
reproducible and cannot be manipulated by text inside a job ad. Local embeddings (when
available) adjust the score slightly; the LLM (when available) only writes a short
explanation of the already-computed result.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ollama import cosine, get_ai
from app.core.errors import AIUnavailableError
from app.matching.extract import extract_requirements
from app.matching.skills import canonical, extract_skills
from app.models import JobListing, JobMatch, Profile
from app.security.untrusted import SYSTEM_GUARD, wrap_untrusted
from app.services import profile_service as ps
from app.services import settings_service as ss

log = logging.getLogger(__name__)
LEVEL_YEARS = {"intern": 0, "junior": 1, "mid": 3, "senior": 6}


def _months(start: str, end: str, current: bool) -> int:
    def parse(s: str, default: date) -> date:
        m = re.match(r"(\d{4})(?:-(\d{2}))?", s or "")
        return date(int(m.group(1)), int(m.group(2) or 1), 1) if m else default

    today = date.today()
    s = parse(start, today)
    e = today if current or not end else parse(end, today)
    return max(0, (e.year - s.year) * 12 + e.month - s.month)


def total_years(p: Profile) -> float:
    return round(sum(_months(e.start_date, e.end_date, e.is_current) for e in p.employment) / 12, 1)


def profile_skill_set(p: Profile) -> set[str]:
    skills = {canonical(s.name).lower() for s in p.skills}
    # Skills literally evidenced in the user's own employment text also count.
    evidence = " ".join(f"{e.title} {e.description} {' '.join(e.achievements or [])}" for e in p.employment)
    skills |= {s.lower() for s in extract_skills(evidence)}
    return skills


def _title_score(job_title: str, p: Profile, targets: list[str]) -> float:
    def toks(s: str) -> set[str]:
        return {t for t in re.findall(r"[a-z]+", s.lower()) if t not in {"the", "and", "of", "a", "an", "for", "i", "ii"}}

    jt = toks(job_title)
    refs = [*targets, p.headline, *[e.title for e in p.employment]]
    best = 0.0
    for r in refs:
        rt = toks(r)
        if rt and jt:
            best = max(best, len(jt & rt) / len(jt | rt))
    return min(1.0, best * 1.6)  # token overlap rarely hits 1.0


def _location_score(job: JobListing, p: Profile) -> tuple[float, str]:
    modes = set(p.work_modes or [])
    if job.remote_type == "remote" and (not modes or "remote" in modes):
        return 1.0, "Remote role matches your preferences"
    locs = [l.lower() for l in [*(p.preferred_locations or []), p.location, p.country] if l]
    jl = (job.location or "").lower()
    if jl and any(l in jl or jl in l for l in locs):
        return 1.0, f"Location '{job.location}' matches your preferences"
    if job.remote_type == "remote":
        return 0.4, "Remote role, but you did not list remote as a preference"
    if not jl and not job.remote_type:
        return 0.6, "Location not stated"
    return 0.2, f"Location '{job.location or job.remote_type}' is outside your preferred locations"


def compute_match(job: JobListing, p: Profile, prefs: dict) -> dict:
    ex = extract_requirements(job.title, job.description_text, job.location)
    have = profile_skill_set(p)
    req, pref = ex.required_skills, ex.preferred_skills
    matched_req = [s for s in req if s.lower() in have]
    missing_req = [s for s in req if s.lower() not in have]
    matched_pref = [s for s in pref if s.lower() in have]
    missing_pref = [s for s in pref if s.lower() not in have]

    if req or pref:
        skills = (len(matched_req) / len(req) if req else 1.0) * (0.85 if pref else 1.0)
        if pref:
            skills += 0.15 * len(matched_pref) / len(pref)
    else:
        skills = 0.5  # nothing to compare: neutral

    years = total_years(p)
    need = ex.years if ex.years is not None else LEVEL_YEARS.get(ex.level)
    if need is None:
        experience, exp_note = 0.7, "Experience level not stated"
    elif years >= need:
        experience, exp_note = 1.0, f"Your {years:g} years meet the ~{need} years asked"
    else:
        experience = max(0.0, years / need) if need else 1.0
        exp_note = f"Role asks ~{need} years; you have {years:g}"

    loc, loc_note = _location_score(job, p)
    title = _title_score(job.title, p, prefs.get("target_titles", []))
    w = prefs["weights"]
    total_w = sum(w.values()) or 1
    score = 100 * (w["skills"] * skills + w["experience"] * experience + w["location"] * loc + w["title"] * title) / total_w

    notes = [exp_note, loc_note]
    excluded = [k for k in prefs.get("excluded_keywords", []) if k and k.lower() in f"{job.title} {job.description_text}".lower()]
    if excluded:
        score = min(score, 10)
        notes.append(f"Contains excluded keyword(s): {', '.join(excluded)}")
    if job.salary_max and p.salary_min and job.salary_max < p.salary_min:
        score -= 10
        notes.append("Advertised salary is below your minimum")
    if job.injection_flags:
        notes.append("Warning: the ad contains instruction-like text, which was ignored")

    return {
        "score": int(max(0, min(100, round(score)))),
        "matched_skills": matched_req + matched_pref,
        "missing_skills": missing_req + missing_pref,
        "missing_required": missing_req,
        "breakdown": {
            "skills": round(skills * 100), "experience": round(experience * 100),
            "location": round(loc * 100), "title": round(title * 100),
            "required_total": len(req), "required_matched": len(matched_req),
            "years_required": need, "years_have": years,
        },
        "notes": notes,
    }


def recommend(score: int, prefs: dict) -> str:
    if score >= prefs["min_apply_score"]:
        return "apply"
    return "consider" if score >= prefs["min_consider_score"] else "skip"


def _explain(job: JobListing, r: dict, rec: str) -> str:
    b = r["breakdown"]
    parts = [f"Score {r['score']}/100 → {rec.upper()}."]
    if b["required_total"]:
        parts.append(f"You cover {b['required_matched']} of {b['required_total']} required skills.")
    if r["matched_skills"]:
        parts.append("Matching: " + ", ".join(r["matched_skills"][:8]) + ".")
    if r["missing_skills"]:
        parts.append("Missing: " + ", ".join(r["missing_skills"][:8]) + ".")
    parts.extend(n + "." for n in r["notes"])
    return " ".join(parts)


def _llm_explanation(job: JobListing, r: dict, rec: str) -> str | None:
    """Optional: ask the local model to phrase the verdict. It cannot change the score."""
    try:
        text = get_ai().chat(
            SYSTEM_GUARD,
            "Write 2-3 plain sentences telling the candidate whether to apply and why, using ONLY these computed facts. "
            f"Do not mention a different score.\nScore: {r['score']}\nRecommendation: {rec}\n"
            f"Matched skills: {r['matched_skills']}\nMissing skills: {r['missing_skills']}\nNotes: {r['notes']}\n"
            f"Job title (untrusted):\n{wrap_untrusted('job_title', job.title, 300)}",
        )
        return text.strip() or None
    except AIUnavailableError:
        return None


def match_listing(db: Session, job: JobListing, p: Profile, *, use_ai: bool = True) -> JobMatch:
    prefs = ss.get_setting(db, "matching")
    ai_cfg = ss.get_setting(db, "ai")
    r = compute_match(job, p, prefs)
    method = "heuristic"
    if use_ai and ai_cfg.get("enabled", True):
        if ai_cfg.get("use_embeddings", True):
            try:
                profile_text = " ".join([p.headline, p.summary, *[s.name for s in p.skills]])[:2000]
                v = get_ai().embed([profile_text, f"{job.title}\n{job.description_text[:2000]}"])
                sim = max(0.0, cosine(v[0], v[1]))
                r["score"] = int(round(0.8 * r["score"] + 0.2 * (sim * 100)))
                r["breakdown"]["semantic"] = round(sim * 100)
                method = "embedding"
            except AIUnavailableError:
                pass
    rec = recommend(r["score"], prefs)
    explanation = _explain(job, r, rec)
    if use_ai and ai_cfg.get("enabled", True):
        if (llm := _llm_explanation(job, r, rec)):
            explanation = llm + "\n\n" + explanation
            method += "+llm"
    m = db.scalar(select(JobMatch).where(JobMatch.listing_id == job.id, JobMatch.profile_id == p.id))
    if m is None:
        m = JobMatch(listing_id=job.id, profile_id=p.id)
        db.add(m)
    m.score, m.recommendation, m.explanation = r["score"], rec, explanation
    m.matched_skills, m.missing_skills, m.breakdown, m.method = r["matched_skills"], r["missing_skills"], r["breakdown"], method
    db.flush()
    return m


def match_all(db: Session, p: Profile, *, only_new: bool = False, use_ai: bool = True) -> list[JobMatch]:
    jobs = db.scalars(select(JobListing).where(JobListing.dismissed.is_(False))).all()
    done = {m.listing_id for m in db.scalars(select(JobMatch).where(JobMatch.profile_id == p.id))} if only_new else set()
    return [match_listing(db, j, p, use_ai=use_ai) for j in jobs if j.id not in done]
