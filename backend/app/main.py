"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import router as api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.security.http_guard import LocalOnlyGuard

log = logging.getLogger(__name__)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _load_runtime_settings() -> None:
    from app.ai.ollama import configure_runtime
    from app.database.session import session_factory
    from app.services import settings_service as ss

    db = session_factory()()
    try:
        configure_runtime(ss.get_setting(db, "ai"))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging()
    if not getattr(app.state, "skip_startup", False):
        from app.database.session import run_migrations

        run_migrations()
        _load_runtime_settings()
        if s.scheduler_enabled:
            from app.tasks.scheduler import start_scheduler

            start_scheduler()
    log.info("Job agent started on %s:%s", s.host, s.port)
    yield
    if not getattr(app.state, "skip_startup", False):
        from app.tasks.scheduler import stop_scheduler

        stop_scheduler()
        from app.automation.session import shutdown_browser

        shutdown_browser()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(LocalOnlyGuard, allowed_origins=s.allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api")

    if FRONTEND_DIST.exists():  # single-process mode: serve the built SPA
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (FRONTEND_DIST / path).resolve()
            if path and f.is_file() and FRONTEND_DIST.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
