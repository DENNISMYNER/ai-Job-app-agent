"""Cover letter generation (template baseline + optional local-LLM rewrite behind a fact guard)."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ollama import get_ai
from app.core.errors import AIUnavailableError
from app.matching.engine import compute_match, profile_skill_set, total_years
from app.matching.skills import extract_skills
from app.models import CoverLetter, JobListing, Profile
from app.security.untrusted import SYSTEM_GUARD, wrap_untrusted
from app.services import profile_service as ps
from app.services import settings_service as ss

_YEARS = re.compile(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)", re.I)


def template_letter(p: Profile, job: JobListing, match: dict) -> str:
    """Fact-only letter. Mentions only matched skills and the user's own achievements."""
    matched = match["matched_skills"][:4]
    best = None
    for e in p.employment:
        for b in (e.achievements or []):
            hit = sum(1 for s in matched if s.lower() in b.lower())
            if best is None or hit > best[0]:
                best = (hit, e, b)
    company = job.company or "your company"
    paras = [f"Dear Hiring Team at {company},"]
    opener = f"I am writing to apply for the {job.title} position at {company}."
    if p.headline:
        opener += f" I am a {p.headline.rstrip('.')}"
        opener += f" with experience in {', '.join(matched)}." if matched else "."
    paras.append(opener)
    if best:
        _, e, b = best
        paras.append(f"A highlight from my role as {e.title} at {e.company}: {b.rstrip('.')}.")
    elif p.summary:
        paras.append(p.summary)
    if matched:
        paras.append(f"The requirements of this role — {', '.join(matched)} — line up with the skills listed in my background, and I would welcome the chance to apply them at {company}.")
    paras.append("Thank you for your time and consideration. I would be glad to discuss how I can contribute.")
    paras.append(f"Kind regards,\n{p.full_name}" + (f"\n{p.email}" if p.email else "") + (f"\n{p.phone}" if p.phone else ""))
    return "\n\n".join(paras)


def validate_letter(text: str, p: Profile, job: JobListing) -> list[str]:
    problems = []
    have = profile_skill_set(p)
    for s in extract_skills(text):
        if s.lower() not in have:
            problems.append(f"claims skill not in profile: {s}")
    yrs = total_years(p)
    for m in _YEARS.finditer(text):
        if float(m.group(1)) > yrs + 0.5:
            problems.append(f"claims {m.group(1)} years of experience (profile shows {yrs})")
    return problems


def generate_letter(
    db: Session, p: Profile, job: JobListing, *, tone: str = "professional", use_ai: bool = True,
    guidance: str = "",
) -> tuple[CoverLetter, list[str]]:
    match = compute_match(job, p, ss.get_setting(db, "matching"))
    text, method, warnings = template_letter(p, job, match), "template", []
    if use_ai and ss.get_setting(db, "ai").get("enabled", True):
        facts = ps.facts_snapshot(p)
        task = (
            f"Write a personalised cover letter (max 250 words, {tone} tone, 3-4 short paragraphs, no clichés like "
            "'I am a hard-working team player'). Use ONLY facts from CANDIDATE PROFILE. Do not claim any skill, "
            "employer, certification or number of years that is not in the profile. Mention the company and role by name. "
            f"Sign off with the candidate's name. {('Extra user guidance: ' + guidance) if guidance else ''}\n"
            f"CANDIDATE PROFILE (JSON): {facts}\nMATCHED SKILLS: {match['matched_skills']}\n"
            f"COMPANY: {job.company}\nROLE: {job.title}\n"
            + wrap_untrusted("job_description", job.description_text, 3500)
        )
        try:
            draft = get_ai().chat(SYSTEM_GUARD, task, temperature=0.6)
            problems = validate_letter(draft, p, job)
            if problems or len(draft) < 120:
                warnings.append("AI draft rejected by fact guard (" + "; ".join(problems[:3]) + "); template used.")
            else:
                text, method = draft, "llm"
        except AIUnavailableError as exc:
            warnings.append(f"AI unavailable, template used: {exc.message}")
    prev = db.scalar(
        select(CoverLetter).where(CoverLetter.profile_id == p.id, CoverLetter.listing_id == job.id, CoverLetter.is_template.is_(False))
        .order_by(CoverLetter.version.desc())
    )
    letter = CoverLetter(
        profile_id=p.id, listing_id=job.id, title=f"Cover letter - {job.title} @ {job.company}",
        content=text, tone=tone, method=method, version=(prev.version + 1) if prev else 1,
    )
    db.add(letter)
    db.flush()
    from app.documents.render import render_letter_pdf

    render_letter_pdf(letter, p.full_name)
    return letter, warnings
