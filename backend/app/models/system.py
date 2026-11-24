from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))  # high_match|interview|rejection|report|info
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailDraft(Base, TimestampMixin):
    """Outgoing emails always start as drafts and need explicit approval to send."""

    __tablename__ = "email_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True
    )
    to_address: Mapped[str] = mapped_column(String(320), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|sent|failed
    error: Mapped[str] = mapped_column(String(500), default="")


class AutomationSchedule(Base, TimestampMixin):
    __tablename__ = "automation_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(40))  # discover_match|daily_report
    cron: Mapped[str] = mapped_column(String(100))  # standard 5-field cron
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(300), default="")


class AgentActivityLog(Base):
    __tablename__ = "agent_activity_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Index("ix_activity_created", AgentActivityLog.created_at)


class UserSetting(Base):
    __tablename__ = "user_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted: Mapped[bool] = mapped_column(default=False)  # value["v"] holds ciphertext
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
