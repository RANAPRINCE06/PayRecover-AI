import uuid
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    Payment,
    RecoveryCase,
    AgentAction,
    HumanApproval,
    PaymentStatus,
    RecoveryStatus,
    PaymentMethod,
    FailureReason,
    User,
    UserRole,
    Customer
)
from app.services.guardrail_service import GuardrailService
from app.services.idempotency_service import IdempotencyService
from app.services.opportunity_service import OpportunityScoringEngine
from app.tools.tool_executor import ToolExecutor, ToolType

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
# PHASE 10 - 10 END-TO-END AUTOMATED TEST SCENARIOS
# -------------------------------------------------------------

def test_scenario_1_standard_upi_card_recovery():
    """Scenario 1: Standard UPI/Card Recovery Workflow."""
    res = client.post("/api/recovery/simulate", json={
        "scenario_type": "DEMO_CARD_DECLINE_UPI",
        "amount": 12999.0
    })
    assert res.status_code == 200
    data = res.json()
    assert "case_id" in data
    assert "payment_id" in data
    assert data["amount"] == 12999.0

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == data["case_id"]).first()
    assert case is not None
    assert case.payment.amount == 12999.0
    assert case.payment.payment_method in [PaymentMethod.CARD.value, PaymentMethod.UPI.value]
    assert case.status in [
        RecoveryStatus.ACTION_IN_PROGRESS.value,
        RecoveryStatus.AWAITING_CUSTOMER.value,
        RecoveryStatus.STRATEGY_SELECTED.value
    ]
    
    # Verify agent actions recorded
    actions = db.query(AgentAction).filter(AgentAction.recovery_case_id == case.id).all()
    assert len(actions) > 0
    db.close()


def test_scenario_2_high_value_review_guardrail():
    """Scenario 2: High-Value Recovery Review (> ₹50,000 / ₹75,000 Threshold)."""
    res = client.post("/api/recovery/simulate", json={
        "scenario_type": "HIGH_VALUE_APPROVAL",
        "amount": 75000.0
    })
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case is not None
    assert case.payment.amount == 75000.0
    assert case.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value

    # Trigger tool execution to enforce approval record generation if not present
    exec_res = client.post(f"/api/recovery/{case_id}/execute", json={"recovery_case_id": case_id})
    assert exec_res.status_code == 200
    assert exec_res.json()["requires_human_approval"] is True

    # Verify human approval record was generated in database
    approval = db.query(HumanApproval).filter(HumanApproval.recovery_case_id == case.id).first()
    assert approval is not None
    assert approval.amount >= 50000.0
    assert approval.status == "PENDING"
    db.close()

    # Operator or Admin approves the case
    admin_token = get_token_for("admin@payrecover.ai", "Admin@123")
    approve_res = client.post(
        f"/api/recovery/{case_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] in ["APPROVED", "EXECUTED", "SUCCESS"]


def test_scenario_3_exact_amount_link_recovery():
    """Scenario 3: ₹2,499 Link Recovery Workflow."""
    res = client.post("/api/recovery/simulate", json={
        "scenario_type": "UPI_TIMEOUT",
        "amount": 2499.0
    })
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case is not None
    assert case.payment.amount == 2499.0
    assert case.payment.failure_reason == FailureReason.UPI_TIMEOUT.value
    assert case.payment_link_url is not None
    assert any(sub in case.payment_link_url for sub in ["plink_", "rzp.io", "http", "pay_"])
    db.close()


def test_scenario_4_checkout_abandonment_recovery():
    """Scenario 4: Checkout Abandonment Recovery Workflow."""
    res = client.post("/api/recovery/simulate", json={
        "scenario_type": "CHECKOUT_ABANDONED",
        "amount": 4999.0
    })
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case is not None
    assert case.payment.failure_reason == FailureReason.CHECKOUT_ABANDONED.value
    
    # Strategy should reflect abandonment nudges or smart recovery
    actions = db.query(AgentAction).filter(AgentAction.recovery_case_id == case.id).all()
    action_types = [a.action_type for a in actions]
    assert any(at in ["SELECT_STRATEGY", "DISPATCH_MESSAGE", "GENERATE_PAYMENT_LINK", "OFFER_DISCOUNT"] for at in action_types)
    db.close()


def test_scenario_5_subscription_renewal_failure():
    """Scenario 5: Recurring Auto-Debit Mandate Failure Recovery."""
    res = client.post("/api/recovery/simulate", json={
        "scenario_type": "SUBSCRIPTION_FAILED",
        "amount": 999.0
    })
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case is not None
    assert case.payment.failure_reason == FailureReason.SUBSCRIPTION_FAILED.value
    assert case.current_strategy is not None
    db.close()


def test_scenario_6_already_paid_pre_execution_guard():
    """Scenario 6: Already-Paid Check Halts Redundant Recovery Action."""
    db = SessionLocal()
    # Create an already recovered payment
    payment_id = f"pay_settled_{uuid.uuid4().hex[:6]}"
    case_id = f"rc_settled_{uuid.uuid4().hex[:6]}"
    cust = db.query(Customer).first()
    
    payment = Payment(
        id=payment_id,
        razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:6]}",
        customer_id=cust.id,
        amount=1999.0,
        currency="INR",
        payment_method="UPI",
        status=PaymentStatus.RECOVERED.value,
        failure_reason=None
    )
    db.add(payment)
    db.flush()

    case = RecoveryCase(
        id=case_id,
        payment_id=payment.id,
        recovery_score=95.0,
        status=RecoveryStatus.RECOVERED.value,
        recovered_amount=1999.0
    )
    db.add(case)
    db.commit()
    db.close()

    # Attempt to execute recovery on already recovered case
    res = client.post(f"/api/recovery/{case_id}/execute", json={"recovery_case_id": case_id})
    assert res.status_code == 200
    data = res.json()
    assert data["tool_type"] == ToolType.VERIFY_PAYMENT.value
    assert "already" in data["message"].lower() or "settled" in data["message"].lower()


def test_scenario_7_retry_blocked_payment_error():
    """Scenario 7: Guardrail Aborts Automated Retry on Exceeded Attempts or Blocked Error."""
    db = SessionLocal()
    payment_id = f"pay_blocked_{uuid.uuid4().hex[:6]}"
    case_id = f"rc_blocked_{uuid.uuid4().hex[:6]}"
    cust = db.query(Customer).first()

    payment = Payment(
        id=payment_id,
        razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:6]}",
        customer_id=cust.id,
        amount=3500.0,
        payment_method="CARD",
        status=PaymentStatus.FAILED.value,
        failure_reason=FailureReason.INSUFFICIENT_FUNDS.value
    )
    db.add(payment)
    db.flush()

    # Retry count already at guardrail limit (3 retries)
    case = RecoveryCase(
        id=case_id,
        payment_id=payment.id,
        recovery_score=40.0,
        status=RecoveryStatus.IDENTIFIED.value,
        retry_count=3
    )
    db.add(case)
    db.commit()

    # Check guardrail action evaluation directly
    is_allowed, reason = GuardrailService.evaluate_action(
        db=db,
        payment=payment,
        recovery_case=case,
        action_type="RETRY_PAYMENT"
    )
    assert is_allowed is False
    assert "retry limit" in reason.lower()
    db.close()


def test_scenario_8_concurrent_webhook_idempotent_replay():
    """Scenario 8: Idempotent Replay Prevents Duplicate Tool/Recovery Actions."""
    idem_key = f"idem-key-{uuid.uuid4().hex}"
    
    # 1. Create a fresh case
    sim_res = client.post("/api/recovery/simulate", json={
        "scenario_type": "DEMO_CARD_DECLINE_UPI",
        "amount": 3499.0
    })
    assert sim_res.status_code == 200
    case_id = sim_res.json()["case_id"]

    # 2. First call with Idempotency-Key
    headers = {"Idempotency-Key": idem_key}
    res1 = client.post(f"/api/recovery/{case_id}/execute", json={"recovery_case_id": case_id}, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()

    # 3. Second call with the same Idempotency-Key
    res2 = client.post(f"/api/recovery/{case_id}/execute", json={"recovery_case_id": case_id}, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()

    # Verify both responses match exactly and execution wasn't duplicated
    assert data1["execution_id"] == data2["execution_id"]
    assert data1["status"] == data2["status"]
    assert data1["tool_type"] == data2["tool_type"]


def test_scenario_9_low_confidence_recovery_score():
    """Scenario 9: Low Confidence / Score (< 40) Handling via Opportunity Scoring."""
    db = SessionLocal()
    # Create customer with repeated failures, churn risk tier, and negative intent
    churn_cust = Customer(
        id=f"cust_churn_{uuid.uuid4().hex[:6]}",
        name="Churn Risk Customer",
        email=f"churn_{uuid.uuid4().hex[:6]}@example.com",
        phone="+919876543999",
        customer_value="CHURN_RISK",
        total_successful_payments=0,
        total_failed_payments=5
    )
    db.add(churn_cust)
    db.flush()

    payment = Payment(
        id=f"pay_low_{uuid.uuid4().hex[:6]}",
        razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:6]}",
        customer_id=churn_cust.id,
        amount=14999.0,
        payment_method="NETBANKING",
        status=PaymentStatus.FAILED.value,
        failure_reason=FailureReason.AUTHENTICATION_FAILED.value
    )
    db.add(payment)
    db.flush()

    case = RecoveryCase(
        id=f"rc_low_{uuid.uuid4().hex[:6]}",
        payment_id=payment.id,
        recovery_score=30.0,
        customer_intent="CANCEL_REQUEST",
        retry_count=3,
        status=RecoveryStatus.IDENTIFIED.value
    )
    db.add(case)
    db.commit()

    opp = OpportunityScoringEngine.calculate_score(case)
    assert opp is not None
    assert opp.score < 40.0
    assert opp.priority == "LOW"
    assert len(opp.negative_factors) > 0
    db.close()


def test_scenario_10_rbac_rejection_viewer_denied():
    """Scenario 10: RBAC Rejection — Viewer User Blocked from Admin/Operator Operations."""
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    
    # 1. Viewer cannot manage users -> 403 Forbidden
    res_users = client.get("/api/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_users.status_code == 403
    assert "insufficient permissions" in res_users.json()["detail"].lower()

    # 2. Viewer cannot approve high-value cases -> 403 Forbidden
    res_approve = client.post(
        "/api/recovery/rc_sample_case/approve",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res_approve.status_code == 403
    assert "not authorized" in res_approve.json()["detail"].lower()
