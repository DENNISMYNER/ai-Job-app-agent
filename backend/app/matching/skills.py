"""Skill taxonomy + deterministic extraction (works with no AI available)."""
from __future__ import annotations

import re
from functools import lru_cache

# canonical name -> aliases (lower-case)
TAXONOMY: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "JavaScript": ["javascript", "js", "ecmascript", "es6"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java"],
    "C#": ["c#", "csharp", ".net", "dotnet", "asp.net"],
    "C++": ["c++", "cpp"],
    "Go": ["golang"],
    "Rust": ["rust"],
    "PHP": ["php", "laravel"],
    "Ruby": ["ruby", "rails", "ruby on rails"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "SQL": ["sql", "t-sql", "plsql"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "sass", "scss"],
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular", "angularjs"],
    "Svelte": ["svelte"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Express": ["express", "express.js", "expressjs"],
    "NestJS": ["nestjs", "nest.js"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Spring": ["spring", "spring boot"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest", "restful", "rest api", "rest apis"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql", "mariadb"],
    "SQLite": ["sqlite"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Prisma": ["prisma"],
    "SQLAlchemy": ["sqlalchemy"],
    "Docker": ["docker", "containers", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Linux": ["linux", "ubuntu", "bash"],
    "Git": ["git", "github", "gitlab", "version control"],
    "CI/CD": ["ci/cd", "cicd", "github actions", "jenkins", "continuous integration"],
    "Terraform": ["terraform"],
    "Testing": ["unit testing", "pytest", "jest", "vitest", "testing", "test automation", "tdd"],
    "Playwright": ["playwright"],
    "Selenium": ["selenium"],
    "Machine Learning": ["machine learning", "ml", "scikit-learn", "sklearn"],
    "Deep Learning": ["deep learning", "pytorch", "tensorflow"],
    "NLP": ["nlp", "natural language processing"],
    "LLMs": ["llm", "llms", "large language models", "openai", "ollama", "langchain"],
    "Data Analysis": ["data analysis", "pandas", "numpy", "excel", "power bi", "tableau"],
    "Agile": ["agile", "scrum", "kanban"],
    "Figma": ["figma", "ui/ux", "ux design"],
    "Customer Support": ["customer support", "customer service", "helpdesk", "help desk", "technical support"],
    "Sales": ["sales", "b2b sales", "lead generation", "business development"],
    "Communication": ["communication skills", "communication", "stakeholder management"],
    "Project Management": ["project management", "jira", "pmp"],
    "Networking": ["networking", "tcp/ip", "cisco", "ccna"],
    "Cybersecurity": ["cybersecurity", "security", "owasp", "penetration testing"],
    "Mobile": ["android", "ios", "react native", "flutter"],
}


@lru_cache
def _patterns() -> list[tuple[str, re.Pattern]]:
    out = []
    for canon, aliases in TAXONOMY.items():
        forms = {canon.lower(), *aliases}
        alt = "|".join(sorted((re.escape(f) for f in forms), key=len, reverse=True))
        # Lookarounds instead of \b so c++, c#, .net and node.js work.
        out.append((canon, re.compile(rf"(?<![A-Za-z0-9+#]){'(?:' + alt + ')'}(?![A-Za-z0-9+#])", re.I)))
    return out


def extract_skills(text: str) -> list[str]:
    """Return canonical skill names mentioned in ``text`` (ordered by first mention)."""
    hits: list[tuple[int, str]] = []
    for canon, pat in _patterns():
        m = pat.search(text)
        if m:
            hits.append((m.start(), canon))
    return [c for _, c in sorted(hits)]


def canonical(name: str) -> str:
    """Map a free-text skill (e.g. 'reactjs') to its canonical name when known."""
    found = extract_skills(name)
    return found[0] if found and len(name.split()) <= 3 else name.strip()


EXPERIENCE_LEVELS = {
    "intern": ["intern", "internship", "trainee"],
    "junior": ["junior", "entry level", "entry-level", "graduate", "jr."],
    "mid": ["mid-level", "mid level", "intermediate"],
    "senior": ["senior", "sr.", "lead", "principal", "staff", "architect"],
}


def detect_level(title: str, text: str = "") -> str:
    hay = f"{title}\n{text[:1500]}".lower()
    for level in ("intern", "junior", "senior", "mid"):
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", hay) for w in EXPERIENCE_LEVELS[level]):
            return level
    return ""


_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)", re.I)


def required_years(text: str) -> int | None:
    vals = [int(m.group(1)) for m in _YEARS.finditer(text)]
    vals = [v for v in vals if 0 < v <= 20]
    return min(vals) if vals else None


def detect_remote(title: str, location: str, text: str) -> str:
    hay = f"{title} {location} {text[:2000]}".lower()
    if re.search(r"\bhybrid\b", hay):
        return "hybrid"
    if re.search(r"\bremote\b|work from home|anywhere", hay):
        return "remote"
    if re.search(r"on-?site|in[- ]office", hay):
        return "onsite"
    return ""
