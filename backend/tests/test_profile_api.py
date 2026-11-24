import io

import pymupdf as fitz
import pytest
from docx import Document as Docx


def test_profile_crud_and_delete(client, profile_payload):
    assert client.get("/api/profile").json() is None
    r = client.put("/api/profile", json=profile_payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Ada Tester"
    assert len(body["skills"]) == 5 and body["employment"][0]["company"] == "Acme Labs"

    profile_payload["skills"] = [{"name": "Go"}, {"name": "go"}]  # case-insensitive dedupe
    profile_payload["employment"] = []
    r = client.put("/api/profile", json=profile_payload)
    assert [s["name"] for s in r.json()["skills"]] == ["Go"]
    assert r.json()["employment"] == []

    assert client.delete("/api/profile").status_code == 200
    assert client.get("/api/profile").json() is None


@pytest.mark.parametrize(
    "patch",
    [{"email": "not-an-email"}, {"github_url": "javascript:alert(1)"}, {"work_modes": ["moon"]},
     {"employment": [{"company": "X", "title": "Y", "start_date": "last year"}]}],
)
def test_profile_validation(client, profile_payload, patch):
    profile_payload.update(patch)
    assert client.put("/api/profile", json=profile_payload).status_code == 422


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    return doc.tobytes()


CV_TEXT = """Jane Doe
jane@doe.dev  +254 711 222 333
github.com/janedoe  linkedin.com/in/janedoe
Summary
Backend developer who likes APIs.
Experience
Backend Developer at Initech 2021 - Present
- Built REST APIs with Python and FastAPI
Education
Kenyatta University
Skills
Python, Docker, PostgreSQL
"""


def test_cv_import_extracts_only_present_data(client):
    r = client.post("/api/profile/import-cv", files={"file": ("cv.pdf", _pdf(CV_TEXT), "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()["draft"]
    assert d["email"] == "jane@doe.dev"
    assert "github.com/janedoe" in d["github_url"]
    assert {"Python", "Docker", "PostgreSQL"} <= {s["name"] for s in d["skills"]}
    assert d["employment"] and d["employment"][0]["is_current"] is True
    assert d.get("salary_min") is None  # never invented
    assert client.get("/api/profile").json() is None  # nothing saved automatically


def test_cv_import_docx(client):
    buf = io.BytesIO()
    doc = Docx()
    for line in CV_TEXT.splitlines():
        doc.add_paragraph(line)
    doc.save(buf)
    r = client.post("/api/profile/import-cv", files={"file": ("cv.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["draft"]["email"] == "jane@doe.dev"


def test_upload_rejects_bad_files(client):
    r = client.post("/api/documents", files={"file": ("x.pdf", b"hello", "application/pdf")}, data={"kind": "cv"})
    assert r.status_code == 422
    r = client.post("/api/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_document_upload_list_download_delete(client):
    r = client.post("/api/documents", files={"file": ("../../my cv.pdf", _pdf(CV_TEXT), "application/pdf")}, data={"kind": "cv"})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["filename"] == "my_cv.pdf"
    assert client.get("/api/documents").json()[0]["id"] == doc["id"]
    d = client.get(f"/api/documents/{doc['id']}/download")
    assert d.status_code == 200 and d.content.startswith(b"%PDF")
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert client.get(f"/api/documents/{doc['id']}/download").status_code == 404


def test_origin_and_host_guard(client):
    r = client.post("/api/profile", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.get("/api/health", headers={"Host": "evil.example"})
    assert r.status_code == 403
    assert client.get("/api/health").json() == {"status": "ok"}


def test_ai_status_graceful_when_ollama_down(client):
    r = client.get("/api/ai/status").json()
    assert r["reachable"] is False and "Ollama" in r["message"]


def test_settings_cannot_silently_disable_approval(client):
    r = client.put("/api/settings/automation", json={"require_approval": False})
    assert r.json()["require_approval"] is True
    r = client.put("/api/settings/automation", json={"require_approval": False, "auto_submit_enabled": True})
    assert r.json()["require_approval"] is False


def test_export_and_delete_all(client, profile_payload):
    client.put("/api/profile", json=profile_payload)
    assert client.get("/api/data/export").json()["profile"]["full_name"] == "Ada Tester"
    assert client.post("/api/data/delete-all", json={"confirm": "nope"}).status_code == 422
    assert client.post("/api/data/delete-all", json={"confirm": "DELETE"}).status_code == 200
    assert client.get("/api/profile").json() is None


def test_saving_same_profile_twice_is_idempotent(client, profile_payload):
    assert client.put("/api/profile", json=profile_payload).status_code == 200
    r = client.put("/api/profile", json=profile_payload)
    assert r.status_code == 200 and len(r.json()["skills"]) == 5
