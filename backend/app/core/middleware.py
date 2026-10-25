import re
import uuid
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("payrecover.middleware")


from app.core.logging_config import current_request_id, current_correlation_id


from app.core.metrics import metrics


def _normalize_metric_path(path: str) -> str:
    """Normalize dynamic IDs to prevent unbounded metric cardinality."""
    # Replace UUIDs or entity IDs (rc_..., pay_..., whe_..., exp_..., etc.)
    norm = re.sub(r"/(rc|pay|whe|exp|usr|act|plink|doc)_[A-Za-z0-9_-]+", r"/:id", path)
    norm = re.sub(r"/[0-9a-fA-F-]{32,36}", r"/:id", norm)
    # Strip query string if any
    return norm.split("?")[0]


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every inbound request is tagged with a unique request_id and correlation_id.
    Propagates the ID to request.state, ContextVars, and response headers.
    Logs structured request duration and records Prometheus-compatible latency metrics.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        corr_id = request.headers.get("X-Correlation-ID") or req_id

        # Set in ContextVar for deep log filtering across async context
        token_req = current_request_id.set(req_id)
        token_corr = current_correlation_id.set(corr_id)

        request.state.request_id = req_id
        request.state.correlation_id = corr_id
        start_time = time.time()
        request.state.start_time = start_time

        try:
            response = await call_next(request)
            duration_s = time.time() - start_time
            duration_ms = duration_s * 1000.0
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            # Record Prometheus metrics (bounded path cardinality)
            if request.url.path != "/metrics":
                norm_path = _normalize_metric_path(request.url.path)
                metrics.increment_counter(
                    "payrecover_http_requests_total",
                    labels={
                        "method": request.method,
                        "endpoint": norm_path,
                        "status_code": str(response.status_code)
                    }
                )
                metrics.observe_histogram(
                    "payrecover_http_request_duration_seconds",
                    value=duration_s,
                    labels={
                        "method": request.method,
                        "endpoint": norm_path
                    }
                )

            # Avoid logging noisy polling health check endpoints at INFO
            if not request.url.path.endswith(("/health", "/health/live", "/health/ready", "/metrics")):
                logger.info(
                    f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)",
                    extra={
                        "route": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2)
                    }
                )
            return response
        finally:
            current_request_id.reset(token_req)
            current_correlation_id.reset(token_corr)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies production-grade security headers to all outgoing HTTP responses.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Standard OWASP security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        
        return response
