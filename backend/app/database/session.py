from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

log = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def build_engine(url: str) -> Engine:
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")  # enforce FK + cascades
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = build_engine(get_settings().db_url)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def configure_engine(engine: Engine) -> None:
    """Override engine (used by tests)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_migrations() -> None:
    """Upgrade the database to the latest Alembic revision."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().db_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    log.info("Database migrations applied")
