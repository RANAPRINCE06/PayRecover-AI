import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import Payment, RecoveryCase, AgentAction
from app.schemas.contracts import PaymentInvestigationResult

client = TestClient(app)


def setup_module(module):
    seed_database()


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "PayRecover AI"


def test_dashboard_metrics():
    res = client.get("/api/dashboard/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "revenue_processed" in data
    assert "recovery_rate" in data
    assert "monthly_trend" in data


# -------------------------------------------------------------
# PHASE 2 - AI Payment Investigator Tests
# -------------------------------------------------------------

def test_1_valid_payment_investigation_succeeds():
    """Test 1: Valid payment -> investigation succeeds with validated structured schema"""
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.status == "FAILED").first()
    db.close()
    assert payment is not None

    res = client.post("/api/ai/analyze-payment", json={"payment_id": payment.id})
    assert res.status_code == 200
    data = res.json()

    # Verify structured fields
    assert data["payment_id"] == payment.id
    assert "failure_category" in data
    assert "recovery_probability" in data
    assert 0.0 <= data["recovery_probability"] <= 1.0
    assert 0 <= data["recovery_score"] <= 100
    assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert "recommended_next_action" in data
    assert "contributing_factors" in data
    assert isinstance(data["contributing_factors"], list)
    assert "confidence" in data
    assert 0.0 <= data["confidence"] <= 1.0


def test_2_unknown_payment_id_returns_404():
    """Test 2: Unknown payment ID -> 404"""
    res = client.post("/api/ai/analyze-payment", json={"payment_id": "pay_nonexistent_99999"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_3_gemini_service_error_handling():
    """Test 3: Gemini service handles external API failures gracefully"""
    db = SessionLocal()
    payment = db.query(Payment).first()
    db.close()

    # Mock external API throwing an exception to verify fallback and non-crashing behavior
    with patch("app.services.gemini_service.GeminiService._call_gemini_rest", side_effect=Exception("API Gateway 503")):
        res = client.post("/api/ai/analyze-payment", json={"payment_id": payment.id})
        assert res.status_code == 200
        data = res.json()
        assert data["payment_id"] == payment.id
        assert "recovery_score" in data


def test_4_malformed_ai_output_handled_safely():
    """Test 4: Malformed AI output validation handled safely by Pydantic"""
    # Invalid failure category or types should trigger validation error
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="invalid_category",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability="not-a-float",  # type error
            recovery_score=85,
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_5_recovery_score_range_validation():
    """Test 5: Recovery score outside 0-100 rejected by Pydantic"""
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="technical",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability=0.85,
            recovery_score=150,  # Invalid: > 100
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )

    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="technical",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability=0.85,
            recovery_score=-5,  # Invalid: < 0
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_6_recovery_probability_range_validation():
    """Test 6: Recovery probability outside 0.0-1.0 rejected by Pydantic"""
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="technical",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability=1.5,  # Invalid: > 1.0
            recovery_score=85,
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_7_successful_investigation_records_agent_action():
    """Test 7: Successful investigation -> AgentAction created in DB"""
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.id == "pay_demo_12999").first()
    if not payment:
        payment = db.query(Payment).first()
    payment_id = payment.id
    db.close()

    res = client.post("/api/ai/analyze-payment", json={"payment_id": payment_id})
    assert res.status_code == 200

    # Verify AgentAction exists in DB
    db = SessionLocal()
    action = (
        db.query(AgentAction)
        .join(RecoveryCase)
        .filter(RecoveryCase.payment_id == payment_id, AgentAction.agent_type == "INVESTIGATOR")
        .order_by(AgentAction.created_at.desc())
        .first()
    )
    assert action is not None
    assert "AI Investigator" in action.reasoning_summary
    assert action.action_type in ["PAYMENT_INVESTIGATION", "INVESTIGATE_PAYMENT"]
    db.close()


def test_simulation_demo_flow():
    """Verify demo workflow stays fully intact"""
    payload = {
        "scenario_type": "DEMO_CARD_DECLINE_UPI",
        "amount": 12999.0
    }
    res = client.post("/api/recovery/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] is not None

    case_id = data["case_id"]
    rec_res = client.post(f"/api/recovery/{case_id}/confirm-settlement")
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "RECOVERED"
