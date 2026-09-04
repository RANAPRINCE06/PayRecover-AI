import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.entities import (
    Payment,
    RecoveryCase,
    RecoveryStatus,
    AgentType,
    ActionType
)
from app.agents.investigator import investigator_agent
from app.agents.strategist import strategist_agent
from app.agents.intent import intent_agent
from app.tools.tool_executor import tool_executor

logger = logging.getLogger("payrecover.orchestrator")


class RecoveryOrchestrator:
    """
    Autonomous Multi-Agent Orchestrator.
    Executes the full pipeline:
    1. Investigator analyzes failure & telemetry
    2. Intent Agent categorizes customer context
    3. Strategist selects recovery plan
    4. Tool Executor enforces guardrails and triggers Razorpay / Messaging
    """

    @classmethod
    def execute_recovery_pipeline(
        cls,
        db: Session,
        recovery_case_id: str,
        customer_reply_text: str = None
    ) -> Dict[str, Any]:
        recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not recovery_case:
            raise ValueError(f"RecoveryCase {recovery_case_id} not found")

        payment = recovery_case.payment

        # Step 1: Investigation
        recovery_case.status = RecoveryStatus.INVESTIGATING.value
        db.commit()

        investigation = investigator_agent.investigate(db, payment)
        recovery_case.recovery_score = investigation.recovery_score
        recovery_case.recovery_probability = investigation.recovery_probability

        # Log Investigator Action
        tool_executor.execute_action(
            db=db,
            recovery_case_id=recovery_case.id,
            agent_type=AgentType.INVESTIGATOR.value,
            action_type=ActionType.INVESTIGATE_PAYMENT.value,
            parameters={"investigation": investigation.model_dump()},
            reasoning=investigation.reasoning_summary
        )

        # Step 2: Intent Detection
        detected_intent = intent_agent.detect_intent(
            message_text=customer_reply_text,
            failure_context=payment.failure_reason
        )
        recovery_case.customer_intent = detected_intent.intent

        # Log Intent Action
        tool_executor.execute_action(
            db=db,
            recovery_case_id=recovery_case.id,
            agent_type=AgentType.INTENT_AI.value,
            action_type=ActionType.DISPATCH_MESSAGE.value if customer_reply_text else ActionType.INVESTIGATE_PAYMENT.value,
            parameters={"intent": detected_intent.model_dump()},
            reasoning=f"Detected intent '{detected_intent.intent}' with {int(detected_intent.confidence*100)}% confidence ({detected_intent.sentiment} sentiment)."
        )

        # Step 3: Strategy Formulation
        strategy = strategist_agent.formulate_strategy(investigation, payment)
        recovery_case.current_strategy = strategy.strategy
        recovery_case.status = RecoveryStatus.STRATEGY_SELECTED.value
        db.commit()

        # Log Strategist Action
        tool_executor.execute_action(
            db=db,
            recovery_case_id=recovery_case.id,
            agent_type=AgentType.STRATEGIST.value,
            action_type=ActionType.SELECT_STRATEGY.value,
            parameters={"strategy": strategy.model_dump()},
            reasoning=strategy.reasoning
        )

        # Step 4: Tool Execution (Guardrail Protected)
        if strategy.create_payment_link:
            exec_res = tool_executor.execute_action(
                db=db,
                recovery_case_id=recovery_case.id,
                agent_type=AgentType.TOOL_EXECUTOR.value,
                action_type=ActionType.GENERATE_PAYMENT_LINK.value,
                parameters={
                    "discount_percentage": strategy.discount_percentage,
                    "preferred_method": "upi"
                },
                reasoning="Generated instant Razorpay UPI payment link under merchant guardrails."
            )

            # Step 5: Send message with link
            if exec_res.get("success"):
                tool_executor.execute_action(
                    db=db,
                    recovery_case_id=recovery_case.id,
                    agent_type=AgentType.TOOL_EXECUTOR.value,
                    action_type=ActionType.DISPATCH_MESSAGE.value,
                    parameters={
                        "channel": strategy.recommended_channel,
                        "message": f"Hi {payment.customer.name}, complete your ₹{payment.amount:,.2f} order securely via UPI: {recovery_case.payment_link_url}"
                    },
                    reasoning=f"Dispatched automated recovery payload via {strategy.recommended_channel}."
                )

        db.refresh(recovery_case)
        return {
            "case_id": recovery_case.id,
            "status": recovery_case.status,
            "score": recovery_case.recovery_score,
            "strategy": recovery_case.current_strategy,
            "payment_link": recovery_case.payment_link_url
        }


orchestrator = RecoveryOrchestrator()
