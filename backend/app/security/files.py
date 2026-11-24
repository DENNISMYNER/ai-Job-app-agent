"""Upload validation and path-traversal protection."""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import SecurityError, ValidationFailed

ALLOWED = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        b"PK\x03\x04",
    ),
}


def safe_filename(name: str) -> str:
    """Strip any directory components and unsafe characters."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base[:120] or "file"


def validate_upload(filename: str, data: bytes) -> tuple[str, str]:
    """Validate extension, size and magic bytes. Returns (extension, mime)."""
    s = get_settings()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValidationFailed("Only PDF and DOCX files are supported.")
    if not data:
        raise ValidationFailed("The uploaded file is empty.")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ValidationFailed(f"File exceeds the {s.max_upload_mb} MB limit.")
    mime, magic = ALLOWED[ext]
    if not data.startswith(magic):
        raise ValidationFailed("File content does not match its extension.")
    return ext, mime


def store_upload(data: bytes, filename: str, subdir: str = "uploads") -> tuple[Path, str]:
    """Persist bytes under documents_dir with a random name. Returns (path, sha256)."""
    ext, _ = validate_upload(filename, data)
    target_dir = resolve_inside(get_settings().documents_dir, subdir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def resolve_inside(base: Path, *parts: str) -> Path:
    """Join ``parts`` to ``base`` and make sure the result cannot escape ``base``."""
    base_r = base.resolve()
    candidate = base_r.joinpath(*parts).resolve()
    if candidate != base_r and base_r not in candidate.parents:
        raise SecurityError("Path escapes the permitted directory.")
    return candidate
