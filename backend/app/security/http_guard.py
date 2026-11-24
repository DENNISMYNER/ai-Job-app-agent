"""Request guards: Host allow-list (DNS-rebinding) and Origin check (CSRF).

The API uses no cookies, so classic CSRF is not possible, but a malicious web
page could still try to reach a locally running API. We therefore reject
state-changing requests whose Origin is not an allowed local origin and
requests whose Host header is not local.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "testserver"}


class LocalOnlyGuard(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
        if host and host not in LOCAL_HOSTS:
            return JSONResponse({"error": "forbidden_host", "message": "Host not allowed."}, 403)
        origin = request.headers.get("origin")
        if request.method not in SAFE_METHODS and origin and origin not in self.allowed_origins:
            return JSONResponse({"error": "forbidden_origin", "message": "Origin not allowed."}, 403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'",
        )
        return response
