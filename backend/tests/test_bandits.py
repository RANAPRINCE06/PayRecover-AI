"""
PayRecover AI — Phase 7 Contextual Multi-Armed Bandits & Safe Policy Envelopes Tests.

Comprehensive test suite verifying:
- Leak-proof context feature construction (zero PII, strict temporal boundaries).
- Safe policy envelopes and deterministic financial guardrail enforcement.
- Bounded economic reward design and non-domination by large payment amounts.
- LinUCB mathematical inference, exploration bounds, and deterministic online updates.
- Shadow-mode execution isolation (recommendations never mutate live customer transactions).
- Asynchronous verified outcome reconciliation and actual reward logging.
- Offline policy evaluation (OPE) with temporal split, Replay, and Doubly Robust estimators.
- REST API contracts, RBAC permissions, and parameter mutation safeguards.
"""
import uuid
import json
import math
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import numpy as np

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    User,
    UserRole,
    BanditPolicyConfig,
    BanditShadowDecision,
    RecoveryCase,
    Payment,
    PaymentStatus,
    RecoveryStatus,
    MerchantGuardrail,
    RecoveryOutcome,
    RecoveryOutcomeStatus
)
from app.services.bandit_service import (
    bandit_service,
    FEATURE_NAMES,
    FEATURE_DIMENSION,
    CANONICAL_BANDIT_ACTIONS
)

client = TestClient(app)


def setup_module(module):
    """Seed test database before running bandit tests."""
    seed_database()


def get_token(role: str = "operator") -> str:
    """Helper to authenticate and retrieve JWT access token."""
    creds = {
        "admin": ("admin@payrecover.ai", "Admin@123"),
        "operator": ("operator@payrecover.ai", "Operator@123"),
        "viewer": ("viewer@payrecover.ai", "Viewer@123")
    }
    email, password = creds.get(role, creds["operator"])
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


# ============================================================================
# 1. CONTEXT FEATURE CONSTRUCTION & TEMPORAL LEAKAGE TESTS
# ============================================================================

def test_feature_construction_zero_pii():
    """Features must have exactly 21 numerical values, bounded, with no sensitive customer PII."""
    db: Session = SessionLocal()
    try:
        payment = Payment(
            id="pay_test_feat_1",
            razorpay_payment_id="pay_rzp_feat_1",
            customer_id="cust_seed_1",
            amount=4500.0,
            payment_method="upi",
            failure_reason="technical_timeout",
            currency="INR"
        )
        case = RecoveryCase(
            id="rc_test_feat_1",
            retry_count=1,
            customer_intent="tech_difficulty"
        )

        feat_vec = bandit_service.extract_context_features(db, payment, case)
        assert feat_vec.schema_version == "v1.0"
        assert len(feat_vec.feature_names) == 21
        assert len(feat_vec.features) == 21

        # Check critical values
        assert feat_vec.features["method_upi"] == 1.0
        assert feat_vec.features["method_card"] == 0.0
        assert feat_vec.features["failure_timeout"] == 1.0
        assert feat_vec.features["tier_low"] == 1.0
        assert feat_vec.features["bias"] == 1.0

        # Verify no PII keys in features
        for forbidden in ["name", "email", "phone", "card_number", "ip_address", "pan"]:
            assert forbidden not in feat_vec.features
    finally:
        db.close()


def test_feature_temporal_leakage_prevention():
    """Customer historical prior must strictly exclude events occurring after as_of_time."""
    db: Session = SessionLocal()
    try:
        cust_id = f"cust_leak_test_{uuid.uuid4().hex[:6]}"
        t0 = datetime(2026, 1, 10, 10, 0, 0)
        t_decision = datetime(2026, 1, 15, 12, 0, 0)
        t_future = datetime(2026, 1, 20, 15, 0, 0)

        rc_past_id = f"rc_past_{uuid.uuid4().hex[:6]}"
        rc_future_id = f"rc_future_{uuid.uuid4().hex[:6]}"
        # Prior outcome before decision (RECOVERED)
        past_out = RecoveryOutcome(
            id=f"out_past_{uuid.uuid4().hex[:8]}",
            recovery_case_id=rc_past_id,
            payment_id=f"pay_{rc_past_id}",
            customer_id=cust_id,
            failure_category="TIMEOUT",
            payment_method="UPI",
            amount=2000.0,
            amount_range="1000-5000",
            selected_strategy="UPI_FALLBACK_LINK",
            outcome_status=RecoveryOutcomeStatus.RECOVERED.value,
            decision_timestamp=t0
        )
        # Future outcome after decision (UNSUCCESSFUL)
        future_out = RecoveryOutcome(
            id=f"out_future_{uuid.uuid4().hex[:8]}",
            recovery_case_id=rc_future_id,
            payment_id=f"pay_{rc_future_id}",
            customer_id=cust_id,
            failure_category="TIMEOUT",
            payment_method="UPI",
            amount=2000.0,
            amount_range="1000-5000",
            selected_strategy="UPI_FALLBACK_LINK",
            outcome_status=RecoveryOutcomeStatus.UNSUCCESSFUL.value,
            decision_timestamp=t_future
        )
        db.add(past_out)
        db.add(future_out)
        db.commit()

        # Decision at t_decision should only count past_out (1 recovered / 1 total)
        p = Payment(id="pay_now", razorpay_payment_id="pay_rzp_now", customer_id=cust_id, amount=3000.0, payment_method="upi", failure_reason="timeout")
        c = RecoveryCase(id="rc_now", retry_count=0)

        feat_vec = bandit_service.extract_context_features(db, p, c, as_of_time=t_decision)
        # Laplace smoothed: (1 + 1) / (1 + 2) = 2/3 = 0.6667
        assert feat_vec.features["customer_prior_success_rate"] == 0.6667
    finally:
        db.close()


# ============================================================================
# 2. SAFE POLICY ENVELOPE & GUARDRAIL INVARIANTS
# ============================================================================

def test_safe_action_space_high_value_guardrail():
    """High-value transactions (>= 50,000) strictly force EXECUTIVE_CONCIERGE_CALL and block automated actions."""
    guardrail = MerchantGuardrail(
        merchant_id="merchant_test",
        high_value_threshold=50000.0,
        max_retries=3,
        max_discount_percentage=10.0
    )
    p = Payment(id="pay_jumbo", razorpay_payment_id="pay_rzp_jumbo", customer_id="cust_seed_1", amount=75000.0, payment_method="card", failure_reason="card_declined")
    c = RecoveryCase(id="rc_jumbo", retry_count=0)

    eligible, overrides = bandit_service.get_safe_eligible_actions(p, guardrail, c)
    assert eligible == ["EXECUTIVE_CONCIERGE_CALL"]
    assert len(overrides) == 1
    assert "exceeds high-value ceiling" in overrides[0]


def test_safe_action_space_max_retries_enforced():
    """When retries reach limit, AUTO_RETRY_MANDATE_UPDATE is strictly excluded."""
    guardrail = MerchantGuardrail(
        merchant_id="merchant_test",
        high_value_threshold=50000.0,
        max_retries=3,
        max_discount_percentage=10.0
    )
    p = Payment(id="pay_retried", razorpay_payment_id="pay_rzp_retried", customer_id="cust_seed_1", amount=3500.0, payment_method="mandate", failure_reason="recurring_failed")
    c = RecoveryCase(id="rc_retried", retry_count=3)  # max retries reached

    eligible, overrides = bandit_service.get_safe_eligible_actions(p, guardrail, c)
    assert "AUTO_RETRY_MANDATE_UPDATE" not in eligible
    assert any("Max retries" in o for o in overrides)


def test_safe_action_space_insufficient_funds_blocks_instant_retries():
    """Insufficient balance failures block instant retries and require scheduled/discount nudges."""
    guardrail = MerchantGuardrail(
        merchant_id="merchant_test",
        high_value_threshold=50000.0,
        max_retries=3,
        max_discount_percentage=10.0
    )
    p = Payment(id="pay_nobal", razorpay_payment_id="pay_rzp_nobal", customer_id="cust_seed_1", amount=2200.0, payment_method="upi", failure_reason="insufficient_funds")
    c = RecoveryCase(id="rc_nobal", retry_count=1)

    eligible, _ = bandit_service.get_safe_eligible_actions(p, guardrail, c)
    assert "AUTO_RETRY_MANDATE_UPDATE" not in eligible
    assert "UPI_FALLBACK_LINK" not in eligible
    assert "PAY_LATER_SCHEDULED_LINK" in eligible


# ============================================================================
# 3. REWARD FUNCTION & ECONOMIC DESIGN TESTS
# ============================================================================

def test_reward_design_bounds_and_penalties():
    """Reward is strictly bounded in [-0.5, 1.0], penalizes discount cost and retries."""
    # 1. Clean immediate full recovery: reward = 1.0
    r1 = bandit_service.compute_reward(
        outcome_status="RECOVERED",
        transaction_amount=5000.0,
        recovered_amount=5000.0,
        discount_offered_percent=0.0,
        attempt_count=1
    )
    assert r1 == 1.0

    # 2. Recovery with 10% discount and 2 retries (attempt_count=3):
    # r = 1.0 - 0.10 - (0.05 * 2) = 0.80
    r2 = bandit_service.compute_reward(
        outcome_status="RECOVERED",
        transaction_amount=5000.0,
        recovered_amount=5000.0,
        discount_offered_percent=10.0,
        attempt_count=3
    )
    assert r2 == 0.80

    # 3. Terminal failure after 3 retries (attempt_count=4):
    # r = 0.0 - (0.05 * 3) = -0.15
    r3 = bandit_service.compute_reward(
        outcome_status="UNSUCCESSFUL",
        transaction_amount=5000.0,
        attempt_count=4
    )
    assert r3 == -0.15

    # 4. Large transactions do not dominate (normalized ratio)
    r_jumbo = bandit_service.compute_reward(
        outcome_status="RECOVERED",
        transaction_amount=500000.0,
        recovered_amount=500000.0
    )
    assert r_jumbo == 1.0


def test_reward_pending_unknown_excluded():
    """Pending and unknown outcomes return None (never treated as failure)."""
    assert bandit_service.compute_reward("PENDING", 2000.0) is None
    assert bandit_service.compute_reward("UNKNOWN", 2000.0) is None


# ============================================================================
# 4. LINUCB MATHEMATICAL INFERENCE & EXPLORATION TESTS
# ============================================================================

def test_linucb_score_calculation():
    """Verifies UCB score computation theta^T x + alpha * sqrt(x^T A^-1 x)."""
    db: Session = SessionLocal()
    try:
        policy = bandit_service.get_or_create_policy(db, "merch_math_test", alpha=1.5, ridge_lambda=2.0)
        x = np.ones((FEATURE_DIMENSION, 1)) / math.sqrt(FEATURE_DIMENSION)

        predictions = bandit_service.predict_ucb(policy, x, ["UPI_FALLBACK_LINK"])
        pred = predictions["UPI_FALLBACK_LINK"]

        assert "expected_reward" in pred
        assert "confidence_width" in pred
        assert "ucb_score" in pred
        assert pred["ucb_score"] == pytest.approx(pred["expected_reward"] + pred["confidence_width"], abs=0.01)
    finally:
        db.close()


def test_linucb_online_update_and_learning():
    """Online ridge update increments A_a and b_a and changes expected reward."""
    db: Session = SessionLocal()
    try:
        mid = f"merch_upd_{uuid.uuid4().hex[:6]}"
        policy = bandit_service.get_or_create_policy(db, mid, alpha=1.0, ridge_lambda=1.0)
        x = np.zeros((FEATURE_DIMENSION, 1))
        x[0, 0] = 1.0  # amount feature active
        x[-1, 0] = 1.0  # bias

        action = "SMART_DISCOUNT_INCENTIVE"
        init_preds = bandit_service.predict_ucb(policy, x, [action])
        init_r = init_preds[action]["expected_reward"]

        # Provide 3 positive rewards of 1.0
        for _ in range(3):
            bandit_service.update_policy_state(db, policy, action, x, reward=1.0)

        new_preds = bandit_service.predict_ucb(policy, x, [action])
        new_r = new_preds[action]["expected_reward"]

        # Expected reward should increase toward 1.0
        assert new_r > init_r
        assert new_preds[action]["count"] == 3
    finally:
        db.close()


# ============================================================================
# 5. SHADOW MODE EXECUTION ISOLATION & RECONCILIATION
# ============================================================================

def test_shadow_mode_isolation():
    """Shadow mode records decision to DB without altering customer transaction or status."""
    db: Session = SessionLocal()
    try:
        p = Payment(id="pay_shd_iso", razorpay_payment_id="pay_rzp_shd_iso", customer_id="cust_seed_1", amount=1800.0, payment_method="upi", failure_reason="timeout")
        c = RecoveryCase(id="rc_shd_iso", payment_id=p.id, status=RecoveryStatus.INVESTIGATING.value, current_strategy="PAYMENT_LINK")
        guardrail = MerchantGuardrail(merchant_id="merch_demo_fintech", high_value_threshold=50000.0)

        shadow_rec = bandit_service.evaluate_and_log_shadow(db, p, c, guardrail, production_strategy="PAYMENT_LINK")
        assert shadow_rec is not None
        assert shadow_rec.recovery_case_id == "rc_shd_iso"
        assert shadow_rec.eventual_outcome == "PENDING"

        # Case status must remain unchanged!
        assert c.status == RecoveryStatus.INVESTIGATING.value
    finally:
        db.close()


def test_shadow_outcome_reconciliation():
    """Reconciling outcome updates shadow record with verified outcome and computed reward."""
    db: Session = SessionLocal()
    try:
        case_id = f"rc_reconcile_{uuid.uuid4().hex[:6]}"
        shd = BanditShadowDecision(
            id=f"shd_rec_{uuid.uuid4().hex[:8]}",
            policy_version="v1.0",
            context_schema_version="v1.0",
            recovery_case_id=case_id,
            payment_id="pay_rec_1",
            merchant_id="merch_demo_fintech",
            eligible_actions_json=json.dumps(["UPI_FALLBACK_LINK"]),
            selected_action="UPI_FALLBACK_LINK",
            selection_reason="Test reason",
            predicted_reward=0.75,
            confidence_width=0.25,
            feature_vector_json=json.dumps({"bias": 1.0}),
            production_strategy="UPI_FALLBACK_LINK",
            is_agreement=True,
            eventual_outcome="PENDING"
        )
        db.add(shd)
        db.commit()

        bandit_service.reconcile_shadow_outcome(
            db=db,
            recovery_case_id=case_id,
            outcome_status="RECOVERED",
            recovered_amount=4000.0,
            transaction_amount=4000.0,
            discount_offered=5.0,
            attempt_count=1
        )

        db.refresh(shd)
        assert shd.eventual_outcome == "RECOVERED"
        assert shd.actual_reward == pytest.approx(0.95, abs=0.01)  # 1.0 - 0.05
    finally:
        db.close()


# ============================================================================
# 6. REST API ENDPOINTS & RBAC PERMISSION TESTS
# ============================================================================

def test_api_bandit_status_viewer_allowed():
    """Viewer role can inspect bandit policy status, learned weights, and agreement."""
    token = get_token("viewer")
    res = client.get("/api/bandits/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["policy_type"] == "LINUCB"
    assert data["version"] == "v1.0"
    assert len(data["arms"]) == 6
    assert "agreement_rate_with_production" in data


def test_api_bandit_recommend_preview():
    """Operator can preview recommendation with feature attributions."""
    token = get_token("operator")
    payload = {
        "payment_method": "UPI",
        "failure_category": "TECHNICAL_TIMEOUT",
        "amount": 3200.0,
        "retry_count": 0
    }
    res = client.post("/api/bandits/recommend", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "selected_action" in data
    assert "predicted_reward" in data
    assert "confidence_width" in data
    assert len(data["eligible_actions"]) > 0
    assert "feature_attributions" in data


def test_api_offline_evaluation():
    """Operator can run offline policy evaluation (OPE) with temporal split."""
    token = get_token("operator")
    payload = {
        "policy_type": "LINUCB",
        "alpha_exploration": 1.0,
        "temporal_split_pct": 0.7,
        "random_seed": 42
    }
    res = client.post("/api/bandits/evaluate", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "policies" in data
    assert "LINUCB" in data["policies"]
    assert "HISTORICAL_BEST" in data["policies"]
    assert "EPSILON_GREEDY" in data["policies"]
    assert "ORACLE_BENCHMARK" in data["policies"]
    assert data["winner_policy"] in ["LINUCB", "HISTORICAL_BEST"]


def test_api_update_parameters_rbac():
    """Admin can update parameters; Viewer is forbidden (403)."""
    viewer_token = get_token("viewer")
    admin_token = get_token("admin")

    # Viewer forbidden
    res_viewer = client.post(
        "/api/bandits/parameters?alpha=1.5&ridge_lambda=2.0",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res_viewer.status_code == 403

    # Admin allowed
    res_admin = client.post(
        "/api/bandits/parameters?alpha=1.5&ridge_lambda=2.0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["alpha_exploration"] == 1.5


def test_api_shadow_decisions_pagination():
    """Viewer can query paginated shadow-mode decision stream."""
    token = get_token("viewer")
    res = client.get("/api/bandits/shadow-decisions?page=1&page_size=5", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "agreement_rate" in data
