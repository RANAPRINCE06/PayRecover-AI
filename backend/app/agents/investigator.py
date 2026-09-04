import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import (
    Payment,
    Customer,
    RecoveryCase,
    AgentAction,
    AgentType,
    ActionType,
    ActionStatus,
    CustomerInteraction
)
from app.schemas.contracts import PaymentInvestigationResult
from app.services.gemini_service import gemini_service

logger = logging.getLogger("payrecover.investigator")


class PaymentInvestigatorAgent:
    """
    AI Payment Investigator Agent.
    Gathers structured payment telemetry, customer historical transactions,
    past recovery cases and customer interactions, and sends them to Gemini
    for validated structured investigation and recovery assessment.
    """

    @classmethod
    def build_investigation_context(cls, db: Session, payment: Payment) -> Dict[str, Any]:
        """Construct clean sanitized context without sensitive card/account data."""
        customer = payment.customer

        # Fetch past customer payments
        past_payments = (
            db.query(Payment)
            .filter(Payment.customer_id == customer.id, Payment.id != payment.id)
            .order_by(desc(Payment.created_at))
            .limit(10)
            .all()
        )

        # Fetch past recovery case & interactions for this customer
        past_interactions = (
            db.query(CustomerInteraction)
            .filter(CustomerInteraction.customer_id == customer.id)
            .order_by(desc(CustomerInteraction.created_at))
            .limit(5)
            .all()
        )

        recovery_case = payment.recovery_case

        context = {
            "payment": {
                "payment_id": payment.id,
                "razorpay_payment_id": payment.razorpay_payment_id,
                "amount": payment.amount,
                "currency": payment.currency,
                "payment_method": payment.payment_method,
                "status": payment.status,
                "failure_reason": payment.failure_reason,
                "created_at": payment.created_at.isoformat() if payment.created_at else None
            },
            "customer": {
                "customer_id": customer.id,
                "name": customer.name,
                "customer_value": customer.customer_value,
                "preferred_payment_method": customer.preferred_payment_method,
                "successful_payments": customer.total_successful_payments,
                "failed_payments": customer.total_failed_payments,
                "total_orders": customer.total_successful_payments + customer.total_failed_payments,
            },
            "history": {
                "past_payments_sample": [
                    {
                        "amount": p.amount,
                        "method": p.payment_method,
                        "status": p.status,
                        "failure_reason": p.failure_reason,
                        "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else None
                    }
                    for p in past_payments
                ],
                "current_case_retries": recovery_case.retry_count if recovery_case else 0,
                "recent_interactions": [
                    {
                        "channel": inter.channel,
                        "direction": inter.direction,
                        "message": inter.message,
                        "detected_intent": inter.detected_intent
                    }
                    for inter in past_interactions
                ]
            }
        }
        return context

    @classmethod
    def investigate(cls, db: Session, payment: Payment) -> PaymentInvestigationResult:
        """Executes full investigation flow using Gemini and records results in DB."""
        context = cls.build_investigation_context(db, payment)

        # Call Gemini Service
        result: PaymentInvestigationResult = gemini_service.investigate_payment(context)

        # Ensure RecoveryCase exists or update it
        recovery_case = payment.recovery_case
        if not recovery_case:
            recovery_case = RecoveryCase(
                id=f"rc_{uuid.uuid4().hex[:8]}",
                payment_id=payment.id,
                recovery_score=float(result.recovery_score),
                recovery_probability=result.recovery_probability,
                current_strategy=result.recommended_next_action,
                status="INVESTIGATING",
                started_at=datetime.utcnow()
            )
            db.add(recovery_case)
            db.flush()
        else:
            recovery_case.recovery_score = float(result.recovery_score)
            recovery_case.recovery_probability = result.recovery_probability
            recovery_case.current_strategy = result.recommended_next_action

        # Record AgentAction in DB audit trail
        action = AgentAction(
            id=f"act_{uuid.uuid4().hex[:8]}",
            recovery_case_id=recovery_case.id,
            agent_type=AgentType.INVESTIGATOR.value,
            action_type="PAYMENT_INVESTIGATION",
            reasoning_summary=(
                f"AI Investigator analyzed payment #{payment.razorpay_payment_id}. "
                f"Score: {result.recovery_score}/100, Risk: {result.risk_level}, "
                f"Action: {result.recommended_next_action}. {result.reasoning_summary}"
            ),
            status=ActionStatus.EXECUTED.value,
            action_metadata=json.dumps({
                "confidence": result.confidence,
                "failure_category": result.failure_category,
                "contributing_factors": result.contributing_factors,
                "negative_factors": result.negative_factors,
                "risk_level": result.risk_level
            }),
            created_at=datetime.utcnow()
        )
        db.add(action)
        db.commit()
        db.refresh(recovery_case)

        logger.info(
            f"Investigation completed for {payment.id}: "
            f"Score={result.recovery_score}%, Risk={result.risk_level}, Action={result.recommended_next_action}"
        )

        return result


investigator_agent = PaymentInvestigatorAgent()
