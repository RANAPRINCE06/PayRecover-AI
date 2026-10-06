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

    op_token = get_token_for("operator@payrecover.ai", "Operator@123")

    # First execution
    res1 = client.post(
        f"/api/recovery/{case.id}/execute",
        json={"tool_type": "CREATE_PAYMENT_LINK", "parameters": {"payment_method": "UPI"}},
        headers={"Idempotency-Key": key, "Authorization": f"Bearer {op_token}"}
    )
    assert res1.status_code == 200
    data1 = res1.json()

    # Replay with identical key
    res2 = client.post(
        f"/api/recovery/{case.id}/execute",
        json={"tool_type": "CREATE_PAYMENT_LINK", "parameters": {"payment_method": "UPI"}},
        headers={"Idempotency-Key": key, "Authorization": f"Bearer {op_token}"}
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
        op_token = get_token_for("operator@payrecover.ai", "Operator@123")
        res = client.post(
            f"/api/recovery/{case.id}/execute",
            headers={"Authorization": f"Bearer {op_token}"}
        )
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


# -------------------------------------------------------------
# 6. COMPREHENSIVE AUTH & RBAC SECURITY TEST SUITE (PHASE 1)
# -------------------------------------------------------------

def test_security_unauthenticated_requests_rejected_with_401():
    """A. No token: all state-changing endpoints must reject with HTTP 401."""
    fake_case_id = "rc_audit_unauth_case"

    # 1. Guardrail update -> 401
    res = client.put("/api/guardrails", json={"max_retries": 4})
    assert res.status_code == 401, f"Expected 401 for PUT /guardrails without token, got {res.status_code}"

    # 2. Recovery execute -> 401
    res = client.post(f"/api/recovery/{fake_case_id}/execute", json={})
    assert res.status_code == 401, f"Expected 401 for POST /recovery/{fake_case_id}/execute without token, got {res.status_code}"

    # 3. Recovery approve -> 401
    res = client.post(f"/api/recovery/{fake_case_id}/approve")
    assert res.status_code == 401, f"Expected 401 for POST /recovery/{fake_case_id}/approve without token, got {res.status_code}"

    # 4. Recovery reject -> 401
    res = client.post(f"/api/recovery/{fake_case_id}/reject", json={"reason": "Customer cancelled"})
    assert res.status_code == 401, f"Expected 401 for POST /recovery/{fake_case_id}/reject without token, got {res.status_code}"

    # 5. Confirm settlement -> 401
    res = client.post(f"/api/recovery/{fake_case_id}/confirm-settlement")
    assert res.status_code == 401, f"Expected 401 for POST /recovery/{fake_case_id}/confirm-settlement without token, got {res.status_code}"

    # 6. Autonomous recovery -> 401
    res = client.post(f"/api/recovery/{fake_case_id}/autonomous")
    assert res.status_code == 401, f"Expected 401 for POST /recovery/{fake_case_id}/autonomous without token, got {res.status_code}"

    # 7. Demo reset -> 401
    res = client.post("/api/demo/reset")
    assert res.status_code == 401, f"Expected 401 for POST /demo/reset without token, got {res.status_code}"


def test_security_invalid_token_rejected_with_401():
    """B. Invalid token: all protected mutations must return HTTP 401."""
    fake_case_id = "rc_audit_invalid_case"
    bad_headers = {"Authorization": "Bearer invalid_malformed_token_signature_xyz"}

    mutations = [
        ("PUT", "/api/guardrails", {"json": {"max_retries": 4}}),
        ("POST", f"/api/recovery/{fake_case_id}/execute", {"json": {}}),
        ("POST", f"/api/recovery/{fake_case_id}/approve", {}),
        ("POST", f"/api/recovery/{fake_case_id}/reject", {"json": {"reason": "test"}}),
        ("POST", f"/api/recovery/{fake_case_id}/confirm-settlement", {}),
        ("POST", f"/api/recovery/{fake_case_id}/autonomous", {}),
        ("POST", "/api/demo/reset", {}),
    ]

    for method, path, kwargs in mutations:
        if method == "PUT":
            res = client.put(path, headers=bad_headers, **kwargs)
        else:
            res = client.post(path, headers=bad_headers, **kwargs)
        assert res.status_code == 401, f"Expected 401 for invalid token at {method} {path}, got {res.status_code}"


def test_security_viewer_token_denied_mutations_with_403():
    """C. VIEWER token: unauthorized mutation attempts must return HTTP 403."""
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    headers = {"Authorization": f"Bearer {viewer_token}"}
    fake_case_id = "rc_audit_viewer_case"

    mutations = [
        ("PUT", "/api/guardrails", {"json": {"max_retries": 5}}),
        ("POST", f"/api/recovery/{fake_case_id}/execute", {"json": {}}),
        ("POST", f"/api/recovery/{fake_case_id}/approve", {}),
        ("POST", f"/api/recovery/{fake_case_id}/reject", {"json": {"reason": "test"}}),
        ("POST", f"/api/recovery/{fake_case_id}/confirm-settlement", {}),
        ("POST", f"/api/recovery/{fake_case_id}/autonomous", {}),
        ("POST", "/api/demo/reset", {}),
    ]

    for method, path, kwargs in mutations:
        if method == "PUT":
            res = client.put(path, headers=headers, **kwargs)
        else:
            res = client.post(path, headers=headers, **kwargs)
        assert res.status_code == 403, f"Expected 403 for VIEWER at {method} {path}, got {res.status_code}"


def test_security_analyst_token_denied_mutations_with_403():
    """D. ANALYST token: unauthorized mutation attempts must return HTTP 403."""
    analyst_token = get_token_for("analyst@payrecover.ai", "Analyst@123")
    headers = {"Authorization": f"Bearer {analyst_token}"}
    fake_case_id = "rc_audit_analyst_case"

    mutations = [
        ("PUT", "/api/guardrails", {"json": {"max_retries": 5}}),
        ("POST", f"/api/recovery/{fake_case_id}/execute", {"json": {}}),
        ("POST", f"/api/recovery/{fake_case_id}/approve", {}),
        ("POST", f"/api/recovery/{fake_case_id}/reject", {"json": {"reason": "test"}}),
        ("POST", f"/api/recovery/{fake_case_id}/confirm-settlement", {}),
        ("POST", f"/api/recovery/{fake_case_id}/autonomous", {}),
        ("POST", "/api/demo/reset", {}),
    ]

    for method, path, kwargs in mutations:
        if method == "PUT":
            res = client.put(path, headers=headers, **kwargs)
        else:
            res = client.post(path, headers=headers, **kwargs)
        assert res.status_code == 403, f"Expected 403 for ANALYST at {method} {path}, got {res.status_code}"


def test_security_operator_permissions_and_boundaries():
    """E. OPERATOR: allowed operational actions succeed, admin actions blocked."""
    op_token = get_token_for("operator@payrecover.ai", "Operator@123")
    headers = {"Authorization": f"Bearer {op_token}"}

    # 1. Blocked from Guardrails update (Admin-only)
    res_guard = client.put("/api/guardrails", json={"max_retries": 5}, headers=headers)
    assert res_guard.status_code == 403

    # 2. Blocked from User Management (Admin-only)
    res_users = client.get("/api/users", headers=headers)
    assert res_users.status_code == 403

    # 3. Allowed on operational settlement
    db = SessionLocal()
    case = db.query(RecoveryCase).first()
    db.close()
    assert case is not None

    res_settle = client.post(f"/api/recovery/{case.id}/confirm-settlement", headers=headers)
    assert res_settle.status_code == 200
    assert res_settle.json()["status"] == "RECOVERED"


def test_security_admin_full_access():
    """F. ADMIN: authorized administrative actions work."""
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin can update guardrails
    res_guard = client.put("/api/guardrails", json={"max_retries": 3}, headers=headers)
    assert res_guard.status_code == 200
    assert res_guard.json()["max_retries"] == 3

    # Admin can list users
    res_users = client.get("/api/users", headers=headers)
    assert res_users.status_code == 200
    assert len(res_users.json()) >= 4


def test_security_privilege_escalation_prevented():
    """Privilege escalation tests: non-admins cannot elevate roles or modify configuration."""
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    v_headers = {"Authorization": f"Bearer {viewer_token}"}

    # VIEWER cannot create an ADMIN account
    res_create = client.post("/api/users", json={
        "email": "malicious_admin@payrecover.ai",
        "name": "Malicious Admin",
        "role": "ADMIN",
        "password": "Password123"
    }, headers=v_headers)
    assert res_create.status_code == 403

    # VIEWER cannot modify existing user role
    res_edit = client.put("/api/users/usr_viewer", json={"role": "ADMIN"}, headers=v_headers)
    assert res_edit.status_code == 403

    # ANALYST cannot modify guardrails
    analyst_token = get_token_for("analyst@payrecover.ai", "Analyst@123")
    a_headers = {"Authorization": f"Bearer {analyst_token}"}
    res_analyst_guard = client.put("/api/guardrails", json={"max_discount_percentage": 50.0}, headers=a_headers)
    assert res_analyst_guard.status_code == 403

