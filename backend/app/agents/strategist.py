import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import (
    Payment,
    Customer,
    RecoveryCase,
    AgentAction,
    MerchantGuardrail,
    CustomerInteraction,
    AgentType,
    ActionType,
    ActionStatus
)
from app.schemas.contracts import (
    PaymentInvestigationResult,
    RecoveryStrategy,
    RecoveryStrategyProposal,
    RecoveryStrategyResult,
    GuardrailStatusType
)
from app.services.gemini_service import gemini_service
from app.services.guardrail_service import guardrail_service

logger = logging.getLogger("payrecover.strategist")


class PrerequisiteContextMissingError(Exception):
    """Raised when required Investigator or Customer Intent intelligence is unavailable."""
    pass


class StrategistContextBuilder:
    """
    Constructs bounded, sanitized contextual intelligence for the AI Recovery Strategist.
    Aggregates Payment, Customer profile, Investigator telemetry, Intent analysis,
    prior recovery actions, and merchant guardrails without exposing sensitive secrets.
    """

    @classmethod
    def build_context(
        cls,
        db: Session,
        payment: Payment,
        recovery_case: RecoveryCase,
        investigator_action: Optional[AgentAction],
        intent_action: Optional[AgentAction],
        guardrail: MerchantGuardrail
    ) -> Dict[str, Any]:
        customer = payment.customer

        # 1. Parse Investigator metadata if available
        inv_data = {}
        if investigator_action and investigator_action.action_metadata:
            try:
                inv_data = json.loads(investigator_action.action_metadata)
            except Exception:
                inv_data = {}

        # 2. Parse Intent metadata if available
        intent_data = {}
        if intent_action and intent_action.action_metadata:
            try:
                intent_data = json.loads(intent_action.action_metadata)
            except Exception:
                intent_data = {}

        # 3. Bounded past actions
        recent_actions = (
            db.query(AgentAction)
            .filter(AgentAction.recovery_case_id == recovery_case.id)
            .order_by(desc(AgentAction.created_at))
            .limit(5)
            .all()
        )

        context = {
            "payment": {
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "currency": payment.currency or "INR",
                "payment_method": payment.payment_method,
                "status": payment.status,
                "failure_reason": payment.failure_reason,
                "retry_count": recovery_case.retry_count
            },
            "customer": {
                "customer_id": customer.id,
                "name": customer.name,
                "customer_value": customer.customer_value,
                "preferred_payment_method": customer.preferred_payment_method,
                "successful_payments": customer.total_successful_payments,
                "failed_payments": customer.total_failed_payments
            },
            "investigator": {
                "recovery_probability": recovery_case.recovery_probability or inv_data.get("recovery_probability", 0.85),
                "recovery_score": recovery_case.recovery_score or inv_data.get("recovery_score", 85),
                "failure_category": inv_data.get("failure_category", "payment_method_issue"),
                "risk_level": inv_data.get("risk_level", "LOW"),
                "recommended_next_action": inv_data.get("recommended_next_action", "ALTERNATE_PAYMENT_METHOD"),
                "contributing_factors": inv_data.get("contributing_factors", []),
                "negative_factors": inv_data.get("negative_factors", [])
            },
            "intent": {
                "intent": recovery_case.customer_intent or intent_data.get("intent", "UNKNOWN"),
                "sentiment": intent_data.get("sentiment", "NEUTRAL"),
                "urgency": intent_data.get("urgency", "MEDIUM"),
                "recommended_action": intent_data.get("recommended_action", "OFFER_ALTERNATE_PAYMENT"),
                "recommended_channel": intent_data.get("recommended_channel", "WHATSAPP"),
                "evidence": intent_data.get("evidence", []),
                "confidence": intent_data.get("confidence", 0.90)
            },
            "recovery": {
                "recovery_case_id": recovery_case.id,
                "retry_count": recovery_case.retry_count,
                "current_strategy": recovery_case.current_strategy,
                "past_actions_summary": [
                    {"agent": act.agent_type, "type": act.action_type, "summary": act.reasoning_summary[:100]}
                    for act in recent_actions
                ]
            },
            "guardrails": {
                "max_retries": guardrail.max_retries,
                "max_discount_percentage": guardrail.max_discount_percentage,
                "quiet_hours_start": guardrail.quiet_hours_start,
                "quiet_hours_end": guardrail.quiet_hours_end,
                "high_value_threshold": guardrail.high_value_threshold
            }
        }
        return context


class RecoveryStrategistAgent:
    """
    AI Recovery Strategist Agent.
    Aggregates full context, invokes Gemini for strategy formulation,
    passes proposals to deterministic guardrail enforcement,
    records audit actions, and returns verified safe recovery strategies.
    """

    @classmethod
    def generate_strategy(cls, db: Session, recovery_case_id: str) -> RecoveryStrategyResult:
        """
        Main advisory pipeline method.
        Requires existing recovery case and prerequisite Investigator & Intent intelligence.
        """
        # 1. Fetch recovery case
        recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not recovery_case:
            raise ValueError(f"Recovery case with ID '{recovery_case_id}' not found")

        payment = recovery_case.payment
        if not payment:
            raise ValueError(f"No payment linked to recovery case '{recovery_case_id}'")

        customer = payment.customer
        if not customer:
            raise ValueError(f"No customer linked to payment '{payment.id}'")

        # 2. Check prerequisite context (Required Context Rule)
        investigator_action = (
            db.query(AgentAction)
            .filter(
                AgentAction.recovery_case_id == recovery_case.id,
                AgentAction.agent_type == AgentType.INVESTIGATOR.value
            )
            .order_by(desc(AgentAction.created_at))
            .first()
        )

        intent_action = (
            db.query(AgentAction)
            .filter(
                AgentAction.recovery_case_id == recovery_case.id,
                AgentAction.agent_type == AgentType.INTENT_AI.value
            )
            .order_by(desc(AgentAction.created_at))
            .first()
        )

        # Ensure prerequisite intelligence is present without fabricating data
        has_investigator_context = bool(investigator_action or (recovery_case.recovery_score > 0 and recovery_case.recovery_probability > 0))
        has_intent_context = bool(intent_action or recovery_case.customer_intent)

        if not has_investigator_context or not has_intent_context:
            missing = []
            if not has_investigator_context:
                missing.append("Payment Investigator intelligence")
            if not has_intent_context:
                missing.append("Customer Intent AI intelligence")
            raise PrerequisiteContextMissingError(
                f"Required prerequisite context unavailable for recovery case '{recovery_case_id}'. Missing: {', '.join(missing)}. "
                "Please run payment investigation and intent analysis before strategy generation."
            )

        # 3. Load merchant guardrails
        guardrail = guardrail_service.get_or_create_guardrails(db)

        # 4. Build bounded context
        context = StrategistContextBuilder.build_context(
            db=db,
            payment=payment,
            recovery_case=recovery_case,
            investigator_action=investigator_action,
            intent_action=intent_action,
            guardrail=guardrail
        )

        # 5. Generate Gemini strategy proposal
        proposal: RecoveryStrategyProposal = gemini_service.generate_recovery_strategy(context)

        # 6. Pass proposal to deterministic backend guardrail enforcement
        final_result: RecoveryStrategyResult = guardrail_service.enforce_strategy_guardrails(
            db=db,
            payment=payment,
            recovery_case=recovery_case,
            proposal=proposal
        )

        # 7. Update RecoveryCase state
        recovery_case.current_strategy = final_result.primary_strategy
        if final_result.human_approval_required:
            recovery_case.status = "AWAITING_HUMAN_APPROVAL"
        else:
            recovery_case.status = "STRATEGY_SELECTED"

        # 8. Record AgentAction in DB audit trail
        action = AgentAction(
            id=f"act_{uuid.uuid4().hex[:8]}",
            recovery_case_id=recovery_case.id,
            agent_type=AgentType.STRATEGIST.value,
            action_type="RECOVERY_STRATEGY_GENERATION",
            reasoning_summary=(
                f"AI Recovery Strategist selected primary strategy: {final_result.primary_strategy} "
                f"(Guardrail Status: {final_result.guardrail_status}). {final_result.reasoning_summary}"
            ),
            status="SUCCESS",
            action_metadata=json.dumps({
                "primary_strategy": final_result.primary_strategy,
                "secondary_strategy": final_result.secondary_strategy,
                "recommended_channel": final_result.recommended_channel,
                "recommended_payment_method": final_result.recommended_payment_method,
                "expected_recovery_probability": final_result.expected_recovery_probability,
                "strategy_confidence": final_result.strategy_confidence,
                "proposed_discount": proposal.proposed_discount_percentage,
                "final_discount": final_result.discount_percentage,
                "discount_amount": final_result.discount_amount,
                "retry_count": final_result.retry_count,
                "human_approval_required": final_result.human_approval_required,
                "approval_reason": final_result.approval_reason,
                "guardrail_status": final_result.guardrail_status,
                "guardrail_constraints": final_result.guardrail_constraints,
                "supporting_factors": final_result.supporting_factors,
                "risk_factors": final_result.risk_factors,
                "rejected_strategies": final_result.rejected_strategies
            }),
            created_at=datetime.utcnow()
        )
        db.add(action)
        db.commit()
        db.refresh(recovery_case)

        logger.info(
            f"Strategy generation completed for recovery case {recovery_case_id}: "
            f"Strategy={final_result.primary_strategy}, Guardrail={final_result.guardrail_status}, "
            f"HumanApproval={final_result.human_approval_required}"
        )

        return final_result

    # -------------------------------------------------------------
    # Backward Compatibility for RecoveryOrchestrator
    # -------------------------------------------------------------
    @classmethod
    def formulate_strategy(cls, investigation: PaymentInvestigationResult, payment: Payment) -> RecoveryStrategy:
        amount = payment.amount
        prob = investigation.recovery_probability
        failure = investigation.failure_category

        if failure == "CARD_DECLINED":
            strategy_name = "UPI_FALLBACK_LINK"
            channel = "WHATSAPP"
            reasoning = "Do not retry failed card. Issuing bank 3DS is blocked. Recommend instant UPI payment link via WhatsApp for highest completion rate."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = amount >= 50000.0

        elif failure == "UPI_TIMEOUT":
            strategy_name = "INSTANT_WHATSAPP_ONE_CLICK_UPI"
            channel = "WHATSAPP"
            reasoning = "UPI PSP timed out. Send instant prefilled VPA link to WhatsApp immediately while intent is fresh."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = False

        elif failure == "INSUFFICIENT_FUNDS":
            strategy_name = "SCHEDULED_PAY_LATER_REMINDER"
            channel = "SMS"
            reasoning = "Customer balance issue. Offer scheduled reminder for next business day."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = False

        elif failure == "CHECKOUT_ABANDONED":
            strategy_name = "SMART_DISCOUNT_NUDGE"
            channel = "WHATSAPP"
            reasoning = "High cart drop-off probability. Offer 5% recovery incentive to seal the purchase within 2 hours."
            discount_pct = 5.0
            retry_payment = False
            create_link = True
            escalate = False

        else:
            strategy_name = "STANDARD_RECOVERY_OMNICHANNEL"
            channel = "EMAIL"
            reasoning = "Standard automated recovery flow across active channels."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = amount >= 50000.0

        estimated_recovery = round(amount * prob * (1.0 - (discount_pct / 100.0)), 2)

        return RecoveryStrategy(
            strategy=strategy_name,
            priority="IMMEDIATE" if prob > 0.8 else "STANDARD",
            expected_recovery_probability=prob,
            estimated_revenue_recovery=estimated_recovery,
            recommended_channel=channel,
            retry_payment=retry_payment,
            create_payment_link=create_link,
            offer_discount=discount_pct > 0,
            discount_percentage=discount_pct,
            schedule_followup=True,
            escalate_to_human=escalate,
            reasoning=reasoning
        )


strategist_agent = RecoveryStrategistAgent()

