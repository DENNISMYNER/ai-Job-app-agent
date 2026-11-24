"""Field mapping: detected form field -> action + value, from verified profile data only.

Every decision is deterministic and explainable. The model (if any) is only consulted for
free-text *open questions*, and sensitive/legal questions always become ``ask``.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.applications import answers as ans
from app.models import JobListing, Profile

COUNTRY_ALIASES = {"united states": ["usa", "us", "united states of america"], "united kingdom": ["uk", "great britain"]}


@dataclass
class FieldPlan:
    field_id: str
    label: str
    kind: str
    required: bool
    action: str  # fill | select | check | upload_cv | upload_letter | ask | skip
    value: str = ""
    source: str = ""
    status: str = "ok"  # ok | review | needs_user
    reason: str = ""
    option_id: str = ""  # radio: the chosen option's element id

    def dict(self) -> dict:
        return asdict(self)


def _text(f: dict) -> str:
    return " ".join(x for x in [f.get("label", ""), f.get("name", ""), f.get("placeholder", "")] if x).lower()


def _match_option(options: list[dict], wanted: str) -> dict | None:
    w = wanted.strip().lower()
    if not w:
        return None
    for o in options:
        if o["label"].strip().lower() == w or str(o.get("value", "")).lower() == w:
            return o
    for o in options:
        ol = o["label"].strip().lower()
        if ol and (w in ol or ol in w):
            return o
    for canon, aliases in COUNTRY_ALIASES.items():
        if w == canon or w in aliases:
            for o in options:
                if o["label"].strip().lower() in [canon, *aliases]:
                    return o
    return None


def plan_field(f: dict, p: Profile, db: Session, job: JobListing | None, *, has_cv: bool, has_letter: bool, use_ai: bool) -> FieldPlan:
    kind, text = f["kind"], _text(f)
    base = dict(field_id=f["id"], label=f.get("label") or f.get("placeholder") or f.get("name") or "(unlabelled)", kind=kind, required=f["required"])

    # ---- file uploads
    if kind == "file":
        if re.search(r"cover ?letter", text):
            return FieldPlan(**base, action="upload_letter" if has_letter else "skip", source="cover_letter",
                             status="ok" if has_letter else ("needs_user" if f["required"] else "ok"),
                             reason="" if has_letter else "No cover letter prepared")
        if re.search(r"resume|\bcv\b|curriculum", text):
            return FieldPlan(**base, action="upload_cv" if has_cv else "skip", source="cv",
                             status="ok" if has_cv else ("needs_user" if f["required"] else "ok"),
                             reason="" if has_cv else "No CV prepared")
        return FieldPlan(**base, action="ask", status="needs_user" if f["required"] else "ok",
                         reason="Unrecognised file upload - please attach it yourself." if f["required"] else "Optional upload left empty")

    # ---- checkboxes are almost always consent/legal -> user decides
    if kind == "checkbox":
        return FieldPlan(**base, action="ask", status="needs_user" if f["required"] or ans.classify(text) else "ok",
                         reason="Consent / agreement checkboxes must be ticked by you." if f["required"] or ans.classify(text) else "Optional checkbox left unchanged")

    # ---- question text for classification
    question = f.get("label") or f.get("placeholder") or f.get("name") or ""
    cat = ans.classify(question)
    if cat:
        return FieldPlan(**base, action="ask", status="needs_user", source=cat,
                         reason=f"{cat.title()} question - never guessed. Please answer it yourself.")

    # ---- direct profile fields (deterministic)
    result = ans.answer_question(db, question, p, job, use_ai=use_ai) if question else None
    if result is None or result.status == "needs_user":
        return FieldPlan(**base, action="ask", status="needs_user" if f["required"] else "ok",
                         reason=(result.reason if result else "Field has no readable label") if f["required"] else "Optional; left blank")

    value, src, status = result.answer, result.source, ("ok" if result.status == "answered" else "review")
    if kind in {"select", "radio"}:
        opts = f["options"]
        opt = _match_option(opts, value)
        if opt is None:
            return FieldPlan(**base, action="ask", status="needs_user" if f["required"] else "ok", source=src,
                             reason=f"No option matches '{value}'. Please choose.")
        return FieldPlan(**base, action="select" if kind == "select" else "check", value=opt["label"], option_id=opt.get("id", ""), source=src, status=status)
    if kind == "date" and not re.match(r"\d{4}-\d{2}-\d{2}$", value):
        return FieldPlan(**base, action="ask", status="needs_user" if f["required"] else "ok", reason="Date format cannot be derived safely.")
    if kind == "number":
        m = re.search(r"\d[\d,]*", value)
        if not m:
            return FieldPlan(**base, action="ask", status="needs_user" if f["required"] else "ok", reason="Needs a number.")
        value = m.group(0).replace(",", "")
    return FieldPlan(**base, action="fill", value=value, source=src, status=status, reason=result.reason)


def plan_page(fields: list[dict], p: Profile, db: Session, job: JobListing | None, *, has_cv: bool, has_letter: bool, use_ai: bool = True) -> list[FieldPlan]:
    return [plan_field(f, p, db, job, has_cv=has_cv, has_letter=has_letter, use_ai=use_ai) for f in fields]
