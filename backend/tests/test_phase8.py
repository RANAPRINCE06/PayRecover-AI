import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import User, UserRole, Payment, RecoveryCase

client = TestClient(app)


def setup_module(module):
    """Ensure database schema is initialized and seeded."""
    seed_database()


def get_token_for(email: str, password: str) -> str:
    """Helper to log in and extract Bearer token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


# -------------------------------------------------------------
# 1. AUTHENTICATION TESTS
# -------------------------------------------------------------

def test_auth_login_success():
    res = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@payrecover.ai"
    assert data["user"]["role"] == "ADMIN"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_auth_login_invalid_password():
    res = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "WrongPassword"})
    assert res.status_code == 401
    assert "detail" in res.json()


def test_auth_login_unknown_user():
    res = client.post("/api/auth/login", json={"email": "nonexistent@payrecover.ai", "password": "Password123"})
    assert res.status_code == 401


def test_auth_me_authenticated():
    token = get_token_for("operator@payrecover.ai", "Operator@123")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "operator@payrecover.ai"
    assert data["role"] == "OPERATOR"
    assert data["name"] == "Priya Nair"


def test_auth_me_unauthenticated():
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_auth_me_invalid_token():
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_junk_token"})
    assert res.status_code == 401


def test_auth_logout():
    token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert "Logged out successfully" in res.json()["message"]


# -------------------------------------------------------------
# 2. RBAC TESTS
# -------------------------------------------------------------

def test_rbac_admin_allowed_user_management():
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    res = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert len(res.json()) >= 4


def test_rbac_operator_denied_user_management():
    op_token = get_token_for("operator@payrecover.ai", "Operator@123")
    res = client.get("/api/users", headers={"Authorization": f"Bearer {op_token}"})
    assert res.status_code == 403
    assert "Insufficient permissions" in res.json()["detail"]


def test_rbac_analyst_denied_user_management():
    analyst_token = get_token_for("analyst@payrecover.ai", "Analyst@123")
    res = client.get("/api/users", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 403


def test_rbac_viewer_denied_user_management():
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    res = client.get("/api/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res.status_code == 403


def test_rbac_admin_allowed_guardrail_update():
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    res = client.put(
        "/api/guardrails",
        json={"max_retries": 3},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    assert res.json()["max_retries"] == 3


def test_rbac_viewer_denied_guardrail_update():
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    res = client.put(
        "/api/guardrails",
        json={"max_retries": 5},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res.status_code == 403


# -------------------------------------------------------------
# 3. USER MANAGEMENT CRUD TESTS
# -------------------------------------------------------------

def test_user_management_create_user():
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    new_email = f"user_{uuid.uuid4().hex[:6]}@payrecover.ai"
    res = client.post(
        "/api/users",
        json={
            "email": new_email,
            "name": "Test Engineer",
            "role": "ANALYST",
            "password": "SecurePassword123"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    user_data = res.json()
    assert user_data["email"] == new_email
    assert user_data["role"] == "ANALYST"
    assert user_data["is_active"] is True

    # Check that new user can log in
    login_token = get_token_for(new_email, "SecurePassword123")
    assert login_token is not None


def test_user_management_duplicate_email_rejected():
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    res = client.post(
        "/api/users",
        json={
            "email": "admin@payrecover.ai",
            "name": "Duplicate Admin",
            "role": "ADMIN",
            "password": "Password123"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_user_management_toggle_active():
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    temp_email = f"temp_{uuid.uuid4().hex[:6]}@payrecover.ai"
    create_res = client.post(
        "/api/users",
        json={
            "email": temp_email,
            "name": "Temporary User",
            "role": "OPERATOR",
            "password": "Password123"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = create_res.json()["id"]

    # Toggle to deactivated
    toggle_res = client.post(f"/api/users/{user_id}/toggle-active", headers={"Authorization": f"Bearer {admin_token}"})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False

    # Try login as deactivated user -> should fail with 403
    login_res = client.post("/api/auth/login", json={"email": temp_email, "password": "Password123"})
    assert login_res.status_code == 403


# -------------------------------------------------------------
# 4. IDEMPOTENCY & CONCURRENCY TESTS
# -------------------------------------------------------------

def test_idempotency_key_replay():
    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.status != "RECOVERED").first()
    db.close()
    assert case is not None

    key = f"idem_test_{uuid.uuid4().hex}"

    # First execution
    res1 = client.post(
        f"/api/recovery/{case.id}/execute",
        json={"tool_type": "CREATE_PAYMENT_LINK", "parameters": {"payment_method": "UPI"}},
        headers={"Idempotency-Key": key}
    )
    assert res1.status_code == 200
    data1 = res1.json()

    # Replay with identical key
    res2 = client.post(
        f"/api/recovery/{case.id}/execute",
        json={"tool_type": "CREATE_PAYMENT_LINK", "parameters": {"payment_method": "UPI"}},
        headers={"Idempotency-Key": key}
    )
    assert res2.status_code == 200
    data2 = res2.json()

    # Must return identical execution outcome
    assert data1["execution_id"] == data2["execution_id"]
    assert data1["status"] == data2["status"]


def test_concurrency_already_recovered_safe():
    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.status == "RECOVERED").first()
    db.close()
    if case:
        res = client.post(f"/api/recovery/{case.id}/execute")
        assert res.status_code == 200
        assert "already been" in res.json()["message"]


# -------------------------------------------------------------
# 5. REAL-TIME EVENTS & SYSTEM HEALTH TESTS
# -------------------------------------------------------------

def test_events_recent_endpoint():
    res = client.get("/api/events/recent")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_system_health_endpoint():
    res = client.get("/api/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "services" in data
    assert "api" in data["services"]
    assert "database" in data["services"]
    assert "redis" in data["services"]
    assert "ai" in data["services"]
    assert "payment_engine" in data["services"]


def test_security_headers_and_correlation_id():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert "X-Correlation-ID" in res.headers
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
