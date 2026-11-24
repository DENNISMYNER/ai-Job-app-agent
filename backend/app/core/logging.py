"""Structured logging with PII redaction."""
from __future__ import annotations

import json
import logging
import re
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")


_NOT_PHONE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$|^\d{4}-\d{2}-\d{2}")  # IPv4, ISO dates


def _mask_phone(m: re.Match) -> str:
    raw = m.group(0)
    digits = sum(c.isdigit() for c in raw)
    if digits < 9 or digits > 15 or _NOT_PHONE.match(raw.strip()):
        return raw
    return "[phone]"


def redact(text: str) -> str:
    """Mask emails and phone numbers so logs never expose personal data."""
    text = _EMAIL.sub("[email]", text)
    return _PHONE.sub(_mask_phone, text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    s = get_settings()
    root = logging.getLogger()
    if getattr(root, "_jobagent_configured", False):
        return
    root.setLevel(s.log_level.upper())
    fmt = RedactingFormatter()
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)
    try:
        fh = RotatingFileHandler(
            s.logs_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:  # read-only FS etc. - console logging still works
        pass
    root._jobagent_configured = True  # type: ignore[attr-defined]
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
