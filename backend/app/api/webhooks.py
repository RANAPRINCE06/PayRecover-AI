import json
import logging
from typing import Optional, List
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.entities import WebhookEvent, WebhookEventStatus, User
from app.core.rbac import require_viewer, require_operator
from app.core.config import settings
from app.core.webhook_verifier import webhook_verifier
from app.services.webhook_service import webhook_service
from app.schemas.contracts import (
    WebhookEventResponse,
    WebhookEventListResponse,
    WebhookHealthResponse
)

logger = logging.getLogger("payrecover.api.webhooks")
router = APIRouter(tags=["Webhooks"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Razorpay Ingestion Endpoints (Signature-Verified Public Webhooks)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def receive_razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Ingest, verify, and durably enqueue incoming Razorpay payment lifecycle events.
    Verifies HMAC-SHA256 signature against the exact raw request body.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Razorpay-Signature")
    event_id_header = request.headers.get("X-Razorpay-Event-Id")
    correlation_id = getattr(request.state, "correlation_id", None)

    # 1. Cryptographic HMAC Signature Verification
    if not webhook_verifier.verify_signature(raw_body, signature_header):
        logger.warning(f"[{correlation_id}] Rejected webhook request: invalid or missing HMAC-SHA256 signature.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature."
        )

    # 2. Parse and validate JSON structure
    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.warning(f"[{correlation_id}] Malformed webhook payload JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload."
        )

    if not isinstance(event_data, dict) or "event" not in event_data or not isinstance(event_data["event"], str):
        logger.warning(f"[{correlation_id}] Missing required 'event' field in webhook payload.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'event' field."
        )

    # 3. Durable PostgreSQL Ingestion & Deduplication
    event_record, is_duplicate = webhook_service.ingest_event(
        db=db,
        raw_body=raw_body,
        event_data=event_data,
        signature_header=signature_header,
        correlation_id=correlation_id,
        event_id_header=event_id_header
    )

    # 4. Asynchronous worker execution (avoid blocking webhook HTTP response)
    if not is_duplicate:
        background_tasks.add_task(webhook_service.process_event, event_record.id)

    return {
        "status": "duplicate" if is_duplicate else "received",
        "event_id": event_record.id,
        "provider_event_id": event_record.provider_event_id,
        "event": event_record.event_type
    }


@router.post("/recovery/webhook", status_code=status.HTTP_200_OK)
async def legacy_recovery_webhook_alias(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Alias for backwards compatibility with existing UI settings reference."""
    return await receive_razorpay_webhook(request, background_tasks, db)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Operational & Inspection Endpoints (Protected by RBAC)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=WebhookEventListResponse)
def list_webhook_events(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    event_type: Optional[str] = Query(default=None),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """
    List paginated webhook events with optional filtering by status and event type.
    Requires VIEWER or higher permission.
    """
    query = db.query(WebhookEvent)

    if status_filter:
        query = query.filter(WebhookEvent.status == status_filter.upper())
    if event_type:
        query = query.filter(WebhookEvent.event_type == event_type)

    total = query.count()
    items = query.order_by(desc(WebhookEvent.received_at)).offset((page - 1) * limit).limit(limit).all()

    return WebhookEventListResponse(
        items=[WebhookEventResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=ceil(total / limit) if total > 0 else 1
    )


@router.get("/events/{event_id}")
def get_webhook_event_detail(
    event_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """
    Inspect an individual webhook event with sanitized payload.
    Requires VIEWER or higher permission.
    """
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found.")

    sanitized_payload = {}
    try:
        sanitized_payload = webhook_verifier.sanitize_payload(json.loads(event.payload_json))
    except Exception:
        pass

    resp = WebhookEventResponse.model_validate(event).model_dump()
    resp["sanitized_payload"] = sanitized_payload
    return resp


@router.get("/failed", response_model=List[WebhookEventResponse])
def list_failed_webhook_events(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """
    List events requiring operational attention (FAILED, DEAD_LETTER, RETRY_PENDING).
    Requires VIEWER or higher permission.
    """
    failed_statuses = [
        WebhookEventStatus.FAILED.value,
        WebhookEventStatus.DEAD_LETTER.value,
        WebhookEventStatus.RETRY_PENDING.value
    ]
    items = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.status.in_(failed_statuses))
        .order_by(desc(WebhookEvent.updated_at))
        .limit(limit)
        .all()
    )
    return [WebhookEventResponse.model_validate(i) for i in items]


@router.post("/events/{event_id}/retry")
def retry_webhook_event(
    event_id: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    """
    Safely reprocess an eligible failed or dead-letter event.
    Requires OPERATOR or ADMIN permission.
    """
    success, message = webhook_service.reprocess_event(db, event_id, operator_email=current_user.email)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "event_id": event_id, "operator": current_user.email}


@router.get("/health", response_model=WebhookHealthResponse)
def get_webhook_processing_health(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """
    Retrieve real-time webhook pipeline health metrics.
    Requires VIEWER or higher permission.
    """
    total_received = db.query(WebhookEvent).count()
    total_processed = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.PROCESSED.value).count()
    total_pending = db.query(WebhookEvent).filter(WebhookEvent.status.in_([WebhookEventStatus.RECEIVED.value, WebhookEventStatus.PROCESSING.value, WebhookEventStatus.RETRY_PENDING.value])).count()
    total_failed = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.FAILED.value).count()
    total_dead_letter = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.DEAD_LETTER.value).count()

    is_degraded = (total_dead_letter > 0 or total_failed > 5)
    secret_configured = bool(getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None))

    return WebhookHealthResponse(
        status="degraded" if is_degraded else "healthy",
        total_received=total_received,
        total_processed=total_processed,
        total_pending=total_pending,
        total_failed=total_failed,
        total_dead_letter=total_dead_letter,
        secret_configured=secret_configured,
        mode="test" if not settings.USE_MOCK_PAYMENTS else "mock/test"
    )


@router.post("/sweep")
def sweep_pending_and_stale_webhooks(
    stale_threshold_seconds: int = Query(default=300, ge=30, le=3600),
    batch_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    """
    Operator action to sweep and recover stale events from crashed workers
    and trigger batch processing of due RETRY_PENDING events.
    Requires OPERATOR or ADMIN permission.
    """
    stale_count = webhook_service.recover_stale_events(db, stale_threshold_seconds=stale_threshold_seconds)
    retried_count = webhook_service.process_pending_retries(db, batch_size=batch_size)
    return {
        "status": "success",
        "stale_events_recovered": stale_count,
        "retries_processed": retried_count
    }
