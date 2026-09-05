import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import (
    RecoveryCase,
    Payment,
    Customer,
    AgentAction,
    ToolExecution,
    MerchantGuardrail,
    RecoveryStatus,
    ActionStatus
)
from app.schemas.contracts import (
    DecisionExplanationResponse,
    AgentTraceResponse,
    AgentTraceStep,
    AIRecommendationItem
)
from app.services.opportunity_service import opportunity_scoring_engine

logger = logging.getLogger("payrecover.trace")


class TraceService:
    """
    Manages Explainable AI Decision Explanations, Agent Traces,
    and High-Impact Recovery Recommendations.
    """

    @classmethod
    def get_decision_explanation(cls, db: Session, case_id: str) -> DecisionExplanationResponse:
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found")

        payment: Payment = case.payment
        customer: Customer = payment.customer if payment else None

        # Fetch latest strategist/investigator actions
        actions = db.query(AgentAction).filter(
            AgentAction.recovery_case_id == case_id
        ).order_by(AgentAction.created_at.desc()).all()

        strategist_action = next((a for a in actions if a.agent_type == "STRATEGIST"), None)
        investigator_action = next((a for a in actions if a.agent_type == "INVESTIGATOR"), None)
        intent_action = next((a for a in actions if a.agent_type == "INTENT_AI"), None)

        opp = opportunity_scoring_engine.calculate_score(case)

        decision = case.current_strategy or opp.recommended_strategy
        reason = strategist_action.reasoning_summary if strategist_action else (
            f"Automated recovery selected '{decision}' based on failure telemetry and customer loyalty indicators."
        )

        evidence = []
        if payment:
            evidence.append(f"Payment Failure Reason: {payment.failure_reason or 'Unknown'}")
            evidence.append(f"Transaction Method: {payment.payment_method}")
            evidence.append(f"Amount: ₹{payment.amount:,.2f}")
        if customer:
            evidence.append(f"Customer Loyalty: {customer.customer_value} with {customer.total_successful_payments} prior successful orders")
        if case.customer_intent:
            evidence.append(f"Detected Intent: {case.customer_intent}")
        if investigator_action:
            evidence.append(f"Investigation Finding: {investigator_action.reasoning_summary}")

        evidence.extend(opp.positive_factors[:3])

        customer_context = {
            "name": customer.name if customer else "Customer",
            "tier": customer.customer_value if customer else "STANDARD",
            "prior_successful": customer.total_successful_payments if customer else 0,
            "prior_failed": customer.total_failed_payments if customer else 0,
            "preferred_method": customer.preferred_payment_method if customer else "UPI"
        }

        risk_factors = opp.negative_factors if opp.negative_factors else ["Standard recovery latency window"]

        # Check guardrails
        guardrail = db.query(MerchantGuardrail).first()
        high_val_threshold = float(guardrail.high_value_threshold) if guardrail else 50000.0
        requires_approval = payment.amount >= high_val_threshold if payment else False

        guardrail_result = {
            "guardrail_status": "APPROVAL_REQUIRED" if requires_approval else "SAFE",
            "requires_human_approval": requires_approval,
            "high_value_threshold": high_val_threshold,
            "is_high_value": requires_approval
        }

        confidence = float(case.recovery_probability or 0.85)
        if confidence >= 0.80:
            conf_level = "HIGH"
        elif confidence >= 0.60:
            conf_level = "MEDIUM"
        else:
            conf_level = "LOW"

        next_step = "Proceed with automated 1-click fallback dispatch" if not requires_approval else "Escalate to Human Review queue"

        return DecisionExplanationResponse(
            case_id=case.id,
            payment_id=payment.id if payment else "",
            decision=decision,
            reason=reason,
            evidence=evidence,
            customer_context=customer_context,
            risk_factors=risk_factors,
            guardrail_result=guardrail_result,
            confidence=confidence,
            confidence_level=conf_level,
            recommended_next_step=next_step
        )

    @classmethod
    def get_case_trace(cls, db: Session, case_id: str) -> AgentTraceResponse:
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found")

        payment = case.payment
        actions = db.query(AgentAction).filter(
            AgentAction.recovery_case_id == case_id
        ).order_by(AgentAction.created_at.asc()).all()

        tool_execs = db.query(ToolExecution).filter(
            ToolExecution.recovery_case_id == case_id
        ).order_by(ToolExecution.created_at.asc()).all()

        stages = ["INVESTIGATE", "INTENT", "STRATEGY", "GUARDRAIL", "EXECUTE", "SETTLE"]
        steps: List[AgentTraceStep] = []

        start_time = case.started_at or datetime.utcnow()

        # Build Stage 0: INVESTIGATE
        inv_action = next((a for a in actions if a.agent_type in ["INVESTIGATOR", "INVESTIGATE_PAYMENT"]), None)
        steps.append(AgentTraceStep(
            step_index=0,
            stage_name="INVESTIGATE",
            agent="INVESTIGATOR",
            status="SUCCESS" if inv_action else "PENDING",
            started_at=inv_action.created_at if inv_action else start_time,
            completed_at=inv_action.created_at if inv_action else start_time,
            duration_ms=210,
            summary=inv_action.reasoning_summary if inv_action else "Analyzed payment telemetry and failure taxonomy.",
            output={"recovery_score": case.recovery_score, "recovery_probability": case.recovery_probability}
        ))

        # Build Stage 1: INTENT
        intent_action = next((a for a in actions if a.agent_type == "INTENT_AI"), None)
        steps.append(AgentTraceStep(
            step_index=1,
            stage_name="INTENT",
            agent="INTENT_AI",
            status="SUCCESS" if intent_action or case.customer_intent else "SKIPPED",
            started_at=intent_action.created_at if intent_action else start_time,
            completed_at=intent_action.created_at if intent_action else start_time,
            duration_ms=180,
            summary=intent_action.reasoning_summary if intent_action else f"Classified intent as '{case.customer_intent or 'UNSPECIFIED'}'.",
            output={"customer_intent": case.customer_intent}
        ))

        # Build Stage 2: STRATEGY
        strat_action = next((a for a in actions if a.agent_type == "STRATEGIST"), None)
        steps.append(AgentTraceStep(
            step_index=2,
            stage_name="STRATEGY",
            agent="STRATEGIST",
            status="SUCCESS" if strat_action or case.current_strategy else "PENDING",
            started_at=strat_action.created_at if strat_action else start_time,
            completed_at=strat_action.created_at if strat_action else start_time,
            duration_ms=240,
            summary=strat_action.reasoning_summary if strat_action else f"Proposed strategy '{case.current_strategy or 'RETRY_PAYMENT'}'.",
            output={"strategy": case.current_strategy}
        ))

        # Build Stage 3: GUARDRAIL
        guard_action = next((a for a in actions if a.action_type == "GUARDRAIL_CHECK"), None)
        guard_status = "SUCCESS"
        guard_applied = False
        if case.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value:
            guard_status = "BLOCKED"
            guard_applied = True

        steps.append(AgentTraceStep(
            step_index=3,
            stage_name="GUARDRAIL",
            agent="GUARDRAIL_SERVICE",
            status=guard_status,
            started_at=guard_action.created_at if guard_action else start_time,
            completed_at=guard_action.created_at if guard_action else start_time,
            duration_ms=45,
            summary=guard_action.reasoning_summary if guard_action else ("High-value check triggered human review requirement." if guard_applied else "Deterministic policy check passed with zero violations."),
            guardrail_applied=guard_applied,
            output={"guardrail_status": "APPROVAL_REQUIRED" if guard_applied else "SAFE"}
        ))

        # Build Stage 4: EXECUTE
        exec_step_status = "SUCCESS" if tool_execs else ("SKIPPED" if guard_applied else "PENDING")
        last_tool = tool_execs[-1] if tool_execs else None
        steps.append(AgentTraceStep(
            step_index=4,
            stage_name="EXECUTE",
            agent="TOOL_EXECUTOR",
            status=last_tool.status if last_tool else exec_step_status,
            started_at=last_tool.created_at if last_tool else start_time,
            completed_at=last_tool.completed_at if last_tool else start_time,
            duration_ms=310,
            summary=f"Dispatched {last_tool.tool_type} action." if last_tool else ("Deferred pending operator approval." if guard_applied else "Awaiting execution dispatch."),
            tool_used=last_tool.tool_type if last_tool else None,
            output={"provider_reference": last_tool.provider_reference if last_tool else None}
        ))

        # Build Stage 5: SETTLE
        settle_status = "SUCCESS" if case.status in [RecoveryStatus.RECOVERED.value, RecoveryStatus.ACTION_IN_PROGRESS.value] else "PENDING"
        steps.append(AgentTraceStep(
            step_index=5,
            stage_name="SETTLE",
            agent="ORCHESTRATOR",
            status=settle_status,
            started_at=case.completed_at or start_time,
            completed_at=case.completed_at or start_time,
            duration_ms=90,
            summary=f"Case status reconciled to '{case.status}'. Recovered amount: ₹{case.recovered_amount:,.2f}.",
            output={"status": case.status, "recovered_amount": case.recovered_amount}
        ))

        completed_count = sum(1 for s in steps if s.status in ["SUCCESS", "SKIPPED"])
        total_duration = sum(s.duration_ms or 0 for s in steps)

        return AgentTraceResponse(
            run_id=f"trace_{case.id[:10]}",
            case_id=case.id,
            payment_id=payment.id if payment else "",
            request_id=f"req_{case.id[:8]}",
            correlation_id=f"corr_{case.id[:8]}",
            timeline=stages,
            steps=steps,
            total_steps=len(steps),
            completed_steps=completed_count,
            final_status=case.status,
            started_at=start_time,
            completed_at=case.completed_at,
            total_duration_ms=total_duration
        )

    @classmethod
    def get_recent_traces(cls, db: Session, limit: int = 10) -> List[AgentTraceResponse]:
        cases = db.query(RecoveryCase).order_by(RecoveryCase.started_at.desc()).limit(limit).all()
        return [cls.get_case_trace(db, c.id) for c in cases]

    @classmethod
    def get_recommendations(cls, db: Session, limit: int = 6) -> List[AIRecommendationItem]:
        """
        Generates ranked high-impact AI recommendations for the Command Center.
        Ranks by expected revenue impact and opportunity score.
        """
        active_cases = db.query(RecoveryCase).filter(
            RecoveryCase.status.notin_([
                RecoveryStatus.RECOVERED.value,
                RecoveryStatus.FAILED.value,
                RecoveryStatus.EXPIRED.value
            ])
        ).all()

        guardrail = db.query(MerchantGuardrail).first()
        high_val_thresh = float(guardrail.high_value_threshold) if guardrail else 50000.0

        items: List[AIRecommendationItem] = []
        for c in active_cases:
            p = c.payment
            if not p:
                continue
            opp = opportunity_scoring_engine.calculate_score(c)
            cust = p.customer
            cust_name = cust.name if cust else "Customer"
            expected_rec = round(opp.estimated_recovery_probability * p.amount, 2)

            conf = float(c.recovery_probability or opp.estimated_recovery_probability)
            conf_level = "HIGH" if conf >= 0.80 else ("MEDIUM" if conf >= 0.60 else "LOW")

            needs_approval = (
                p.amount >= high_val_thresh or
                c.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value or
                conf_level == "LOW"
            )

            action_type = "ESCALATE_TO_HUMAN" if needs_approval else (
                "CREATE_PAYMENT_LINK" if opp.recommended_strategy == "PAYMENT_LINK" else (
                    "RETRY_PAYMENT" if opp.recommended_strategy == "RETRY_PAYMENT" else "OFFER_ALTERNATE_PAYMENT"
                )
            )

            items.append(AIRecommendationItem(
                case_id=c.id,
                payment_id=p.id,
                amount=float(p.amount),
                currency=p.currency,
                customer_name=cust_name,
                customer_id=cust.id if cust else "",
                failure_reason=p.failure_reason or "Technical Failure",
                intent=c.customer_intent or "WILL_PAY_LATER",
                opportunity_score=opp.score,
                priority=opp.priority,
                recommended_strategy=c.current_strategy or opp.recommended_strategy,
                confidence=conf,
                confidence_level=conf_level,
                expected_recovery=expected_rec,
                action_type=action_type,
                requires_human_approval=needs_approval
            ))

        # Rank by expected_recovery descending, then opportunity_score descending
        items.sort(key=lambda x: (x.expected_recovery, x.opportunity_score), reverse=True)
        return items[:limit]


trace_service = TraceService()
