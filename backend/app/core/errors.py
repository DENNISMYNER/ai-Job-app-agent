"""Domain exceptions and their HTTP mapping."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class AIUnavailableError(AppError):
    """Ollama is not running or the configured model is not installed."""

    status_code = 503
    code = "ai_unavailable"


class ApprovalRequiredError(AppError):
    status_code = 403
    code = "approval_required"


class UserInterventionRequired(AppError):
    """Automation paused (CAPTCHA, MFA, unknown required field...)."""

    status_code = 409
    code = "user_intervention_required"


class SecurityError(AppError):
    status_code = 400
    code = "security_error"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Unexpected server error.", "detail": {}},
        )
