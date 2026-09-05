import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    Payment,
    RecoveryCase,
    Customer,
    MerchantGuardrail,
    RecoveryStatus,
    PaymentStatus
)
from app.services.opportunity_service import opportunity_scoring_engine

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_headers():
    """Login as Admin to get bearer token."""
    res = client.post("/api/auth/login", json={"email": "admin@payrecover.ai", "password": "Admin@123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------
# 1. Copilot Endpoint & Grounding Tests
# -------------------------------------------------------------

def test_copilot_endpoint_basic(auth_headers):
    """Test POST /api/ai/copilot returns valid structured schema."""
    res = client.post(
        "/api/ai/copilot",
        json={"message": "What is my biggest recovery opportunity?"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data or "reply" in data
    assert isinstance(data["insights"], list)
    assert isinstance(data["recommended_actions"], list)
    assert "confidence" in data
    assert data["confidence"] >= 0.0 and data["confidence"] <= 1.0
    assert data["confidence_level"] in ["HIGH", "MEDIUM", "LOW"]
    assert isinstance(data["data_sources"], list)
    assert len(data["data_sources"]) > 0


def test_copilot_empty_query_rejected(auth_headers):
    """Test POST /api/ai/copilot rejects blank queries."""
    res = client.post("/api/ai/copilot", json={"message": "   "}, headers=auth_headers)
    assert res.status_code == 400


def test_copilot_natural_language_queries(auth_headers):
    """Test various merchant domain questions."""
    questions = [
        "How much revenue is currently at risk?",
        "Which payment method is failing the most?",
        "Why did payments fail?",
        "What should I fix first?"
    ]
    for q in questions:
        res = client.post("/api/ai/copilot", json={"message": q}, headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert len(body["answer"]) > 10
        assert len(body["insights"]) > 0


# -------------------------------------------------------------
# 2. Opportunity Scoring Engine Tests
# -------------------------------------------------------------

def test_opportunity_scoring_calculation(db_session):
    """Test deterministic 0-100 scoring engine."""
    case = db_session.query(RecoveryCase).first()
    assert case is not None

    score_resp = opportunity_scoring_engine.calculate_score(case)
    assert score_resp.score >= 0.0 and score_resp.score <= 100.0
    assert score_resp.priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert isinstance(score_resp.positive_factors, list)
    assert isinstance(score_resp.negative_factors, list)
    assert score_resp.is_heuristic is True
    assert score_resp.estimated_recovery_probability >= 0.0 and score_resp.estimated_recovery_probability <= 1.0


def test_opportunity_scoring_status_gating(db_session):
    """Test completed/failed cases status gating in scoring engine."""
    case = db_session.query(RecoveryCase).first()
    assert case is not None

    orig_status = case.status
    try:
        case.status = RecoveryStatus.RECOVERED.value
        recovered_score = opportunity_scoring_engine.calculate_score(case)
        assert recovered_score.score == 100.0
        assert recovered_score.estimated_recovery_probability == 1.0

        case.status = RecoveryStatus.FAILED.value
        failed_score = opportunity_scoring_engine.calculate_score(case)
        assert failed_score.score == 0.0
        assert failed_score.estimated_recovery_probability == 0.0
    finally:
        case.status = orig_status
        db_session.commit()


# -------------------------------------------------------------
# 3. Revenue At Risk API Tests
# -------------------------------------------------------------

def test_revenue_at_risk_endpoint(auth_headers):
    """Test GET /api/analytics/revenue-at-risk."""
    res = client.get("/api/analytics/revenue-at-risk", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "critical" in data
    assert "high" in data
    assert "medium" in data
    assert "low" in data
    assert "case_count" in data
    assert isinstance(data["trend"], list)
    assert data["total"] >= 0.0


# -------------------------------------------------------------
# 4. AI Operations Metrics API Tests
# -------------------------------------------------------------

def test_ai_operations_metrics(auth_headers):
    """Test GET /api/analytics/ai-metrics."""
    res = client.get("/api/analytics/ai-metrics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "ai_decisions_count" in data
    assert "ai_success_rate" in data
    assert "average_ai_latency_ms" in data
    assert "human_escalation_rate" in data
    assert "tool_success_rate" in data
    assert data["active_agents"] == 4


# -------------------------------------------------------------
# 5. AI Decision Explanation & Opportunity API Tests
# -------------------------------------------------------------

def test_case_decision_explanation(db_session, auth_headers):
    """Test GET /api/recovery/{case_id}/explanation."""
    case = db_session.query(RecoveryCase).first()
    assert case is not None

    res = client.get(f"/api/recovery/{case.id}/explanation", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case.id
    assert "decision" in data
    assert "reason" in data
    assert isinstance(data["evidence"], list)
    assert isinstance(data["customer_context"], dict)
    assert isinstance(data["risk_factors"], list)
    assert isinstance(data["guardrail_result"], dict)
    assert data["confidence"] >= 0.0 and data["confidence"] <= 1.0
    assert data["confidence_level"] in ["HIGH", "MEDIUM", "LOW"]
    assert "recommended_next_step" in data


def test_case_opportunity_score_endpoint(db_session, auth_headers):
    """Test GET /api/recovery/{case_id}/opportunity."""
    case = db_session.query(RecoveryCase).first()
    assert case is not None

    res = client.get(f"/api/recovery/{case.id}/opportunity", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case.id
    assert data["score"] >= 0.0 and data["score"] <= 100.0
    assert data["priority"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert "estimated_recovery_probability" in data


# -------------------------------------------------------------
# 6. Agent Traces API Tests
# -------------------------------------------------------------

def test_case_agent_trace(db_session, auth_headers):
    """Test GET /api/recovery/{case_id}/trace."""
    case = db_session.query(RecoveryCase).first()
    assert case is not None

    res = client.get(f"/api/recovery/{case.id}/trace", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case.id
    assert "timeline" in data
    assert data["timeline"] == ["INVESTIGATE", "INTENT", "STRATEGY", "GUARDRAIL", "EXECUTE", "SETTLE"]
    assert len(data["steps"]) == 6
    for step in data["steps"]:
        assert "stage_name" in step
        assert "agent" in step
        assert "status" in step
        assert "duration_ms" in step


def test_recent_agent_traces(auth_headers):
    """Test GET /api/recovery/traces."""
    res = client.get("/api/recovery/traces", headers=auth_headers)
    assert res.status_code == 200
    traces = res.json()
    assert isinstance(traces, list)
    if traces:
        assert "run_id" in traces[0]
        assert "steps" in traces[0]


# -------------------------------------------------------------
# 7. AI Recommendations API Tests
# -------------------------------------------------------------

def test_ai_recommendations(auth_headers):
    """Test GET /api/recovery/recommendations."""
    res = client.get("/api/recovery/recommendations", headers=auth_headers)
    assert res.status_code == 200
    recs = res.json()
    assert isinstance(recs, list)
    if recs:
        first = recs[0]
        assert "case_id" in first
        assert "amount" in first
        assert "opportunity_score" in first
        assert "confidence" in first
        assert "expected_recovery" in first
        assert "requires_human_approval" in first


# -------------------------------------------------------------
# 8. Data Sanitization & Safety
# -------------------------------------------------------------

def test_copilot_context_sanitization(db_session):
    """Verify copilot context does not contain passwords or secrets."""
    from app.services.copilot_service import copilot_service
    context = copilot_service.build_database_context(db_session)
    context_str = str(context).lower()

    assert "password" not in context_str
    assert "secret" not in context_str
    assert "token" not in context_str
    assert "authorization" not in context_str
