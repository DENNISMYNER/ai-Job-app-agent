from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow


class Document(Base):
    """An uploaded file (CV, cover letter, other)."""

    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="cv")
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GeneratedCV(Base, TimestampMixin):
    __tablename__ = "generated_cvs"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("generated_cvs.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(80), default="general")
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf_path: Mapped[str] = mapped_column(String(500), default="")
    docx_path: Mapped[str] = mapped_column(String(500), default="")
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    ats_keywords: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(30), default="template")


class CoverLetter(Base, TimestampMixin):
    __tablename__ = "cover_letters"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    is_template: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    tone: Mapped[str] = mapped_column(String(30), default="professional")
    method: Mapped[str] = mapped_column(String(30), default="template")
    pdf_path: Mapped[str] = mapped_column(String(500), default="")


class ApplicationAnswer(Base, TimestampMixin):
    __tablename__ = "application_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    normalized_question: Mapped[str] = mapped_column(String(300), index=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="general")
    approved: Mapped[bool] = mapped_column(default=False)
    sensitive: Mapped[bool] = mapped_column(default=False)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="user")  # user|ai|profile


Index("ix_answers_approved", ApplicationAnswer.approved)
