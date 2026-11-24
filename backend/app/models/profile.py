from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    headline: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    portfolio_url: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(500), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    employment_types: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    work_modes: Mapped[list] = mapped_column(JSON, default=list)  # remote/hybrid/onsite
    notice_period: Mapped[str] = mapped_column(String(100), default="")
    available_from: Mapped[str] = mapped_column(String(50), default="")
    # User-verified answers to eligibility/legal questions, e.g. {"work_authorization": "..."}.
    verified_facts: Mapped[dict] = mapped_column(JSON, default=dict)

    education: Mapped[list["Education"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Education.id"
    )
    employment: Mapped[list["Employment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Employment.id"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Skill.name"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Certification.id"
    )
    languages: Mapped[list["LanguageSkill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="LanguageSkill.id"
    )


class Education(Base):
    __tablename__ = "education"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(200), default="")
    field_of_study: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[Profile] = relationship(back_populates="education")


class Employment(Base):
    __tablename__ = "employment"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    profile: Mapped[Profile] = relationship(back_populates="employment")


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_skills_profile_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), default="technical")
    level: Mapped[str] = mapped_column(String(30), default="")
    years: Mapped[float | None] = mapped_column(nullable=True)
    profile: Mapped[Profile] = relationship(back_populates="skills")


class Certification(Base):
    __tablename__ = "certifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str] = mapped_column(String(200), default="")
    issue_date: Mapped[str] = mapped_column(String(20), default="")
    expiry_date: Mapped[str] = mapped_column(String(20), default="")
    credential_url: Mapped[str] = mapped_column(String(500), default="")
    profile: Mapped[Profile] = relationship(back_populates="certifications")


class LanguageSkill(Base):
    __tablename__ = "languages"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(80))
    proficiency: Mapped[str] = mapped_column(String(50), default="")
    profile: Mapped[Profile] = relationship(back_populates="languages")


Index("ix_education_profile_institution", Education.profile_id, Education.institution)
