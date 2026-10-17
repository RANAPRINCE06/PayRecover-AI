import time
import uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.auth import (
    create_access_token,
    decode_access_token,
    revoke_token,
    is_token_revoked
)
from app.services.redis_service import redis_service
from app.db.seed_data import seed_database
from app.models.entities import RecoveryCase
from app.db.session import SessionLocal

client = TestClient(app)


def setup_module(module):
    """Seed DB before running security tests."""
    seed_database()


@pytest.fixture(autouse=True)
def clean_redis_state():
    """Ensure in-memory fallback state is clean before each test."""
    redis_service.clear_in_memory()
    yield
    redis_service.clear_in_memory()


# ============================================================================
# 1. JWT STRUCTURE & REVOCATION TESTS (Items 1-10)
# ============================================================================

def test_1_jwt_contains_unique_jti():
    """1. Every issued JWT must contain a unique token identifier (jti)."""
    token_1 = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}).json()["access_token"]
    token_2 = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}).json()["access_token"]

    payload_1 = decode_access_token(token_1)
    payload_2 = decode_access_token(token_2)

    assert "jti" in payload_1
    assert "jti" in payload_2
    assert payload_1["jti"].startswith("jwt_") or payload_1["jti"].startswith("token_")
    assert payload_1["jti"] != payload_2["jti"], "Different tokens must have unique JTIs"


def test_2_valid_token_works():
    """2. Valid unexpired, unrevoked token works on protected endpoints."""
    res_login = client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]

    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "operator@payrecover.ai"


def test_3_expired_token_rejected():
    """3. Expired token is rejected with HTTP 401."""
    expired_token = create_access_token(
        data={"sub": "usr_admin", "email": "admin@payrecover.ai", "role": "ADMIN"},
        expires_delta=timedelta(seconds=-10)
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_4_revoked_token_rejected():
    """4. Server-side revoked token is rejected with HTTP 401."""
    res_login = client.post("/api/auth/login", json={"email": "viewer@payrecover.ai", "password": "Viewer@123"})
    token = res_login.json()["access_token"]
    payload = decode_access_token(token)

    # Manually revoke
    assert revoke_token(token) is True
    assert is_token_revoked(payload["jti"]) is True

    # Request with revoked token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "revoked" in res.json()["detail"].lower()


def test_5_logout_revokes_current_token():
    """5. POST /api/auth/logout revokes the token presented."""
    res_login = client.post("/api/auth/login", json={"email": "analyst@payrecover.ai", "password": "Analyst@123"})
    token = res_login.json()["access_token"]

    res_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res_logout.status_code == 200
    assert "Logged out successfully" in res_logout.json()["message"]

    # Verify token is now rejected
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 401
    assert "revoked" in res_me.json()["detail"].lower()


def test_6_revoked_token_cannot_access_auth_me():
    """6. Revoked token cannot access GET /api/auth/me."""
    res_login = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"})
    token = res_login.json()["access_token"]

    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_7_revoked_token_cannot_access_protected_mutations():
    """7. Revoked token cannot execute state-changing protected mutations."""
    res_login = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"})
    admin_token = res_login.json()["access_token"]

    # Logout to revoke
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})

    # Attempt mutation 1: Guardrails update
    res1 = client.put("/api/guardrails", json={"max_retries": 4}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res1.status_code == 401, f"Expected 401 on revoked token at /guardrails, got {res1.status_code}"

    # Attempt mutation 2: Demo reset
    res2 = client.post("/api/demo/reset", headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 401, f"Expected 401 on revoked token at /demo/reset, got {res2.status_code}"


def test_8_logout_twice_is_safe_and_idempotent():
    """8. Logout must be idempotent: calling logout twice does not cause an error."""
    res_login = client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
    token = res_login.json()["access_token"]

    # First logout
    res1 = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200

    # Second logout with same token
    res2 = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert "Logged out successfully" in res2.json()["message"]


def test_9_revoking_token_a_does_not_revoke_token_b():
    """9. Revoking token A does not revoke unrelated token B for the same user."""
    res_a = client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
    token_a = res_a.json()["access_token"]

    res_b = client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
    token_b = res_b.json()["access_token"]

    # Revoke Token A
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token_a}"})

    # Token A is rejected
    res_check_a = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert res_check_a.status_code == 401

    # Token B remains completely valid!
    res_check_b = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert res_check_b.status_code == 200
    assert res_check_b.json()["email"] == "operator@payrecover.ai"


def test_10_revocation_ttl_matches_remaining_token_lifetime():
    """10. Revocation record uses TTL equal to remaining lifetime."""
    short_token = create_access_token(
        data={"sub": "usr_temp", "email": "temp@payrecover.ai", "role": "VIEWER"},
        expires_delta=timedelta(seconds=120)
    )
    payload = decode_access_token(short_token)
    revoke_token(short_token)

    ttl = redis_service.ttl(f"auth:revoked:{payload['jti']}")
    assert 0 < ttl <= 120, f"TTL must match remaining lifetime (got {ttl})"


# ============================================================================
# 2. REDIS FAILURE & RESILIENCE TESTS (Items 11-13)
# ============================================================================

def test_11_redis_available_revocation_works():
    """11. Revocation works normally when storage layer is available."""
    token = create_access_token({"sub": "usr_test", "email": "test@payrecover.ai", "role": "VIEWER"})
    payload = decode_access_token(token)

    assert is_token_revoked(payload["jti"]) is False
    revoke_token(token)
    assert is_token_revoked(payload["jti"]) is True


def test_12_redis_unavailable_strict_fail_closed_mode():
    """12. If strict fail-closed mode is enabled and Redis is offline, service fails closed."""
    orig_fail_closed = settings.AUTH_FAIL_CLOSED_ON_REDIS_ERROR
    orig_connected = redis_service._is_connected
    try:
        settings.AUTH_FAIL_CLOSED_ON_REDIS_ERROR = True
        redis_service._is_connected = False

        token = create_access_token({"sub": "usr_fail_closed", "email": "fc@payrecover.ai", "role": "ADMIN"})
        payload = decode_access_token(token)

        # In fail-closed mode without Redis, checking revocation must raise 503
        with pytest.raises(Exception) as exc_info:
            is_token_revoked(payload["jti"])
        assert "503" in str(exc_info.value)
    finally:
        settings.AUTH_FAIL_CLOSED_ON_REDIS_ERROR = orig_fail_closed
        redis_service._is_connected = orig_connected


def test_13_redis_fallback_does_not_silently_create_security_bypass():
    """13. Resilient in-memory fallback ensures revocation works even when live Redis server is offline."""
    orig_connected = redis_service._is_connected
    try:
        # Simulate live Redis server unavailable
        redis_service._is_connected = False

        token = create_access_token({"sub": "usr_fallback", "email": "fallback@payrecover.ai", "role": "OPERATOR"})
        payload = decode_access_token(token)

        # Revoke token while Redis is offline
        revoke_token(token)

        # Fallback store must record the revocation — not silently ignore it!
        assert is_token_revoked(payload["jti"]) is True

        # Subsequent auth check must reject the token
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "revoked" in res.json()["detail"].lower()
    finally:
        redis_service._is_connected = orig_connected


# ============================================================================
# 3. RATE LIMITING TESTS (Items 14-22)
# ============================================================================

def test_14_repeated_failed_logins_from_same_ip_returns_429():
    """14. Repeated failed logins from same IP return 429 Too Many Requests."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 3
        headers = {"X-Forwarded-For": "203.0.113.10"}

        # Attempts 1, 2, 3 fail with 401
        for i in range(3):
            res = client.post("/api/auth/login", json={"email": f"victim_{i}@payrecover.ai", "password": "BadPassword"}, headers=headers)
            assert res.status_code == 401

        # Attempt 4 blocked by IP rate limit -> 429
        res4 = client.post("/api/auth/login", json={"email": "victim_4@payrecover.ai", "password": "BadPassword"}, headers=headers)
        assert res4.status_code == 429
        assert "too many" in res4.json()["detail"].lower()
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max


def test_15_repeated_failed_logins_against_same_account_returns_429():
    """15. Repeated failed logins against same account from multiple IPs return 429."""
    orig_max = settings.LOGIN_ACCOUNT_MAX_ATTEMPTS
    try:
        settings.LOGIN_ACCOUNT_MAX_ATTEMPTS = 3
        target_email = "bruteforce_target@payrecover.ai"

        # 3 attempts from 3 distinct IPs
        for i in range(3):
            ip_header = {"X-Forwarded-For": f"198.51.100.{i+1}"}
            res = client.post("/api/auth/login", json={"email": target_email, "password": "WrongPassword"}, headers=ip_header)
            assert res.status_code == 401

        # 4th attempt from a fresh 4th IP against the same account -> blocked with 429
        res4 = client.post("/api/auth/login", json={"email": target_email, "password": "WrongPassword"}, headers={"X-Forwarded-For": "198.51.100.99"})
        assert res4.status_code == 429
        assert "too many" in res4.json()["detail"].lower()
    finally:
        settings.LOGIN_ACCOUNT_MAX_ATTEMPTS = orig_max


def test_16_retry_after_header_present_on_rate_limit():
    """16. Rate limited response includes a valid numeric Retry-After header."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 2
        headers = {"X-Forwarded-For": "192.0.2.55"}

        client.post("/api/auth/login", json={"email": "a@payrecover.ai", "password": "wrong"}, headers=headers)
        client.post("/api/auth/login", json={"email": "a@payrecover.ai", "password": "wrong"}, headers=headers)

        res_limited = client.post("/api/auth/login", json={"email": "a@payrecover.ai", "password": "wrong"}, headers=headers)
        assert res_limited.status_code == 429
        assert "Retry-After" in res_limited.headers
        retry_val = int(res_limited.headers["Retry-After"])
        assert retry_val > 0
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max


def test_17_successful_login_does_not_count_as_failed_attempt():
    """17. Successful login does not increment failed attempt counters."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 3
        headers = {"X-Forwarded-For": "192.0.2.77"}

        # 5 successful logins in a row from the same IP
        for _ in range(5):
            res = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers=headers)
            assert res.status_code == 200
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max


def test_18_separate_ips_independently_tracked():
    """18. Rate limit on IP A does not affect requests from IP B."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 2
        ip_a = {"X-Forwarded-For": "10.0.0.1"}
        ip_b = {"X-Forwarded-For": "10.0.0.2"}

        # Exhaust IP A limit
        client.post("/api/auth/login", json={"email": "u1@payrecover.ai", "password": "wrong"}, headers=ip_a)
        client.post("/api/auth/login", json={"email": "u2@payrecover.ai", "password": "wrong"}, headers=ip_a)
        res_a = client.post("/api/auth/login", json={"email": "u3@payrecover.ai", "password": "wrong"}, headers=ip_a)
        assert res_a.status_code == 429

        # IP B should NOT be rate limited
        res_b = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers=ip_b)
        assert res_b.status_code == 200
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max


def test_19_separate_accounts_independently_tracked():
    """19. Rate limit on Account A does not affect Account B."""
    orig_max = settings.LOGIN_ACCOUNT_MAX_ATTEMPTS
    try:
        settings.LOGIN_ACCOUNT_MAX_ATTEMPTS = 2
        
        # Exhaust Account A limit using varied IPs
        client.post("/api/auth/login", json={"email": "acc_a@payrecover.ai", "password": "wrong"}, headers={"X-Forwarded-For": "1.1.1.1"})
        client.post("/api/auth/login", json={"email": "acc_a@payrecover.ai", "password": "wrong"}, headers={"X-Forwarded-For": "1.1.1.2"})
        res_a = client.post("/api/auth/login", json={"email": "acc_a@payrecover.ai", "password": "wrong"}, headers={"X-Forwarded-For": "1.1.1.3"})
        assert res_a.status_code == 429

        # Account B should not be rate limited
        res_b = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers={"X-Forwarded-For": "1.1.1.4"})
        assert res_b.status_code == 200
    finally:
        settings.LOGIN_ACCOUNT_MAX_ATTEMPTS = orig_max


def test_20_limits_reset_after_window_expires():
    """20. Expired rate-limit windows permit subsequent login attempts."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    orig_window = settings.LOGIN_IP_WINDOW_SECONDS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 2
        settings.LOGIN_IP_WINDOW_SECONDS = 1  # 1 second window
        headers = {"X-Forwarded-For": "192.168.10.99"}

        client.post("/api/auth/login", json={"email": "t@payrecover.ai", "password": "wrong"}, headers=headers)
        client.post("/api/auth/login", json={"email": "t@payrecover.ai", "password": "wrong"}, headers=headers)

        res_blocked = client.post("/api/auth/login", json={"email": "t@payrecover.ai", "password": "wrong"}, headers=headers)
        assert res_blocked.status_code == 429

        # Wait for window to expire
        time.sleep(1.2)

        # After window expires, should be allowed again
        res_after = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers=headers)
        assert res_after.status_code == 200
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max
        settings.LOGIN_IP_WINDOW_SECONDS = orig_window


def test_21_rate_limiting_cannot_be_bypassed_by_malformed_credentials():
    """21. Malformed or unusual credentials cannot bypass rate limiting."""
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 2
        headers = {"X-Forwarded-For": "172.16.0.44"}

        # Attempt with SQL injection payload and Unicode
        client.post("/api/auth/login", json={"email": "' OR '1'='1", "password": "bad'--"}, headers=headers)
        client.post("/api/auth/login", json={"email": "\x00nullbyte", "password": "bad\u2603"}, headers=headers)

        # Next request must be rate limited
        res = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers=headers)
        assert res.status_code == 429
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max


def test_22_rate_limiting_cannot_expose_account_existence():
    """22. Responses for nonexistent vs existent accounts are indistinguishable under rate limit and failure."""
    # 1. Compare failed 401 responses
    res_fake = client.post("/api/auth/login", json={"email": "completely_fake_nonexistent@payrecover.ai", "password": "WrongPassword"})
    res_real = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "WrongPassword"})

    assert res_fake.status_code == 401
    assert res_real.status_code == 401
    assert res_fake.json() == res_real.json() == {"detail": "Invalid email or password."}

    # 2. Compare 429 rate limit responses
    orig_max = settings.LOGIN_IP_MAX_ATTEMPTS
    try:
        settings.LOGIN_IP_MAX_ATTEMPTS = 1
        headers = {"X-Forwarded-For": "10.99.99.99"}

        client.post("/api/auth/login", json={"email": "fake1@payrecover.ai", "password": "wrong"}, headers=headers)
        res_limit = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"}, headers=headers)

        assert res_limit.status_code == 429
        # Does not leak account details or Redis keys
        assert "admin@payrecover.ai" not in res_limit.text
        assert "ratelimit" not in res_limit.text
        assert res_limit.json()["detail"] == "Too many login attempts. Please try again later."
    finally:
        settings.LOGIN_IP_MAX_ATTEMPTS = orig_max
