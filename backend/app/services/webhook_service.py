import json
import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import (
    WebhookEvent,
    WebhookEventStatus,
    Payment,
    RecoveryCase,
    PaymentStatus,
    RecoveryStatus,
    AgentAction,
    AgentType,
    ActionType,
    ActionStatus
)
from app.core.webhook_verifier import webhook_verifier
from app.services.payment_state_machine import payment_state_machine
from app.services.event_service import event_service
from app.services.redis_service import redis_service
from app.integrations.razorpay_client import RazorpayClientWrapper
from app.agents.orchestrator import RecoveryOrchestrator

logger = logging.getLogger("payrecover.webhook.service")


class WebhookService:
    """
    Durable, transactional webhook event ingestion and reliable background processing.
    Implements outbox deduplication, atomic worker claiming, bounded retries with
    exponential backoff and jitter, dead-letter queuing, and safe idempotency.
    """

    @classmethod
    def generate_dedup_id(cls, event_type: str, payload_data: Dict[str, Any], event_id_header: Optional[str] = None) -> str:
        """Derive a deterministic provider event identifier for deduplication."""
        if event_id_header and event_id_header.strip():
            return event_id_header.strip()

        # Check for top-level id in event
        if "id" in payload_data and payload_data["id"]:
            return str(payload_data["id"])

        # Extract entity id and timestamp
        payload = payload_data.get("payload", {})
        entity_id = "unknown"
        if isinstance(payload, dict):
            for key in ["payment", "payment_link", "order"]:
                if key in payload and isinstance(payload[key], dict) and "entity" in payload[key]:
                    entity_dict = payload[key]["entity"]
                    if isinstance(entity_dict, dict):
                        entity_id = entity_dict.get("id", entity_id)
                        break

        created_at = payload_data.get("created_at", int(datetime.utcnow().timestamp()))
        return f"{event_type}:{entity_id}:{created_at}"

    @classmethod
    def ingest_event(
        cls,
        db: Session,
        raw_body: bytes,
        event_data: Dict[str, Any],
        signature_header: Optional[str],
        correlation_id: Optional[str] = None,
        event_id_header: Optional[str] = None
    ) -> Tuple[WebhookEvent, bool]:
        """
        Atomically persist a verified webhook event into PostgreSQL/SQLite before acknowledgment.
        Protects against concurrent delivery races using database unique constraints.
        Returns: (WebhookEvent, is_duplicate)
        """
        event_type = event_data.get("event", "unknown")
        provider_event_id = cls.generate_dedup_id(event_type, event_data, event_id_header)

        # 1. Deduplication check in DB
        existing = db.query(WebhookEvent).filter(WebhookEvent.provider_event_id == provider_event_id).first()
        if existing:
            logger.info(f"[WebhookIngest] Duplicate event detected for provider_event_id='{provider_event_id}' (status: {existing.status}).")
            return existing, True

        # Extract target entity identifier
        payload = event_data.get("payload", {})
        entity_id = None
        if isinstance(payload, dict):
            for key in ["payment", "payment_link", "order"]:
                if key in payload and isinstance(payload[key], dict) and "entity" in payload[key]:
                    entity_dict = payload[key]["entity"]
                    if isinstance(entity_dict, dict):
                        entity_id = entity_dict.get("id")
                        if entity_id:
                            break

        # Sanitize metadata for storage
        sanitized_payload = webhook_verifier.sanitize_payload(event_data)

        # 2. Persist new event record
        event_record = WebhookEvent(
            id=f"whe_{uuid.uuid4().hex[:12]}",
            provider="razorpay",
            provider_event_id=provider_event_id,
            event_type=event_type,
            status=WebhookEventStatus.RECEIVED.value,
            entity_id=entity_id,
            payload_json=json.dumps(event_data),
            attempt_count=0,
            max_attempts=5,
            next_retry_at=datetime.utcnow(),
            correlation_id=correlation_id,
            processing_metadata_json=json.dumps({"sanitized": sanitized_payload}),
            received_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        try:
            db.add(event_record)
            db.commit()
            db.refresh(event_record)
            logger.info(f"[WebhookIngest] Durably recorded event {event_record.id} ({event_type}) for entity {entity_id}.")
            return event_record, False
        except IntegrityError:
            db.rollback()
            existing = db.query(WebhookEvent).filter(WebhookEvent.provider_event_id == provider_event_id).first()
            if existing:
                logger.info(f"[WebhookIngest] Concurrent delivery resolved via deduplication: {provider_event_id}")
                return existing, True
            raise

    @classmethod
    def process_event(cls, event_id: str) -> bool:
        """
        Worker task to process a single webhook event with atomic status transition locking.
        Prevents concurrent workers from executing the same event simultaneously.
        Can run asynchronously in background or via worker queue.
        """
        db = SessionLocal()
        try:
            # 1. Atomic claim: Only transition if in RECEIVED or RETRY_PENDING
            rows_updated = db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id,
                WebhookEvent.status.in_([
                    WebhookEventStatus.RECEIVED.value,
                    WebhookEventStatus.RETRY_PENDING.value
                ])
            ).update({
                WebhookEvent.status: WebhookEventStatus.PROCESSING.value,
                WebhookEvent.attempt_count: WebhookEvent.attempt_count + 1,
                WebhookEvent.updated_at: datetime.utcnow()
            }, synchronize_session=False)
            db.commit()

            if rows_updated == 0:
                current = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                if current and current.status == WebhookEventStatus.PROCESSED.value:
                    logger.info(f"[WebhookWorker] Event {event_id} is already PROCESSED. Skipping duplicate execution.")
                    return True
                logger.info(f"[WebhookWorker] Event {event_id} could not be claimed (status: {current.status if current else 'missing'}). Skipping.")
                return False

            # Refresh entity
            event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
            if not event:
                return False

            # 2. Execute event business logic
            cls._execute_event_logic(db, event)

            # 3. Mark as PROCESSED
            event.status = WebhookEventStatus.PROCESSED.value
            event.processed_at = datetime.utcnow()
            event.last_error = None
            event.updated_at = datetime.utcnow()
            db.commit()

            logger.info(f"[WebhookWorker] Successfully processed event {event.id} ({event.event_type}).")
            return True

        except Exception as e:
            logger.exception(f"[WebhookWorker] Error processing event {event_id}: {e}")
            db.rollback()

            # Re-fetch event to update error and retry metadata
            event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
            if event:
                event.last_error = str(e)[:500]
                if event.attempt_count >= event.max_attempts:
                    event.status = WebhookEventStatus.DEAD_LETTER.value
                    logger.error(f"[WebhookWorker] Event {event_id} exhausted max retries ({event.max_attempts}). Moved to DEAD_LETTER.")
                else:
                    event.status = WebhookEventStatus.RETRY_PENDING.value
                    backoff = min(3600, (2 ** event.attempt_count) * 2 + random.uniform(0, 1))
                    event.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
                    logger.warning(f"[WebhookWorker] Event {event_id} scheduled for retry at {event.next_retry_at}.")
                event.updated_at = datetime.utcnow()
                db.commit()
            return False
        finally:
            db.close()

    @classmethod
    def _execute_event_logic(cls, db: Session, event: WebhookEvent) -> None:
        """Dispatch event payload to domain handlers."""
        data = json.loads(event.payload_json)
        event_type = event.event_type
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            logger.warning(f"[WebhookWorker] Event {event.id} payload is not a dictionary. Skipping.")
            return

        if event_type == "payment.failed":
            cls._handle_payment_failed(db, event, payload.get("payment", {}).get("entity", {}))
        elif event_type in ("payment.captured", "payment.authorized"):
            cls._handle_payment_settled(db, event, payload.get("payment", {}).get("entity", {}))
        elif event_type == "payment_link.paid":
            cls._handle_payment_link_paid(db, event, payload)
        elif event_type == "payment_link.expired":
            cls._handle_payment_link_expired(db, event, payload)
        else:
            logger.info(f"[WebhookWorker] Handled non-actionable or unknown event type: {event_type}")

    @classmethod
    def _handle_payment_failed(cls, db: Session, event: WebhookEvent, payment_entity: Dict[str, Any]) -> None:
        """Handle payment.failed event: validate transition, resolve case, trigger recovery."""
        if not isinstance(payment_entity, dict):
            return
        rzp_id = payment_entity.get("id")
        if not rzp_id:
            logger.warning("[WebhookHandler] payment.failed event missing payment id.")
            return

        notes = payment_entity.get("notes", {})
        internal_payment_id = notes.get("internal_payment_id") if isinstance(notes, dict) else None

        # Resolve Payment
        payment = None
        if internal_payment_id:
            payment = db.query(Payment).filter(Payment.id == internal_payment_id).first()
            # Correlation check: verify payment matches razorpay_payment_id
            if payment and payment.razorpay_payment_id and payment.razorpay_payment_id != rzp_id:
                logger.warning(
                    f"[WebhookHandler] Correlation mismatch: Webhook rzp_id='{rzp_id}' differs from internal payment "
                    f"'{payment.id}' razorpay_payment_id='{payment.razorpay_payment_id}'. Refusing arbitrary failure."
                )
                return

        if not payment:
            payment = db.query(Payment).filter(Payment.razorpay_payment_id == rzp_id).first()

        failure_reason = payment_entity.get("error_description") or payment_entity.get("error_reason") or "Payment declined"

        if payment:
            event.internal_payment_id = payment.id
            if payment.recovery_case:
                event.internal_case_id = payment.recovery_case.id

            # Apply state transition
            success, msg = payment_state_machine.transition_payment(
                db=db,
                payment=payment,
                target_status=PaymentStatus.FAILED.value,
                failure_reason=failure_reason,
                source_event=event.id
            )
            if not success:
                logger.info(f"[WebhookHandler] payment.failed transition rejected for {payment.id}: {msg}")
                return

            case = payment.recovery_case
            if not case:
                case = RecoveryCase(
                    id=f"rc_wh_{uuid.uuid4().hex[:8]}",
                    payment_id=payment.id,
                    status=RecoveryStatus.IDENTIFIED.value,
                    recovery_score=0.0,
                    recovery_probability=0.0,
                    started_at=datetime.utcnow()
                )
                db.add(case)
                db.commit()
                db.refresh(case)
                event.internal_case_id = case.id

            # Broadcast SSE event
            event_service.broadcast_sync(
                event_type="PAYMENT_FAILED",
                message=f"Payment #{payment.razorpay_payment_id} failed: {failure_reason}",
                case_id=case.id,
                payment_id=payment.id,
                amount=payment.amount,
                correlation_id=event.correlation_id
            )

            # Trigger autonomous recovery pipeline asynchronously if eligible
            if case.status in (RecoveryStatus.IDENTIFIED.value, RecoveryStatus.INVESTIGATING.value):
                try:
                    RecoveryOrchestrator.run_autonomous_recovery(db, case.id)
                except Exception as auto_err:
                    logger.warning(f"[WebhookHandler] Autonomous recovery pipeline encountered error: {auto_err}")

    @classmethod
    def _handle_payment_settled(cls, db: Session, event: WebhookEvent, payment_entity: Dict[str, Any]) -> None:
        """Handle payment.captured or payment.authorized: confirm revenue recovery."""
        if not isinstance(payment_entity, dict):
            return
        rzp_id = payment_entity.get("id")
        if not rzp_id:
            return

        notes = payment_entity.get("notes", {})
        internal_payment_id = notes.get("internal_payment_id") if isinstance(notes, dict) else None

        payment = None
        if internal_payment_id:
            payment = db.query(Payment).filter(Payment.id == internal_payment_id).first()
            # Correlation check: verify payment matches razorpay_payment_id
            if payment and payment.razorpay_payment_id and payment.razorpay_payment_id != rzp_id:
                logger.warning(
                    f"[WebhookHandler] Correlation mismatch: Webhook rzp_id='{rzp_id}' differs from internal payment "
                    f"'{payment.id}' razorpay_payment_id='{payment.razorpay_payment_id}'. Refusing arbitrary settlement."
                )
                return

        if not payment:
            payment = db.query(Payment).filter(Payment.razorpay_payment_id == rzp_id).first()

        if payment:
            event.internal_payment_id = payment.id
            if payment.recovery_case:
                event.internal_case_id = payment.recovery_case.id

            # Apply state transition
            target_status = PaymentStatus.RECOVERED.value if payment.status == PaymentStatus.FAILED.value else PaymentStatus.SUCCESS.value
            success, msg = payment_state_machine.transition_payment(
                db=db,
                payment=payment,
                target_status=target_status,
                source_event=event.id
            )

            if success and payment.recovery_case:
                action = AgentAction(
                    id=f"act_{uuid.uuid4().hex[:8]}",
                    recovery_case_id=payment.recovery_case.id,
                    agent_type=AgentType.TOOL_EXECUTOR.value,
                    action_type=ActionType.PAYMENT_CONFIRMED.value,
                    reasoning_summary=f"Razorpay Webhook: Verified payment capture for #{payment.razorpay_payment_id}. Revenue settled.",
                    status=ActionStatus.EXECUTED.value,
                    created_at=datetime.utcnow()
                )
                db.add(action)
                db.commit()

                # Broadcast recovery event
                event_service.broadcast_sync(
                    event_type="PAYMENT_RECOVERED",
                    message=f"Payment #{payment.razorpay_payment_id} recovered: ₹{payment.amount:,.2f} verified captured.",
                    case_id=payment.recovery_case.id,
                    payment_id=payment.id,
                    amount=payment.amount,
                    correlation_id=event.correlation_id
                )

                # Clear dashboard cache
                redis_service.delete("dashboard:metrics")

                # Phase 4: Record verified recovery outcome
                try:
                    from app.services.intelligence_service import outcome_service
                    outcome_service.record_verified_outcome(
                        db=db,
                        recovery_case_id=payment.recovery_case.id,
                        verification_source=f"razorpay_webhook:{event.provider_event_id or event.id}",
                        outcome_time=datetime.utcnow()
                    )
                except Exception as out_err:
                    logger.warning(f"[WebhookHandler] Error updating outcome record: {out_err}")

    @classmethod
    def _handle_payment_link_paid(cls, db: Session, event: WebhookEvent, payload: Dict[str, Any]) -> None:
        """Handle payment_link.paid: autonomous resolution via customer payment link."""
        link_entity = payload.get("payment_link", {}).get("entity", {})
        if not isinstance(link_entity, dict):
            return

        notes = link_entity.get("notes", {})
        case_id = link_entity.get("reference_id") or (notes.get("case_id") if isinstance(notes, dict) else None)
        internal_payment_id = notes.get("internal_payment_id") if isinstance(notes, dict) else None

        case = None
        if case_id:
            case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case and internal_payment_id:
            payment = db.query(Payment).filter(Payment.id == internal_payment_id).first()
            if payment:
                case = payment.recovery_case

        if case:
            event.internal_case_id = case.id
            event.internal_payment_id = case.payment_id

            payment = case.payment
            if payment:
                payment_state_machine.transition_payment(
                    db=db,
                    payment=payment,
                    target_status=PaymentStatus.RECOVERED.value,
                    source_event=event.id
                )

                action = AgentAction(
                    id=f"act_{uuid.uuid4().hex[:8]}",
                    recovery_case_id=case.id,
                    agent_type=AgentType.TOOL_EXECUTOR.value,
                    action_type=ActionType.PAYMENT_CONFIRMED.value,
                    reasoning_summary=f"Payment Link Completed: Customer completed fallback link {link_entity.get('id', '')}. Revenue recovered.",
                    status=ActionStatus.EXECUTED.value,
                    created_at=datetime.utcnow()
                )
                db.add(action)
                db.commit()

                event_service.broadcast_sync(
                    event_type="PAYMENT_RECOVERED",
                    message=f"Payment link paid: ₹{payment.amount:,.2f} recovered for case {case.id}",
                    case_id=case.id,
                    payment_id=payment.id,
                    amount=payment.amount,
                    correlation_id=event.correlation_id
                )
                redis_service.delete("dashboard:metrics")

                # Phase 4: Record verified recovery outcome
                try:
                    from app.services.intelligence_service import outcome_service
                    outcome_service.record_verified_outcome(
                        db=db,
                        recovery_case_id=case.id,
                        verification_source=f"razorpay_payment_link:{link_entity.get('id', 'unknown')}",
                        outcome_time=datetime.utcnow()
                    )
                except Exception as out_err:
                    logger.warning(f"[WebhookHandler] Error updating outcome record for link paid: {out_err}")

    @classmethod
    def _handle_payment_link_expired(cls, db: Session, event: WebhookEvent, payload: Dict[str, Any]) -> None:
        """Handle payment_link.expired."""
        link_entity = payload.get("payment_link", {}).get("entity", {})
        if not isinstance(link_entity, dict):
            return
        notes = link_entity.get("notes", {})
        case_id = link_entity.get("reference_id") or (notes.get("case_id") if isinstance(notes, dict) else None)
        if case_id:
            case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
            if case and case.status not in (RecoveryStatus.RECOVERED.value, RecoveryStatus.FAILED.value):
                case.status = RecoveryStatus.EXPIRED.value
                db.commit()

                # Phase 4: Record unsuccessful recovery outcome on expiration
                try:
                    from app.services.intelligence_service import outcome_service
                    outcome_service.record_verified_outcome(
                        db=db,
                        recovery_case_id=case.id,
                        verification_source=f"razorpay_payment_link_expired:{link_entity.get('id', 'unknown')}",
                        outcome_time=datetime.utcnow()
                    )
                except Exception as out_err:
                    logger.warning(f"[WebhookHandler] Error updating outcome record for expired link: {out_err}")
                event.internal_case_id = case.id

    @classmethod
    def reprocess_event(cls, db: Session, event_id: str) -> Tuple[bool, str]:
        """Safely reprocess a failed or dead-letter event upon operator request."""
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            return False, "Webhook event not found"

        if event.status not in (WebhookEventStatus.FAILED.value, WebhookEventStatus.DEAD_LETTER.value, WebhookEventStatus.RETRY_PENDING.value):
            return False, f"Event in state '{event.status}' is not eligible for reprocessing."

        event.status = WebhookEventStatus.RETRY_PENDING.value
        event.next_retry_at = datetime.utcnow()
        event.updated_at = datetime.utcnow()
        db.commit()

        # Run processing
        success = cls.process_event(event.id)
        if success:
            return True, "Event reprocessed successfully."
        return False, "Reprocessing attempt failed. See event error log."

    @classmethod
    def recover_stale_events(cls, db: Session, stale_threshold_seconds: int = 300) -> int:
        """
        Recover events that have been in 'PROCESSING' state longer than threshold
        (e.g., worker crashed or process interrupted).
        Resets them to 'RETRY_PENDING' or 'DEAD_LETTER'.
        """
        threshold_time = datetime.utcnow() - timedelta(seconds=stale_threshold_seconds)
        stale_events = db.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.PROCESSING.value,
            WebhookEvent.updated_at < threshold_time
        ).all()

        recovered_count = 0
        for event in stale_events:
            logger.warning(f"[WebhookWorker] Recovering stale event {event.id} stuck in PROCESSING since {event.updated_at}")
            if event.attempt_count >= event.max_attempts:
                event.status = WebhookEventStatus.DEAD_LETTER.value
                event.last_error = f"Worker crashed/timed out; max attempts ({event.max_attempts}) reached"
            else:
                event.status = WebhookEventStatus.RETRY_PENDING.value
                event.last_error = "Worker execution timed out or interrupted; queued for retry"
                event.next_retry_at = datetime.utcnow()
            event.updated_at = datetime.utcnow()
            recovered_count += 1

        if recovered_count > 0:
            db.commit()
        return recovered_count

    @classmethod
    def process_pending_retries(cls, db: Session, batch_size: int = 10) -> int:
        """
        Find events in RETRY_PENDING whose next_retry_at <= now() and execute them.
        """
        now = datetime.utcnow()
        due_events = db.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.RETRY_PENDING.value,
            WebhookEvent.next_retry_at <= now
        ).order_by(WebhookEvent.next_retry_at.asc()).limit(batch_size).all()

        processed_count = 0
        for event in due_events:
            logger.info(f"[WebhookWorker] Executing scheduled retry for event {event.id} (attempt {event.attempt_count}/{event.max_attempts})")
            success = cls.process_event(event.id)
            if success:
                processed_count += 1
        return processed_count


webhook_service = WebhookService()
