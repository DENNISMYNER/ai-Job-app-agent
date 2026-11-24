"""Text extraction from CV files and deterministic CV -> profile draft extraction."""
from __future__ import annotations

import io
import re
from pathlib import Path

from app.core.errors import ValidationFailed
from app.matching.skills import extract_skills
from app.security.untrusted import normalise_text


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pymupdf as fitz  # PyMuPDF

            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
        elif ext == ".docx":
            from docx import Document

            d = Document(str(path))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            text = "\n".join(parts)
        else:
            raise ValidationFailed("Unsupported file type.")
    except ValidationFailed:
        raise
    except Exception as exc:  # corrupt / encrypted files
        raise ValidationFailed(f"Could not read the document: {type(exc).__name__}") from exc
    return normalise_text(text, max_len=60000)


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,16}\d)(?!\d)")
_URL = re.compile(r"https?://[^\s)>\]]+|(?:www\.|linkedin\.com/|github\.com/)[^\s)>\]]+", re.I)
_SECTION = re.compile(
    r"^\s*(summary|profile|objective|about me|experience|work experience|employment|employment history|"
    r"professional experience|education|skills|technical skills|certifications?|languages?|projects?)\s*:?\s*$",
    re.I,
)
_DATE_RANGE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4})\s*[-–—to]+\s*"
    r"(Present|Current|Now|(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4})",
    re.I,
)
_MONTHS = {m: i for i, m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}


def _ym(month_word: str | None, year: str) -> str:
    if month_word:
        m = _MONTHS.get(month_word.strip().lower()[:3])
        if m:
            return f"{year}-{m:02d}"
    return year


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    cur = "header"
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            name = m.group(1).lower()
            cur = (
                "summary" if name in {"summary", "profile", "objective", "about me"}
                else "experience" if "experience" in name or name.startswith("employment")
                else "education" if name == "education"
                else "skills" if "skills" in name
                else "certifications" if name.startswith("certif")
                else "languages" if name.startswith("language")
                else "projects"
            )
            sections.setdefault(cur, [])
        else:
            sections[cur].append(line.rstrip())
    return sections


def extract_profile_draft(text: str) -> dict:
    """Best-effort, rule-based extraction. Only returns what is literally present.

    The result is a *draft* the user must review; nothing is saved automatically and
    missing information is left blank rather than guessed.
    """
    sec = _sections(text)
    header = "\n".join(sec["header"])
    draft: dict = {
        "full_name": "", "email": "", "phone": "", "location": "", "headline": "",
        "summary": "", "portfolio_url": "", "github_url": "", "linkedin_url": "",
        "skills": [], "employment": [], "education": [], "certifications": [], "languages": [],
    }
    if m := _EMAIL.search(text):
        draft["email"] = m.group(0)
    if m := _PHONE.search(header or text[:600]):
        draft["phone"] = m.group(1).strip()
    for u in _URL.findall(text):
        low = u.lower()
        url = u if low.startswith("http") else f"https://{u}"
        if "linkedin.com" in low and not draft["linkedin_url"]:
            draft["linkedin_url"] = url.rstrip(".,;")
        elif "github.com" in low and not draft["github_url"]:
            draft["github_url"] = url.rstrip(".,;")
        elif not draft["portfolio_url"] and "mailto" not in low:
            draft["portfolio_url"] = url.rstrip(".,;")
    # Name: first non-empty header line that is short and has no digits/@.
    for line in sec["header"]:
        line = line.strip()
        if line and len(line.split()) <= 5 and not re.search(r"[\d@:/]", line):
            draft["full_name"] = line.title() if line.isupper() else line
            break
    draft["summary"] = " ".join(l.strip() for l in sec.get("summary", []) if l.strip())[:1500]

    skills_text = "\n".join(sec.get("skills", [])) or text
    draft["skills"] = [{"name": n, "category": "technical"} for n in extract_skills(skills_text)]

    # Employment: group lines by date-range headers.
    exp_lines = sec.get("experience", [])
    entries: list[dict] = []
    for i, line in enumerate(exp_lines):
        dm = _DATE_RANGE.search(line)
        if dm:
            start = _ym(dm.group(1), dm.group(2))
            end_raw = dm.group(3)
            current = end_raw.lower() in {"present", "current", "now"}
            end = "" if current else _ym(
                (re.match(r"([A-Za-z]+)", end_raw).group(1) if re.match(r"[A-Za-z]+\s", end_raw) else None),
                re.search(r"\d{4}", end_raw).group(0),
            )
            title_line = (line[: dm.start()] + line[dm.end():]).strip(" -–—|,()")
            if not title_line:  # title on the previous non-empty line
                prev = [l.strip() for l in exp_lines[:i] if l.strip()]
                title_line = prev[-1] if prev else ""
            title, company = title_line, ""
            for sep in (" at ", " | ", " - ", " – ", ", "):
                if sep in title_line:
                    title, company = [x.strip() for x in title_line.split(sep, 1)]
                    break
            entries.append({
                "title": title, "company": company, "start_date": start, "end_date": end,
                "is_current": current, "description": "", "achievements": [],
            })
        elif entries and line.strip():
            bullet = line.strip().lstrip("•*-– ").strip()
            if bullet:
                entries[-1]["achievements"].append(bullet[:500])
    for e in entries:
        if e["title"] or e["company"]:
            e["company"] = e["company"] or "(company not detected)"
            e["title"] = e["title"] or "(title not detected)"
            draft["employment"].append(e)

    for line in sec.get("education", []):
        line = line.strip()
        if line and re.search(r"university|college|institute|school|academy|polytechnic", line, re.I):
            draft["education"].append({"institution": line[:200], "degree": "", "field_of_study": ""})
    for line in sec.get("certifications", []):
        line = line.strip().lstrip("•*-– ").strip()
        if line:
            draft["certifications"].append({"name": line[:200]})
    for line in sec.get("languages", []):
        for part in re.split(r"[,;•|]", line):
            part = part.strip()
            if part:
                name, _, prof = part.partition("(")
                draft["languages"].append({"language": name.strip()[:80], "proficiency": prof.strip(") ")})
    return draft
