from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utcnow

STATUSES = [
    "discovered",
    "shortlisted",
    "preparing",
    "awaiting_approval",
    "applied",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
]


class JobApplication(Base, TimestampMixin):
    __tablename__ = "job_applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(300))
    job_url: Mapped[str] = mapped_column(String(1000))
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="discovered", index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("generated_cvs.id", ondelete="SET NULL"), nullable=True
    )
    cover_letter_id: Mapped[int | None] = mapped_column(
        ForeignKey("cover_letters.id", ondelete="SET NULL"), nullable=True
    )
    confirmation: Mapped[str] = mapped_column(Text, default="")
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    fill_report: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_result: Mapped[str] = mapped_column(String(20), default="")  # success|failed|incomplete|""

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.id"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    recruiters: Mapped[list["RecruiterContact"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    application: Mapped[JobApplication] = relationship(back_populates="events")


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="general")
    location: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    prep: Mapped[dict] = mapped_column(JSON, default=dict)
    application: Mapped[JobApplication] = relationship(back_populates="interviews")


class RecruiterContact(Base):
    __tablename__ = "recruiter_contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    application: Mapped[JobApplication | None] = relationship(back_populates="recruiters")


Index("ix_applications_company_position", JobApplication.company, JobApplication.position)
