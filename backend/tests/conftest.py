"""Test fixtures: isolated temp dirs + in-memory-style SQLite per test."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="jobagent-test-"))
os.environ["JOBAGENT_DATA_DIR"] = str(_TMP / "data")
os.environ["JOBAGENT_DOCUMENTS_DIR"] = str(_TMP / "documents")
os.environ["JOBAGENT_LOGS_DIR"] = str(_TMP / "logs")
os.environ["JOBAGENT_SCHEDULER_ENABLED"] = "false"
os.environ["JOBAGENT_AI_ENABLED"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.ai.ollama import set_ai_override  # noqa: E402
from app.database import session as dbs  # noqa: E402
from app.database.base import Base  # noqa: E402
import app.models  # noqa: E402,F401


@pytest.fixture()
def engine(tmp_path):
    eng = dbs.build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(eng)
    dbs.configure_engine(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def client(engine):
    from app.main import create_app

    app = create_app()
    app.state.skip_startup = True
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_real_ollama():
    """Tests must never talk to a real Ollama; default to 'unavailable'."""
    import httpx

    from app.ai.ollama import OllamaClient

    def refuse(request):
        raise httpx.ConnectError("ollama disabled in tests", request=request)

    set_ai_override(OllamaClient(transport=httpx.MockTransport(refuse)))
    yield
    set_ai_override(None)


SAMPLE_PROFILE = {
    "full_name": "Ada Tester",
    "email": "ada@example.com",
    "phone": "+254700000000",
    "location": "Nairobi",
    "country": "Kenya",
    "headline": "Junior Full-Stack Developer",
    "summary": "Developer who builds web apps with React and Python.",
    "github_url": "https://github.com/ada",
    "salary_min": 1000,
    "salary_max": 2000,
    "salary_currency": "USD",
    "work_modes": ["remote", "hybrid"],
    "employment_types": ["full-time"],
    "preferred_locations": ["Nairobi"],
    "notice_period": "2 weeks",
    "skills": [
        {"name": "Python"}, {"name": "React"}, {"name": "TypeScript"},
        {"name": "PostgreSQL"}, {"name": "Docker"},
    ],
    "employment": [
        {
            "company": "Acme Labs", "title": "Software Intern", "start_date": "2023-03",
            "end_date": "2024-01", "description": "Built internal tools.",
            "achievements": ["Built a React dashboard used by 40 staff", "Wrote Python data scripts"],
        }
    ],
    "education": [{"institution": "University of Nairobi", "degree": "BSc", "field_of_study": "Computer Science", "end_date": "2023"}],
    "certifications": [{"name": "AWS Cloud Practitioner", "issuer": "AWS"}],
    "languages": [{"language": "English", "proficiency": "Fluent"}],
}


@pytest.fixture()
def profile_payload():
    import copy

    return copy.deepcopy(SAMPLE_PROFILE)


@pytest.fixture()
def saved_profile(db, profile_payload):
    from app.schemas.profile import ProfileIn
    from app.services.profile_service import upsert_profile

    p = upsert_profile(db, ProfileIn(**profile_payload))
    db.commit()
    return p
