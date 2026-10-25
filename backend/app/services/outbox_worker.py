import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.entities import WebhookEvent, WebhookEventStatus
from app.services.webhook_service import webhook_service
from app.core.metrics import metrics

logger = logging.getLogger("payrecover.outbox.worker")


class OutboxWorker:
    """
    Continuous, resilient background worker for webhook event outbox processing.
    Executes atomic claiming, bounded retries with exponential backoff & jitter,
    crash-recovery of stale processing claims, and graceful shutdown draining.
    """

    def __init__(self, poll_interval_seconds: float = 3.0, stale_threshold_seconds: int = 120):
        self.poll_interval_seconds = poll_interval_seconds
        self.stale_threshold_seconds = stale_threshold_seconds
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._last_heartbeat: Optional[datetime] = None
        self._stale_recovered_total: int = 0
        self._retries_processed_total: int = 0
        self._in_flight: bool = False

    @property
    def is_running(self) -> bool:
        return self._running and (self._task is not None and not self._task.done())

    @property
    def last_heartbeat(self) -> Optional[datetime]:
        return self._last_heartbeat

    def is_healthy(self, max_lag_seconds: float = 30.0) -> bool:
        """Determines if worker loop is alive and actively heartbeating."""
        if not self.is_running:
            return False
        if not self._last_heartbeat:
            return False
        lag = (datetime.utcnow() - self._last_heartbeat).total_seconds()
        return lag <= max_lag_seconds

    async def start(self):
        """Starts the background worker loop as an asyncio task."""
        if self._running:
            logger.warning("[OutboxWorker] Worker is already running.")
            return

        self._running = True
        self._last_heartbeat = datetime.utcnow()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[OutboxWorker] Background worker started (poll_interval={self.poll_interval_seconds}s).")

    async def stop(self, drain_timeout: float = 5.0):
        """
        Gracefully stops background processing.
        Waits for any currently in-flight batch to drain within timeout.
        """
        logger.info("[OutboxWorker] Gracefully stopping outbox worker...")
        self._running = False

        if self._task:
            start_drain = datetime.utcnow()
            while self._in_flight and (datetime.utcnow() - start_drain).total_seconds() < drain_timeout:
                await asyncio.sleep(0.1)

            if not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        logger.info("[OutboxWorker] Background worker stopped cleanly.")

    async def _run_loop(self):
        """Main periodic processing loop."""
        while self._running:
            try:
                self._last_heartbeat = datetime.utcnow()
                await self.run_single_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[OutboxWorker] Unhandled error in background loop: {e}", exc_info=True)
                metrics.increment_counter("payrecover_dependency_errors_total", labels={"dependency": "outbox_worker"})

            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_single_cycle(self) -> Dict[str, int]:
        """
        Executes one batch cycle:
        1. Recovers stale processing locks from crashed workers.
        2. Processes scheduled RETRY_PENDING events whose backoff expired.
        3. Records queue depth and age metrics.
        """
        self._in_flight = True
        db: Session = SessionLocal()
        try:
            # 1. Recover stale processing claims (crashed worker detection)
            recovered = webhook_service.recover_stale_events(db, stale_threshold_seconds=self.stale_threshold_seconds)
            if recovered > 0:
                self._stale_recovered_total += recovered
                metrics.increment_counter("payrecover_outbox_stale_claims_recovered_total", value=float(recovered))
                logger.warning(f"[OutboxWorker] Reclaimed {recovered} stale processing events.")

            # 2. Process due retries
            retried = webhook_service.process_pending_retries(db, batch_size=10)
            if retried > 0:
                self._retries_processed_total += retried

            # 3. Collect gauge telemetry
            pending_count = db.query(WebhookEvent).filter(
                WebhookEvent.status.in_([
                    WebhookEventStatus.RECEIVED.value,
                    WebhookEventStatus.PROCESSING.value,
                    WebhookEventStatus.RETRY_PENDING.value
                ])
            ).count()
            dead_letter_count = db.query(WebhookEvent).filter(
                WebhookEvent.status == WebhookEventStatus.DEAD_LETTER.value
            ).count()

            oldest_pending = db.query(WebhookEvent.received_at).filter(
                WebhookEvent.status.in_([
                    WebhookEventStatus.RECEIVED.value,
                    WebhookEventStatus.RETRY_PENDING.value
                ])
            ).order_by(WebhookEvent.received_at.asc()).first()

            oldest_age_s = 0.0
            if oldest_pending and oldest_pending[0]:
                oldest_age_s = max(0.0, (datetime.utcnow() - oldest_pending[0]).total_seconds())

            metrics.set_gauge("payrecover_outbox_events_pending", float(pending_count))
            metrics.set_gauge("payrecover_outbox_oldest_pending_age_seconds", oldest_age_s)

            return {
                "recovered_stale": recovered,
                "retries_processed": retried,
                "pending_count": pending_count,
                "dead_letter_count": dead_letter_count
            }
        finally:
            db.close()
            self._in_flight = False

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive operational status for health endpoints and dashboards."""
        db: Session = SessionLocal()
        try:
            total_received = db.query(WebhookEvent).count()
            total_processed = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.PROCESSED.value).count()
            total_pending = db.query(WebhookEvent).filter(
                WebhookEvent.status.in_([
                    WebhookEventStatus.RECEIVED.value,
                    WebhookEventStatus.PROCESSING.value,
                    WebhookEventStatus.RETRY_PENDING.value
                ])
            ).count()
            total_failed = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.FAILED.value).count()
            total_dead_letter = db.query(WebhookEvent).filter(WebhookEvent.status == WebhookEventStatus.DEAD_LETTER.value).count()

            oldest_pending = db.query(WebhookEvent.received_at).filter(
                WebhookEvent.status.in_([
                    WebhookEventStatus.RECEIVED.value,
                    WebhookEventStatus.RETRY_PENDING.value
                ])
            ).order_by(WebhookEvent.received_at.asc()).first()

            oldest_age_s = 0.0
            if oldest_pending and oldest_pending[0]:
                oldest_age_s = round(max(0.0, (datetime.utcnow() - oldest_pending[0]).total_seconds()), 1)

            return {
                "running": self.is_running,
                "healthy": self.is_healthy() if self.is_running else True,
                "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
                "poll_interval_seconds": self.poll_interval_seconds,
                "stale_threshold_seconds": self.stale_threshold_seconds,
                "stale_claims_recovered": self._stale_recovered_total,
                "retries_processed": self._retries_processed_total,
                "queue": {
                    "total_received": total_received,
                    "total_processed": total_processed,
                    "total_pending": total_pending,
                    "total_failed": total_failed,
                    "total_dead_letter": total_dead_letter,
                    "oldest_pending_age_seconds": oldest_age_s
                }
            }
        finally:
            db.close()


outbox_worker = OutboxWorker()
