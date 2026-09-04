import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import (
    Customer,
    Payment,
    RecoveryCase,
    CustomerInteraction,
    AgentAction,
    AgentType,
    ActionType,
    ActionStatus,
    InteractionDirection
)
from app.schemas.contracts import CustomerIntentResult
from app.services.gemini_service import gemini_service

logger = logging.getLogger("payrecover.intent")


class CustomerIntentAgent:
    """
    AI Customer Intent Agent.
    Gathers customer messages, transaction history, recovery case state,
    and interaction telemetry to classify true customer intent, sentiment,
    urgency, and next recommended actions via Gemini.
    """

    @classmethod
    def build_intent_context(
        cls,
        db: Session,
        customer: Customer,
        message: str,
        channel: str,
        recovery_case: Optional[RecoveryCase] = None,
        payment: Optional[Payment] = None
    ) -> Dict[str, Any]:
        """Construct sanitized intent context without raw payment credentials."""
        # Fetch bounded recent payments
        past_payments = (
            db.query(Payment)
            .filter(Payment.customer_id == customer.id)
            .order_by(desc(Payment.created_at))
            .limit(5)
            .all()
        )

        # Fetch bounded recent customer interactions
        past_interactions = (
            db.query(CustomerInteraction)
            .filter(CustomerInteraction.customer_id == customer.id)
            .order_by(desc(CustomerInteraction.created_at))
            .limit(5)
            .all()
        )

        context = {
            "customer": {
                "customer_id": customer.id,
                "name": customer.name,
                "customer_value": customer.customer_value,
                "preferred_payment_method": customer.preferred_payment_method,
                "successful_payments": customer.total_successful_payments,
                "failed_payments": customer.total_failed_payments
            },
            "payment": {
                "payment_id": payment.id if payment else None,
                "amount": payment.amount if payment else None,
                "currency": payment.currency if payment else "INR",
                "payment_method": payment.payment_method if payment else customer.preferred_payment_method,
                "status": payment.status if payment else None,
                "failure_reason": payment.failure_reason if payment else None
            },
            "recovery": {
                "recovery_case_id": recovery_case.id if recovery_case else None,
                "recovery_score": recovery_case.recovery_score if recovery_case else None,
                "recovery_probability": recovery_case.recovery_probability if recovery_case else None,
                "status": recovery_case.status if recovery_case else None,
                "retry_count": recovery_case.retry_count if recovery_case else 0
            },
            "interaction": {
                "message": message,
                "channel": channel,
                "recent_history": [
                    {
                        "direction": inter.direction,
                        "channel": inter.channel,
                        "message": inter.message,
                        "detected_intent": inter.detected_intent,
                        "confidence": inter.confidence
                    }
                    for inter in past_interactions
                ]
            }
        }
        return context

    @classmethod
    def analyze_intent(
        cls,
        db: Session,
        customer_id: str,
        message: str,
        channel: str = "WHATSAPP",
        recovery_case_id: Optional[str] = None
    ) -> CustomerIntentResult:
        """
        Executes full intent analysis pipeline using Gemini and logs
        interactions and agent actions in the database.
        """
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer with ID '{customer_id}' not found")

        recovery_case = None
        payment = None

        if recovery_case_id:
            recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
            if not recovery_case:
                raise ValueError(f"RecoveryCase with ID '{recovery_case_id}' not found")
            payment = recovery_case.payment
        else:
            # Look up most recent recovery case for customer if not explicitly passed
            payment = (
                db.query(Payment)
                .filter(Payment.customer_id == customer.id)
                .order_by(desc(Payment.created_at))
                .first()
            )
            if payment and payment.recovery_case:
                recovery_case = payment.recovery_case

        context = cls.build_intent_context(
            db=db,
            customer=customer,
            message=message,
            channel=channel,
            recovery_case=recovery_case,
            payment=payment
        )

        # Call Gemini service
        result: CustomerIntentResult = gemini_service.analyze_customer_intent(context)

        # 1. Store CustomerInteraction in DB
        interaction = CustomerInteraction(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            customer_id=customer.id,
            recovery_case_id=recovery_case.id if recovery_case else None,
            channel=channel,
            direction=InteractionDirection.INBOUND.value,
            message=message,
            detected_intent=result.intent,
            confidence=result.confidence,
            created_at=datetime.utcnow()
        )
        db.add(interaction)

        # 2. Update recovery case intent if present
        if recovery_case:
            recovery_case.customer_intent = result.intent

        # 3. Store AgentAction in audit trail if recovery case is available
        if recovery_case:
            action = AgentAction(
                id=f"act_{uuid.uuid4().hex[:8]}",
                recovery_case_id=recovery_case.id,
                agent_type=AgentType.INTENT_AI.value,
                action_type="CUSTOMER_INTENT_ANALYSIS",
                reasoning_summary=(
                    f"Intent AI analyzed inbound {channel} message from {customer.name}: "
                    f"'{message}'. Classified intent as {result.intent} ({int(result.confidence*100)}% conf, {result.sentiment} sentiment). "
                    f"Recommended Action: {result.recommended_action} via {result.recommended_channel}."
                ),
                status=ActionStatus.EXECUTED.value,
                action_metadata=json.dumps({
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "sentiment": result.sentiment,
                    "urgency": result.urgency,
                    "recommended_action": result.recommended_action,
                    "recommended_channel": result.recommended_channel,
                    "evidence": result.evidence
                }),
                created_at=datetime.utcnow()
            )
            db.add(action)

        db.commit()

        logger.info(
            f"Customer Intent classified for {customer.id}: "
            f"Intent={result.intent}, Sentiment={result.sentiment}, Urgency={result.urgency}, Action={result.recommended_action}"
        )

        return result

    @classmethod
    def detect_intent(
        cls,
        message_text: Optional[str] = None,
        failure_context: Optional[str] = None
    ) -> CustomerIntentResult:
        """Helper method for orchestrator pipeline fallback context."""
        context = {
            "customer": {"customer_id": "cust_demo"},
            "interaction": {"message": message_text or f"Context: {failure_context}", "channel": "WHATSAPP"},
            "payment": {"failure_reason": failure_context}
        }
        return gemini_service.analyze_customer_intent(context)


intent_agent = CustomerIntentAgent()
