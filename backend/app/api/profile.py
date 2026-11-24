from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import delete

from app.api.deps import DB
from app.core.errors import NotFoundError
from app.documents.parsing import extract_profile_draft, extract_text
from app.models import Document
from app.schemas.common import Message
from app.schemas.profile import ProfileIn, ProfileOut
from app.security.files import store_upload
from app.services import profile_service as ps
from app.services.activity import log_activity

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut | None)
def read_profile(db: DB):
    return ps.get_profile(db)


@router.put("", response_model=ProfileOut)
def save_profile(data: ProfileIn, db: DB):
    p = ps.upsert_profile(db, data)
    log_activity(db, "profile", "saved", "Profile saved")
    return p


@router.delete("", response_model=Message)
def remove_profile(db: DB):
    ps.delete_profile(db)
    log_activity(db, "profile", "deleted", "Profile deleted")
    return Message(message="Profile deleted")


@router.post("/import-cv")
async def import_cv(db: DB, file: UploadFile = File(...)):
    """Extract a *draft* profile from a CV. Nothing is saved until the user reviews it."""
    data = await file.read()
    path, sha = store_upload(data, file.filename or "cv.pdf", "imports")
    try:
        text = extract_text(path)
        draft = extract_profile_draft(text)
    finally:
        path.unlink(missing_ok=True)  # the draft flow does not retain the file
    return {"draft": draft, "characters_read": len(text), "note": "Review before saving; nothing was invented."}
