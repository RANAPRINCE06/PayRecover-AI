import uuid
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("payrecover.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every inbound request is tagged with a unique request_id and correlation_id.
    Propagates the ID to request.state and sets response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        corr_id = request.headers.get("X-Correlation-ID") or req_id

        request.state.request_id = req_id
        request.state.correlation_id = corr_id
        request.state.start_time = time.time()

        response = await call_next(request)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Correlation-ID"] = corr_id
        return response


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
