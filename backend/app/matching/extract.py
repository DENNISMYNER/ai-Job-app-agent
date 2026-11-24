"""Deterministic extraction of requirements from a job description."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.matching.skills import detect_level, detect_remote, extract_skills, required_years

_REQ_HEAD = re.compile(r"^\s*(requirements?|qualifications?|what you('|’)ll need|must[- ]have|you have|about you|skills|who you are|minimum qualifications)\b", re.I)
_PREF_HEAD = re.compile(r"^\s*(nice to have|preferred|bonus|plus|desired|good to have|preferred qualifications)\b", re.I)
_OTHER_HEAD = re.compile(r"^\s*(responsibilities|what you('|’)ll do|about (us|the (role|company|team))|benefits|perks|we offer|how to apply)\b", re.I)


@dataclass
class ExtractedJob:
    required: list[tuple[str, str]] = field(default_factory=list)  # (text, skill)
    preferred: list[tuple[str, str]] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    years: int | None = None
    level: str = ""
    remote_type: str = ""

    @property
    def required_skills(self) -> list[str]:
        return list(dict.fromkeys(s for _, s in self.required if s))

    @property
    def preferred_skills(self) -> list[str]:
        return [s for s in dict.fromkeys(s for _, s in self.preferred if s) if s not in self.required_skills]


def extract_requirements(title: str, description: str, location: str = "") -> ExtractedJob:
    out = ExtractedJob()
    mode = "other"
    for raw in description.splitlines():
        line = raw.strip(" \t•*-–·")
        if not line:
            continue
        short = len(line) < 60 and not line.endswith(".")
        if short and _PREF_HEAD.match(line):
            mode = "preferred"
            continue
        if short and _REQ_HEAD.match(line):
            mode = "required"
            continue
        if short and _OTHER_HEAD.match(line):
            mode = "other"
            continue
        skills = extract_skills(line)
        if re.search(r"\b(nice to have|preferred|bonus|a plus|desirable)\b", line, re.I):
            bucket = "preferred"
        else:
            bucket = mode
        if bucket in {"required", "preferred"}:
            for s in skills or [""]:
                if s or len(line) > 15:
                    (out.required if bucket == "required" else out.preferred).append((line[:400], s))
        if required_years(line) and bucket != "other":
            out.experience.append(line[:300])
    # Fallback when the ad has no structured sections: treat skills mentioned anywhere as required.
    if not out.required and not out.preferred:
        for s in extract_skills(f"{title}\n{description}"):
            out.required.append((f"Mentions {s}", s))
    out.technologies = extract_skills(f"{title}\n{description}")
    out.years = required_years("\n".join(out.experience)) or required_years(description[:4000])
    out.level = detect_level(title, description)
    out.remote_type = detect_remote(title, location, description)
    return out
