from __future__ import annotations

import re
from typing import Annotated

from pydantic import AnyUrl, BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORM

DATE = re.compile(r"^(\d{4}(-\d{2})?)?$")  # "", "2023", "2023-03"
Short = Annotated[str, Field(max_length=200)]


def _check_date(v: str) -> str:
    if not DATE.match(v or ""):
        raise ValueError("Use YYYY or YYYY-MM")
    return v or ""


def _check_url(v: str) -> str:
    v = (v or "").strip()
    if v and not re.match(r"^https?://", v, re.I):
        raise ValueError("URL must start with http:// or https://")
    return v


class EducationIn(BaseModel):
    institution: Short
    degree: Short = ""
    field_of_study: Short = ""
    start_date: str = ""
    end_date: str = ""
    description: str = Field("", max_length=3000)
    _d1 = field_validator("start_date", "end_date")(_check_date)


class EducationOut(EducationIn, ORM):
    id: int


class EmploymentIn(BaseModel):
    company: Short
    title: Short
    location: Short = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    description: str = Field("", max_length=5000)
    achievements: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=30)
    _d1 = field_validator("start_date", "end_date")(_check_date)


class EmploymentOut(EmploymentIn, ORM):
    id: int


class SkillIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    category: str = "technical"
    level: str = ""
    years: float | None = Field(None, ge=0, le=60)


class SkillOut(SkillIn, ORM):
    id: int


class CertificationIn(BaseModel):
    name: Short
    issuer: Short = ""
    issue_date: str = ""
    expiry_date: str = ""
    credential_url: str = ""
    _d1 = field_validator("issue_date", "expiry_date")(_check_date)
    _u = field_validator("credential_url")(_check_url)


class CertificationOut(CertificationIn, ORM):
    id: int


class LanguageIn(BaseModel):
    language: Annotated[str, Field(min_length=1, max_length=80)]
    proficiency: str = ""


class LanguageOut(LanguageIn, ORM):
    id: int


class ProfileIn(BaseModel):
    full_name: Short = ""
    email: str = ""
    phone: str = Field("", max_length=50)
    location: Short = ""
    country: str = Field("", max_length=100)
    headline: str = Field("", max_length=300)
    summary: str = Field("", max_length=4000)
    portfolio_url: str = ""
    github_url: str = ""
    linkedin_url: str = ""
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str = Field("USD", max_length=10)
    employment_types: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_modes: list[str] = Field(default_factory=list)
    notice_period: str = Field("", max_length=100)
    available_from: str = Field("", max_length=50)
    verified_facts: dict[str, str] = Field(default_factory=dict)
    education: list[EducationIn] = Field(default_factory=list)
    employment: list[EmploymentIn] = Field(default_factory=list)
    skills: list[SkillIn] = Field(default_factory=list)
    certifications: list[CertificationIn] = Field(default_factory=list)
    languages: list[LanguageIn] = Field(default_factory=list)

    _urls = field_validator("portfolio_url", "github_url", "linkedin_url")(_check_url)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("work_modes")
    @classmethod
    def _modes(cls, v: list[str]) -> list[str]:
        ok = {"remote", "hybrid", "onsite"}
        bad = [x for x in v if x not in ok]
        if bad:
            raise ValueError(f"work_modes must be among {sorted(ok)}")
        return v


class ProfileOut(ProfileIn, ORM):
    id: int
    education: list[EducationOut] = []  # type: ignore[assignment]
    employment: list[EmploymentOut] = []  # type: ignore[assignment]
    skills: list[SkillOut] = []  # type: ignore[assignment]
    certifications: list[CertificationOut] = []  # type: ignore[assignment]
    languages: list[LanguageOut] = []  # type: ignore[assignment]
