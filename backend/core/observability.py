"""Observability: Prometheus metrics and structured JSON logging."""
import json
import logging
import time
from datetime import datetime, timezone

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# --- Prometheus metrics ---
REQUEST_COUNT = Counter(
    "pfp_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "pfp_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
FEA_GENERATED = Counter("pfp_fea_generated_total", "FEAs generated", ["tenant"])
FEA_VERIFIED = Counter("pfp_fea_verified_total", "FEA verifications", ["result"])
AUDIT_EVENTS = Counter("pfp_audit_events_total", "Audit events recorded", ["action"])


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- Structured JSON logging ---
class JsonLogFormatter(logging.Formatter):
    """Emits each log record as a single JSON line."""

    _REDACT = ("password", "private_key", "secret", "authorization", "x-api-key", "token")

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = self._redact(key, value)
        return json.dumps(payload, ensure_ascii=False)

    def _redact(self, key: str, value):
        if any(s in key.lower() for s in self._REDACT):
            return "***REDACTED***"
        return value


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count + latency per route template."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            REQUEST_COUNT.labels(request.method, path, 500).inc()
            raise
        elapsed = time.perf_counter() - start
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        REQUEST_COUNT.labels(request.method, path, status).inc()
        return response
