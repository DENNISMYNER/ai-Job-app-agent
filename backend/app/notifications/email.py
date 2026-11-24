"""Optional email assistant (IMAP/SMTP). Never required; credentials are stored encrypted.

* Incoming mail is classified with deterministic rules and treated as untrusted text.
* Outgoing mail is always created as a DRAFT and is only sent after explicit approval.
"""
from __future__ import annotations

import imaplib
import logging
import re
import smtplib
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApprovalRequiredError, ConflictError, NotFoundError, ValidationFailed
from app.models import EmailDraft, JobApplication, Profile
from app.security.untrusted import html_to_text
from app.services import settings_service as ss
from app.services.activity import log_activity, notify

log = logging.getLogger(__name__)

# Overridable in tests.
imap_factory = lambda host, port: imaplib.IMAP4_SSL(host, port)  # noqa: E731
smtp_factory = lambda host, port: smtplib.SMTP_SSL(host, port) if port == 465 else smtplib.SMTP(host, port)  # noqa: E731

RULES = [
    ("offer", r"\b(pleased to offer|job offer|offer of employment|we would like to offer)\b"),
    ("rejection", r"\b(unfortunately|regret to inform|not (be )?moving forward|decided to (move forward|proceed) with (other|another)|will not be (proceeding|moving)|position has been filled|not selected)\b"),
    ("interview", r"\b(interview|schedule a (call|chat)|invite you to (a|an)|availability for a (call|chat)|meet with (our|the) team)\b"),
    ("assessment", r"\b(assessment|coding (challenge|test)|take-?home|hackerrank|codility|online test)\b"),
    ("recruiter", r"\b(recruiter|talent acquisition|came across your (profile|cv|resume)|opportunity at)\b"),
]


def classify_email(subject: str, body: str) -> str:
    text = f"{subject}\n{body[:3000]}".lower()
    for label, pat in RULES:  # order matters: rejection wins over the word 'interview' in a decline
        if re.search(pat, text):
            return label
    return "other"


# --------------------------------------------------------------------- config
def get_config(db: Session, *, include_password: bool = False) -> dict:
    cfg = _raw(db)
    if not include_password:
        cfg = {**cfg, "has_password": bool(cfg.get("password"))}
        cfg.pop("password", None)
    return cfg


def _raw(db: Session) -> dict:
    from app.models import UserSetting
    from app.security.crypto import decrypt
    import json

    row = db.get(UserSetting, "email_config")
    return json.loads(decrypt(row.value["v"])) if row and row.encrypted else {}


def save_config(db: Session, cfg: dict) -> dict:
    old = _raw(db)
    if not cfg.get("password"):  # keep existing secret when the UI sends a blank password
        cfg["password"] = old.get("password", "")
    ss.set_setting(db, "email_config", cfg, encrypted=True)
    return get_config(db)


def delete_config(db: Session) -> None:
    from app.models import UserSetting

    row = db.get(UserSetting, "email_config")
    if row:
        db.delete(row)


# ---------------------------------------------------------------------- drafts
def follow_up_draft(db: Session, app: JobApplication, p: Profile, to: str = "") -> EmailDraft:
    to = to or (app.recruiters[0].email if app.recruiters else "")
    when = app.applied_at.strftime("%d %B %Y") if app.applied_at else "recently"
    d = EmailDraft(
        application_id=app.id, to_address=to, status="draft",
        subject=f"Following up: {app.position} application - {p.full_name}",
        body=(f"Dear Hiring Team,\n\nI applied for the {app.position} position at {app.company} on {when} and wanted to "
              "follow up to express my continued interest. Please let me know if you need any further information "
              "from me.\n\nThank you for your time.\n\nKind regards,\n" + p.full_name),
    )
    db.add(d)
    db.flush()
    return d


REPLY_TEMPLATES = {
    "interview": "Dear {name},\n\nThank you for the invitation. I would be glad to interview for the {role} role. "
                 "Please let me know the available slots, or I can share my availability.\n\nKind regards,\n{me}",
    "assessment": "Dear {name},\n\nThank you for the update. I will complete the assessment within the requested time frame. "
                  "Please let me know if there is anything I should prepare.\n\nKind regards,\n{me}",
    "rejection": "Dear {name},\n\nThank you for letting me know and for considering my application. I would appreciate any "
                 "feedback you can share and would be glad to be considered for future roles.\n\nKind regards,\n{me}",
    "recruiter": "Dear {name},\n\nThank you for reaching out. I would be happy to learn more about the opportunity. "
                 "Could you share the job description and next steps?\n\nKind regards,\n{me}",
    "offer": "Dear {name},\n\nThank you very much for the offer. I would like to review the details and will respond shortly.\n\nKind regards,\n{me}",
}


def suggest_reply(db: Session, label: str, p: Profile, *, to: str, sender_name: str = "", role: str = "", application_id: int | None = None, subject: str = "") -> EmailDraft:
    tpl = REPLY_TEMPLATES.get(label)
    if not tpl:
        raise ValidationFailed("No reply template for this kind of email.")
    d = EmailDraft(application_id=application_id, to_address=to, status="draft", subject="Re: " + (subject or role or "your message"),
                   body=tpl.format(name=sender_name or "there", role=role or "advertised", me=p.full_name))
    db.add(d)
    db.flush()
    return d


def approve_draft(db: Session, draft_id: int, edits: dict | None = None) -> EmailDraft:
    d = db.get(EmailDraft, draft_id)
    if not d:
        raise NotFoundError("Draft not found")
    if d.status == "sent":
        raise ConflictError("Already sent.")
    for k in ("to_address", "subject", "body"):
        if edits and k in edits:
            setattr(d, k, str(edits[k]))
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", d.to_address):
        raise ValidationFailed("A valid recipient address is required.")
    d.status = "approved"
    return d


def send_draft(db: Session, draft_id: int) -> EmailDraft:
    d = db.get(EmailDraft, draft_id)
    if not d:
        raise NotFoundError("Draft not found")
    if d.status != "approved":
        raise ApprovalRequiredError("Emails are only sent after you approve the draft.")
    cfg = _raw(db)
    if not cfg.get("smtp_host"):
        raise ValidationFailed("Email is not configured. Add SMTP settings first (optional feature).")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg.get("from_address") or cfg["username"], d.to_address, d.subject.replace("\n", " ")
    msg.set_content(d.body)
    try:
        with smtp_factory(cfg["smtp_host"], int(cfg.get("smtp_port", 465))) as s:
            if not isinstance(s, smtplib.SMTP_SSL) and cfg.get("smtp_starttls", True):
                try:
                    s.starttls()
                except Exception:  # noqa: BLE001
                    pass
            s.login(cfg["username"], cfg["password"])
            s.send_message(msg)
        d.status, d.error = "sent", ""
    except Exception as exc:  # noqa: BLE001
        d.status, d.error = "failed", type(exc).__name__
    log_activity(db, "email", "send", f"Draft {d.id}: {d.status}")
    return d


# ---------------------------------------------------------------------- inbox
def _decode(v) -> str:
    return str(make_header(decode_header(v or "")))


def _body(msg) -> str:
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype in {"text/plain", "text/html"} and not part.get_filename():
            raw = part.get_payload(decode=True) or b""
            text = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
            return html_to_text(text) if ctype == "text/html" else text
    return ""


def poll_inbox(db: Session, limit: int = 30) -> list[dict]:
    """Read recent unseen mail, classify, link to applications and raise notifications. Read-only."""
    cfg = _raw(db)
    if not cfg.get("imap_host"):
        raise ValidationFailed("Email is not configured. Add IMAP settings first (optional feature).")
    apps = db.scalars(select(JobApplication)).all()
    found = []
    imap = imap_factory(cfg["imap_host"], int(cfg.get("imap_port", 993)))
    try:
        imap.login(cfg["username"], cfg["password"])
        imap.select("INBOX", readonly=True)  # readonly: never marks mail as read or deletes anything
        _, data = imap.search(None, "UNSEEN")
        for num in (data[0].split() if data and data[0] else [])[-limit:]:
            _, msgdata = imap.fetch(num, "(BODY.PEEK[])")
            msg = message_from_bytes(msgdata[0][1])
            subject, sender, body = _decode(msg["Subject"]), _decode(msg["From"]), _body(msg)
            label = classify_email(subject, body)
            if label == "other":
                continue
            hay = f"{subject} {sender} {body[:1500]}".lower()
            app = next((a for a in apps if a.company and a.company.lower() in hay), None)
            item = {"label": label, "subject": subject[:200], "from": sender[:200], "application_id": app.id if app else None}
            found.append(item)
            notify(db, label if label in {"interview", "rejection"} else "info", f"{label.title()} email: {subject[:120]}",
                   f"From {sender[:100]}" + (f" - matches {app.position} @ {app.company}" if app else ""), application_id=item["application_id"], label=label)
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
    return found
