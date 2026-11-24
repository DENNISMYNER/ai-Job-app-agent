"""Encryption of sensitive stored values (email passwords, tokens).

A Fernet key is taken from JOBAGENT_SECRET_KEY or generated once into
``data/secret.key`` (permissions 0600). Secrets are never stored in plaintext.
"""
from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import SecurityError


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    if s.secret_key:
        return Fernet(s.secret_key.encode())
    key_path = s.data_dir / "secret.key"
    if key_path.exists():
        return Fernet(key_path.read_bytes().strip())
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:  # Windows: best effort
        pass
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecurityError("Stored secret cannot be decrypted (key changed?).") from exc


def reset_key_cache() -> None:
    _fernet.cache_clear()
