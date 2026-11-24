"""Agent activity log + notification helpers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import redact
from app.models import AgentActivityLog, Notification


def log_activity(db: Session, actor: str, action: str, message: str = "", *, level: str = "info", **meta) -> None:
    db.add(
        AgentActivityLog(
            actor=actor,
            action=action,
            level=level,
            message=redact(message)[:1000],
            meta={k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool, type(None)))},
        )
    )
    db.flush()


def notify(db: Session, kind: str, title: str, body: str = "", **payload) -> Notification:
    n = Notification(kind=kind, title=title[:300], body=body, payload=payload)
    db.add(n)
    db.flush()
    return n
