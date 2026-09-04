import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
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
from app.tools.tool_executor import ToolExecutor, tool_executor
from app.schemas.contracts import (
    AutonomousPipelineStep,
    AutonomousPipelineStepStatus,
    AutonomousRecoveryResult,
    ToolType
)

logger = logging.getLogger("payrecover.orchestrator")

# ---------------------------------------------------------------------------
# Helper: build a completed pipeline step
# ---------------------------------------------------------------------------

def _make_step(
    index: int,
    stage: str,
    agent: str,
    status: str,
    summary: str,
    start: datetime,
    output: Optional[Dict[str, Any]] = None,
    guardrail_applied: bool = False,
    guardrail_constraints: Optional[list] = None
) -> AutonomousPipelineStep:
    completed = datetime.utcnow()
    ms = int((completed - start).total_seconds() * 1000)
    return AutonomousPipelineStep(
        step_index=index,
        stage_name=stage,
        agent=agent,
        status=status,
        started_at=start,
        completed_at=completed,
        duration_ms=ms,
        summary=summary,
        output=output,
        guardrail_applied=guardrail_applied,
        guardrail_constraints=guardrail_constraints or []
    )


class RecoveryOrchestrator:
    """
    Autonomous Multi-Agent Orchestrator.

    Phase 1-5 method (execute_recovery_pipeline) is kept for backward compatibility.
    Phase 6 adds run_autonomous_recovery which returns a fully-typed
    AutonomousRecoveryResult with per-step timing and guardrail audit.
    """

    # ------------------------------------------------------------------
    # Phase 1-5: Existing pipeline (do NOT modify)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Phase 6: Autonomous Recovery Pipeline — returns AutonomousRecoveryResult
    # ------------------------------------------------------------------

    @classmethod
    def run_autonomous_recovery(
        cls,
        db: Session,
        recovery_case_id: str,
        customer_message: Optional[str] = None
    ) -> AutonomousRecoveryResult:
        """
        One-click autonomous pipeline that sequences all 6 stages and returns
        a fully-typed, idempotent AutonomousRecoveryResult.

        Stages:
            0 - INVESTIGATE  (PaymentInvestigator)
            1 - INTENT       (CustomerIntentAI)
            2 - STRATEGY     (RecoveryStrategist)
            3 - GUARDRAIL    (GuardrailService – deterministic gating)
            4 - EXECUTE      (ToolExecutor – allowlisted only)
            5 - SETTLE       (Status reconciliation)

        AI output is always treated as untrusted input.
        Backend code is the final authority at every stage.
        """
        pipeline_start = datetime.utcnow()
        run_id = f"auto_{uuid.uuid4().hex[:12]}"
        steps: list[AutonomousPipelineStep] = []

        # ── Load case ──────────────────────────────────────────────────
        case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not case:
            raise ValueError(f"RecoveryCase '{recovery_case_id}' not found")

        payment = case.payment
        if not payment:
            raise ValueError(f"No payment linked to case '{recovery_case_id}'")

        customer = payment.customer
        customer_name = customer.name if customer else "Customer"

        def _fail(msg: str) -> AutonomousRecoveryResult:
            end = datetime.utcnow()
            return AutonomousRecoveryResult(
                run_id=run_id,
                case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id if customer else "",
                customer_name=customer_name,
                amount=payment.amount,
                currency=payment.currency,
                steps=steps,
                total_steps=len(steps),
                completed_steps=sum(1 for s in steps if s.status == AutonomousPipelineStepStatus.SUCCESS.value),
                final_status="FAILED",
                recovery_score=float(case.recovery_score or 0),
                recovery_probability=float(case.recovery_probability or 0),
                strategy_selected=case.current_strategy,
                guardrail_status="SAFE",
                started_at=pipeline_start,
                completed_at=end,
                total_duration_ms=int((end - pipeline_start).total_seconds() * 1000),
                executive_summary=msg
            )

        # ── STAGE 0: INVESTIGATE ───────────────────────────────────────
        s0_start = datetime.utcnow()
        case.status = RecoveryStatus.INVESTIGATING.value
        db.commit()
        try:
            investigation = investigator_agent.investigate(db, payment)
            case.recovery_score = investigation.recovery_score
            case.recovery_probability = investigation.recovery_probability
            db.commit()
            steps.append(_make_step(
                0, "INVESTIGATE", "INVESTIGATOR",
                AutonomousPipelineStepStatus.SUCCESS.value,
                f"Score {investigation.recovery_score}/100 — {investigation.failure_category}. {investigation.reasoning_summary}",
                s0_start,
                output={
                    "recovery_score": investigation.recovery_score,
                    "failure_category": investigation.failure_category,
                    "risk_level": investigation.risk_level,
                    "recovery_probability": investigation.recovery_probability,
                    "contributing_factors": investigation.contributing_factors,
                }
            ))
        except Exception as e:
            logger.exception(f"[{run_id}] INVESTIGATE stage failed: {e}")
            steps.append(_make_step(
                0, "INVESTIGATE", "INVESTIGATOR",
                AutonomousPipelineStepStatus.FAILED.value,
                f"Investigation error: {e}", s0_start
            ))
            return _fail(f"Pipeline aborted at INVESTIGATE stage: {e}")

        # ── STAGE 1: INTENT ────────────────────────────────────────────
        s1_start = datetime.utcnow()
        try:
            detected_intent = intent_agent.detect_intent(
                message_text=customer_message,
                failure_context=payment.failure_reason
            )
            case.customer_intent = detected_intent.intent
            db.commit()
            steps.append(_make_step(
                1, "INTENT", "INTENT_AI",
                AutonomousPipelineStepStatus.SUCCESS.value,
                f"Intent '{detected_intent.intent}' ({int(detected_intent.confidence*100)}% conf) — {detected_intent.sentiment} sentiment.",
                s1_start,
                output={
                    "intent": detected_intent.intent,
                    "confidence": detected_intent.confidence,
                    "sentiment": detected_intent.sentiment,
                    "urgency": detected_intent.urgency,
                    "recommended_action": detected_intent.recommended_action,
                }
            ))
        except Exception as e:
            logger.exception(f"[{run_id}] INTENT stage failed: {e}")
            steps.append(_make_step(
                1, "INTENT", "INTENT_AI",
                AutonomousPipelineStepStatus.FAILED.value,
                f"Intent error: {e}", s1_start
            ))
            return _fail(f"Pipeline aborted at INTENT stage: {e}")

        # ── STAGE 2: STRATEGY ──────────────────────────────────────────
        s2_start = datetime.utcnow()
        try:
            strategy = strategist_agent.formulate_strategy(investigation, payment)
            case.current_strategy = strategy.strategy
            case.status = RecoveryStatus.STRATEGY_SELECTED.value
            db.commit()
            steps.append(_make_step(
                2, "STRATEGY", "STRATEGIST",
                AutonomousPipelineStepStatus.SUCCESS.value,
                f"Strategy '{strategy.strategy}' selected — {int(strategy.expected_recovery_probability*100)}% expected recovery.",
                s2_start,
                output={
                    "strategy": strategy.strategy,
                    "priority": strategy.priority,
                    "expected_recovery_probability": strategy.expected_recovery_probability,
                    "create_payment_link": strategy.create_payment_link,
                    "offer_discount": strategy.offer_discount,
                    "discount_percentage": strategy.discount_percentage,
                    "recommended_channel": strategy.recommended_channel,
                    "escalate_to_human": strategy.escalate_to_human,
                }
            ))
        except Exception as e:
            logger.exception(f"[{run_id}] STRATEGY stage failed: {e}")
            steps.append(_make_step(
                2, "STRATEGY", "STRATEGIST",
                AutonomousPipelineStepStatus.FAILED.value,
                f"Strategy error: {e}", s2_start
            ))
            return _fail(f"Pipeline aborted at STRATEGY stage: {e}")

        # ── STAGE 3: GUARDRAIL (deterministic) ────────────────────────
        s3_start = datetime.utcnow()
        from app.services.guardrail_service import guardrail_service
        guardrails = guardrail_service.get_or_create_guardrails(db)

        g_constraints: list[str] = []
        g_status = "SAFE"
        needs_approval = False

        if guardrails.human_approval_required and payment.amount >= guardrails.high_value_threshold:
            needs_approval = True
            g_status = "APPROVAL_REQUIRED"
            g_constraints.append(
                f"High-Value: ₹{payment.amount:,.2f} ≥ threshold ₹{guardrails.high_value_threshold:,.2f}"
            )
        if strategy.offer_discount and strategy.discount_percentage > guardrails.max_discount_percentage:
            g_constraints.append(
                f"Discount capped: {strategy.discount_percentage}% → {guardrails.max_discount_percentage}%"
            )
            strategy.discount_percentage = guardrails.max_discount_percentage
        if guardrail_service.is_in_quiet_hours(guardrails.quiet_hours_start, guardrails.quiet_hours_end):
            g_status = "BLOCKED"
            g_constraints.append(
                f"Quiet hours active ({guardrails.quiet_hours_start}–{guardrails.quiet_hours_end})"
            )

        g_step_status = AutonomousPipelineStepStatus.SUCCESS.value
        if g_status == "BLOCKED":
            g_step_status = AutonomousPipelineStepStatus.BLOCKED.value
        elif g_status == "APPROVAL_REQUIRED":
            g_step_status = AutonomousPipelineStepStatus.SUCCESS.value  # guardrail passed but flagged

        steps.append(_make_step(
            3, "GUARDRAIL", "GUARDRAIL_ENGINE",
            g_step_status,
            f"Guardrail status: {g_status}. {'; '.join(g_constraints) if g_constraints else 'All policies satisfied.'}",
            s3_start,
            guardrail_applied=bool(g_constraints),
            guardrail_constraints=g_constraints,
            output={"guardrail_status": g_status, "needs_approval": needs_approval}
        ))

        if g_status == "BLOCKED":
            end = datetime.utcnow()
            return AutonomousRecoveryResult(
                run_id=run_id,
                case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id if customer else "",
                customer_name=customer_name,
                amount=payment.amount,
                currency=payment.currency,
                steps=steps,
                total_steps=len(steps),
                completed_steps=sum(1 for s in steps if s.status == AutonomousPipelineStepStatus.SUCCESS.value),
                final_status="BLOCKED",
                recovery_score=float(case.recovery_score or 0),
                recovery_probability=float(case.recovery_probability or 0),
                strategy_selected=case.current_strategy,
                guardrail_status=g_status,
                guardrail_constraints=g_constraints,
                requires_human_approval=needs_approval,
                started_at=pipeline_start,
                completed_at=end,
                total_duration_ms=int((end - pipeline_start).total_seconds() * 1000),
                executive_summary=f"Recovery blocked by guardrail: {'; '.join(g_constraints)}"
            )

        # ── STAGE 4: EXECUTE ───────────────────────────────────────────
        s4_start = datetime.utcnow()
        exec_result = None
        tool_executed: Optional[str] = None
        payment_link: Optional[str] = None

        try:
            # Determine tool type from strategy
            if strategy.escalate_to_human or needs_approval:
                resolved_tool = ToolType.ESCALATE_TO_HUMAN
            elif "VERIFY" in strategy.strategy.upper() or detected_intent.intent == "ALREADY_PAID":
                resolved_tool = ToolType.VERIFY_PAYMENT
            elif "RETRY" in strategy.strategy.upper():
                resolved_tool = ToolType.RETRY_PAYMENT
            elif "ALTERNATE" in strategy.strategy.upper() or "UPI" in strategy.strategy.upper():
                resolved_tool = ToolType.OFFER_ALTERNATE_PAYMENT
            elif strategy.create_payment_link:
                resolved_tool = ToolType.CREATE_PAYMENT_LINK
            elif "FOLLOW" in strategy.strategy.upper():
                resolved_tool = ToolType.SCHEDULE_FOLLOW_UP
            else:
                resolved_tool = ToolType.CREATE_PAYMENT_LINK

            tool_executed = resolved_tool.value

            exec_result = ToolExecutor.execute(
                db=db,
                recovery_case_id=case.id,
                tool_type=resolved_tool,
                parameters={
                    "discount_percentage": strategy.discount_percentage,
                    "preferred_method": strategy.recommended_channel.lower() if strategy.recommended_channel else "upi",
                    "channel": strategy.recommended_channel,
                    "payment_method": "UPI",
                    "reason": strategy.reasoning if hasattr(strategy, "reasoning") else strategy.strategy,
                    "target_tool": ToolType.CREATE_PAYMENT_LINK.value,
                    "message": f"Hi {customer_name}, complete your ₹{payment.amount:,.2f} payment securely. Our support team has your order ready.",
                }
            )
            payment_link = exec_result.payment_link_url

            exec_status = AutonomousPipelineStepStatus.SUCCESS.value if exec_result.success else AutonomousPipelineStepStatus.FAILED.value
            if exec_result.status in ("BLOCKED", "APPROVAL_REQUIRED"):
                exec_status = AutonomousPipelineStepStatus.BLOCKED.value if exec_result.status == "BLOCKED" else AutonomousPipelineStepStatus.SUCCESS.value

            steps.append(_make_step(
                4, "EXECUTE", "TOOL_EXECUTOR",
                exec_status,
                exec_result.message,
                s4_start,
                output={
                    "tool_type": exec_result.tool_type,
                    "success": exec_result.success,
                    "provider_reference": exec_result.provider_reference,
                    "payment_link_url": exec_result.payment_link_url,
                    "guardrail_status": exec_result.guardrail_status,
                    "requires_human_approval": exec_result.requires_human_approval,
                },
                guardrail_applied=exec_result.guardrail_status != "SAFE",
                guardrail_constraints=exec_result.guardrail_constraints
            ))
        except Exception as e:
            logger.exception(f"[{run_id}] EXECUTE stage failed: {e}")
            steps.append(_make_step(
                4, "EXECUTE", "TOOL_EXECUTOR",
                AutonomousPipelineStepStatus.FAILED.value,
                f"Execution error: {e}", s4_start
            ))
            return _fail(f"Pipeline aborted at EXECUTE stage: {e}")

        # ── STAGE 5: SETTLE ────────────────────────────────────────────
        s5_start = datetime.utcnow()
        db.refresh(case)

        final_status = case.status
        settle_summary = f"Case status: {final_status}."
        if final_status == RecoveryStatus.RECOVERED.value:
            settle_summary = f"✅ Payment fully recovered. ₹{payment.amount:,.2f} settled."
        elif final_status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value:
            settle_summary = f"⏳ Awaiting merchant approval. Escalated for high-value review."
        elif final_status == RecoveryStatus.ACTION_IN_PROGRESS.value:
            settle_summary = f"⚡ Recovery action dispatched. Awaiting customer response."
        elif final_status == RecoveryStatus.AWAITING_CUSTOMER.value:
            settle_summary = f"📅 Follow-up scheduled. Waiting for customer to complete payment."

        steps.append(_make_step(
            5, "SETTLE", "ORCHESTRATOR",
            AutonomousPipelineStepStatus.SUCCESS.value,
            settle_summary,
            s5_start,
            output={"case_status": final_status, "recovered_amount": case.recovered_amount}
        ))

        # ── Build final result ─────────────────────────────────────────
        pipeline_end = datetime.utcnow()
        completed_steps = sum(1 for s in steps if s.status == AutonomousPipelineStepStatus.SUCCESS.value)

        # Map case status → AutonomousRecoveryResult.final_status
        outcome_map = {
            RecoveryStatus.RECOVERED.value: "RECOVERED",
            RecoveryStatus.AWAITING_HUMAN_APPROVAL.value: "AWAITING_HUMAN_APPROVAL",
            RecoveryStatus.ACTION_IN_PROGRESS.value: "IN_PROGRESS",
            RecoveryStatus.AWAITING_CUSTOMER.value: "IN_PROGRESS",
            RecoveryStatus.FAILED.value: "FAILED",
        }
        outcome = outcome_map.get(case.status, "IN_PROGRESS")

        # Executive summary
        summary_parts = [
            f"Autonomous pipeline completed in {int((pipeline_end - pipeline_start).total_seconds() * 1000)}ms.",
            f"Score: {case.recovery_score}/100 | Strategy: {case.current_strategy or 'N/A'}.",
            f"Tool: {tool_executed or 'None'} | Outcome: {outcome}.",
        ]
        if payment_link:
            summary_parts.append(f"Payment link: {payment_link}")

        exec_result_dict: Optional[Dict[str, Any]] = None
        if exec_result:
            exec_result_dict = exec_result.model_dump(mode="json")

        return AutonomousRecoveryResult(
            run_id=run_id,
            case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id if customer else "",
            customer_name=customer_name,
            amount=payment.amount,
            currency=payment.currency,
            steps=steps,
            total_steps=len(steps),
            completed_steps=completed_steps,
            final_status=outcome,
            recovery_score=float(case.recovery_score or 0),
            recovery_probability=float(case.recovery_probability or 0),
            strategy_selected=case.current_strategy,
            tool_executed=tool_executed,
            payment_link_url=payment_link,
            tool_execution_result=exec_result_dict,
            guardrail_status=g_status,
            requires_human_approval=(
                needs_approval or (exec_result.requires_human_approval if exec_result else False)
            ),
            started_at=pipeline_start,
            completed_at=pipeline_end,
            total_duration_ms=int((pipeline_end - pipeline_start).total_seconds() * 1000),
            executive_summary=" ".join(summary_parts)
        )


orchestrator = RecoveryOrchestrator()
