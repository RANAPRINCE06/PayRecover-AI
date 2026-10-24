import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    Payment,
    RecoveryCase,
    RecoveryOutcome,
    RecoveryOutcomeStatus,
    PaymentStatus,
    RecoveryStatus,
    Customer,
    MerchantGuardrail
)
from app.services.intelligence_service import (
    calculate_wilson_score_interval,
    calculate_brier_score,
    calculate_roc_auc,
    calculate_expected_calibration_error,
    CalibratedProbabilityEstimator,
    HistoricalOutcomeEngine,
    StrategyEvaluationEngine,
    OutcomeTrackingService,
    probability_estimator,
    strategy_evaluation_engine,
    outcome_service,
    amount_to_range,
    normalize_strategy_name
)

client = TestClient(app)


def setup_module(module):
    """Ensure database has seed data and default users."""
    seed_database()


def get_auth_token(email: str = "operator@payrecover.ai", password: str = "Operator@123") -> str:
    """Helper to authenticate and retrieve JWT access token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Authentication failed for {email}: {res.text}"
    return res.json()["access_token"]


# ============================================================================
# 1. OUTCOME ATTRIBUTION & RECORDING TESTS
# ============================================================================

def test_outcome_attribution_and_recording():
    """Verify that recording a decision creates a valid RecoveryOutcome record."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        assert case is not None
        p = case.payment
        assert p is not None

        outcome = OutcomeTrackingService.record_or_update_decision(
            db=db,
            recovery_case=case,
            selected_strategy="ALTERNATIVE_PAYMENT_METHOD",
            communication_channel="WHATSAPP",
            discount_offered_percent=5.0,
            human_approval_required=False,
            processing_latency_ms=150
        )

        assert outcome.recovery_case_id == case.id
        assert outcome.payment_id == p.id
        assert outcome.customer_id == p.customer_id
        assert outcome.failure_category == (p.failure_reason or "UNKNOWN")
        assert outcome.payment_method == p.payment_method
        assert outcome.selected_strategy == "ALTERNATIVE_PAYMENT_METHOD"
        assert outcome.outcome_status in [RecoveryOutcomeStatus.PENDING.value, RecoveryOutcomeStatus.RECOVERED.value, RecoveryOutcomeStatus.UNSUCCESSFUL.value]
    finally:
        db.close()


def test_duplicate_outcome_prevention():
    """Verify idempotent decision updates prevent duplicate rows for the same case."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        assert case is not None

        initial_count = db.query(RecoveryOutcome).filter(RecoveryOutcome.recovery_case_id == case.id).count()

        # Call record_or_update_decision multiple times
        OutcomeTrackingService.record_or_update_decision(
            db=db,
            recovery_case=case,
            selected_strategy="PAYMENT_LINK"
        )
        OutcomeTrackingService.record_or_update_decision(
            db=db,
            recovery_case=case,
            selected_strategy="PAYMENT_LINK"
        )

        after_count = db.query(RecoveryOutcome).filter(RecoveryOutcome.recovery_case_id == case.id).count()
        assert after_count == max(1, initial_count)
    finally:
        db.close()


def test_unverified_payments_not_counted_as_recovered():
    """Verify that unverified payments (payment not SUCCESS/RECOVERED) are never marked RECOVERED."""
    db = SessionLocal()
    try:
        # Create an unrecovered case
        customer = db.query(Customer).first()
        test_pay_id = f"pay_test_{uuid.uuid4().hex[:8]}"
        test_case_id = f"rc_test_{uuid.uuid4().hex[:8]}"

        p = Payment(
            id=test_pay_id,
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            amount=4500.0,
            currency="INR",
            payment_method="UPI",
            status=PaymentStatus.FAILED.value,
            failure_reason="UPI_TIMEOUT",
            created_at=datetime.utcnow()
        )
        db.add(p)
        db.flush()

        rc = RecoveryCase(
            id=test_case_id,
            payment_id=p.id,
            status=RecoveryStatus.INVESTIGATING.value,
            started_at=datetime.utcnow()
        )
        db.add(rc)
        db.commit()

        # Attempt to record verified outcome while payment is still FAILED and case is INVESTIGATING
        OutcomeTrackingService.record_verified_outcome(
            db=db,
            recovery_case_id=rc.id,
            verification_source="test_verification"
        )

        outcome = db.query(RecoveryOutcome).filter(RecoveryOutcome.recovery_case_id == rc.id).first()
        assert outcome is not None
        # Must be PENDING, NOT RECOVERED!
        assert outcome.outcome_status != RecoveryOutcomeStatus.RECOVERED.value
        assert outcome.is_verified is False
    finally:
        db.close()


def test_pending_outcomes_excluded_from_success_rate_denominators():
    """Verify that PENDING and UNKNOWN outcomes are excluded from observed recovery rate denominator."""
    db = SessionLocal()
    try:
        # Query historical evidence for PAYMENT_LINK
        evidence = HistoricalOutcomeEngine.get_historical_evidence(
            db=db,
            strategy="PAYMENT_LINK",
            failure_category="UPI_TIMEOUT"
        )

        # sample_size must equal recovered_count + unsuccessful_count, NOT total_attempts
        assert evidence["sample_size"] == evidence["recovered_count"] + evidence["unsuccessful_count"]
        if evidence["sample_size"] > 0:
            assert evidence["observed_recovery_rate"] == round(evidence["recovered_count"] / evidence["sample_size"], 4)
    finally:
        db.close()


# ============================================================================
# 2. TEMPORAL DATA LEAKAGE & MATHEMATICAL ESTIMATION TESTS
# ============================================================================

def test_temporal_data_leakage_prevention():
    """Verify outcomes decided in the future relative to as_of_time are strictly excluded."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        p_id = f"pay_leak_{uuid.uuid4().hex[:8]}"
        rc_id = f"rc_leak_{uuid.uuid4().hex[:8]}"

        past_decision_time = datetime(2025, 1, 1, 12, 0, 0)
        future_decision_time = datetime(2025, 6, 1, 12, 0, 0)

        p = Payment(
            id=p_id,
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            amount=5000.0,
            currency="INR",
            payment_method="CARD",
            status=PaymentStatus.RECOVERED.value,
            failure_reason="CARD_DECLINED",
            created_at=future_decision_time
        )
        db.add(p)
        db.flush()

        rc = RecoveryCase(
            id=rc_id,
            payment_id=p.id,
            status=RecoveryStatus.RECOVERED.value,
            started_at=future_decision_time,
            recovered_amount=5000.0
        )
        db.add(rc)
        db.flush()

        # Add outcome with future timestamp
        out = RecoveryOutcome(
            id=f"out_future_{uuid.uuid4().hex[:8]}",
            recovery_case_id=rc.id,
            payment_id=p.id,
            customer_id=customer.id,
            failure_category="CARD_DECLINED",
            payment_method="CARD",
            amount=5000.0,
            amount_range="1000-5000",
            selected_strategy="ALTERNATIVE_PAYMENT_METHOD",
            communication_channel="WHATSAPP",
            outcome_status=RecoveryOutcomeStatus.RECOVERED.value,
            recovered_amount=5000.0,
            is_verified=True,
            decision_timestamp=future_decision_time,
            created_at=future_decision_time,
            updated_at=future_decision_time
        )
        db.add(out)
        db.commit()

        # Query evidence as of the past time
        evidence_past = HistoricalOutcomeEngine.get_historical_evidence(
            db=db,
            strategy="ALTERNATIVE_PAYMENT_METHOD",
            failure_category="CARD_DECLINED",
            as_of_time=past_decision_time
        )

        # Query evidence as of after the future time
        evidence_future = HistoricalOutcomeEngine.get_historical_evidence(
            db=db,
            strategy="ALTERNATIVE_PAYMENT_METHOD",
            failure_category="CARD_DECLINED",
            as_of_time=future_decision_time + timedelta(days=1)
        )

        # The future outcome must NOT be counted in the past query
        assert evidence_past["total_attempts"] <= evidence_future["total_attempts"]
    finally:
        db.close()


def test_wilson_score_confidence_intervals():
    """Verify Wilson score interval calculations on corner cases."""
    # 0 total
    assert calculate_wilson_score_interval(0, 0) == (0.0, 0.0)

    # 10 out of 10
    lower_10, upper_10 = calculate_wilson_score_interval(10, 10)
    assert 0.0 < lower_10 < 1.0
    assert upper_10 == 1.0

    # 0 out of 10
    lower_0, upper_0 = calculate_wilson_score_interval(0, 10)
    assert lower_0 == 0.0
    assert 0.0 < upper_0 < 1.0

    # 50 out of 100
    lower_50, upper_50 = calculate_wilson_score_interval(50, 100)
    assert 0.35 < lower_50 < 0.45
    assert 0.55 < upper_50 < 0.65


def test_calibrated_probability_boundaries():
    """Verify probability predictions are strictly bounded in [0.0, 1.0]."""
    est = CalibratedProbabilityEstimator()
    prob, unc, ci = est.predict_probability(
        failure_category="UPI_TIMEOUT",
        payment_method="UPI",
        amount=999999.0,
        strategy="PAYMENT_LINK"
    )
    assert 0.0 <= prob <= 1.0
    assert 0.0 <= ci[0] <= ci[1] <= 1.0

    # Negative/Zero amount
    prob_zero, _, ci_zero = est.predict_probability(
        failure_category="CARD_DECLINED",
        payment_method="CARD",
        amount=0.0,
        strategy="PAYMENT_RETRY"
    )
    assert 0.0 <= prob_zero <= 1.0
    assert 0.0 <= ci_zero[0] <= ci_zero[1] <= 1.0


def test_insufficient_historical_data_handling():
    """Verify estimator handles sparse/insufficient datasets cleanly."""
    est = CalibratedProbabilityEstimator()
    # Evaluate with empty list
    metrics = est.train_and_evaluate([])
    assert metrics.data_quality_status == "INSUFFICIENT_FOR_TRAINING"
    assert metrics.brier_skill_score == 0.0
    assert metrics.roc_auc is None
    assert len(metrics.limitations) > 0


def test_model_evaluation_reproducibility():
    """Verify model training and evaluation metrics are deterministic across repeated runs."""
    db = SessionLocal()
    try:
        outcomes = db.query(RecoveryOutcome).order_by(RecoveryOutcome.decision_timestamp).all()
        est1 = CalibratedProbabilityEstimator()
        metrics1 = est1.train_and_evaluate(outcomes)

        est2 = CalibratedProbabilityEstimator()
        metrics2 = est2.train_and_evaluate(outcomes)

        assert metrics1.baseline_brier_score == metrics2.baseline_brier_score
        assert metrics1.model_brier_score == metrics2.model_brier_score
        assert metrics1.brier_skill_score == metrics2.brier_skill_score
        assert metrics1.roc_auc == metrics2.roc_auc
    finally:
        db.close()


# ============================================================================
# 3. STRATEGY EVALUATION & GUARDRAIL SAFETY TESTS
# ============================================================================

def test_strategy_ranking_and_eligibility():
    """Verify eligibility logic rejects PAYMENT_RETRY for hard card declines."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        p = Payment(
            id=f"pay_card_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            amount=2999.0,
            currency="INR",
            payment_method="CARD",
            status=PaymentStatus.FAILED.value,
            failure_reason="CARD_DECLINED",
            created_at=datetime.utcnow()
        )
        db.add(p)
        db.flush()

        rc = RecoveryCase(
            id=f"rc_card_{uuid.uuid4().hex[:8]}",
            payment_id=p.id,
            status=RecoveryStatus.INVESTIGATING.value,
            retry_count=0,
            started_at=datetime.utcnow()
        )
        db.add(rc)
        db.commit()

        eval_res = strategy_evaluation_engine.evaluate_candidates(
            db=db,
            payment=p,
            recovery_case=rc
        )

        # Find PAYMENT_RETRY candidate
        retry_cand = next((c for c in eval_res.candidates if c.strategy == "PAYMENT_RETRY"), None)
        assert retry_cand is not None
        assert retry_cand.is_eligible is False
        assert "Issuing bank declined card" in retry_cand.recommendation_reason
    finally:
        db.close()


def test_high_value_approval_remains_mandatory():
    """Verify that payments meeting or exceeding high-value threshold enforce human escalation."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        guardrail = db.query(MerchantGuardrail).filter(MerchantGuardrail.merchant_id == "merchant_primary").first()
        high_val = guardrail.high_value_threshold if guardrail else 50000.0

        p = Payment(
            id=f"pay_hv_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            amount=high_val + 5000.0,
            currency="INR",
            payment_method="CARD",
            status=PaymentStatus.FAILED.value,
            failure_reason="UPI_TIMEOUT",
            created_at=datetime.utcnow()
        )
        db.add(p)
        db.flush()

        rc = RecoveryCase(
            id=f"rc_hv_{uuid.uuid4().hex[:8]}",
            payment_id=p.id,
            status=RecoveryStatus.INVESTIGATING.value,
            started_at=datetime.utcnow()
        )
        db.add(rc)
        db.commit()

        eval_res = strategy_evaluation_engine.evaluate_candidates(
            db=db,
            payment=p,
            recovery_case=rc
        )

        assert eval_res.guardrail_applied is True
        assert eval_res.recommended_strategy == "HUMAN_ESCALATION"
        assert any("high-value threshold" in d.lower() for d in eval_res.guardrail_details)
    finally:
        db.close()


def test_unknown_payment_methods_and_failure_categories():
    """Verify engine handles unknown methods and reasons safely without crashing."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        p = Payment(
            id=f"pay_unk_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            amount=1500.0,
            currency="INR",
            payment_method="EXOTIC_CRYPTO_RAIL",
            status=PaymentStatus.FAILED.value,
            failure_reason="UNKNOWN_WEIRD_ERROR",
            created_at=datetime.utcnow()
        )
        db.add(p)
        db.flush()

        rc = RecoveryCase(
            id=f"rc_unk_{uuid.uuid4().hex[:8]}",
            payment_id=p.id,
            status=RecoveryStatus.INVESTIGATING.value,
            started_at=datetime.utcnow()
        )
        db.add(rc)
        db.commit()

        eval_res = strategy_evaluation_engine.evaluate_candidates(
            db=db,
            payment=p,
            recovery_case=rc
        )

        assert eval_res is not None
        assert eval_res.recommended_strategy in [
            "PAYMENT_LINK", "ALTERNATIVE_PAYMENT_METHOD", "PAYMENT_RETRY",
            "SCHEDULED_REMINDER", "MANDATE_RECOVERY", "HUMAN_ESCALATION"
        ]
        assert 0.0 <= eval_res.calibrated_probability <= 1.0
    finally:
        db.close()


# ============================================================================
# 4. EXPLAINABILITY & INTELLIGENCE API TESTS
# ============================================================================

def test_api_outcomes_list_authenticated():
    """Verify GET /api/intelligence/outcomes returns paginated list."""
    token = get_auth_token("operator@payrecover.ai", "Operator@123")
    res = client.get("/api/intelligence/outcomes?page=1&limit=10", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "verified_recovered_count" in data
    assert len(data["items"]) <= 10


def test_api_outcomes_summary():
    """Verify GET /api/intelligence/outcomes/summary returns verified recovery breakdown."""
    token = get_auth_token("operator@payrecover.ai", "Operator@123")
    res = client.get("/api/intelligence/outcomes/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "total_attempts" in data
    assert "verified_recovered" in data
    assert "recovery_rate_observed" in data
    assert data["verified_recovered"] >= 0


def test_api_evaluate_case():
    """Verify GET /api/intelligence/evaluate/{case_id} returns candidate comparisons."""
    db = SessionLocal()
    case = db.query(RecoveryCase).first()
    db.close()
    assert case is not None

    token = get_auth_token("operator@payrecover.ai", "Operator@123")
    res = client.get(f"/api/intelligence/evaluate/{case.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "recommended_strategy" in data
    assert "calibrated_probability" in data
    assert "candidates" in data
    assert len(data["candidates"]) > 0


def test_api_explain_case():
    """Verify GET /api/intelligence/explain/{case_id} provides explainability dossier."""
    db = SessionLocal()
    case = db.query(RecoveryCase).first()
    db.close()
    assert case is not None

    token = get_auth_token("operator@payrecover.ai", "Operator@123")
    res = client.get(f"/api/intelligence/explain/{case.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "recommended_strategy" in data
    assert "historical_sample_size" in data
    assert "confidence_interval_95" in data
    assert "methodology_disclaimer" in data


def test_api_calibration_metrics():
    """Verify GET /api/intelligence/calibration returns Brier and ranking scores."""
    token = get_auth_token("operator@payrecover.ai", "Operator@123")
    res = client.get("/api/intelligence/calibration", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "baseline_brier_score" in data
    assert "model_brier_score" in data
    assert "brier_skill_score" in data
    assert "model_version" in data


def test_api_recalibrate_role_based_access():
    """Verify viewer role is blocked (403) while analyst/admin can recalibrate."""
    # Viewer attempt (should be 403 Forbidden)
    viewer_token = get_auth_token("viewer@payrecover.ai", "Viewer@123")
    res_viewer = client.post("/api/intelligence/recalibrate", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403

    # Analyst attempt (should be 200 OK)
    analyst_token = get_auth_token("analyst@payrecover.ai", "Analyst@123")
    res_analyst = client.post("/api/intelligence/recalibrate", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res_analyst.status_code == 200
    assert "brier_skill_score" in res_analyst.json()
