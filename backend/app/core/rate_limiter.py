import hashlib
import logging
from typing import Optional
from fastapi import Request, HTTPException, status

from app.core.config import settings
from app.services.redis_service import redis_service

logger = logging.getLogger("payrecover.ratelimiter")


class LoginRateLimiter:
    """
    Two-dimensional Redis-backed rate limiter for authentication endpoints.
    Protects against credential stuffing and brute-force attacks across:
    1. IP-based limits (prevents 1 IP attacking multiple accounts)
    2. Account-based limits (prevents distributed attacks against 1 account)
    """

    @staticmethod
    def get_client_ip(request: Request) -> str:
        """Safely extract client IP from proxy headers or connection state."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP in X-Forwarded-For is client's original IP
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    @staticmethod
    def _account_hash(email: str) -> str:
        """Create a consistent, safe identifier for the account key."""
        clean = (email or "").strip().lower()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:24]

    def check_rate_limit(self, request: Request, email: str) -> None:
        """
        Check both IP and Account rate limit thresholds before attempting credentials.
        Raises HTTP 429 with Retry-After header if limits are exceeded.
        """
        if not settings.LOGIN_RATE_LIMIT_ENABLED:
            return

        client_ip = self.get_client_ip(request)
        account_hash = self._account_hash(email)

        # 1. Evaluate IP dimension
        ip_key = f"ratelimit:login:ip:{client_ip}"
        ip_attempts = redis_service.get(ip_key)
        if ip_attempts is not None:
            try:
                ip_count = int(ip_attempts)
            except (ValueError, TypeError):
                ip_count = 0

            if ip_count >= settings.LOGIN_IP_MAX_ATTEMPTS:
                retry_after = redis_service.ttl(ip_key)
                retry_after_val = max(1, retry_after if retry_after > 0 else settings.LOGIN_IP_WINDOW_SECONDS)
                logger.warning(
                    f"Login rate limit exceeded for IP: {client_ip} "
                    f"({ip_count}/{settings.LOGIN_IP_MAX_ATTEMPTS} attempts, retry-after: {retry_after_val}s)"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after_val)}
                )

        # 2. Evaluate Account dimension (independent of IP)
        account_key = f"ratelimit:login:account:{account_hash}"
        acc_attempts = redis_service.get(account_key)
        if acc_attempts is not None:
            try:
                acc_count = int(acc_attempts)
            except (ValueError, TypeError):
                acc_count = 0

            if acc_count >= settings.LOGIN_ACCOUNT_MAX_ATTEMPTS:
                retry_after = redis_service.ttl(account_key)
                retry_after_val = max(1, retry_after if retry_after > 0 else settings.LOGIN_ACCOUNT_WINDOW_SECONDS)
                logger.warning(
                    f"Login rate limit exceeded for account hash: {account_hash} "
                    f"({acc_count}/{settings.LOGIN_ACCOUNT_MAX_ATTEMPTS} attempts, retry-after: {retry_after_val}s)"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after_val)}
                )

    def record_failed_attempt(self, request: Request, email: str) -> None:
        """
        Record a failed credential attempt on both IP and account counters.
        """
        if not settings.LOGIN_RATE_LIMIT_ENABLED:
            return

        client_ip = self.get_client_ip(request)
        account_hash = self._account_hash(email)

        ip_key = f"ratelimit:login:ip:{client_ip}"
        account_key = f"ratelimit:login:account:{account_hash}"

        redis_service.incr(ip_key, expire_seconds=settings.LOGIN_IP_WINDOW_SECONDS)
        redis_service.incr(account_key, expire_seconds=settings.LOGIN_ACCOUNT_WINDOW_SECONDS)

    def record_successful_attempt(self, request: Request, email: str) -> None:
        """
        Reset account-level failure counter upon valid login.
        IP counter remains un-reset to prevent credential cycling attacks.
        """
        if not settings.LOGIN_RATE_LIMIT_ENABLED:
            return

        account_hash = self._account_hash(email)
        account_key = f"ratelimit:login:account:{account_hash}"
        redis_service.delete(account_key)


login_rate_limiter = LoginRateLimiter()
