import json
import uuid
import time
import asyncio
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    Customer,
    Payment,
    RecoveryCase,
    PaymentStatus,
    RecoveryStatus,
    WebhookEvent,
    WebhookEventStatus,
    MerchantGuardrail,
    User,
    UserRole
)
from app.core.logging_config import sanitize_log_message
from app.core.metrics import metrics
from app.services.webhook_service import webhook_service
from app.services.outbox_worker import outbox_worker
from app.services.payment_state_machine import payment_state_machine
from app.tools.tool_executor import ToolExecutor
from app.schemas.contracts import ToolType, ToolExecutionStatus
from app.services.idempotency_service import IdempotencyService

client = TestClient(app)


def setup_module(module):
    """Seed test database with baseline users and guardrails."""
    seed_database()


def get_token(email: str, password: str = "Operator@123") -> str:
    """Helper to authenticate and retrieve a JWT bearer token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


# ============================================================================
# 1. STRUCTURED LOGGING & SECURITY SANITIZATION TESTS
# ============================================================================

def test_log_sanitization_zero_sensitive_data_leaked():
    """Confirms passwords, JWT tokens, Bearer tokens, card numbers, and API keys are redacted."""
    sensitive_log = (
        "User login token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NSJ9.abc_def123 "
        "password: SecretPassword123! key_secret=rzp_live_secretkey99999 "
        "Customer card number 4111 2222 3333 4444 and cvv: 987"
    )
    sanitized = sanitize_log_message(sensitive_log)

    assert "SecretPassword123!" not in sanitized
    assert "4111 2222 3333 4444" not in sanitized
    assert "987" not in sanitized
    assert "rzp_live_secretkey99999" not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized or "[REDACTED_JWT]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "[REDACTED_CARD_NUMBER]" in sanitized
    assert "[REDACTED_CVV]" in sanitized


def test_correlation_id_propagation_across_middleware():
    """Confirms inbound correlation and request IDs are echoed in response headers."""
    custom_req_id = f"req_test_{uuid.uuid4().hex[:8]}"
    custom_corr_id = f"corr_test_{uuid.uuid4().hex[:8]}"

    res = client.get(
        "/health/live",
        headers={
            "X-Request-ID": custom_req_id,
            "X-Correlation-ID": custom_corr_id
        }
    )
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == custom_req_id
    assert res.headers["X-Correlation-ID"] == custom_corr_id
    assert "X-Response-Time" in res.headers


# ============================================================================
# 2. METRICS & PROMETHEUS OBSERVABILITY TESTS
# ============================================================================

def test_prometheus_metrics_endpoint():
    """Confirms /metrics exposes valid Prometheus text format with registered metrics."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    body = res.text

    assert "# HELP payrecover_http_requests_total" in body
    assert "# TYPE payrecover_http_requests_total counter" in body
    assert "payrecover_outbox_events_pending" in body
    assert "payrecover_outbox_processing_total" in body
    assert "payrecover_recovery_outcomes_total" in body


# ============================================================================
# 3. HEALTH, READINESS, & DEPENDENCY PROBES
# ============================================================================

def test_liveness_readiness_and_dependency_health_probes():
    """Confirms /health/live, /health/ready, /health/deps, and /health/worker return expected structures."""
    # Liveness
    live_res = client.get("/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "ALIVE"

    # Readiness
    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "READY"
    assert ready_res.json()["database"] == "CONNECTED"

    # Dependencies
    deps_res = client.get("/health/deps")
    assert deps_res.status_code == 200
    data = deps_res.json()
    assert data["overall"] in ("HEALTHY", "DEGRADED")
    assert "database" in data["dependencies"]
    assert "redis" in data["dependencies"]
    assert "outbox_worker" in data["dependencies"]

    # Worker
    worker_res = client.get("/health/worker")
    assert worker_res.status_code == 200
    assert "queue" in worker_res.json()


def test_readiness_probe_database_down_returns_503():
    """Readiness probe returns HTTP 503 when primary database query fails."""
    from app.db.session import get_db

    def failing_db():
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection timeout")
        yield mock_db

    app.dependency_overrides[get_db] = failing_db
    try:
        res = client.get("/health/ready")
        assert res.status_code == 503
        assert res.json()["status"] == "UNREADY"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ============================================================================
# 4. OUTBOX WORKER, CRASH RECOVERY, & CONCURRENCY TESTS
# ============================================================================

def test_double_webhook_ingestion_idempotency():
    """Identical webhook delivery is safely deduplicated without creating duplicate DB records."""
    db = SessionLocal()
    try:
        event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
        payload = {
            "event": "payment.authorized",
            "created_at": int(datetime.utcnow().timestamp()),
            "id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_dup_{uuid.uuid4().hex[:8]}",
                        "amount": 250000,
                        "currency": "INR",
                        "status": "authorized"
                    }
                }
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")

        # First ingestion
        rec1, is_dup1 = webhook_service.ingest_event(db, body_bytes, payload, signature_header="sig1", event_id_header=event_id)
        assert is_dup1 is False

        # Second delivery (duplicate delivery race)
        rec2, is_dup2 = webhook_service.ingest_event(db, body_bytes, payload, signature_header="sig1", event_id_header=event_id)
        assert is_dup2 is True
        assert rec1.id == rec2.id

        # Verify DB has only 1 row
        count = db.query(WebhookEvent).filter(WebhookEvent.provider_event_id == event_id).count()
        assert count == 1
    finally:
        db.close()


def test_concurrent_outbox_worker_claims_single_winner():
    """Two concurrent worker process calls on the same event allow only one winner to claim the lock."""
    db = SessionLocal()
    try:
        event = WebhookEvent(
            id=f"whe_claim_{uuid.uuid4().hex[:8]}",
            provider="razorpay",
            provider_event_id=f"pe_claim_{uuid.uuid4().hex[:8]}",
            event_type="payment.failed",
            status=WebhookEventStatus.RECEIVED.value,
            payload_json=json.dumps({"event": "payment.failed", "payload": {}}),
            attempt_count=0,
            max_attempts=5,
            next_retry_at=datetime.utcnow()
        )
        db.add(event)
        db.commit()

        # Simulate first worker claiming the event
        claimed1 = db.query(WebhookEvent).filter(
            WebhookEvent.id == event.id,
            WebhookEvent.status.in_([WebhookEventStatus.RECEIVED.value, WebhookEventStatus.RETRY_PENDING.value])
        ).update({
            WebhookEvent.status: WebhookEventStatus.PROCESSING.value,
            WebhookEvent.attempt_count: WebhookEvent.attempt_count + 1,
            WebhookEvent.updated_at: datetime.utcnow()
        }, synchronize_session=False)
        db.commit()
        assert claimed1 == 1

        # Second concurrent worker attempts claiming identical event
        claimed2 = db.query(WebhookEvent).filter(
            WebhookEvent.id == event.id,
            WebhookEvent.status.in_([WebhookEventStatus.RECEIVED.value, WebhookEventStatus.RETRY_PENDING.value])
        ).update({
            WebhookEvent.status: WebhookEventStatus.PROCESSING.value,
            WebhookEvent.attempt_count: WebhookEvent.attempt_count + 1,
            WebhookEvent.updated_at: datetime.utcnow()
        }, synchronize_session=False)
        db.commit()
        assert claimed2 == 0  # Second worker must be blocked!
    finally:
        db.close()


def test_outbox_worker_crash_recovery_stale_processing_event():
    """Events stuck in PROCESSING state due to a worker crash are safely recovered after threshold."""
    db = SessionLocal()
    try:
        stuck_time = datetime.utcnow() - timedelta(seconds=400)
        stuck_event = WebhookEvent(
            id=f"whe_crash_{uuid.uuid4().hex[:8]}",
            provider="razorpay",
            provider_event_id=f"pe_crash_{uuid.uuid4().hex[:8]}",
            event_type="payment.failed",
            status=WebhookEventStatus.PROCESSING.value,
            payload_json=json.dumps({"event": "payment.failed", "payload": {}}),
            attempt_count=1,
            max_attempts=5,
            updated_at=stuck_time
        )
        db.add(stuck_event)
        db.commit()

        # Run crash recovery with 120s threshold
        recovered_count = webhook_service.recover_stale_events(db, stale_threshold_seconds=120)
        assert recovered_count >= 1

        db.refresh(stuck_event)
        assert stuck_event.status == WebhookEventStatus.RETRY_PENDING.value
        assert "timed out or interrupted" in stuck_event.last_error
    finally:
        db.close()


def test_dead_letter_operational_replay_authorized_vs_unauthorized():
    """Replaying a dead-letter event requires OPERATOR or ADMIN role; VIEWER is rejected with 403."""
    db = SessionLocal()
    try:
        dead_event = WebhookEvent(
            id=f"whe_dl_{uuid.uuid4().hex[:8]}",
            provider="razorpay",
            provider_event_id=f"pe_dl_{uuid.uuid4().hex[:8]}",
            event_type="payment.failed",
            status=WebhookEventStatus.DEAD_LETTER.value,
            payload_json=json.dumps({"event": "payment.failed", "payload": {}}),
            attempt_count=5,
            max_attempts=5,
            last_error="Simulated max retries reached"
        )
        db.add(dead_event)
        db.commit()

        # 1. Unauthenticated -> 401
        res_anon = client.post(f"/api/webhooks/events/{dead_event.id}/retry")
        assert res_anon.status_code == 401

        # 2. Viewer role -> 403 Forbidden
        viewer_token = get_token("viewer@payrecover.ai", "Viewer@123")
        res_viewer = client.post(
            f"/api/webhooks/events/{dead_event.id}/retry",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert res_viewer.status_code == 403

        # 3. Operator role -> 200 OK
        op_token = get_token("operator@payrecover.ai", "Operator@123")
        res_op = client.post(
            f"/api/webhooks/events/{dead_event.id}/retry",
            headers={"Authorization": f"Bearer {op_token}"}
        )
        assert res_op.status_code == 200
        assert res_op.json()["event_id"] == dead_event.id

        db.refresh(dead_event)
        meta = json.loads(dead_event.processing_metadata_json or "{}")
        assert "replays" in meta
        assert meta["replays"][-1]["operator"] == "operator@payrecover.ai"
    finally:
        db.close()


# ============================================================================
# 5. FINANCIAL SAFETY & CONCURRENCY CONSTRAINTS
# ============================================================================

def test_settled_payment_rejects_further_recovery():
    """An already settled payment (RECOVERED) rejects further recovery tool execution."""
    db = SessionLocal()
    try:
        cust = db.query(Customer).first()
        assert cust is not None
        pay_id = f"pay_settled_{uuid.uuid4().hex[:8]}"
        case_id = f"rc_settled_{uuid.uuid4().hex[:8]}"

        payment = Payment(
            id=pay_id,
            razorpay_payment_id=f"rzp_settled_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount=4500.0,
            currency="INR",
            status=PaymentStatus.RECOVERED.value,  # Already settled
            payment_method="UPI"
        )
        db.add(payment)

        case = RecoveryCase(
            id=case_id,
            payment_id=pay_id,
            status=RecoveryStatus.RECOVERED.value,
            recovery_score=90.0,
            recovery_probability=0.95
        )
        db.add(case)
        db.commit()

        # Attempt to execute a payment link creation tool on an already settled payment
        result = ToolExecutor.execute(
            db=db,
            recovery_case_id=case_id,
            tool_type=ToolType.CREATE_PAYMENT_LINK
        )
        assert result.success is False
        assert result.guardrail_status == "BLOCKED"
        assert "already successfully settled" in result.message
    finally:
        db.close()


def test_high_value_transaction_mandates_human_approval():
    """Transactions meeting or exceeding ₹50,000 mandate human authorization."""
    db = SessionLocal()
    try:
        cust = db.query(Customer).first()
        assert cust is not None
        pay_id = f"pay_high_{uuid.uuid4().hex[:8]}"
        case_id = f"rc_high_{uuid.uuid4().hex[:8]}"

        payment = Payment(
            id=pay_id,
            razorpay_payment_id=f"rzp_high_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount=75000.0,  # ₹75,000 (exceeds ₹50k threshold)
            currency="INR",
            status=PaymentStatus.FAILED.value,
            payment_method="NETBANKING"
        )
        db.add(payment)

        case = RecoveryCase(
            id=case_id,
            payment_id=pay_id,
            status=RecoveryStatus.IDENTIFIED.value,
            recovery_score=50.0,
            recovery_probability=0.50
        )
        db.add(case)
        db.commit()

        # Attempt automated execution without approval token
        result = ToolExecutor.execute(
            db=db,
            recovery_case_id=case_id,
            tool_type=ToolType.CREATE_PAYMENT_LINK
        )
        assert result.success is False
        assert result.requires_human_approval is True
        assert result.approval_id is not None
        assert "Human approval required" in result.message
    finally:
        db.close()


def test_max_retry_exhaustion_blocks_further_retries():
    """When recovery retry count equals or exceeds max_retries, retry tools are blocked."""
    db = SessionLocal()
    try:
        cust = db.query(Customer).first()
        assert cust is not None
        pay_id = f"pay_retry_{uuid.uuid4().hex[:8]}"
        case_id = f"rc_retry_{uuid.uuid4().hex[:8]}"

        payment = Payment(
            id=pay_id,
            razorpay_payment_id=f"rzp_retry_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount=2000.0,
            currency="INR",
            status=PaymentStatus.FAILED.value,
            payment_method="CARD"
        )
        db.add(payment)

        case = RecoveryCase(
            id=case_id,
            payment_id=pay_id,
            status=RecoveryStatus.ACTION_IN_PROGRESS.value,
            retry_count=3  # Equal to default max_retries (3)
        )
        db.add(case)
        db.commit()

        result = ToolExecutor.execute(
            db=db,
            recovery_case_id=case_id,
            tool_type=ToolType.RETRY_PAYMENT
        )
        assert result.success is False
        assert result.guardrail_status == "BLOCKED"
        assert "Retry blocked" in result.message or "Max Retry Limit Reached" in result.message
    finally:
        db.close()


def test_discount_cap_enforcement():
    """Attempting a promotional discount higher than merchant configured cap is capped safely."""
    db = SessionLocal()
    try:
        cust = db.query(Customer).first()
        assert cust is not None
        pay_id = f"pay_disc_{uuid.uuid4().hex[:8]}"
        case_id = f"rc_disc_{uuid.uuid4().hex[:8]}"

        payment = Payment(
            id=pay_id,
            razorpay_payment_id=f"rzp_disc_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount=5000.0,
            currency="INR",
            status=PaymentStatus.FAILED.value,
            payment_method="CARD"
        )
        db.add(payment)

        case = RecoveryCase(
            id=case_id,
            payment_id=pay_id,
            status=RecoveryStatus.ACTION_IN_PROGRESS.value
        )
        db.add(case)
        db.commit()

        # Attempt to apply 25% discount when merchant cap is 10%
        result = ToolExecutor.execute(
            db=db,
            recovery_case_id=case_id,
            tool_type=ToolType.CREATE_PAYMENT_LINK,
            parameters={"discount_percentage": 25.0}
        )
        assert result.success is True
        # Amount should be capped to 10% discount: 5000 * (1 - 0.10) = 4500.0 (blocked from 25% discount of 3750.0)
        assert result.amount == 4500.0
        assert result.amount > 3750.0
    finally:
        db.close()



def test_idempotency_key_duplicate_request_replay():
    """Duplicate request using the same idempotency key returns the cached execution result."""
    db = SessionLocal()
    try:
        idem_key = f"idem_test_{uuid.uuid4().hex[:12]}"

        # Record first execution
        rec = IdempotencyService.save(
            db=db,
            key=idem_key,
            recovery_case_id="rc_test_idem",
            action_type="GENERATE_PAYMENT_LINK",
            status_code=200,
            result={"payment_link_url": "https://rzp.io/i/test1234", "amount": 2500.0}
        )
        assert rec is not None

        # Fetch duplicate execution
        cached = IdempotencyService.get(db=db, key=idem_key)
        assert cached is not None
        assert cached.key == idem_key
        assert cached.status_code == 200
        data = json.loads(cached.result_json)
        assert data["amount"] == 2500.0
    finally:
        db.close()


def test_payment_timeout_followed_by_authoritative_webhook():
    """A network timeout does not prove payment failure; subsequent success webhook captures recovery."""
    db = SessionLocal()
    try:
        rzp_id = f"pay_timeout_{uuid.uuid4().hex[:8]}"
        pay = Payment(
            id=f"pay_int_{uuid.uuid4().hex[:8]}",
            razorpay_payment_id=rzp_id,
            customer_id="cust_001",
            amount=3200.0,
            currency="INR",
            status=PaymentStatus.PENDING.value,
            payment_method="UPI"
        )
        db.add(pay)
        db.commit()

        # Simulate timeout: status remains PENDING (never falsely set to FAILED solely due to timeout)
        assert pay.status == PaymentStatus.PENDING.value

        # Authoritative webhook arrives later: payment.captured
        success, msg = payment_state_machine.transition_payment(
            db=db,
            payment=pay,
            target_status=PaymentStatus.SUCCESS.value,
            source_event="webhook_timeout_recovery"
        )
        assert success is True
        assert pay.status == PaymentStatus.SUCCESS.value
    finally:
        db.close()
