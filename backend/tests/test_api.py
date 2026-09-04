import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import Payment, RecoveryCase, AgentAction, Customer, CustomerInteraction, MerchantGuardrail
from app.schemas.contracts import (
    PaymentInvestigationResult,
    CustomerIntentResult,
    CustomerIntentRequest,
    RecoveryStrategyResult,
    RecoveryStrategyProposal,
    RecoveryStrategyRequest,
    RecoveryStrategyType,
    GuardrailStatusType
)

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


# -------------------------------------------------------------
# PHASE 4 - AI Recovery Strategist & Guardrails Tests (14 Tests)
# -------------------------------------------------------------

def _setup_case_with_prerequisites(failure_reason="CARD_DECLINED", message="Can I pay using UPI?", amount=12999.0):
    """Helper to create a failed payment, recovery case, and prerequisite investigator & intent records."""
    import uuid
    from datetime import datetime
    from app.services.guardrail_service import guardrail_service

    db = SessionLocal()
    cust = db.query(Customer).first()

    payment = Payment(
        id=f"pay_strat_{uuid.uuid4().hex[:8]}",
        razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
        customer_id=cust.id,
        amount=amount,
        currency="INR",
        payment_method="CARD" if "CARD" in failure_reason else "UPI",
        status="FAILED",
        failure_reason=failure_reason,
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.flush()

    case = RecoveryCase(
        id=f"rc_strat_{uuid.uuid4().hex[:8]}",
        payment_id=payment.id,
        recovery_score=85.0,
        recovery_probability=0.85,
        status="IDENTIFIED",
        retry_count=0,
        started_at=datetime.utcnow()
    )
    db.add(case)
    db.commit()

    # Run investigator
    client.post("/api/ai/analyze-payment", json={"payment_id": payment.id})

    # Run intent
    client.post("/api/ai/analyze-intent", json={
        "customer_id": cust.id,
        "recovery_case_id": case.id,
        "message": message,
        "channel": "WHATSAPP"
    })

    case_id = case.id
    db.close()
    return case_id


def test_strategist_1_alternate_payment_method():
    """Test 1: Card 3DS failure + UPI customer request -> ALTERNATE_PAYMENT_METHOD via WhatsApp (UPI, SAFE)"""
    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "My card isn't working. Can I use UPI?", 12999.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["recovery_case_id"] == case_id
    assert data["primary_strategy"] == "ALTERNATE_PAYMENT_METHOD"
    assert data["recommended_channel"] == "WHATSAPP"
    assert data["recommended_payment_method"] == "UPI"
    assert data["guardrail_status"] == "SAFE"
    assert data["human_approval_required"] is False
    assert data["discount_percentage"] == 0.0
    assert 0.0 <= data["expected_recovery_probability"] <= 1.0
    assert 0.0 <= data["strategy_confidence"] <= 1.0


def test_strategist_2_retry_strategy():
    """Test 2: Transient network/gateway failure with retry intent -> RETRY_PAYMENT"""
    case_id = _setup_case_with_prerequisites("BANK_SERVER_DOWN", "Please retry the transaction.", 4500.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["primary_strategy"] == "RETRY_PAYMENT"
    assert data["guardrail_status"] == "SAFE"
    assert data["retry_count"] >= 1


def test_strategist_3_follow_up_strategy():
    """Test 3: Insufficient balance / pay later intent -> FOLLOW_UP"""
    case_id = _setup_case_with_prerequisites("INSUFFICIENT_FUNDS", "I don't have enough balance right now. Remind me tomorrow.", 8000.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["primary_strategy"] == "FOLLOW_UP"
    assert data["recommended_channel"] == "WHATSAPP"
    assert data["recommended_delay_minutes"] >= 0


def test_strategist_4_stop_recovery_strategy():
    """Test 4: Customer cancellation request -> STOP_RECOVERY"""
    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "Please cancel this order. I don't want it.", 3000.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["primary_strategy"] == "STOP_RECOVERY"
    assert data["recommended_channel"] == "NONE"


def test_strategist_5_verify_payment_strategy():
    """Test 5: Customer claims already paid -> VERIFY_PAYMENT"""
    case_id = _setup_case_with_prerequisites("UPI_TIMEOUT", "Money was already deducted from my bank account. Please verify.", 6500.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["primary_strategy"] == "VERIFY_PAYMENT"
    assert data["recommended_channel"] == "WHATSAPP"


def test_strategist_6_discount_cap_guardrail():
    """Test 6: Proposal with excessive discount (15%) is deterministically capped at merchant maximum (10%)."""
    case_id = _setup_case_with_prerequisites("CHECKOUT_ABANDONED", "Is there any discount available?", 10000.0)

    # Mock Gemini returning 15% discount
    mock_proposal = RecoveryStrategyProposal(
        primary_strategy="INCENTIVE",
        secondary_strategy="PAYMENT_LINK",
        recommended_channel="WHATSAPP",
        recommended_payment_method="UPI",
        proposed_discount_percentage=15.0,  # Exceeds merchant max 10.0%
        proposed_retry_count=0,
        expected_recovery_probability=0.88,
        strategy_confidence=0.92,
        recommended_delay_minutes=0,
        human_approval_required=False,
        approval_reason=None,
        strategy_summary="Offer 15% discount incentive to convert price-sensitive buyer.",
        reasoning_summary="Customer requested discount.",
        supporting_factors=["High customer lifetime value"],
        risk_factors=[],
        rejected_strategies=[]
    )

    with patch("app.services.gemini_service.GeminiService.generate_recovery_strategy", return_value=mock_proposal):
        res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
        assert res.status_code == 200
        data = res.json()

        assert data["discount_percentage"] == 10.0
        assert data["discount_amount"] == 1000.0  # 10% of 10,000
        assert data["guardrail_status"] == "CAPPED"
        assert any("Discount reduced to merchant maximum" in c for c in data["guardrail_constraints"])


def test_strategist_7_retry_cap_guardrail():
    """Test 7: Retry count at max retries (3) blocks RETRY_PAYMENT proposal."""
    case_id = _setup_case_with_prerequisites("BANK_SERVER_DOWN", "Try the payment again.", 5000.0)

    # Artificially set retry_count to 3 in DB
    db = SessionLocal()
    rc = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    rc.retry_count = 3
    db.commit()
    db.close()

    mock_proposal = RecoveryStrategyProposal(
        primary_strategy="RETRY_PAYMENT",
        secondary_strategy="PAYMENT_LINK",
        recommended_channel="SMS",
        recommended_payment_method="CARD",
        proposed_discount_percentage=0.0,
        proposed_retry_count=4,
        expected_recovery_probability=0.75,
        strategy_confidence=0.85,
        recommended_delay_minutes=0,
        human_approval_required=False,
        approval_reason=None,
        strategy_summary="Re-attempt payment directly via gateway.",
        reasoning_summary="Gateway returned transient error.",
        supporting_factors=[],
        risk_factors=[],
        rejected_strategies=[]
    )

    with patch("app.services.gemini_service.GeminiService.generate_recovery_strategy", return_value=mock_proposal):
        res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
        assert res.status_code == 200
        data = res.json()

        assert data["primary_strategy"] != "RETRY_PAYMENT"
        assert data["guardrail_status"] in ["BLOCKED", "CAPPED"]
        assert any("Retry blocked" in c for c in data["guardrail_constraints"])


def test_strategist_8_high_value_approval_guardrail():
    """Test 8: Transaction value >= ₹50,000 mandates human approval (APPROVAL_REQUIRED)."""
    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "Please help with this order.", 55000.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()

    assert data["human_approval_required"] is True
    assert data["guardrail_status"] == "APPROVAL_REQUIRED"
    assert "high-value" in data["approval_reason"].lower()
    assert any("high-value" in c.lower() for c in data["guardrail_constraints"])


def test_strategist_9_quiet_hours_guardrail():
    """Test 9: Quiet hours evaluation calculates delay and applies constraint."""
    from app.services.guardrail_service import guardrail_service

    db = SessionLocal()
    gdr = guardrail_service.get_or_create_guardrails(db)
    gdr.quiet_hours_start = "00:00"
    gdr.quiet_hours_end = "23:59"  # Force all day quiet hours for testing
    db.commit()
    db.close()

    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "Can I use UPI?", 12999.0)

    try:
        res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
        assert res.status_code == 200
        data = res.json()
        assert any("Quiet hours active" in c for c in data["guardrail_constraints"])
        assert data["recommended_delay_minutes"] > 0
    finally:
        # Reset quiet hours
        db = SessionLocal()
        gdr = guardrail_service.get_or_create_guardrails(db)
        gdr.quiet_hours_start = "22:00"
        gdr.quiet_hours_end = "08:00"
        db.commit()
        db.close()


def test_strategist_10_missing_recovery_case_404():
    """Test 10: Non-existent recovery case -> HTTP 404"""
    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": "rc_nonexistent_99999"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_strategist_11_missing_prerequisite_context_409():
    """Test 11: Recovery case without prerequisite Investigator & Intent intelligence -> HTTP 409 Conflict"""
    import uuid
    from datetime import datetime

    db = SessionLocal()
    cust = db.query(Customer).first()
    payment = Payment(
        id=f"pay_nopre_{uuid.uuid4().hex[:8]}",
        razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
        customer_id=cust.id,
        amount=12999.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_reason="CARD_DECLINED",
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.flush()

    case = RecoveryCase(
        id=f"rc_nopre_{uuid.uuid4().hex[:8]}",
        payment_id=payment.id,
        recovery_score=0.0,
        recovery_probability=0.0,
        customer_intent=None,
        status="IDENTIFIED",
        retry_count=0,
        started_at=datetime.utcnow()
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 409
    assert "prerequisite context unavailable" in res.json()["detail"].lower()


def test_strategist_12_gemini_failure_handled():
    """Test 12: Gemini failure gracefully falls back to deterministic strategist."""
    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "Can I pay via UPI?", 12999.0)

    with patch("app.services.gemini_service.GeminiService._execute_gemini_call", side_effect=Exception("Gemini API Error 503")):
        res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
        assert res.status_code == 200
        data = res.json()
        assert data["primary_strategy"] == "ALTERNATE_PAYMENT_METHOD"
        assert data["guardrail_status"] == "SAFE"


def test_strategist_13_invalid_proposal_schema_rejected():
    """Test 13: Invalid AI probability or negative discount rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        RecoveryStrategyProposal(
            primary_strategy="RETRY_PAYMENT",
            expected_recovery_probability=1.5,  # Invalid: > 1.0
            strategy_confidence=0.9,
            strategy_summary="Test",
            reasoning_summary="Test"
        )

    with pytest.raises(ValidationError):
        RecoveryStrategyResult(
            recovery_case_id="rc_1",
            payment_id="pay_1",
            customer_id="cust_1",
            primary_strategy="RETRY_PAYMENT",
            recommended_channel="WHATSAPP",
            discount_percentage=-5.0,  # Invalid: < 0
            expected_recovery_probability=0.8,
            strategy_confidence=0.9,
            strategy_summary="Test",
            reasoning_summary="Test",
            guardrail_status="SAFE"
        )


def test_strategist_14_agent_action_persisted():
    """Test 14: Strategy generation creates an AgentAction audit record with metadata."""
    case_id = _setup_case_with_prerequisites("CARD_DECLINED", "Can I pay with Google Pay?", 12999.0)

    res = client.post("/api/ai/generate-strategy", json={"recovery_case_id": case_id})
    assert res.status_code == 200

    db = SessionLocal()
    action = (
        db.query(AgentAction)
        .filter(AgentAction.recovery_case_id == case_id, AgentAction.agent_type == "STRATEGIST")
        .order_by(AgentAction.created_at.desc())
        .first()
    )
    assert action is not None
    assert action.action_type == "RECOVERY_STRATEGY_GENERATION"
    assert action.status == "SUCCESS"
    assert "ALTERNATE_PAYMENT_METHOD" in action.reasoning_summary
    assert "guardrail_status" in action.action_metadata
    db.close()

