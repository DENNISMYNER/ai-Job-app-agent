from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str
    identifier: str = Field(min_length=1, max_length=500)
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class SourceOut(ORM):
    id: int
    name: str
    kind: str
    identifier: str
    enabled: bool
    config: dict
    last_run_at: datetime | None
    last_status: str


class MatchOut(ORM):
    score: int
    recommendation: str
    explanation: str
    matched_skills: list
    missing_skills: list
    breakdown: dict
    method: str


class RequirementOut(ORM):
    kind: str
    text: str
    skill: str


class JobOut(ORM):
    id: int
    title: str
    company: str
    location: str
    remote_type: str
    employment_type: str
    experience_level: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    url: str
    technologies: list
    posted_at: datetime | None
    discovered_at: datetime
    injection_flags: list
    dismissed: bool
    match: MatchOut | None = None


class JobDetail(JobOut):
    description_text: str
    requirements: list[RequirementOut] = []


class ImportUrl(BaseModel):
    url: str
    company: str = ""


class ImportText(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    company: str = Field("", max_length=200)
    description: str = Field(min_length=20)
    url: str = ""
