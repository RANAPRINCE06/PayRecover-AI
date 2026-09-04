import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.entities import (
    Payment,
    RecoveryCase,
    AgentAction,
    AgentType,
    ActionType,
    ActionStatus,
    PaymentStatus,
    RecoveryStatus,
    InteractionChannel
)
from app.services.guardrail_service import guardrail_service
from app.services.messaging_service import messaging_service
from app.integrations.razorpay_client import razorpay_client

logger = logging.getLogger("payrecover.tool_executor")


class ToolExecutor:
    """
    Controlled Tool Executor.
    The AI agent proposes actions, but the Tool Executor decides whether actions
    are permitted by evaluating merchant guardrails, payment state, and authorization.
    Never allows raw LLM text to execute arbitrary payment operations.
    """

    @classmethod
    def execute_action(
        cls,
        db: Session,
        recovery_case_id: str,
        agent_type: str,
        action_type: str,
        parameters: Dict[str, Any],
        reasoning: str
    ) -> Dict[str, Any]:
        recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not recovery_case:
            raise ValueError(f"Recovery case {recovery_case_id} not found.")

        payment = recovery_case.payment
        if not payment:
            raise ValueError(f"Payment for case {recovery_case_id} not found.")

        # 1. Guardrail validation
        discount = parameters.get("discount_percentage", 0.0)
        is_allowed, reason = guardrail_service.evaluate_action(
            db=db,
            payment=payment,
            recovery_case=recovery_case,
            action_type=action_type,
            discount_percentage=discount
        )

        action_id = f"act_{uuid.uuid4().hex[:10]}"

        if not is_allowed:
            # Record blocked action
            action = AgentAction(
                id=action_id,
                recovery_case_id=recovery_case.id,
                agent_type=agent_type,
                action_type=action_type,
                reasoning_summary=f"BLOCKED BY GUARDRAIL: {reason}. Agent proposal: {reasoning}",
                status=ActionStatus.BLOCKED_BY_GUARDRAIL.value,
                action_metadata=json.dumps(parameters),
                created_at=datetime.utcnow()
            )
            db.add(action)
            
            # Escalate to human review if high value
            if "High-Value" in reason:
                recovery_case.status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
            
            db.commit()
            return {
                "success": False,
                "action_id": action_id,
                "status": ActionStatus.BLOCKED_BY_GUARDRAIL.value,
                "reason": reason
            }

        # 2. Execute approved tool
        result_metadata = {}
        try:
            if action_type == ActionType.GENERATE_PAYMENT_LINK.value:
                desc = f"Recovery for Payment #{payment.razorpay_payment_id}"
                link_res = razorpay_client.create_payment_link(
                    amount_inr=payment.amount * (1 - discount / 100),
                    customer_name=payment.customer.name,
                    customer_email=payment.customer.email,
                    customer_phone=payment.customer.phone,
                    description=desc,
                    preferred_method=parameters.get("preferred_method", "upi")
                )
                recovery_case.payment_link_url = link_res.get("short_url")
                recovery_case.retry_count += 1
                recovery_case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
                result_metadata = link_res

            elif action_type == ActionType.DISPATCH_MESSAGE.value:
                channel = parameters.get("channel", InteractionChannel.WHATSAPP.value)
                msg_text = parameters.get("message", f"Hi {payment.customer.name}, complete your payment easily: {recovery_case.payment_link_url or 'https://rzp.io/i/demo'}")
                msg = messaging_service.send_recovery_message(
                    db=db,
                    customer_id=payment.customer_id,
                    recovery_case_id=recovery_case.id,
                    channel=channel,
                    message=msg_text,
                    detected_intent=recovery_case.customer_intent
                )
                result_metadata = {"interaction_id": msg.id, "channel": channel}

            elif action_type == ActionType.PAYMENT_CONFIRMED.value:
                # Mark payment and recovery case as recovered
                payment.status = PaymentStatus.RECOVERED.value
                recovery_case.status = RecoveryStatus.RECOVERED.value
                recovery_case.recovered_amount = payment.amount * (1 - discount / 100)
                recovery_case.completed_at = datetime.utcnow()
                payment.customer.total_successful_payments += 1
                result_metadata = {"recovered_amount": recovery_case.recovered_amount}

            elif action_type == ActionType.ESCALATE_HUMAN.value:
                recovery_case.status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
                result_metadata = {"escalation_reason": reasoning}

            # Record Successful Action
            action = AgentAction(
                id=action_id,
                recovery_case_id=recovery_case.id,
                agent_type=agent_type,
                action_type=action_type,
                reasoning_summary=reasoning,
                status=ActionStatus.EXECUTED.value,
                action_metadata=json.dumps({**parameters, **result_metadata}),
                created_at=datetime.utcnow()
            )
            db.add(action)
            db.commit()
            db.refresh(recovery_case)

            return {
                "success": True,
                "action_id": action_id,
                "status": ActionStatus.EXECUTED.value,
                "details": result_metadata
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Tool execution failed: {e}")
            action = AgentAction(
                id=action_id,
                recovery_case_id=recovery_case.id,
                agent_type=agent_type,
                action_type=action_type,
                reasoning_summary=f"FAILED: {str(e)}",
                status=ActionStatus.FAILED.value,
                action_metadata=json.dumps({"error": str(e)}),
                created_at=datetime.utcnow()
            )
            db.add(action)
            db.commit()
            return {
                "success": False,
                "action_id": action_id,
                "status": ActionStatus.FAILED.value,
                "error": str(e)
            }


tool_executor = ToolExecutor()
