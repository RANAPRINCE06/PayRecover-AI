import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import Payment, RecoveryCase, AgentAction, Customer, CustomerInteraction
from app.schemas.contracts import PaymentInvestigationResult, CustomerIntentResult, CustomerIntentRequest

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

def test_investigator_valid_payment_succeeds():
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.status == "FAILED").first()
    db.close()
    assert payment is not None

    res = client.post("/api/ai/analyze-payment", json={"payment_id": payment.id})
    assert res.status_code == 200
    data = res.json()

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


def test_investigator_unknown_payment_id_404():
    res = client.post("/api/ai/analyze-payment", json={"payment_id": "pay_nonexistent_99999"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_investigator_gemini_service_error_handling():
    db = SessionLocal()
    payment = db.query(Payment).first()
    db.close()

    with patch("app.services.gemini_service.GeminiService._call_gemini_rest", side_effect=Exception("API Gateway 503")):
        res = client.post("/api/ai/analyze-payment", json={"payment_id": payment.id})
        assert res.status_code == 200
        data = res.json()
        assert data["payment_id"] == payment.id
        assert "recovery_score" in data


def test_investigator_malformed_ai_output_handled():
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="invalid_category",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability="not-a-float",
            recovery_score=85,
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_investigator_recovery_score_range_validation():
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="technical",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability=0.85,
            recovery_score=150,
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_investigator_recovery_probability_range_validation():
    with pytest.raises(ValidationError):
        PaymentInvestigationResult(
            payment_id="pay_test",
            failure_category="technical",
            failure_explanation="Test",
            customer_profile_summary="Test",
            payment_history_summary="Test",
            recovery_probability=1.5,
            recovery_score=85,
            risk_level="LOW",
            recommended_next_action="RETRY",
            reasoning_summary="Test",
            confidence=0.9
        )


def test_investigator_records_agent_action():
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.id == "pay_demo_12999").first()
    if not payment:
        payment = db.query(Payment).first()
    payment_id = payment.id
    db.close()

    res = client.post("/api/ai/analyze-payment", json={"payment_id": payment_id})
    assert res.status_code == 200

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
    db.close()


# -------------------------------------------------------------
# PHASE 3 - Customer Intent AI Engine Tests (14 Required Tests)
# -------------------------------------------------------------

def test_intent_1_alternate_payment_method():
    """Test 1: 'My card isn't working. Can I use UPI?' -> ALTERNATE_PAYMENT_METHOD"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "My card isn't working. Can I use UPI?",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "ALTERNATE_PAYMENT_METHOD"
    assert data["recommended_action"] in ["OFFER_ALTERNATE_PAYMENT", "PROVIDE_PAYMENT_LINK"]
    assert 0.0 <= data["confidence"] <= 1.0


def test_intent_2_will_pay_later():
    """Test 2: 'I don't have enough balance right now. Remind me tomorrow.' -> WILL_PAY_LATER"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "I don't have enough balance right now. Remind me tomorrow.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "WILL_PAY_LATER"
    assert data["recommended_action"] == "WAIT_AND_FOLLOW_UP"


def test_intent_3_already_paid():
    """Test 3: 'I already completed the payment. Please verify.' -> ALREADY_PAID"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "I already completed the payment. Please verify.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "ALREADY_PAID"
    assert data["recommended_action"] == "REVIEW_PAYMENT_STATUS"


def test_intent_4_cancel_request():
    """Test 4: 'Please cancel this. I don't want it.' -> CANCEL_REQUEST"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "Please cancel this. I don't want it.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["CANCEL_REQUEST", "NOT_INTERESTED"]
    assert data["recommended_action"] == "STOP_CONTACT"


def test_intent_5_payment_link_request():
    """Test 5: 'Can you send me a payment link?' -> PAYMENT_LINK_REQUEST"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "Can you send me a payment link?",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "PAYMENT_LINK_REQUEST"
    assert data["recommended_action"] == "PROVIDE_PAYMENT_LINK"


def test_intent_6_empty_message_rejected():
    """Test 6: Empty message -> validation error (422)"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": "   ",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 422


def test_intent_7_unknown_customer_404():
    """Test 7: Unknown customer -> 404"""
    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": "cust_nonexistent_9999",
        "message": "Hello, my payment failed.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_intent_8_unknown_recovery_case_error():
    """Test 8: Unknown recovery case -> controlled error"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "recovery_case_id": "rc_nonexistent_9999",
        "message": "Hello, my payment failed.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 404 or res.status_code == 400


def test_intent_9_gemini_failure_handled_safely():
    """Test 9: Gemini failure is handled safely"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    db.close()

    with patch("app.services.gemini_service.GeminiService._call_gemini_rest", side_effect=Exception("Timeout 504")):
        res = client.post("/api/ai/analyze-intent", json={
            "customer_id": cust.id,
            "message": "Can I pay through UPI instead?",
            "channel": "WHATSAPP"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "ALTERNATE_PAYMENT_METHOD"


def test_intent_10_invalid_confidence_rejected():
    """Test 10: Invalid confidence rejected by Pydantic"""
    with pytest.raises(ValidationError):
        CustomerIntentResult(
            customer_id="cust_1",
            intent="ALTERNATE_PAYMENT_METHOD",
            confidence=1.5,  # Invalid: > 1.0
            sentiment="POSITIVE",
            urgency="HIGH",
            intent_summary="Test",
            evidence=["Test"],
            recommended_channel="WHATSAPP",
            recommended_action="OFFER_ALTERNATE_PAYMENT",
            reasoning_summary="Test"
        )


def test_intent_11_customer_interaction_created():
    """Test 11: Successful intent analysis -> CustomerInteraction record created"""
    db = SessionLocal()
    cust = db.query(Customer).first()
    msg = "Where is my payment link?"
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "message": msg,
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200

    db = SessionLocal()
    interaction = (
        db.query(CustomerInteraction)
        .filter(CustomerInteraction.customer_id == cust.id, CustomerInteraction.message == msg)
        .order_by(CustomerInteraction.created_at.desc())
        .first()
    )
    assert interaction is not None
    assert interaction.detected_intent == "PAYMENT_LINK_REQUEST"
    assert interaction.direction == "INBOUND"
    db.close()


def test_intent_12_agent_action_created():
    """Test 12: Successful intent analysis with recovery case -> AgentAction created"""
    db = SessionLocal()
    rc = db.query(RecoveryCase).first()
    cust_id = rc.payment.customer_id
    rc_id = rc.id
    db.close()

    res = client.post("/api/ai/analyze-intent", json={
        "customer_id": cust_id,
        "recovery_case_id": rc_id,
        "message": "Please cancel my order.",
        "channel": "WHATSAPP"
    })
    assert res.status_code == 200

    db = SessionLocal()
    action = (
        db.query(AgentAction)
        .filter(AgentAction.recovery_case_id == rc_id, AgentAction.agent_type == "INTENT_AI")
        .order_by(AgentAction.created_at.desc())
        .first()
    )
    assert action is not None
    assert action.action_type == "CUSTOMER_INTENT_ANALYSIS"
    db.close()


def test_simulation_demo_flow_backward_compatible():
    """Test 14: Existing Razorpay/mock recovery demo remains passing"""
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
