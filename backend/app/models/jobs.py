from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utcnow


class JobSource(Base, TimestampMixin):
    __tablename__ = "job_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # greenhouse|lever|rss|career_page|manual
    identifier: Mapped[str] = mapped_column(String(500))  # board token, feed URL, page URL
    enabled: Mapped[bool] = mapped_column(default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(300), default="")

    listings: Mapped[list["JobListing"]] = relationship(back_populates="source")
    __table_args__ = (UniqueConstraint("kind", "identifier", name="uq_job_sources_kind_identifier"),)


class JobListing(Base):
    __tablename__ = "job_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    remote_type: Mapped[str] = mapped_column(String(20), default="")  # remote|hybrid|onsite|""
    employment_type: Mapped[str] = mapped_column(String(30), default="")
    experience_level: Mapped[str] = mapped_column(String(30), default="")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="")
    url: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(1000), unique=True)
    description_text: Mapped[str] = mapped_column(Text, default="")
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    injection_flags: Mapped[list] = mapped_column(JSON, default=list)
    dismissed: Mapped[bool] = mapped_column(default=False)

    source: Mapped[JobSource | None] = relationship(back_populates="listings")
    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    matches: Mapped[list["JobMatch"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_job_listings_source_external"),
        Index("ix_job_listings_company_title", "company", "title"),
        Index("ix_job_listings_posted_at", "posted_at"),
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # required|preferred|experience
    text: Mapped[str] = mapped_column(Text)
    skill: Mapped[str] = mapped_column(String(100), default="")
    listing: Mapped[JobListing] = relationship(back_populates="requirements")


class JobMatch(Base):
    __tablename__ = "job_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(String(20))  # apply|consider|skip
    explanation: Mapped[str] = mapped_column(Text, default="")
    matched_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    method: Mapped[str] = mapped_column(String(30), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing: Mapped[JobListing] = relationship(back_populates="matches")
    __table_args__ = (
        UniqueConstraint("listing_id", "profile_id", name="uq_job_matches_listing_profile"),
        Index("ix_job_matches_score", "score"),
    )
