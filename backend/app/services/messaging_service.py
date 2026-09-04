import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import CustomerInteraction, InteractionChannel, InteractionDirection

logger = logging.getLogger("payrecover.messaging")


class MessagingService:
    """
    Simulated Messaging Engine for multi-channel recovery dispatch
    (WhatsApp, SMS, Email, Voice). Records interactions for audit and AI intent analysis.
    """

    @staticmethod
    def send_recovery_message(
        db: Session,
        customer_id: str,
        recovery_case_id: str,
        channel: str,
        message: str,
        detected_intent: Optional[str] = None,
        confidence: float = 0.95
    ) -> CustomerInteraction:
        interaction_id = f"msg_{uuid.uuid4().hex[:10]}"

        interaction = CustomerInteraction(
            id=interaction_id,
            customer_id=customer_id,
            recovery_case_id=recovery_case_id,
            channel=channel,
            direction=InteractionDirection.OUTBOUND.value,
            message=message,
            detected_intent=detected_intent,
            confidence=confidence,
            created_at=datetime.utcnow()
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        logger.info(f"[SIMULATED {channel.upper()}] Dispatched to customer {customer_id}: {message[:60]}...")
        return interaction

    @staticmethod
    def record_inbound_reply(
        db: Session,
        customer_id: str,
        recovery_case_id: str,
        channel: str,
        reply_message: str,
        detected_intent: str,
        confidence: float = 0.92
    ) -> CustomerInteraction:
        interaction_id = f"msg_{uuid.uuid4().hex[:10]}"

        interaction = CustomerInteraction(
            id=interaction_id,
            customer_id=customer_id,
            recovery_case_id=recovery_case_id,
            channel=channel,
            direction=InteractionDirection.INBOUND.value,
            message=reply_message,
            detected_intent=detected_intent,
            confidence=confidence,
            created_at=datetime.utcnow()
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        logger.info(f"[SIMULATED INBOUND {channel.upper()}] Customer {customer_id} replied: '{reply_message}' (Intent: {detected_intent})")
        return interaction


messaging_service = MessagingService()
