"""Security middleware: security headers + request body size limit."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import settings


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# Relaxed CSP for the interactive API docs (Swagger UI / ReDoc), which load
# assets from the jsDelivr CDN and use inline scripts/styles. Scoped ONLY to the
# docs routes so the strict CSP still protects every other response.
_DOCS_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:; "
    "connect-src 'self'"
)
_DOCS_PREFIXES = ("/api/docs", "/api/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to every response. Adds HSTS in prod."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        is_docs = request.url.path.startswith(_DOCS_PREFIXES)
        for header, value in SECURITY_HEADERS.items():
            if header == "Content-Security-Policy" and is_docs:
                value = _DOCS_CSP
            response.headers.setdefault(header, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
            )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose body exceeds MAX_REQUEST_BYTES."""

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > settings.MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large (max {settings.MAX_REQUEST_BYTES} bytes)"
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)
