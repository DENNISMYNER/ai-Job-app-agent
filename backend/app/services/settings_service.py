"""Key/value user settings with optional encryption for secrets."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import UserSetting
from app.security.crypto import decrypt, encrypt

DEFAULTS: dict[str, Any] = {
    "ai": {"enabled": True, "model": None, "embedding_model": None, "use_embeddings": True},
    "matching": {
        "min_apply_score": 70,
        "min_consider_score": 45,
        "weights": {"skills": 0.55, "experience": 0.15, "location": 0.15, "title": 0.15},
        "target_titles": [],
        "excluded_keywords": [],
    },
    "automation": {
        # Explicit approval before final submit is the default and recommended policy.
        "require_approval": True,
        "auto_submit_enabled": False,
        "auto_submit_min_score": 85,
        "auto_submit_daily_limit": 5,
        "headless": False,
        "notify_min_score": 75,
    },
    "system": {"retention_days": 0, "theme": "system", "page_size": 20},
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(UserSetting, key)
    base = dict(DEFAULTS.get(key, {}))
    if row is None:
        return base
    value = decrypt(row.value["v"]) if row.encrypted else row.value
    if row.encrypted:
        import json

        value = json.loads(value)
    base.update(value)
    return base


def set_setting(db: Session, key: str, value: dict, *, encrypted: bool = False) -> dict:
    import json

    row = db.get(UserSetting, key)
    stored = {"v": encrypt(json.dumps(value))} if encrypted else value
    if row is None:
        db.add(UserSetting(key=key, value=stored, encrypted=encrypted))
    else:
        row.value, row.encrypted = stored, encrypted
    db.flush()
    return value


def update_setting(db: Session, key: str, patch: dict) -> dict:
    current = get_setting(db, key)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(current.get(k), dict):
            current[k] = {**current[k], **v}
        else:
            current[k] = v
    return set_setting(db, key, current)
