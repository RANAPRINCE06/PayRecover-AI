"""
PayRecover AI — Phase 6 Controlled Strategy Experimentation & Optimization Engine Tests
Comprehensive test suite covering configuration validation, RBAC, deterministic stable assignment,
concurrency protection, guardrail preservation, strategy deviations, verified outcome reconciliation,
Wilson score confidence intervals, two-proportion hypothesis tests, offline bandit simulation, and orchestrator integration.
"""
import uuid
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    User,
    UserRole,
    RecoveryExperiment,
    ExperimentAssignment,
    ExperimentOutcomeAttribution,
    ExperimentStatus,
    RecoveryCase,
    Payment,
    PaymentStatus,
    RecoveryStatus,
    PaymentMethod,
    FailureReason,
    MerchantGuardrail
)
from app.schemas.contracts import (
    ExperimentArmConfig,
    ExperimentCreateRequest,
    ExperimentUpdateRequest,
    ExperimentStatusTransitionRequest,
    OfflineSimulationRequest
)
from app.services.experiment_service import experiment_service, _two_proportion_z_test
from app.services.intelligence_service import calculate_wilson_score_interval
from app.agents.orchestrator import RecoveryOrchestrator

client = TestClient(app)


def setup_module(module):
    """Seed test database before running experimentation tests."""
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
# 1. EXPERIMENT CONFIGURATION & VALIDATION TESTS
# ============================================================================

def test_validation_valid_config_accepted():
    """Valid experiment configuration with 50/50 split and control arm passes validation."""
    token = get_token("operator")
    payload = {
        "name": "Test UPI Link vs Alt Method",
        "objective": "Evaluate conversion lift of alternative payment rails on UPI timeout.",
        "hypothesis": "Alternative method increases recovery rate by 8%.",
        "primary_metric": "recovery_rate",
        "is_sandbox_only": True,
        "target_failure_categories": ["UPI_TIMEOUT"],
        "target_payment_methods": ["UPI"],
        "candidate_strategies": [
            {
                "arm_id": "ctrl_link",
                "strategy": "PAYMENT_LINK",
                "traffic_percentage": 50.0,
                "is_control": True,
                "description": "Control Arm: Standard Link"
            },
            {
                "arm_id": "treat_alt",
                "strategy": "ALTERNATIVE_PAYMENT_METHOD",
                "traffic_percentage": 50.0,
                "is_control": False,
                "description": "Treatment Arm: Alt Rail"
            }
        ],
        "min_observation_count": 30
    }
    res = client.post("/api/experiments", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "DRAFT"
    assert data["version"] == 1
    assert len(data["candidate_strategies"]) == 2


def test_validation_traffic_not_100_rejected():
    """Experiment with traffic allocations not summing to 100% must be rejected."""
    token = get_token("operator")
    payload = {
        "name": "Invalid Traffic Sum Experiment",
        "objective": "Test traffic validation failure when sum is 80%.",
        "candidate_strategies": [
            {"arm_id": "ctrl", "strategy": "PAYMENT_LINK", "traffic_percentage": 40.0, "is_control": True},
            {"arm_id": "treat", "strategy": "ALTERNATIVE_PAYMENT_METHOD", "traffic_percentage": 40.0, "is_control": False}
        ]
    }
    res = client.post("/api/experiments", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "100.0%" in res.json()["detail"]


def test_validation_missing_control_arm_rejected():
    """Experiment missing a designated control arm must be rejected."""
    token = get_token("operator")
    payload = {
        "name": "Missing Control Arm Experiment",
        "objective": "Test validation failure when no arm has is_control=True.",
        "candidate_strategies": [
            {"arm_id": "arm_a", "strategy": "PAYMENT_LINK", "traffic_percentage": 50.0, "is_control": False},
            {"arm_id": "arm_b", "strategy": "ALTERNATIVE_PAYMENT_METHOD", "traffic_percentage": 50.0, "is_control": False}
        ]
    }
    res = client.post("/api/experiments", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "control" in res.json()["detail"].lower()


def test_validation_duplicate_arm_ids_rejected():
    """Candidate arms with duplicate arm_ids must be rejected."""
    token = get_token("operator")
    payload = {
        "name": "Duplicate Arm ID Experiment",
        "objective": "Test validation failure for duplicate arm IDs.",
        "candidate_strategies": [
            {"arm_id": "arm_dup", "strategy": "PAYMENT_LINK", "traffic_percentage": 50.0, "is_control": True},
            {"arm_id": "arm_dup", "strategy": "ALTERNATIVE_PAYMENT_METHOD", "traffic_percentage": 50.0, "is_control": False}
        ]
    }
    res = client.post("/api/experiments", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "unique" in res.json()["detail"].lower()


# ============================================================================
# 2. RBAC & PERMISSIONS TESTS
# ============================================================================

def test_rbac_viewer_cannot_create_experiment():
    """User with VIEWER role must be forbidden (403) from creating an experiment."""
    token = get_token("viewer")
    payload = {
        "name": "Viewer Unauthorized Experiment",
        "objective": "Attempt creation by read-only viewer.",
        "candidate_strategies": [
            {"arm_id": "ctrl", "strategy": "PAYMENT_LINK", "traffic_percentage": 50.0, "is_control": True},
            {"arm_id": "treat", "strategy": "ALTERNATIVE_PAYMENT_METHOD", "traffic_percentage": 50.0, "is_control": False}
        ]
    }
    res = client.post("/api/experiments", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_rbac_viewer_can_read_experiments():
    """User with VIEWER role can read experiment lists and metrics."""
    token = get_token("viewer")
    res = client.get("/api/experiments", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "experiments" in data
    assert data["total"] >= 1


# ============================================================================
# 3. DETERMINISTIC & STABLE STRATEGY ASSIGNMENT TESTS
# ============================================================================

def test_stable_assignment_same_case_returns_identical_arm():
    """Querying assignment multiple times for the same case returns identical arm and strategy."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        assert case is not None
        payment = case.payment

        # First assignment
        asgn_1 = experiment_service.assign_strategy_for_case(
            db=db,
            recovery_case=case,
            payment=payment,
            is_sandbox_request=True
        )
        assert asgn_1 is not None

        # Repeat assignment (simulate retry or subsequent agent step)
        asgn_2 = experiment_service.assign_strategy_for_case(
            db=db,
            recovery_case=case,
            payment=payment,
            is_sandbox_request=True
        )
        assert asgn_2 is not None
        assert asgn_1.id == asgn_2.id
        assert asgn_1.arm_id == asgn_2.arm_id
        assert asgn_1.assigned_strategy == asgn_2.assigned_strategy
        assert asgn_1.hash_bucket == asgn_2.hash_bucket
    finally:
        db.close()


def test_concurrency_protection_duplicate_assignment_prevented():
    """Database unique constraint on (experiment_id, recovery_case_id) prevents duplicates."""
    db = SessionLocal()
    try:
        exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.status == "RUNNING").first()
        assert exp is not None
        case = db.query(RecoveryCase).first()
        assert case is not None

        # Query existing assignment
        existing = db.query(ExperimentAssignment).filter(
            ExperimentAssignment.experiment_id == exp.id,
            ExperimentAssignment.recovery_case_id == case.id
        ).first()

        if not existing:
            existing = ExperimentAssignment(
                id=f"asgn_test_{uuid.uuid4().hex[:8]}",
                experiment_id=exp.id,
                experiment_version=exp.version,
                recovery_case_id=case.id,
                payment_id=case.payment_id,
                arm_id="control_link",
                assigned_strategy="PAYMENT_LINK",
                is_control=True,
                hash_bucket=1234,
                assignment_salt="test_salt",
                assigned_at=datetime.utcnow()
            )
            db.add(existing)
            db.commit()

        # Attempting to insert a duplicate assignment record must fail
        dup = ExperimentAssignment(
            id=f"asgn_test_dup_{uuid.uuid4().hex[:8]}",
            experiment_id=exp.id,
            experiment_version=exp.version,
            recovery_case_id=case.id,
            payment_id=case.payment_id,
            arm_id="variant_alt_method",
            assigned_strategy="ALTERNATIVE_PAYMENT_METHOD",
            is_control=False,
            hash_bucket=5678,
            assignment_salt="test_salt",
            assigned_at=datetime.utcnow()
        )
        db.add(dup)
        with pytest.raises(Exception):
            db.commit()
        db.rollback()
    finally:
        db.close()


# ============================================================================
# 4. ELIGIBILITY & STATUS BOUNDS TESTS
# ============================================================================

def test_ineligible_mismatched_payment_method():
    """Case with payment method not in experiment targets is excluded."""
    db = SessionLocal()
    try:
        exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.id == "exp_upi_recovery_v1").first()
        assert exp is not None

        # Create mock non-UPI payment
        p = Payment(
            id=f"pay_ineligible_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id="cust_test",
            amount=2500.0,
            currency="INR",
            status=PaymentStatus.FAILED.value,
            payment_method="NETBANKING",
            failure_reason="BANK_SERVER_DOWN"
        )
        rc = RecoveryCase(
            id=f"rc_ineligible_{uuid.uuid4().hex[:8]}",
            payment_id=p.id,
            status=RecoveryStatus.IDENTIFIED.value
        )

        eligible, reason = experiment_service.evaluate_case_eligibility(
            experiment=exp,
            payment=p,
            recovery_case=rc,
            is_sandbox_request=True
        )
        assert eligible is False
        assert "NETBANKING" in reason
    finally:
        db.close()


def test_paused_experiment_rejects_new_assignments():
    """An experiment in PAUSED status does not accept new case assignments."""
    db = SessionLocal()
    try:
        # Create a paused experiment
        exp = RecoveryExperiment(
            id=f"exp_paused_{uuid.uuid4().hex[:8]}",
            name="Paused Experiment",
            objective="Testing paused state rejection.",
            status=ExperimentStatus.PAUSED.value,
            version=1,
            owner_email="operator@payrecover.ai",
            primary_metric="recovery_rate",
            candidate_strategies_json=json.dumps([
                {"arm_id": "ctrl", "strategy": "PAYMENT_LINK", "traffic_percentage": 50.0, "is_control": True},
                {"arm_id": "treat", "strategy": "ALTERNATIVE_PAYMENT_METHOD", "traffic_percentage": 50.0, "is_control": False}
            ]),
            min_observation_count=30,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(exp)
        db.commit()

        p = Payment(
            id=f"pay_test_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=f"pay_rzp_{uuid.uuid4().hex[:8]}",
            customer_id="cust_test",
            amount=1500.0,
            currency="INR",
            status=PaymentStatus.FAILED.value,
            payment_method="UPI",
            failure_reason="UPI_TIMEOUT"
        )
        rc = RecoveryCase(id=f"rc_test_{uuid.uuid4().hex[:8]}", payment_id=p.id)

        eligible, reason = experiment_service.evaluate_case_eligibility(exp, p, rc, is_sandbox_request=True)
        assert eligible is False
        assert "PAUSED" in reason
    finally:
        db.close()


# ============================================================================
# 5. FINANCIAL GUARDRAIL PRESERVATION & STRATEGY DEVIATIONS
# ============================================================================

def test_high_value_guardrail_enforces_human_escalation_and_logs_deviation():
    """
    Even if an experiment assigns an automated link or retry, high-value payments
    (>= threshold) MUST enforce human escalation and record a strategy deviation.
    """
    db = SessionLocal()
    try:
        exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.status == "RUNNING").first()
        assert exp is not None

        case = db.query(RecoveryCase).first()
        assert case is not None

        # Create assignment
        asgn = db.query(ExperimentAssignment).filter(ExperimentAssignment.recovery_case_id == case.id).first()
        if not asgn:
            asgn = ExperimentAssignment(
                id=f"asgn_dev_{uuid.uuid4().hex[:8]}",
                experiment_id=exp.id,
                experiment_version=exp.version,
                recovery_case_id=case.id,
                payment_id=case.payment_id,
                arm_id="variant_alt_method",
                assigned_strategy="ALTERNATIVE_PAYMENT_METHOD",
                is_control=False,
                hash_bucket=5000,
                assignment_salt="salt",
                assigned_at=datetime.utcnow()
            )
            db.add(asgn)
            db.commit()

        # Guardrail overrides treatment to HUMAN_ESCALATION
        att = experiment_service.record_strategy_execution(
            db=db,
            recovery_case_id=case.id,
            executed_strategy="HUMAN_ESCALATION",
            human_escalated=True,
            discount_offered=0.0,
            retry_count=0
        )
        assert att is not None
        assert att.actual_executed_strategy == "HUMAN_ESCALATION"
        assert att.is_strategy_deviated is True
        assert "HIGH_VALUE" in att.deviation_reason
    finally:
        db.close()


# ============================================================================
# 6. AUTHORITATIVE OUTCOME RECONCILIATION TESTS
# ============================================================================

def test_outcome_reconciliation_recovered_authoritative():
    """Verified settlement updates attribution to RECOVERED with amount and time to recovery."""
    db = SessionLocal()
    try:
        # Find a case with a settled payment
        payment = db.query(Payment).filter(Payment.status.in_([PaymentStatus.RECOVERED.value, PaymentStatus.SUCCESS.value])).first()
        assert payment is not None
        case = payment.recovery_case
        assert case is not None

        # Ensure assignment exists
        exp = db.query(RecoveryExperiment).first()
        asgn = db.query(ExperimentAssignment).filter(ExperimentAssignment.recovery_case_id == case.id).first()
        if not asgn:
            asgn = ExperimentAssignment(
                id=f"asgn_rec_{uuid.uuid4().hex[:8]}",
                experiment_id=exp.id,
                experiment_version=exp.version,
                recovery_case_id=case.id,
                payment_id=payment.id,
                arm_id="control_link",
                assigned_strategy="PAYMENT_LINK",
                is_control=True,
                hash_bucket=1000,
                assignment_salt="salt",
                assigned_at=datetime.utcnow() - timedelta(minutes=45)
            )
            db.add(asgn)
            db.commit()

        att = experiment_service.reconcile_experiment_outcome(
            db=db,
            recovery_case_id=case.id,
            verification_source="test_gateway_webhook"
        )
        assert att is not None
        assert att.outcome_status == "RECOVERED"
        assert att.is_verified is True
        assert att.recovered_amount > 0
        assert att.time_to_recovery_seconds is not None
        assert att.time_to_recovery_seconds >= 0.0
    finally:
        db.close()


def test_pending_outcomes_not_treated_as_failures():
    """Non-terminal cases remain PENDING and are not classified as failures."""
    db = SessionLocal()
    try:
        # Find or create a pending case
        case = db.query(RecoveryCase).filter(
            RecoveryCase.status.in_([RecoveryStatus.ACTION_IN_PROGRESS.value, RecoveryStatus.STRATEGY_SELECTED.value])
        ).first()

        if case and case.payment:
            case.payment.status = PaymentStatus.PENDING.value
            db.commit()

            exp = db.query(RecoveryExperiment).first()
            asgn = db.query(ExperimentAssignment).filter(ExperimentAssignment.recovery_case_id == case.id).first()
            if not asgn:
                asgn = ExperimentAssignment(
                    id=f"asgn_pnd_{uuid.uuid4().hex[:8]}",
                    experiment_id=exp.id,
                    experiment_version=exp.version,
                    recovery_case_id=case.id,
                    payment_id=case.payment.id,
                    arm_id="control_link",
                    assigned_strategy="PAYMENT_LINK",
                    is_control=True,
                    hash_bucket=1000,
                    assignment_salt="salt",
                    assigned_at=datetime.utcnow()
                )
                db.add(asgn)
                db.commit()

            att = experiment_service.reconcile_experiment_outcome(db=db, recovery_case_id=case.id)
            assert att is not None
            assert att.outcome_status == "PENDING"
            assert att.is_verified is False
    finally:
        db.close()


# ============================================================================
# 7. STATISTICAL CALCULATIONS & HYPOTHESIS TESTING
# ============================================================================

def test_wilson_score_interval_mathematical_properties():
    """Wilson score intervals are bounded in [0, 1] and handle edge cases correctly."""
    # Zero sample size
    assert calculate_wilson_score_interval(0, 0) == (0.0, 0.0)

    # 100% successes on small sample
    lower, upper = calculate_wilson_score_interval(5, 5)
    assert 0.0 <= lower < 1.0
    assert upper == 1.0

    # 0% successes
    lower, upper = calculate_wilson_score_interval(0, 10)
    assert lower == 0.0
    assert 0.0 < upper <= 1.0

    # Large sample (standard normal approximation convergence)
    lower, upper = calculate_wilson_score_interval(500, 1000)
    assert round(lower, 2) == 0.47
    assert round(upper, 2) == 0.53


def test_two_proportion_z_test_calculation():
    """Two-proportion z-test correctly computes lift, z-score, and p-value."""
    # Treatment: 70/100 (70%), Control: 50/100 (50%)
    z, p_val, ci_diff = _two_proportion_z_test(x1=70, n1=100, x2=50, n2=100)
    assert z > 0
    assert p_val < 0.01  # Statistically significant difference
    assert ci_diff[0] > 0  # Lower bound of difference is positive


def test_experiment_metrics_api_endpoint():
    """GET /api/experiments/{id}/metrics returns comprehensive analytics and safeguards."""
    token = get_token("viewer")
    res = client.get("/api/experiments/exp_upi_recovery_v1/metrics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["experiment_id"] == "exp_upi_recovery_v1"
    assert "arm_metrics" in data
    assert len(data["arm_metrics"]) >= 2
    assert "methodological_safeguards" in data
    assert "rate_denominator" in data["methodological_safeguards"]
    assert "as_of_timestamp" in data


# ============================================================================
# 8. OFFLINE SIMULATION TESTS
# ============================================================================

def test_offline_simulation_fixed_split_and_bandit():
    """POST /api/experiments/{id}/simulate executes deterministic synthetic simulations."""
    token = get_token("operator")
    req = {
        "cohort_size": 50,
        "failure_category": "UPI_TIMEOUT",
        "payment_method": "UPI",
        "random_seed": 42,
        "enable_thompson_sampling": True
    }
    res = client.post("/api/experiments/exp_upi_recovery_v1/simulate", json=req, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["simulation_id"].startswith("sim_")
    assert data["cohort_size"] == 50
    assert data["allocation_method"] == "ADAPTIVE_THOMPSON_SAMPLING"
    assert "methodology_disclaimer" in data
    assert "OFFLINE SIMULATION ONLY" in data["methodology_disclaimer"]


# ============================================================================
# 9. EXPORT ENDPOINT TESTS
# ============================================================================

def test_export_experiment_telemetry_csv_and_json():
    """GET /api/experiments/{id}/export supports sanitized JSON and CSV formats."""
    token = get_token("viewer")

    # JSON export
    res_json = client.get("/api/experiments/exp_upi_recovery_v1/export?format=json", headers={"Authorization": f"Bearer {token}"})
    assert res_json.status_code == 200
    data = res_json.json()
    assert "records" in data

    # CSV export
    res_csv = client.get("/api/experiments/exp_upi_recovery_v1/export?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "assignment_id" in res_csv.text


# ============================================================================
# 10. END-TO-END AUTONOMOUS PIPELINE INTEGRATION
# ============================================================================

def test_orchestrator_autonomous_recovery_with_experiment():
    """End-to-end autonomous recovery pipeline assigns experiment and records execution telemetry."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        assert case is not None

        result = RecoveryOrchestrator.run_autonomous_recovery(db=db, recovery_case_id=case.id)
        assert result is not None
        assert result.case_id == case.id
        assert result.total_steps == 6

        # Check that assignment and execution were registered
        asgn = db.query(ExperimentAssignment).filter(ExperimentAssignment.recovery_case_id == case.id).first()
        if asgn:
            att = db.query(ExperimentOutcomeAttribution).filter(ExperimentOutcomeAttribution.assignment_id == asgn.id).first()
            assert att is not None
            assert att.actual_executed_strategy is not None
    finally:
        db.close()
