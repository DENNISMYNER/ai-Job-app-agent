from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.documents.parsing import extract_text
from app.models import Document
from app.schemas.common import ORM, Message
from app.security.files import resolve_inside, safe_filename, store_upload
from app.services import profile_service as ps

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentOut(ORM):
    id: int
    kind: str
    filename: str
    mime: str
    size: int
    sha256: str


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DB, kind: str | None = None):
    q = select(Document).order_by(Document.id.desc())
    if kind:
        q = q.where(Document.kind == kind)
    return db.scalars(q).all()


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(db: DB, file: UploadFile = File(...), kind: str = Form("cv")):
    if kind not in {"cv", "cover_letter", "other"}:
        kind = "other"
    data = await file.read()
    path, sha = store_upload(data, file.filename or "document.pdf")
    profile = ps.get_profile(db)
    doc = Document(
        profile_id=profile.id if profile else None,
        kind=kind,
        filename=safe_filename(file.filename or "document"),
        stored_path=path.name,
        mime="application/pdf" if path.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=len(data),
        sha256=sha,
        extracted_text=extract_text(path),
    )
    db.add(doc)
    db.flush()
    return doc


def _doc_path(doc: Document) -> Path:
    return resolve_inside(get_settings().documents_dir, "uploads", doc.stored_path)


@router.get("/{doc_id}/download")
def download(doc_id: int, db: DB):
    doc = db.get(Document, doc_id)
    if not doc:
        raise NotFoundError("Document not found")
    return FileResponse(_doc_path(doc), media_type=doc.mime, filename=doc.filename)


@router.delete("/{doc_id}", response_model=Message)
def delete_document(doc_id: int, db: DB):
    doc = db.get(Document, doc_id)
    if not doc:
        raise NotFoundError("Document not found")
    _doc_path(doc).unlink(missing_ok=True)
    db.delete(doc)
    return Message(message="Document deleted")
