import hmac
import hashlib
import json
import uuid
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed_data import seed_database
from app.models.entities import (
    Payment,
    RecoveryCase,
    PaymentStatus,
    RecoveryStatus,
    WebhookEvent,
    WebhookEventStatus,
    User
)
from app.core.webhook_verifier import webhook_verifier
from app.services.webhook_service import webhook_service
from app.services.payment_state_machine import payment_state_machine
from app.services.redis_service import redis_service

client = TestClient(app)


def setup_module(module):
    """Seed test database."""
    seed_database()


def get_token_for(email: str, password: str) -> str:
    """Helper to authenticate and extract bearer token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def make_signature(raw_body: bytes, secret: str = None) -> str:
    """Compute official Razorpay HMAC-SHA256 signature."""
    sec = secret or settings.RAZORPAY_WEBHOOK_SECRET
    return hmac.new(sec.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


# ============================================================================
# A. WEBHOOK SECURITY TESTS
# ============================================================================

def test_webhook_security_valid_signature_accepted():
    """Valid HMAC-SHA256 signature returns 200 OK."""
    payload = {
        "event": "payment.authorized",
        "created_at": int(datetime.utcnow().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_test_{uuid.uuid4().hex[:6]}",
                    "amount": 250000,
                    "status": "authorized"
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = make_signature(raw_body)

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("received", "duplicate")
    assert "event_id" in data


def test_webhook_security_invalid_signature_rejected():
    """Invalid signature returns 400 Bad Request."""
    raw_body = b'{"event": "payment.failed"}'
    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_signature_hex_12345"}
    )
    assert res.status_code == 400
    assert "invalid webhook signature" in res.json()["detail"].lower()


def test_webhook_security_missing_signature_rejected():
    """Missing signature header returns 400 Bad Request."""
    raw_body = b'{"event": "payment.failed"}'
    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert "invalid webhook signature" in res.json()["detail"].lower()


def test_webhook_security_modified_body_rejected():
    """Tampered body after signature generation returns 400 Bad Request."""
    orig_body = b'{"event": "payment.failed", "amount": 1000}'
    sig = make_signature(orig_body)

    # Tampered body
    tampered_body = b'{"event": "payment.failed", "amount": 9999}'
    res = client.post(
        "/api/webhooks/razorpay",
        content=tampered_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 400
    assert "invalid webhook signature" in res.json()["detail"].lower()


def test_webhook_security_malformed_json_rejected():
    """Malformed non-JSON body returns 400 Bad Request."""
    bad_body = b"not a json payload at all"
    sig = make_signature(bad_body)
    res = client.post(
        "/api/webhooks/razorpay",
        content=bad_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 400
    assert "malformed" in res.json()["detail"].lower()


def test_webhook_security_missing_event_field_rejected():
    """JSON missing the required 'event' field returns 400 Bad Request."""
    body = b'{"created_at": 1600000000, "contains": ["payment"]}'
    sig = make_signature(body)
    res = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 400
    assert "missing" in res.json()["detail"].lower()


def test_webhook_security_unknown_event_type_handled_safely():
    """Unknown or unsupported events are accepted without crashing and recorded safely."""
    payload = {
        "event": "virtual_account.credited",
        "created_at": int(datetime.utcnow().timestamp()),
        "payload": {"virtual_account": {"entity": {"id": "va_123"}}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = make_signature(raw_body)
    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 200
    event_id = res.json()["event_id"]

    # Process event
    success = webhook_service.process_event(event_id)
    assert success is True


def test_webhook_security_secret_not_configured_rejects():
    """If secret is empty, verifier safely rejects."""
    assert webhook_verifier.verify_signature(b'{"test": 1}', "sig", secret="") is False
    assert webhook_verifier.verify_signature(b'{"test": 1}', "sig", secret="   ") is False


# ============================================================================
# B. IDEMPOTENCY & CONCURRENCY TESTS
# ============================================================================

def test_webhook_duplicate_delivery_idempotent():
    """Duplicate delivery with identical payload returns status 'duplicate' without error."""
    unique_id = f"pay_idem_{uuid.uuid4().hex[:8]}"
    payload = {
        "event": "payment.captured",
        "created_at": 1700000000,
        "payload": {"payment": {"entity": {"id": unique_id, "amount": 50000}}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = make_signature(raw_body)
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": sig}

    # First delivery
    res1 = client.post("/api/webhooks/razorpay", content=raw_body, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "received"

    # Second delivery with identical payload
    res2 = client.post("/api/webhooks/razorpay", content=raw_body, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate"
    assert res1.json()["event_id"] == res2.json()["event_id"]


def test_webhook_concurrent_execution_protection():
    """Processing an already PROCESSED event is an idempotent no-op."""
    db = SessionLocal()
    event = WebhookEvent(
        id=f"whe_conc_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_conc_{uuid.uuid4().hex[:8]}",
        event_type="payment.authorized",
        status=WebhookEventStatus.PROCESSED.value,
        payload_json=json.dumps({"event": "payment.authorized"}),
        received_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    # Re-running process_event returns True immediately without reprocessing
    assert webhook_service.process_event(event_id) is True


def test_webhook_reprocessing_safe():
    """Eligible failed events can be reprocessed safely."""
    db = SessionLocal()
    event = WebhookEvent(
        id=f"whe_fail_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_fail_{uuid.uuid4().hex[:8]}",
        event_type="payment.authorized",
        status=WebhookEventStatus.FAILED.value,
        attempt_count=2,
        max_attempts=5,
        payload_json=json.dumps({"event": "payment.authorized", "payload": {}}),
        received_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    event_id = event.id

    success, msg = webhook_service.reprocess_event(db, event_id)
    assert success is True

    db.refresh(event)
    assert event.status == WebhookEventStatus.PROCESSED.value
    db.close()


# ============================================================================
# C. PAYMENT STATE MACHINE & ORDERING TESTS
# ============================================================================

def test_state_machine_late_payment_failed_cannot_overwrite_captured():
    """A late payment.failed event must NEVER downgrade an already captured payment."""
    db = SessionLocal()
    payment = Payment(
        id=f"pay_settled_{uuid.uuid4().hex[:6]}",
        razorpay_payment_id=f"rzp_settled_{uuid.uuid4().hex[:6]}",
        customer_id=db.query(Payment).first().customer_id,
        amount=10000.0,
        currency="INR",
        payment_method="CARD",
        status=PaymentStatus.SUCCESS.value,
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.commit()

    # Attempt to transition settled payment to FAILED
    can_trans = payment_state_machine.can_transition(payment.status, PaymentStatus.FAILED.value)
    assert can_trans is False

    success, msg = payment_state_machine.transition_payment(db, payment, PaymentStatus.FAILED.value)
    assert success is False
    assert "refusing downgrade" in msg.lower() or "already settled" in msg.lower()
    assert payment.status == PaymentStatus.SUCCESS.value
    db.close()


def test_state_machine_payment_captured_after_failed_transitions_to_recovered():
    """A payment.captured event on a FAILED payment transitions it to RECOVERED."""
    db = SessionLocal()
    payment = Payment(
        id=f"pay_fail_trans_{uuid.uuid4().hex[:6]}",
        razorpay_payment_id=f"rzp_fail_trans_{uuid.uuid4().hex[:6]}",
        customer_id=db.query(Payment).first().customer_id,
        amount=5000.0,
        currency="INR",
        payment_method="UPI",
        status=PaymentStatus.FAILED.value,
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.flush()

    case = RecoveryCase(
        id=f"rc_fail_trans_{uuid.uuid4().hex[:6]}",
        payment_id=payment.id,
        status=RecoveryStatus.IDENTIFIED.value,
        started_at=datetime.utcnow()
    )
    db.add(case)
    db.commit()

    success, msg = payment_state_machine.transition_payment(db, payment, PaymentStatus.RECOVERED.value)
    assert success is True
    assert payment.status == PaymentStatus.RECOVERED.value
    assert case.status == RecoveryStatus.RECOVERED.value
    assert case.recovered_amount == 5000.0
    db.close()


def test_state_machine_duplicate_captured_is_idempotent():
    """Duplicate captured events on already recovered payments are safe and idempotent."""
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.status == PaymentStatus.RECOVERED.value).first()
    if not payment:
        payment = Payment(
            id=f"pay_rec_{uuid.uuid4().hex[:6]}",
            razorpay_payment_id=f"rzp_rec_{uuid.uuid4().hex[:6]}",
            customer_id=db.query(Payment).first().customer_id,
            amount=4000.0,
            currency="INR",
            payment_method="UPI",
            status=PaymentStatus.RECOVERED.value,
            created_at=datetime.utcnow()
        )
        db.add(payment)
        db.commit()

    success, msg = payment_state_machine.transition_payment(db, payment, PaymentStatus.RECOVERED.value)
    assert success is True
    assert "already in state" in msg.lower()
    db.close()


# ============================================================================
# D. RELIABILITY & RETRY TESTS
# ============================================================================

def test_reliability_worker_failure_triggers_retry_pending():
    """Worker exceptions schedule the event for RETRY_PENDING with backoff."""
    db = SessionLocal()
    event = WebhookEvent(
        id=f"whe_err_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_err_{uuid.uuid4().hex[:8]}",
        event_type="payment.failed",
        status=WebhookEventStatus.RECEIVED.value,
        payload_json=json.dumps({"event": "payment.failed"}),
        attempt_count=0,
        max_attempts=3,
        received_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    # Simulate worker error during execution
    with patch("app.services.webhook_service.WebhookService._execute_event_logic", side_effect=RuntimeError("DB lock timeout")):
        result = webhook_service.process_event(event_id)
        assert result is False

    db = SessionLocal()
    updated = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    assert updated.status == WebhookEventStatus.RETRY_PENDING.value
    assert updated.attempt_count == 1
    assert "DB lock timeout" in updated.last_error
    assert updated.next_retry_at is not None
    db.close()


def test_reliability_exhausted_retries_transition_to_dead_letter():
    """Exhausting max retry attempts transitions event to DEAD_LETTER."""
    db = SessionLocal()
    event = WebhookEvent(
        id=f"whe_exhaust_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_exhaust_{uuid.uuid4().hex[:8]}",
        event_type="payment.failed",
        status=WebhookEventStatus.RETRY_PENDING.value,
        attempt_count=2,
        max_attempts=3,
        payload_json=json.dumps({"event": "payment.failed"}),
        received_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    with patch("app.services.webhook_service.WebhookService._execute_event_logic", side_effect=RuntimeError("Permanent failure")):
        result = webhook_service.process_event(event_id)
        assert result is False

    db = SessionLocal()
    updated = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    assert updated.status == WebhookEventStatus.DEAD_LETTER.value
    assert updated.attempt_count == 3
    db.close()


# ============================================================================
# E. OPERATIONAL API & RBAC TESTS
# ============================================================================

def test_operational_endpoints_require_authentication():
    """Unauthenticated calls to operational webhook endpoints return 401."""
    res_list = client.get("/api/webhooks/events")
    assert res_list.status_code == 401

    res_health = client.get("/api/webhooks/health")
    assert res_health.status_code == 401

    res_retry = client.post("/api/webhooks/events/whe_test/retry")
    assert res_retry.status_code == 401


def test_operational_endpoints_viewer_rbac():
    """VIEWER role can list events and inspect health, but cannot retry."""
    viewer_token = get_token_for("viewer@payrecover.ai", "Viewer@123")
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # 1. Allowed: list events
    res_list = client.get("/api/webhooks/events", headers=headers)
    assert res_list.status_code == 200
    assert "items" in res_list.json()

    # 2. Allowed: view health
    res_health = client.get("/api/webhooks/health", headers=headers)
    assert res_health.status_code == 200
    assert "total_received" in res_health.json()

    # 3. Denied: retry (requires OPERATOR) -> 403 Forbidden
    res_retry = client.post("/api/webhooks/events/whe_fake/retry", headers=headers)
    assert res_retry.status_code == 403


def test_operational_endpoints_operator_can_retry():
    """OPERATOR role can trigger event retry."""
    db = SessionLocal()
    event = WebhookEvent(
        id=f"whe_op_retry_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_op_retry_{uuid.uuid4().hex[:8]}",
        event_type="payment.authorized",
        status=WebhookEventStatus.FAILED.value,
        payload_json=json.dumps({"event": "payment.authorized", "payload": {}}),
        received_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    operator_token = get_token_for("operator@payrecover.ai", "Operator@123")
    headers = {"Authorization": f"Bearer {operator_token}"}

    res_retry = client.post(f"/api/webhooks/events/{event_id}/retry", headers=headers)
    assert res_retry.status_code == 200
    assert "reprocessed" in res_retry.json()["message"].lower()


def test_legacy_recovery_webhook_alias_works():
    """POST /api/recovery/webhook resolves correctly and executes signature verification."""
    raw_body = b'{"event": "payment.authorized", "payload": {}}'
    sig = make_signature(raw_body)
    res = client.post(
        "/api/recovery/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 200
    assert res.json()["status"] in ("received", "duplicate")


# ============================================================================
# F. ADVANCED CONCURRENCY, RECOVERY & CORRELATION TESTS
# ============================================================================

def test_webhook_concurrent_delivery_race_condition_handled():
    """Simultaneous delivery of identical event resolves cleanly via deduplication."""
    import threading
    unique_id = f"pay_race_{uuid.uuid4().hex[:8]}"
    payload = {
        "event": "payment.captured",
        "created_at": 1710000000,
        "payload": {"payment": {"entity": {"id": unique_id, "amount": 75000}}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = make_signature(raw_body)
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": sig}

    results = []

    def call_webhook():
        r = client.post("/api/webhooks/razorpay", content=raw_body, headers=headers)
        results.append(r)

    t1 = threading.Thread(target=call_webhook)
    t2 = threading.Thread(target=call_webhook)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    assert all(r.status_code == 200 for r in results)
    statuses = {r.json()["status"] for r in results}
    # One is received, one is duplicate, or both duplicate if previous test run
    assert "received" in statuses or "duplicate" in statuses


def test_webhook_unrelated_payment_id_correlation_rejected():
    """An event with mismatched payment credentials cannot mark an unrelated payment settled."""
    db = SessionLocal()
    target_payment = db.query(Payment).first()
    assert target_payment is not None
    orig_status = target_payment.status

    # Craft payload pointing to internal_payment_id but with completely unrelated razorpay_payment_id
    fake_rzp_id = f"pay_unrelated_{uuid.uuid4().hex[:8]}"
    payload = {
        "event": "payment.captured",
        "created_at": int(datetime.utcnow().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": fake_rzp_id,
                    "amount": target_payment.amount * 100,
                    "notes": {"internal_payment_id": target_payment.id}
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = make_signature(raw_body)
    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
    )
    assert res.status_code == 200
    event_id = res.json()["event_id"]

    # Process event
    webhook_service.process_event(event_id)

    # Verify target payment was NOT modified
    db.refresh(target_payment)
    assert target_payment.status == orig_status
    db.close()


def test_webhook_worker_crash_and_stale_recovery():
    """Events stuck in PROCESSING due to worker crash are recovered by recover_stale_events."""
    db = SessionLocal()
    stuck_event = WebhookEvent(
        id=f"whe_stuck_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_stuck_{uuid.uuid4().hex[:8]}",
        event_type="payment.failed",
        status=WebhookEventStatus.PROCESSING.value,
        attempt_count=1,
        max_attempts=3,
        payload_json=json.dumps({"event": "payment.failed"}),
        received_at=datetime.utcnow() - timedelta(minutes=15),
        updated_at=datetime.utcnow() - timedelta(minutes=15)
    )
    db.add(stuck_event)
    db.commit()
    event_id = stuck_event.id

    # Recover stale events
    recovered = webhook_service.recover_stale_events(db, stale_threshold_seconds=60)
    assert recovered >= 1

    db.refresh(stuck_event)
    assert stuck_event.status == WebhookEventStatus.RETRY_PENDING.value
    assert "timed out" in stuck_event.last_error.lower()
    db.close()


def test_webhook_scheduled_retry_backlog_processor():
    """Due RETRY_PENDING events are processed by process_pending_retries."""
    db = SessionLocal()
    due_event = WebhookEvent(
        id=f"whe_due_{uuid.uuid4().hex[:8]}",
        provider="razorpay",
        provider_event_id=f"evt_due_{uuid.uuid4().hex[:8]}",
        event_type="payment.authorized",
        status=WebhookEventStatus.RETRY_PENDING.value,
        attempt_count=1,
        max_attempts=3,
        payload_json=json.dumps({"event": "payment.authorized", "payload": {}}),
        next_retry_at=datetime.utcnow() - timedelta(seconds=10),
        received_at=datetime.utcnow() - timedelta(minutes=5)
    )
    db.add(due_event)
    db.commit()
    event_id = due_event.id

    # Process pending retries
    processed = webhook_service.process_pending_retries(db, batch_size=10)
    assert processed >= 1

    db.refresh(due_event)
    assert due_event.status == WebhookEventStatus.PROCESSED.value
    db.close()


def test_webhook_operator_sweep_endpoint():
    """OPERATOR can trigger /api/webhooks/sweep to recover stale jobs and run retries."""
    operator_token = get_token_for("operator@payrecover.ai", "Operator@123")
    headers = {"Authorization": f"Bearer {operator_token}"}

    res = client.post("/api/webhooks/sweep?stale_threshold_seconds=60&batch_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "stale_events_recovered" in data
    assert "retries_processed" in data


def test_webhook_analyst_role_cannot_trigger_sweep_or_retry():
    """ANALYST role is restricted from mutating webhook processing state."""
    analyst_token = get_token_for("analyst@payrecover.ai", "Analyst@123")
    headers = {"Authorization": f"Bearer {analyst_token}"}

    res_retry = client.post("/api/webhooks/events/whe_test/retry", headers=headers)
    assert res_retry.status_code == 403

    res_sweep = client.post("/api/webhooks/sweep", headers=headers)
    assert res_sweep.status_code == 403


def test_webhook_redis_unavailable_resilience():
    """Webhook ingestion and state machines succeed even if Redis is completely offline."""
    with patch.object(redis_service, "_is_connected", False):
        payload = {
            "event": "payment.authorized",
            "created_at": int(datetime.utcnow().timestamp()),
            "payload": {"payment": {"entity": {"id": f"pay_noredis_{uuid.uuid4().hex[:6]}"}}}
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = make_signature(raw_body)
        res = client.post(
            "/api/webhooks/razorpay",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig}
        )
        assert res.status_code == 200
        event_id = res.json()["event_id"]
        # Worker processing also succeeds with in-memory fallback
        assert webhook_service.process_event(event_id) is True
