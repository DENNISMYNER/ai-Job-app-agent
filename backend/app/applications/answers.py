"""Application question answering.

Order of precedence (never guess):
1. Sensitive / legal / demographic question  -> ``needs_user`` (or a user-verified fact, flagged for review)
2. Deterministic fact from the profile      -> ``answered`` (salary, notice, contact, links, years...)
3. Previously APPROVED answer (fuzzy match) -> ``answered``
4. Open-ended question                      -> ``draft`` generated from verified profile (needs approval)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ollama import get_ai
from app.core.errors import AIUnavailableError
from app.matching.engine import profile_skill_set, total_years
from app.matching.skills import extract_skills
from app.models import ApplicationAnswer, JobListing, Profile
from app.security.untrusted import SYSTEM_GUARD, wrap_untrusted
from app.services import profile_service as ps

SENSITIVE = [
    (r"\b(gender|sex|pronouns?)\b", "demographic"),
    (r"\b(race|racial|ethnic\w*|hispanic|latino)\b", "demographic"),
    (r"\b(disabilit\w*|disabled|handicap\w*|chronic|medical condition)\b", "demographic"),
    (r"\b(veteran|military service)\b", "demographic"),
    (r"\b(sexual orientation|lgbt\w*|transgender)\b", "demographic"),
    (r"\b(religio\w*|political)\b", "demographic"),
    (r"\b(date of birth|birth ?date|\bage\b|how old)\b", "demographic"),
    (r"\b(marital|married|children|pregnan\w*)\b", "demographic"),
    (r"\b(criminal|convict\w*|felony|arrest\w*|background check)\b", "legal"),
    (r"\b(authori[sz]ed to work|work authori[sz]ation|right to work|visa|sponsorship|citizen\w*|work permit|immigration)\b", "eligibility"),
    (r"\b(non-?compete|conflict of interest|security clearance)\b", "legal"),
    (r"\b(i (agree|certify|consent|acknowledge|confirm)|terms and conditions|privacy policy|declaration)\b", "legal"),
    (r"\b(social security|ssn|national id|id number|passport|tax id|bank)\b", "identity"),
]
_STOP = {"the", "a", "an", "of", "to", "is", "are", "do", "you", "your", "our", "we", "us", "in", "for", "this", "that", "and", "or", "please", "describe", "tell", "what", "why", "how", "with", "at", "on", "be", "can", "will", "would"}


def normalize_question(q: str) -> str:
    toks = [t for t in re.findall(r"[a-z0-9+#.]+", q.lower()) if t not in _STOP]
    return " ".join(toks)[:300]


def _jaccard(a: str, b: str) -> float:
    x, y = set(a.split()), set(b.split())
    return len(x & y) / len(x | y) if x and y else 0.0


def classify(question: str) -> str | None:
    low = question.lower()
    for pat, cat in SENSITIVE:
        if re.search(pat, low):
            return cat
    return None


@dataclass
class AnswerResult:
    status: str  # answered | draft | needs_user | review
    answer: str = ""
    source: str = ""
    category: str = "general"
    reason: str = ""
    answer_id: int | None = None
    warnings: list[str] = field(default_factory=list)


def _fact_answer(q: str, p: Profile) -> tuple[str, str] | None:
    low = q.lower()
    f = ps.facts_snapshot(p)
    rules: list[tuple[str, str, str]] = [
        (r"\b(first name)\b", p.full_name.split(" ")[0] if p.full_name else "", "profile"),
        (r"\b(last name|surname|family name)\b", p.full_name.split(" ")[-1] if p.full_name else "", "profile"),
        (r"\b(full name|your name|legal name)\b", p.full_name, "profile"),
        (r"\b(e-?mail)\b", p.email, "profile"),
        (r"\b(phone|mobile|telephone|contact number)\b", p.phone, "profile"),
        (r"\b(linkedin)\b", p.linkedin_url, "profile"),
        (r"\b(github)\b", p.github_url, "profile"),
        (r"\b(portfolio|website|personal site)\b", p.portfolio_url, "profile"),
        (r"\b(notice period)\b", p.notice_period, "profile"),
        (r"\b(when can you start|start date|available to start|availability|earliest)\b", p.available_from or p.notice_period, "profile"),
        (r"\b(current location|where are you (based|located)|city|location)\b", ", ".join(x for x in [p.location, p.country] if x), "profile"),
        (r"\b(country)\b", p.country, "profile"),
    ]
    sal = f["salary"]
    if re.search(r"\b(salary|compensation|pay)\b.*\b(expect\w*|desired|requirement)|\bexpected (salary|compensation)\b|\bsalary expectations?\b", low):
        if sal["min"] and sal["max"]:
            return f"{sal['min']:,}–{sal['max']:,} {sal['currency']}", "profile"
        if sal["min"] or sal["max"]:
            return f"{(sal['min'] or sal['max']):,} {sal['currency']}", "profile"
        return None  # never invent a salary
    for pat, val, src in rules:
        if re.search(pat, low) and val:
            return val, src
    m = re.search(r"years? of (?:professional |work )?experience", low)
    if m and not extract_skills(q):
        yrs = total_years(p)
        return (f"{yrs:g}", "profile") if p.employment else None
    return None


def _skill_experience(q: str, p: Profile) -> AnswerResult | None:
    if not re.search(r"\b(experience|familiar|proficien\w*|worked|used|knowledge|skilled)\b", q.lower()):
        return None
    techs = extract_skills(q)
    if not techs:
        return None
    have = profile_skill_set(p)
    by_name = {s.name.lower(): s for s in p.skills}
    t = techs[0]
    if t.lower() in have:
        s = by_name.get(t.lower())
        yrs = f" ({s.years:g} years)" if s and s.years else ""
        if re.search(r"how many years|years of", q.lower()):
            if s and s.years:
                return AnswerResult("answered", f"{s.years:g}", "profile", "skill")
            return AnswerResult("needs_user", category="skill", reason=f"Your profile lists {t} but not how many years; please enter it.")
        return AnswerResult("answered", f"Yes{yrs}", "profile", "skill")
    return AnswerResult("draft", f"No professional experience with {t} is listed in my profile.", "profile", "skill",
                        reason="Not in your profile — confirm before submitting.")


def find_approved(db: Session, question: str) -> ApplicationAnswer | None:
    norm = normalize_question(question)
    best, best_score = None, 0.0
    for a in db.scalars(select(ApplicationAnswer).where(ApplicationAnswer.approved.is_(True), ApplicationAnswer.sensitive.is_(False))):
        score = 1.0 if a.normalized_question == norm else _jaccard(norm, a.normalized_question)
        if score > best_score:
            best, best_score = a, score
    return best if best_score >= 0.8 else None


def _llm_draft(question: str, p: Profile, job: JobListing | None) -> str | None:
    task = (
        "Answer this job-application question in first person, 60-150 words, plain and specific. "
        "Use ONLY facts from CANDIDATE PROFILE; never invent employers, skills, numbers or achievements. "
        "If the profile lacks the information, say what is available instead.\n"
        f"CANDIDATE PROFILE (JSON): {ps.facts_snapshot(p)}\n"
        f"QUESTION (untrusted form text): {wrap_untrusted('form_question', question, 600)}\n"
    )
    if job:
        task += f"COMPANY: {job.company}\nROLE: {job.title}\n" + wrap_untrusted("job_description", job.description_text, 2500)
    try:
        text = get_ai().chat(SYSTEM_GUARD, task, temperature=0.5).strip()
    except AIUnavailableError:
        return None
    from app.documents.letters import validate_letter  # same fact guard as letters

    if validate_letter(text, p, job):  # type: ignore[arg-type]
        return None
    return text or None


def _template_draft(question: str, p: Profile, job: JobListing | None) -> str:
    low = question.lower()
    skills = ", ".join(s.name for s in p.skills[:6])
    latest = p.employment[0] if p.employment else None
    if re.search(r"about yourself|introduce yourself|tell us about you", low):
        base = p.summary or f"I am {p.full_name}" + (f", a {p.headline}" if p.headline else "")
        return base + (f" My main skills include {skills}." if skills else "")
    if re.search(r"why .*(work|join|apply|interested)|why us|why this (company|role)", low) and job:
        return f"The {job.title} role at {job.company} fits my background" + (f" in {skills}" if skills else "") + ". I would like to contribute to your team and keep growing in this field."
    if re.search(r"why should we hire|what makes you", low):
        return "I bring " + (f"hands-on experience with {skills}" if skills else "relevant experience") + (f" and practical work as {latest.title} at {latest.company}" if latest else "") + "."
    if re.search(r"strength", low):
        return f"My strengths are my practical skills in {skills}." if skills else ""
    if re.search(r"relevant experience|describe your experience|work experience", low) and latest:
        ach = "; ".join((latest.achievements or [])[:2])
        return f"As {latest.title} at {latest.company}" + (f": {ach}." if ach else ".")
    return ""  # unrecognised question: never pad with unrelated profile text


def answer_question(db: Session, question: str, p: Profile, job: JobListing | None = None, use_ai: bool = True) -> AnswerResult:
    question = question.strip()
    if (cat := classify(question)):
        # A fact the user explicitly verified in their profile may be offered - but never auto-filled.
        key = {"eligibility": "work_authorization"}.get(cat)
        vf = (p.verified_facts or {}).get(key or "", "")
        if vf:
            return AnswerResult("review", vf, "verified_fact", cat, "Taken from your verified facts - please confirm.")
        return AnswerResult("needs_user", category=cat, reason="Sensitive/legal/eligibility question: the agent never guesses these. Please answer it yourself.")
    if (hit := _fact_answer(question, p)):
        return AnswerResult("answered", hit[0], hit[1], "fact")
    if (sk := _skill_experience(question, p)):
        return sk
    if (approved := find_approved(db, question)):
        approved.times_used += 1
        return AnswerResult("answered", approved.answer, "approved", approved.category, answer_id=approved.id)
    draft = _llm_draft(question, p, job) if use_ai else None
    if draft:
        res = AnswerResult("draft", draft, "ai", "open", "AI draft from your profile - review and approve.")
    else:
        text = _template_draft(question, p, job)
        if not text:
            return AnswerResult("needs_user", category="open", reason="Not enough verified profile data to answer this.")
        res = AnswerResult("draft", text, "template", "open", "Draft from your profile - review and approve.")
    return res


def save_answer(db: Session, question: str, answer: str, *, approved: bool, source: str = "user", category: str = "general") -> ApplicationAnswer:
    norm = normalize_question(question)
    sensitive = classify(question) is not None
    row = db.scalar(select(ApplicationAnswer).where(ApplicationAnswer.normalized_question == norm))
    if row is None:
        row = ApplicationAnswer(question=question, normalized_question=norm)
        db.add(row)
    row.answer, row.approved, row.source, row.category, row.sensitive = answer, approved, source, category, sensitive
    db.flush()
    return row
