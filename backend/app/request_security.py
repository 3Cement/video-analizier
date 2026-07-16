from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings


class CookieOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("va_session"):
            origin = request.headers.get("origin")
            settings = get_settings()
            if not origin and settings.auth_required:
                return JSONResponse({"detail": "Origin required"}, status_code=403)
            if origin:
                allowed = set(settings.allowed_origin_list)
                if settings.public_base_url:
                    allowed.add(settings.public_base_url.rstrip("/"))
                host_origin = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
                allowed.add(host_origin)
                normalized = f"{urlparse(origin).scheme}://{urlparse(origin).netloc}".rstrip("/")
                if normalized not in allowed:
                    return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)
