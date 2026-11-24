"""Interview preparation: questions, exercises, STAR guidance, company notes.

Everything is built from the user's real profile and the job ad. Suggested answers use ONLY the
user's own achievements; the model (optional) may add extra questions but never facts.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.ollama import get_ai
from app.core.errors import AIUnavailableError
from app.documents.letters import validate_letter
from app.matching.engine import compute_match
from app.matching.extract import extract_requirements
from app.models import Interview, JobApplication, JobListing, Profile
from app.security.untrusted import SYSTEM_GUARD, wrap_untrusted
from app.services import settings_service as ss

log = logging.getLogger(__name__)

BEHAVIORAL = [
    "Tell me about a time you had to learn something quickly.",
    "Describe a challenge you faced at work and how you handled it.",
    "Tell me about a time you worked in a team to deliver something.",
    "Describe a mistake you made and what you learned from it.",
    "Tell me about a time you disagreed with a colleague or manager.",
]
EXERCISES = {
    "Python": "Write a function that groups a list of log lines by severity and returns counts; add unit tests.",
    "React": "Build a searchable, paginated list component that fetches from an API with loading and error states.",
    "TypeScript": "Model a form's state with discriminated unions and write a type-safe reducer.",
    "SQL": "Given orders and customers tables, write a query for the top 3 customers by revenue per month.",
    "PostgreSQL": "Design a schema for a booking system and explain which indexes you would add and why.",
    "Docker": "Write a Dockerfile and docker-compose.yml for an API plus database; explain your layer caching choices.",
    "JavaScript": "Implement debounce and explain closures and the event loop with an example.",
    "Node.js": "Build a small REST endpoint with validation and error handling; discuss how you would test it.",
    "Git": "Explain how you would resolve a merge conflict and undo a bad commit on a shared branch.",
    "Customer Support": "Role-play: an angry customer reports a recurring outage. Walk through triage, communication and follow-up.",
    "Sales": "Pitch a product you know well to a sceptical buyer; handle the objection 'it is too expensive'.",
}


def _star_for(p: Profile) -> list[dict]:
    """STAR scaffolds seeded with the user's REAL achievements; blanks are for the user to fill."""
    out = []
    for e in p.employment:
        for b in (e.achievements or [])[:2]:
            out.append({
                "situation": f"My role as {e.title} at {e.company}.",
                "task": "(Add: what you were responsible for.)",
                "action": b,
                "result": "(Add: the measurable outcome, if you have one.)",
            })
    return out[:4]


def generate_prep(db: Session, app: JobApplication, p: Profile, job: JobListing | None, *, use_ai: bool = True) -> dict:
    ex = extract_requirements(job.title if job else app.position, job.description_text if job else "", job.location if job else "")
    have = {s.name.lower() for s in p.skills}
    skills = (ex.required_skills + ex.preferred_skills)[:8]
    tech_q = [f"How have you used {s} in your projects? Walk me through a concrete example." if s.lower() in have
              else f"The role uses {s}, which is not in your CV. How would you get up to speed?" for s in skills]
    tech_q += ["Walk me through a project you are proud of, including trade-offs you made.",
               "How do you debug a problem you have never seen before?"]
    exercises = [{"skill": s, "exercise": EXERCISES[s]} for s in skills if s in EXERCISES][:5]
    star = _star_for(p)
    behavioral = [{"question": q, "star_guidance": "Situation → Task → Action → Result. Keep it to ~90 seconds and quantify the result.",
                   "suggested_basis": star[i % len(star)] if star else None} for i, q in enumerate(BEHAVIORAL)]
    gaps = compute_match(job, p, ss.get_setting(db, "matching"))["missing_skills"] if job else []
    research = {
        "source": "Job advertisement only (no web lookup was performed).",
        "company": app.company, "role": app.position,
        "what_they_ask_for": ex.required_skills, "nice_to_have": ex.preferred_skills,
        "seniority": ex.level or "not stated", "work_mode": (job.remote_type if job else "") or "not stated",
        "to_research_yourself": ["Products and customers", "Recent news and funding", "Engineering blog / tech stack", "Team and interviewers on LinkedIn"],
        "gaps_to_prepare": gaps,
    }
    prep = {"company_research": research, "technical_questions": tech_q, "technical_exercises": exercises,
            "behavioral": behavioral,
            "questions_to_ask_them": ["What does success look like in the first 90 days?", "How is work reviewed and deployed here?", "How does the team handle on-call and learning time?"]}
    if use_ai and job is not None:
        try:
            out = get_ai().chat_json(SYSTEM_GUARD,
                "Suggest 5 additional likely interview questions for this role as JSON {\"questions\": [str]}. Questions only, no answers.\n"
                + wrap_untrusted("job_description", f"{job.title}\n{job.description_text}", 3000))
            extra = [q.strip() for q in out.get("questions", []) if isinstance(q, str) and 10 < len(q) < 300 and q.strip().endswith("?")]
            prep["ai_questions"] = extra[:5]
        except AIUnavailableError:
            prep["ai_questions"] = []
    return prep


def save_prep(db: Session, app: JobApplication, prep: dict, interview_id: int | None = None) -> Interview:
    iv = db.get(Interview, interview_id) if interview_id else None
    if iv is None:
        iv = Interview(application_id=app.id, kind="preparation")
        db.add(iv)
    iv.prep = prep
    db.flush()
    return iv
