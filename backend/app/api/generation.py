"""CV, cover-letter and application-answer endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB
from app.applications import answers as ans
from app.core.errors import NotFoundError, ValidationFailed
from app.documents import cv as cvmod
from app.documents import letters
from app.documents.render import generated_file, render_cv, render_letter_pdf
from app.jobs.service import get_listing
from app.models import ApplicationAnswer, CoverLetter, GeneratedCV
from app.schemas.common import ORM, Message
from app.services import profile_service as ps

router = APIRouter(tags=["generation"])


# -------------------------------------------------------------------- CVs
class CVOut(ORM):
    id: int
    listing_id: int | None
    parent_id: int | None
    category: str
    version: int
    title: str
    content: dict
    warnings: list
    ats_keywords: list
    method: str
    pdf_path: str
    docx_path: str


class CVRequest(BaseModel):
    listing_id: int | None = None
    category: str = Field("general", max_length=80)
    title: str = ""
    use_ai: bool = True


@router.post("/cvs", response_model=CVOut, status_code=201)
def create_cv(body: CVRequest, db: DB):
    p = ps.require_profile(db)
    job = get_listing(db, body.listing_id) if body.listing_id else None
    return cvmod.generate_cv(db, p, job=job, category=body.category, title=body.title, use_ai=body.use_ai)


@router.get("/cvs", response_model=list[CVOut])
def list_cvs(db: DB, listing_id: int | None = None):
    q = select(GeneratedCV).order_by(GeneratedCV.id.desc())
    if listing_id:
        q = q.where(GeneratedCV.listing_id == listing_id)
    return db.scalars(q).all()


def _cv(db, cv_id: int) -> GeneratedCV:
    cv = db.get(GeneratedCV, cv_id)
    if not cv:
        raise NotFoundError("CV not found")
    return cv


@router.get("/cvs/{cv_id}", response_model=CVOut)
def get_cv(cv_id: int, db: DB):
    return _cv(db, cv_id)


@router.put("/cvs/{cv_id}", response_model=CVOut)
def edit_cv(cv_id: int, content: dict, db: DB):
    """Save a manual edit as a NEW version; the fact guard still applies."""
    old = _cv(db, cv_id)
    p = ps.require_profile(db)
    new_content = {**old.content, **{k: v for k, v in content.items() if k in {"summary", "skills", "experience", "headline"}}}
    problems = cvmod.validate_cv(new_content, p)
    if problems:
        raise ValidationFailed("Edit contains content that is not in your profile.", detail={"problems": problems})
    cv = GeneratedCV(profile_id=p.id, listing_id=old.listing_id, parent_id=old.id, category=old.category,
                     version=old.version + 1, title=old.title, content=new_content, warnings=old.warnings,
                     ats_keywords=old.ats_keywords, method="manual")
    db.add(cv)
    db.flush()
    render_cv(cv)
    return cv


@router.get("/cvs/{cv_id}/download/{fmt}")
def download_cv(cv_id: int, fmt: str, db: DB):
    cv = _cv(db, cv_id)
    if fmt not in {"pdf", "docx"}:
        raise ValidationFailed("Format must be pdf or docx")
    name = cv.pdf_path if fmt == "pdf" else cv.docx_path
    media = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(generated_file(name), media_type=media, filename=f"CV_v{cv.version}.{fmt}")


@router.delete("/cvs/{cv_id}", response_model=Message)
def delete_cv(cv_id: int, db: DB):
    cv = _cv(db, cv_id)
    for n in (cv.pdf_path, cv.docx_path):
        if n:
            generated_file(n).unlink(missing_ok=True)
    db.delete(cv)
    return Message(message="CV deleted")


# ---------------------------------------------------------- cover letters
class LetterOut(ORM):
    id: int
    listing_id: int | None
    title: str
    content: str
    is_template: bool
    version: int
    tone: str
    method: str


class LetterRequest(BaseModel):
    listing_id: int
    tone: str = "professional"
    use_ai: bool = True
    guidance: str = Field("", max_length=500)


class LetterEdit(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    title: str | None = None


@router.post("/cover-letters", status_code=201)
def create_letter(body: LetterRequest, db: DB):
    p = ps.require_profile(db)
    letter, warnings = letters.generate_letter(db, p, get_listing(db, body.listing_id), tone=body.tone, use_ai=body.use_ai, guidance=body.guidance)
    return {"letter": LetterOut.model_validate(letter), "warnings": warnings}


@router.get("/cover-letters", response_model=list[LetterOut])
def list_letters(db: DB):
    return db.scalars(select(CoverLetter).order_by(CoverLetter.id.desc())).all()


def _letter(db, lid: int) -> CoverLetter:
    obj = db.get(CoverLetter, lid)
    if not obj:
        raise NotFoundError("Cover letter not found")
    return obj


@router.put("/cover-letters/{lid}", response_model=LetterOut)
def edit_letter(lid: int, body: LetterEdit, db: DB):
    letter = _letter(db, lid)
    letter.content = body.content
    if body.title:
        letter.title = body.title
    letter.method = "manual"
    p = ps.get_profile(db)
    render_letter_pdf(letter, p.full_name if p else "")
    return letter


@router.post("/cover-letters/templates", response_model=LetterOut, status_code=201)
def create_template(body: LetterEdit, db: DB):
    p = ps.require_profile(db)
    t = CoverLetter(profile_id=p.id, title=body.title or "Template", content=body.content, is_template=True, method="manual")
    db.add(t)
    db.flush()
    return t


@router.get("/cover-letters/{lid}/download")
def download_letter(lid: int, db: DB):
    letter = _letter(db, lid)
    if not letter.pdf_path:
        p = ps.get_profile(db)
        render_letter_pdf(letter, p.full_name if p else "")
    return FileResponse(generated_file(letter.pdf_path), media_type="application/pdf", filename=f"cover_letter_{lid}.pdf")


@router.delete("/cover-letters/{lid}", response_model=Message)
def delete_letter(lid: int, db: DB):
    db.delete(_letter(db, lid))
    return Message(message="Cover letter deleted")


# ---------------------------------------------------------------- answers
class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    listing_id: int | None = None
    use_ai: bool = True


class SaveAnswer(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    answer: str = Field(max_length=4000)
    approved: bool = True


class AnswerOut(ORM):
    id: int
    question: str
    answer: str
    category: str
    approved: bool
    sensitive: bool
    times_used: int
    source: str


@router.post("/answers/ask")
def ask(body: AskBody, db: DB):
    p = ps.require_profile(db)
    job = get_listing(db, body.listing_id) if body.listing_id else None
    return ans.answer_question(db, body.question, p, job, use_ai=body.use_ai).__dict__


@router.post("/answers", response_model=AnswerOut, status_code=201)
def save(body: SaveAnswer, db: DB):
    return ans.save_answer(db, body.question, body.answer, approved=body.approved)


@router.get("/answers", response_model=list[AnswerOut])
def list_answers(db: DB, approved: bool | None = None):
    q = select(ApplicationAnswer).order_by(ApplicationAnswer.id.desc())
    if approved is not None:
        q = q.where(ApplicationAnswer.approved.is_(approved))
    return db.scalars(q).all()


@router.patch("/answers/{aid}", response_model=AnswerOut)
def edit_answer(aid: int, patch: dict, db: DB):
    row = db.get(ApplicationAnswer, aid)
    if not row:
        raise NotFoundError("Answer not found")
    if "answer" in patch:
        row.answer = str(patch["answer"])[:4000]
    if "approved" in patch:
        row.approved = bool(patch["approved"])
    return row


@router.delete("/answers/{aid}", response_model=Message)
def delete_answer(aid: int, db: DB):
    row = db.get(ApplicationAnswer, aid)
    if not row:
        raise NotFoundError("Answer not found")
    db.delete(row)
    return Message(message="Answer deleted")
