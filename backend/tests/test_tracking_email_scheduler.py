import smtplib
from email.message import EmailMessage

import httpx
import pytest

from app.notifications import email as em
from app.tasks import scheduler as sch
from tests.test_jobs_matching import add, mock_http  # noqa: F401  (autouse mock transport fixture)


def mk(client, company="Acme", position="Dev", url="https://x.example/job/1", status="shortlisted"):
    r = client.post("/api/applications", json={"company": company, "position": position, "url": url, "status": status})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------- tracking (I)
def test_tracker_crud_status_events_and_filters(client):
    a = mk(client)
    assert a["status"] == "shortlisted"
    r = client.patch(f"/api/applications/{a['id']}", json={"status": "interview", "notes": "Call Tuesday", "follow_up_date": "2026-12-01T09:00:00Z"})
    assert r.json()["status"] == "interview" and r.json()["notes"] == "Call Tuesday"
    assert client.patch(f"/api/applications/{a['id']}", json={"status": "bogus"}).status_code == 422
    mk(client, "Beta", "Analyst", "https://y.example/2", "rejected")
    assert client.get("/api/applications?status=rejected").json()["total"] == 1
    assert client.get("/api/applications?q=acme").json()["total"] == 1
    assert client.get("/api/applications?page_size=1&sort=company").json()["items"][0]["company"] == "Acme"
    ev = client.get(f"/api/applications/{a['id']}").json()["events"]
    assert [e["type"] for e in ev] == ["created", "status_changed"]
    assert client.delete(f"/api/applications/{a['id']}").status_code == 200
    assert client.get(f"/api/applications/{a['id']}").status_code == 404


def test_manual_applied_sets_dates_and_is_recorded(client):
    a = mk(client)
    r = client.patch(f"/api/applications/{a['id']}", json={"status": "applied"}).json()
    assert r["applied_at"] and r["follow_up_date"]
    types = [e["type"] for e in client.get(f"/api/applications/{a['id']}").json()["events"]]
    assert "marked_applied_manually" in types


def test_duplicate_detection_variants(client):
    a = mk(client, "Globex Corp.", "Junior React Developer", "https://g.example/jobs/1?utm_source=x")
    for company, pos, url in [("globex corp", "junior react developer!", "https://z.example/q"),
                              ("Other", "Other role", "https://g.example/jobs/1/")]:
        r = client.post("/api/applications", json={"company": company, "position": pos, "url": url})
        assert r.status_code == 409 and r.json()["detail"]["existing_id"] == a["id"]
    assert client.get("/api/applications/check-duplicate", params={"company": "GLOBEX corp", "position": "Junior React Developer"}).json()["duplicate"]
    assert not client.get("/api/applications/check-duplicate", params={"company": "Globex", "position": "Senior Dev"}).json()["duplicate"]


def test_interviews_recruiters_and_dashboard(client, profile_payload):
    client.put("/api/profile", json=profile_payload)
    a = mk(client, status="applied")
    iv = client.post(f"/api/applications/{a['id']}/interviews", json={"scheduled_at": "2030-01-01T10:00:00Z", "kind": "technical", "notes": "Bring laptop"})
    assert iv.status_code == 201
    assert client.get(f"/api/applications/{a['id']}").json()["status"] == "interview"
    assert len(client.get("/api/interviews?upcoming=true").json()) == 1
    rc = client.post(f"/api/applications/{a['id']}/recruiters", json={"name": "Rita", "email": "rita@acme.example"})
    assert rc.status_code == 201
    d = client.get("/api/dashboard").json()
    assert d["interviews"] == 1 and d["by_status"]["interview"] == 1 and "recent_activity" in d
    # cascade: deleting the application removes interviews and contacts
    client.delete(f"/api/applications/{a['id']}")
    assert client.get("/api/interviews").json() == []


def test_interview_prep_uses_real_experience_and_flags_gaps(client, profile_payload):
    client.put("/api/profile", json=profile_payload)
    job = client.post("/api/jobs/import-text", json={"title": "Junior React Developer", "company": "Globex", "url": "https://g.example/j",
                      "description": "Requirements:\n- React and Kubernetes\n- Python"}).json()
    a = client.post("/api/applications", json={"listing_id": job["id"]}).json()
    r = client.post(f"/api/applications/{a['id']}/interview-prep", json={"use_ai": False}).json()["prep"]
    assert any("Kubernetes" in q and "not in your CV" in q for q in r["technical_questions"])
    assert "Kubernetes" in r["company_research"]["gaps_to_prepare"]
    assert r["company_research"]["source"].startswith("Job advertisement only")
    basis = r["behavioral"][0]["suggested_basis"]
    assert "Acme Labs" in basis["situation"] and "React dashboard" in basis["action"]
    assert "(Add:" in basis["task"]  # unknown parts are left for the user, not invented
    assert any(e["skill"] == "React" for e in r["technical_exercises"])


# ------------------------------------------------------------------ email (K)
@pytest.mark.parametrize("subject,body,label", [
    ("Interview invitation", "We'd like to invite you to an interview next week", "interview"),
    ("Your application", "Unfortunately we will not be moving forward. Thank you for the interview.", "rejection"),
    ("Next steps", "Please complete the coding challenge on HackerRank", "assessment"),
    ("Hello", "I'm a recruiter and came across your profile", "recruiter"),
    ("Offer", "We are pleased to offer you the position", "offer"),
    ("Newsletter", "Weekly tips", "other"),
])
def test_email_classification(subject, body, label):
    assert em.classify_email(subject, body) == label


class FakeSMTP:
    sent = []
    fail = False

    def __init__(self, *a): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def login(self, u, p):
        if FakeSMTP.fail: raise smtplib.SMTPAuthenticationError(535, b"bad")
        FakeSMTP.login_args = (u, p)
    def send_message(self, m): FakeSMTP.sent.append(m)
    def starttls(self): pass


class FakeIMAP:
    def __init__(self, *a): self.raw = FakeIMAP.messages
    def login(self, u, p): pass
    def select(self, box, readonly=False): assert readonly, "inbox must be opened read-only"
    def search(self, *a): return "OK", [b" ".join(str(i).encode() for i in range(1, len(self.raw) + 1))]
    def fetch(self, num, spec):
        assert "PEEK" in spec  # never marks as read
        return "OK", [(b"", self.raw[int(num) - 1])]
    def logout(self): pass


def raw_mail(subject, body, sender="HR <hr@acme.example>"):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, sender, "ada@example.com"
    m.set_content(body)
    return m.as_bytes()


def test_email_config_secret_encrypted_and_never_returned(client, db):
    client.put("/api/email/config", json={"smtp_host": "smtp.example", "username": "ada", "password": "hunter2-secret"})
    cfg = client.get("/api/email/config").json()
    assert cfg["has_password"] is True and "password" not in cfg and "hunter2" not in str(cfg)
    from app.models import UserSetting
    raw = db.get(UserSetting, "email_config")
    assert raw.encrypted and "hunter2" not in str(raw.value)
    client.put("/api/email/config", json={"smtp_host": "smtp2.example", "username": "ada", "password": ""})  # blank keeps secret
    assert client.get("/api/email/config").json()["has_password"] is True
    assert client.delete("/api/email/config").status_code == 200
    assert client.get("/api/email/config").json().get("has_password") is False


def test_email_send_requires_approval_and_is_optional(client, profile_payload, monkeypatch):
    client.put("/api/profile", json=profile_payload)
    a = mk(client, status="applied")
    d = client.post(f"/api/applications/{a['id']}/follow-up-draft", json={"to": "hr@acme.example"}).json()
    assert d["status"] == "draft" and "Acme" in d["body"] and "Ada Tester" in d["body"]
    monkeypatch.setattr(em, "smtp_factory", lambda h, p: FakeSMTP())
    FakeSMTP.sent, FakeSMTP.fail = [], False
    r = client.post(f"/api/email/drafts/{d['id']}/send")
    assert r.status_code == 403 and FakeSMTP.sent == []  # not approved -> never sent
    client.post(f"/api/email/drafts/{d['id']}/approve", json={})
    r = client.post(f"/api/email/drafts/{d['id']}/send")
    assert r.status_code == 422  # approved but email not configured: optional feature, clear message
    client.put("/api/email/config", json={"smtp_host": "smtp.example", "username": "ada", "password": "pw", "from_address": "ada@example.com"})
    r = client.post(f"/api/email/drafts/{d['id']}/send").json()
    assert r["status"] == "sent" and len(FakeSMTP.sent) == 1 and FakeSMTP.sent[0]["To"] == "hr@acme.example"
    assert FakeSMTP.login_args == ("ada", "pw")


def test_email_send_failure_is_recorded(client, profile_payload, monkeypatch):
    client.put("/api/profile", json=profile_payload)
    d = client.post("/api/email/suggest-reply", json={"label": "interview", "to": "hr@acme.example", "sender_name": "Rita", "role": "Dev"}).json()
    assert "Rita" in d["body"]
    monkeypatch.setattr(em, "smtp_factory", lambda h, p: FakeSMTP())
    FakeSMTP.fail = True
    client.put("/api/email/config", json={"smtp_host": "s", "username": "u", "password": "p"})
    client.post(f"/api/email/drafts/{d['id']}/approve", json={})
    r = client.post(f"/api/email/drafts/{d['id']}/send").json()
    assert r["status"] == "failed" and r["error"] == "SMTPAuthenticationError"
    FakeSMTP.fail = False


def test_inbox_poll_detects_and_links_without_changing_status(client, monkeypatch):
    a = mk(client, "Acme", "Dev", status="applied")
    FakeIMAP.messages = [raw_mail("Interview invitation - Dev role at Acme", "We would like to schedule a call with you."),
                         raw_mail("Update on your Acme application", "Unfortunately we are not moving forward."),
                         raw_mail("Sale!", "50% off")]
    monkeypatch.setattr(em, "imap_factory", lambda h, p: FakeIMAP())
    client.put("/api/email/config", json={"imap_host": "imap.example", "username": "u", "password": "p"})
    found = client.post("/api/email/poll").json()["found"]
    assert [f["label"] for f in found] == ["interview", "rejection"] and all(f["application_id"] == a["id"] for f in found)
    assert client.get(f"/api/applications/{a['id']}").json()["status"] == "applied"  # only suggests, never auto-changes
    assert len(client.get("/api/notifications?unread=true").json()) == 2


def test_email_not_required_for_app_to_work(client):
    assert client.get("/api/dashboard").status_code == 200
    assert client.post("/api/email/poll").status_code == 422


# ------------------------------------------------------------- scheduler (L)
def test_schedule_validation_and_lifecycle(client):
    bad = client.post("/api/automation/schedules", json={"name": "x", "task_type": "nope", "cron": "0 8 * * *"})
    assert bad.status_code == 422
    assert client.post("/api/automation/schedules", json={"name": "x", "task_type": "daily_report", "cron": "not cron"}).status_code == 422
    r = client.post("/api/automation/schedules", json={"name": "Morning search", "task_type": "discover_match", "cron": "0 8 * * *", "params": {"keywords": ["react"]}})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.post(f"/api/automation/schedules/{sid}/pause").json()["enabled"] is False
    assert client.post(f"/api/automation/schedules/{sid}/resume").json()["enabled"] is True
    assert client.post(f"/api/automation/schedules/{sid}/explode").status_code == 422
    assert client.delete(f"/api/automation/schedules/{sid}").status_code == 200


def test_scheduler_registers_and_pauses_jobs(client):
    sch.start_scheduler()
    try:
        s = client.post("/api/automation/schedules", json={"name": "A", "task_type": "daily_report", "cron": "30 7 * * *"}).json()
        st = client.get("/api/automation/status").json()["scheduler"]
        assert st["running"] and [j["id"] for j in st["jobs"]] == [f"sched-{s['id']}"] and st["jobs"][0]["next_run"]
        client.post(f"/api/automation/schedules/{s['id']}/pause")
        assert client.get("/api/automation/status").json()["scheduler"]["jobs"] == []
        client.post(f"/api/automation/schedules/{s['id']}/resume")
        client.post("/api/automation/pause-all")
        assert client.get("/api/automation/status").json()["scheduler"]["paused"] is True
        client.post("/api/automation/resume-all")
        assert client.get("/api/automation/status").json()["scheduler"]["paused"] is False
    finally:
        sch.stop_scheduler()


def test_discover_match_run_notifies_high_matches_and_reports(client, profile_payload):
    client.put("/api/profile", json=profile_payload)
    add(client, "greenhouse", "acme", company="Acme")
    s = client.post("/api/automation/schedules", json={"name": "Daily", "task_type": "discover_match", "cron": "0 8 * * *",
                    "params": {"keywords": ["developer"], "min_score": 60}}).json()
    r = client.post(f"/api/automation/schedules/{s['id']}/run-now").json()
    assert r["last_status"].startswith("ok") and "1 high matches" in r["last_status"]
    notes = client.get("/api/notifications").json()
    assert any(n["kind"] == "high_match" and "Junior Full-Stack Developer" in n["title"] for n in notes)
    assert not any("Rust" in n["title"] for n in notes)  # filtered by keyword + score
    rep = client.post("/api/automation/schedules", json={"name": "Report", "task_type": "daily_report", "cron": "0 20 * * *"}).json()
    out = client.post(f"/api/automation/schedules/{rep['id']}/run-now").json()
    assert out["last_status"].startswith("ok: New jobs: 2")
    assert any(n["kind"] == "report" for n in client.get("/api/notifications").json())
    # discovery never creates applications on its own
    assert client.get("/api/applications").json()["total"] == 0


def test_failing_schedule_is_contained(client, monkeypatch):
    s = client.post("/api/automation/schedules", json={"name": "Boom", "task_type": "daily_report", "cron": "0 8 * * *"}).json()
    monkeypatch.setitem(sch.RUNNERS, "daily_report", lambda db, p: 1 / 0)
    r = client.post(f"/api/automation/schedules/{s['id']}/run-now").json()
    assert r["last_status"] == "error: ZeroDivisionError"
