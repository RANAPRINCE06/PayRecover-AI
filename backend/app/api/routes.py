import json
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.session import get_db
from app.models.entities import (
    Merchant,
    Customer,
    Payment,
    RecoveryCase,
    AgentAction,
    MerchantGuardrail,
    CustomerInteraction,
    PaymentStatus,
    RecoveryStatus,
    PaymentMethod,
    FailureReason,
    AgentType,
    ActionType,
    ActionStatus,
    User,
    UserRole
)
from app.core.auth import get_optional_user
from app.services.event_service import event_service
from app.services.idempotency_service import IdempotencyService
from app.schemas.contracts import (
    DashboardMetrics,
    PaymentSchema,
    RecoveryCaseSchema,
    AgentActionSchema,
    CustomerInteractionSchema,
    GuardrailSchema,
    GuardrailUpdateSchema,
    CopilotRequest,
    CopilotResponse,
    SimulateRecoveryRequest,
    PaymentInvestigationResult,
    CustomerIntentRequest,
    CustomerIntentResult,
    RecoveryStrategyRequest,
    RecoveryStrategyResult,
    ToolType,
    ToolExecutionStatus,
    ToolExecutionRequest,
    ToolExecutionResult,
    AutonomousRecoveryResult,
    OpportunityScoreResponse,
    DecisionExplanationResponse,
    AgentTraceResponse,
    AIRecommendationItem
)
from app.agents.investigator import investigator_agent
from app.agents.intent import intent_agent
from app.agents.strategist import strategist_agent, PrerequisiteContextMissingError
from app.agents.orchestrator import orchestrator
from app.tools.tool_executor import ToolExecutor
from app.services.guardrail_service import guardrail_service
from app.services.redis_service import redis_service
from app.services.copilot_service import copilot_service
from app.services.opportunity_service import opportunity_scoring_engine
from app.services.trace_service import trace_service
from app.integrations.mock_payment_engine import mock_payment_engine

router = APIRouter()


# 1. Health
@router.get("/health", tags=["System"])
def get_health():
    return {
        "status": "healthy",
        "service": "PayRecover AI",
        "version": "1.0.0",
        "redis_connected": redis_service.is_connected,
        "timestamp": datetime.utcnow().isoformat()
    }


# 2. Dashboard Metrics
@router.get("/dashboard/metrics", response_model=DashboardMetrics, tags=["Dashboard"])
def get_dashboard_metrics(db: Session = Depends(get_db)):
    cached = redis_service.get("dashboard:metrics")
    if cached:
        return cached

    # Calculate aggregations
    all_payments = db.query(Payment).all()
    total_processed = sum(p.amount for p in all_payments)
    failed_payments = [p for p in all_payments if p.status == PaymentStatus.FAILED.value]
    revenue_at_risk = sum(p.amount for p in failed_payments)

    recovered_cases = db.query(RecoveryCase).filter(RecoveryCase.status == RecoveryStatus.RECOVERED.value).all()
    revenue_recovered = sum(rc.recovered_amount or rc.payment.amount for rc in recovered_cases if rc.payment)

    active_cases = db.query(RecoveryCase).filter(
        RecoveryCase.status.in_([
            RecoveryStatus.IDENTIFIED.value,
            RecoveryStatus.INVESTIGATING.value,
            RecoveryStatus.STRATEGY_SELECTED.value,
            RecoveryStatus.ACTION_IN_PROGRESS.value,
            RecoveryStatus.AWAITING_CUSTOMER.value
        ])
    ).all()

    human_queue = db.query(RecoveryCase).filter(
        RecoveryCase.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
    ).count()

    predicted_recoverable = sum((rc.recovery_probability * rc.payment.amount) for rc in active_cases if rc.payment)

    total_failed_and_rec = revenue_at_risk + revenue_recovered
    recovery_rate = (revenue_recovered / total_failed_and_rec * 100) if total_failed_and_rec > 0 else 0.0

    # Trend by week/day
    trend_data = [
        {"day": "Mon", "at_risk": 32000, "recovered": 26500, "prevented_churn": 4},
        {"day": "Tue", "at_risk": 48500, "recovered": 41200, "prevented_churn": 7},
        {"day": "Wed", "at_risk": 29000, "recovered": 24000, "prevented_churn": 3},
        {"day": "Thu", "at_risk": 54000, "recovered": 46800, "prevented_churn": 8},
        {"day": "Fri", "at_risk": 68000, "recovered": 59400, "prevented_churn": 11},
        {"day": "Sat", "at_risk": 41000, "recovered": 36200, "prevented_churn": 6},
        {"day": "Sun", "at_risk": 35000, "recovered": 31500, "prevented_churn": 5},
    ]

    # Breakdown by Method
    method_data = [
        {"method": "UPI", "failed": 18, "recovered": 16, "recovery_rate": 88.8},
        {"method": "Cards", "failed": 14, "recovered": 11, "recovery_rate": 78.5},
        {"method": "NetBanking", "failed": 8, "recovered": 5, "recovery_rate": 62.5},
    ]

    # Breakdown by Reason
    reason_data = [
        {"reason": "Card 3DS Declined", "count": 14, "recovered": 11, "rate": 78.5},
        {"reason": "UPI PSP Timeout", "count": 12, "recovered": 11, "rate": 91.6},
        {"reason": "Insufficient Funds", "count": 8, "recovered": 5, "rate": 62.5},
        {"reason": "Checkout Abandoned", "count": 6, "recovered": 4, "rate": 66.6},
    ]

    pipeline = [
        {"stage": "Detected & Investigated", "count": len(failed_payments) + len(recovered_cases), "value": revenue_at_risk + revenue_recovered},
        {"stage": "Strategy & Intent Mapped", "count": len(active_cases) + len(recovered_cases), "value": predicted_recoverable + revenue_recovered},
        {"stage": "Action Dispatched", "count": len(active_cases), "value": predicted_recoverable},
        {"stage": "Fully Recovered", "count": len(recovered_cases), "value": revenue_recovered},
    ]

    metrics = DashboardMetrics(
        revenue_processed=round(total_processed, 2),
        revenue_at_risk=round(revenue_at_risk, 2),
        predicted_recoverable=round(predicted_recoverable, 2),
        revenue_recovered=round(revenue_recovered, 2),
        recovery_rate=round(recovery_rate, 1),
        failed_payments_count=len(failed_payments),
        active_recoveries_count=len(active_cases),
        human_review_queue_count=human_queue,
        monthly_trend=trend_data,
        recovery_by_method=method_data,
        recovery_by_reason=reason_data,
        recovery_pipeline=pipeline
    )

    redis_service.set("dashboard:metrics", metrics.model_dump(), expire_seconds=15)
    return metrics


# 3. Payments
@router.get("/payments", response_model=List[PaymentSchema], tags=["Payments"])
def get_payments(
    status: Optional[str] = None,
    method: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status.upper())
    if method:
        query = query.filter(Payment.payment_method == method.upper())
    if search:
        query = query.join(Customer).filter(
            (Customer.name.ilike(f"%{search}%")) |
            (Payment.razorpay_payment_id.ilike(f"%{search}%")) |
            (Payment.failure_reason.ilike(f"%{search}%"))
        )
    return query.order_by(desc(Payment.created_at)).offset(offset).limit(limit).all()


@router.get("/payments/{payment_id}", response_model=PaymentSchema, tags=["Payments"])
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


# 4. Recovery Cases
@router.get("/recovery/cases", response_model=List[RecoveryCaseSchema], tags=["Recovery"])
def get_recovery_cases(
    status: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(RecoveryCase)
    if status:
        query = query.filter(RecoveryCase.status == status.upper())
    return query.order_by(desc(RecoveryCase.started_at)).limit(limit).all()


@router.get("/recovery/cases/{case_id}", response_model=RecoveryCaseSchema, tags=["Recovery"])
def get_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery Case not found")
    return case


# 5. Agent Activity
@router.get("/agent/activity", response_model=List[AgentActionSchema], tags=["AI Agents"])
def get_agent_activity(limit: int = Query(50, le=100), db: Session = Depends(get_db)):
    return db.query(AgentAction).order_by(desc(AgentAction.created_at)).limit(limit).all()


# 6. Guardrails
@router.get("/guardrails", response_model=GuardrailSchema, tags=["Guardrails"])
def get_guardrails(db: Session = Depends(get_db)):
    return guardrail_service.get_or_create_guardrails(db)


@router.put("/guardrails", response_model=GuardrailSchema, tags=["Guardrails"])
def update_guardrails(
    payload: GuardrailUpdateSchema,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    if current_user and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' is unauthorized to modify merchant guardrails. Admin required."
        )
    guardrail = guardrail_service.get_or_create_guardrails(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(guardrail, field, value)
    guardrail.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(guardrail)
    return guardrail


# 7. AI Analyze Payment
@router.post("/ai/analyze-payment", response_model=PaymentInvestigationResult, tags=["AI Agents"])
def analyze_payment(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    payment_id = payload.get("payment_id")
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment_id in request payload")
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment with ID '{payment_id}' not found")
    
    return investigator_agent.investigate(db, payment)


# 8. AI Analyze Customer Intent
@router.post("/ai/analyze-intent", response_model=CustomerIntentResult, tags=["AI Agents"])
def analyze_customer_intent(payload: CustomerIntentRequest, db: Session = Depends(get_db)):
    try:
        return intent_agent.analyze_intent(
            db=db,
            customer_id=payload.customer_id,
            message=payload.message,
            channel=payload.channel,
            recovery_case_id=payload.recovery_case_id
        )
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent analysis error: {str(e)}")


# 9. AI Generate Recovery Strategy (Phase 4)
@router.post("/ai/generate-strategy", response_model=RecoveryStrategyResult, tags=["AI Agents"])
def generate_recovery_strategy(payload: RecoveryStrategyRequest, db: Session = Depends(get_db)):
    try:
        return strategist_agent.generate_strategy(
            db=db,
            recovery_case_id=payload.recovery_case_id
        )
    except PrerequisiteContextMissingError as pre_err:
        raise HTTPException(status_code=409, detail=str(pre_err))
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy generation error: {str(e)}")


# 10. AI Copilot
@router.post("/ai/copilot", response_model=CopilotResponse, tags=["AI Agents"])
def ask_copilot(payload: CopilotRequest, db: Session = Depends(get_db)):
    """
    Phase 9: AI Recovery Copilot.
    Provides natural-language recovery intelligence strictly grounded in real database analytics.
    """
    query = payload.message or payload.prompt or ""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query message or prompt is required")
    return copilot_service.ask(query, db)


# 11. AI Decision Explanation & Opportunity Scoring
@router.get("/recovery/{case_id}/explanation", response_model=DecisionExplanationResponse, tags=["AI Agents"])
def get_decision_explanation(case_id: str, db: Session = Depends(get_db)):
    """
    Phase 9: Structured explainability for AI recovery decisions.
    Returns decision, reason, evidence, customer context, risk factors, guardrail result, and confidence.
    """
    try:
        return trace_service.get_decision_explanation(db, case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation error: {str(e)}")


@router.get("/recovery/{case_id}/opportunity", response_model=OpportunityScoreResponse, tags=["AI Agents"])
def get_case_opportunity_score(case_id: str, db: Session = Depends(get_db)):
    """
    Phase 9: Deterministic and explainable recovery opportunity scoring for a case.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")
    return opportunity_scoring_engine.calculate_score(case)


# 12. Agent Traces & Timeline
@router.get("/recovery/{case_id}/trace", response_model=AgentTraceResponse, tags=["Recovery Engine"])
def get_case_agent_trace(case_id: str, db: Session = Depends(get_db)):
    """
    Phase 9: Step-by-step agent trace timeline for a recovery run.
    Timeline: INVESTIGATE → INTENT → STRATEGY → GUARDRAIL → EXECUTE → SETTLE.
    """
    try:
        return trace_service.get_case_trace(db, case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trace error: {str(e)}")


@router.get("/recovery/traces", response_model=List[AgentTraceResponse], tags=["Recovery Engine"])
def get_recent_agent_traces(limit: int = 10, db: Session = Depends(get_db)):
    """
    Phase 9: Lists recent autonomous recovery execution traces.
    """
    return trace_service.get_recent_traces(db, limit=limit)


# 13. AI Recommended Actions
@router.get("/recovery/recommendations", response_model=List[AIRecommendationItem], tags=["Recovery Engine"])
def get_ai_recommendations(limit: int = 6, db: Session = Depends(get_db)):
    """
    Phase 9: Ranked AI Recommended Actions for Command Center.
    Ranked by expected revenue impact and recovery opportunity score.
    """
    return trace_service.get_recommendations(db, limit=limit)



# 9. Recovery Simulation (Exact Demo & Scenarios)
@router.post("/recovery/simulate", tags=["Recovery Engine"])
def simulate_recovery_pipeline(payload: SimulateRecoveryRequest, db: Session = Depends(get_db)):
    scenario = mock_payment_engine.SCENARIOS.get(payload.scenario_type, mock_payment_engine.SCENARIOS["DEMO_CARD_DECLINE_UPI"])

    # Find or create customer
    customer = db.query(Customer).filter(Customer.name == "Vikram Malhotra").first()
    if not customer:
        customer = db.query(Customer).first()

    # Create fresh failed payment
    payment_id = f"pay_sim_{uuid.uuid4().hex[:8]}"
    payment = Payment(
        id=payment_id,
        razorpay_payment_id=f"pay_RzP_{random.randint(100000, 999999)}",
        customer_id=customer.id,
        amount=payload.amount,
        currency="INR",
        payment_method=scenario["payment_method"],
        status=PaymentStatus.FAILED.value,
        failure_reason=scenario["failure_reason"],
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.flush()

    # Create recovery case
    case_id = f"rc_sim_{uuid.uuid4().hex[:8]}"
    case = RecoveryCase(
        id=case_id,
        payment_id=payment.id,
        recovery_score=0.0,
        recovery_probability=0.0,
        status=RecoveryStatus.IDENTIFIED.value,
        retry_count=0,
        recovered_amount=0.0,
        started_at=datetime.utcnow()
    )
    db.add(case)
    db.commit()

    # Broadcast simulated events for real-time live activity feed
    event_service.broadcast_sync(
        event_type="PAYMENT_FAILED",
        message=f"Payment failed for ₹{payment.amount:,.0f} ({scenario['payment_method']}: {scenario['failure_reason']})",
        case_id=case.id,
        payment_id=payment.id,
        amount=payment.amount
    )
    event_service.broadcast_sync(
        event_type="CASE_CREATED",
        message=f"Recovery case {case.id} created for {scenario['title']}",
        case_id=case.id,
        payment_id=payment.id,
        amount=payment.amount
    )

    # Run Multi-Agent Orchestrator Pipeline
    result = orchestrator.execute_recovery_pipeline(
        db=db,
        recovery_case_id=case.id,
        customer_reply_text="Yes, my card failed. Can I pay via UPI?"
    )

    event_service.broadcast_sync(
        event_type="RECOVERY_EXECUTED",
        message=f"Autonomous recovery pipeline completed for {case.id}",
        case_id=case.id,
        amount=payment.amount
    )

    return {
        "scenario": scenario["title"],
        "payment_id": payment.id,
        "case_id": case.id,
        "amount": payment.amount,
        "orchestration_result": result,
        "actions_count": len(case.actions)
    }


# 10. Execute, Approve, Reject Actions on Case (Phase 5 Tool Calling & Execution)
@router.post("/recovery/{case_id}/execute", response_model=ToolExecutionResult, tags=["Recovery Engine"])
def execute_case_recovery(
    case_id: str,
    payload: Optional[ToolExecutionRequest] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    if current_user and current_user.role not in [UserRole.ADMIN.value, UserRole.OPERATOR.value]:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' is not authorized to execute recovery tools. Operator or Admin required."
        )

    effective_key = idempotency_key or (payload.idempotency_key if payload else None)

    # 1. Check Idempotency Cache
    if effective_key:
        cached_record = IdempotencyService.get(db, effective_key)
        if cached_record:
            try:
                cached_data = json.loads(cached_record.result_json)
                return ToolExecutionResult(**cached_data)
            except Exception:
                pass

    # 2. Concurrency check: If already recovered, prevent double execution
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")
    if case.status == RecoveryStatus.RECOVERED.value:
        return ToolExecutionResult(
            execution_id=f"exec_settled_{case.id}",
            recovery_case_id=case.id,
            payment_id=case.payment_id,
            customer_id=case.payment.customer_id if case.payment else "",
            tool_type=ToolType.VERIFY_PAYMENT.value,
            status=ToolExecutionStatus.SUCCESS.value,
            success=True,
            message="Payment has already been successfully recovered and settled.",
            guardrail_status="SAFE",
            created_at=datetime.utcnow()
        )

    try:
        res = ToolExecutor.execute(
            db=db,
            recovery_case_id=case_id,
            tool_type=payload.tool_type if payload else None,
            parameters=payload.parameters if payload else None,
            idempotency_key=effective_key,
            approval_token=payload.approval_token if payload else None
        )
        if effective_key:
            IdempotencyService.save(
                db=db,
                key=effective_key,
                recovery_case_id=case_id,
                action_type="EXECUTE",
                status_code=200,
                result=res.model_dump()
            )
        event_service.broadcast_sync(
            event_type="RECOVERY_EXECUTED",
            message=f"Executed tool {res.tool_type} for case {case_id}",
            case_id=case_id,
            amount=res.amount,
            tool_type=res.tool_type
        )
        return res
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.post("/recovery/{case_id}/approve", response_model=ToolExecutionResult, tags=["Recovery Engine"])
def approve_recovery_case(
    case_id: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    if current_user and current_user.role not in [UserRole.ADMIN.value, UserRole.OPERATOR.value]:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' is not authorized to approve high-value cases. Operator or Admin required."
        )

    if idempotency_key:
        cached_record = IdempotencyService.get(db, idempotency_key)
        if cached_record:
            try:
                cached_data = json.loads(cached_record.result_json)
                return ToolExecutionResult(**cached_data)
            except Exception:
                pass

    try:
        res = ToolExecutor.approve_case(db=db, case_id=case_id)
        if idempotency_key:
            IdempotencyService.save(
                db=db,
                key=idempotency_key,
                recovery_case_id=case_id,
                action_type="APPROVE",
                status_code=200,
                result=res.model_dump()
            )
        event_service.broadcast_sync(
            event_type="RECOVERY_EXECUTED",
            message=f"Approved high-value recovery case {case_id}",
            case_id=case_id,
            amount=res.amount
        )
        return res
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Case approval execution failed: {str(e)}")


@router.post("/recovery/{case_id}/reject", tags=["Recovery Engine"])
def reject_recovery_case(
    case_id: str,
    reason: str = Body("Merchant rejected automated outreach", embed=True),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    if current_user and current_user.role not in [UserRole.ADMIN.value, UserRole.OPERATOR.value]:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' is not authorized to reject recovery cases."
        )
    try:
        res = ToolExecutor.reject_case(db=db, case_id=case_id, reason=reason)
        event_service.broadcast_sync(
            event_type="RECOVERY_BLOCKED",
            message=f"Recovery case {case_id} rejected: {reason}",
            case_id=case_id
        )
        return res
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Case rejection failed: {str(e)}")


# Confirm Payment Recovery (Used to simulate completion of payment link by customer)
@router.post("/recovery/{case_id}/confirm-settlement", tags=["Recovery Engine"])
def confirm_settlement(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    payment = case.payment
    payment.status = PaymentStatus.RECOVERED.value
    case.status = RecoveryStatus.RECOVERED.value
    case.recovered_amount = payment.amount
    case.completed_at = datetime.utcnow()
    payment.customer.total_successful_payments += 1

    action = AgentAction(
        id=f"act_{uuid.uuid4().hex[:8]}",
        recovery_case_id=case.id,
        agent_type=AgentType.TOOL_EXECUTOR.value,
        action_type=ActionType.PAYMENT_CONFIRMED.value,
        reasoning_summary=f"Razorpay Webhook: Payment #{payment.razorpay_payment_id} successfully settled via UPI. Revenue Recovered: ₹{payment.amount:,.2f}.",
        status=ActionStatus.EXECUTED.value,
        created_at=datetime.utcnow()
    )
    db.add(action)
    db.commit()

    # Broadcast settlement event
    event_service.broadcast_sync(
        event_type="PAYMENT_RECOVERED",
        message=f"Payment #{payment.razorpay_payment_id} recovered: ₹{payment.amount:,.2f} settled successfully",
        case_id=case.id,
        payment_id=payment.id,
        amount=payment.amount
    )

    # Clear dashboard cache
    redis_service.delete("dashboard:metrics")

    return {
        "status": "RECOVERED",
        "recovered_amount": case.recovered_amount,
        "payment_id": payment.id
    }


# ── Phase 6: Autonomous Recovery Orchestrator ────────────────────────────────

@router.post("/recovery/{case_id}/autonomous", response_model=AutonomousRecoveryResult, tags=["Recovery Engine"])
def run_autonomous_recovery(
    case_id: str,
    customer_message: Optional[str] = Body(default=None, embed=True,
                                           description="Optional customer message for intent analysis"),
    db: Session = Depends(get_db)
):
    """
    Phase 6: One-click Autonomous Recovery Pipeline.

    Sequences all 6 stages:
      INVESTIGATE → INTENT → STRATEGY → GUARDRAIL → EXECUTE → SETTLE

    Returns a fully-typed AutonomousRecoveryResult with per-step timing,
    guardrail audit, tool execution outcome, and executive summary.

    AI output is advisory; backend guardrails are always authoritative.
    """
    try:
        return orchestrator.run_autonomous_recovery(
            db=db,
            recovery_case_id=case_id,
            customer_message=customer_message
        )
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autonomous recovery pipeline error: {str(e)}")


@router.get("/recovery/{case_id}/autonomous/status", tags=["Recovery Engine"])
def get_autonomous_recovery_status(case_id: str, db: Session = Depends(get_db)):
    """
    Phase 6: Live status poll for an autonomous recovery case.
    Returns a lightweight status snapshot suitable for frontend polling.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    payment = case.payment
    recent_actions = [
        {
            "id": a.id,
            "agent_type": a.agent_type,
            "action_type": a.action_type,
            "status": a.status,
            "reasoning_summary": a.reasoning_summary,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in sorted(case.actions, key=lambda x: x.created_at, reverse=True)[:10]
    ]

    return {
        "case_id": case.id,
        "status": case.status,
        "recovery_score": case.recovery_score,
        "recovery_probability": case.recovery_probability,
        "current_strategy": case.current_strategy,
        "customer_intent": case.customer_intent,
        "payment_link_url": case.payment_link_url,
        "recovered_amount": case.recovered_amount,
        "retry_count": case.retry_count,
        "payment_amount": payment.amount if payment else None,
        "payment_method": payment.payment_method if payment else None,
        "actions_count": len(case.actions),
        "recent_actions": recent_actions,
        "started_at": case.started_at.isoformat() if case.started_at else None,
        "completed_at": case.completed_at.isoformat() if case.completed_at else None
    }


# 15. Reset Demo Environment
@router.post("/demo/reset", tags=["Demo Center"])
def reset_demo_environment(db: Session = Depends(get_db)):
    """
    Cleans up simulated test cases, resets merchant guardrails to baseline,
    and returns a clean slate for buildathon demonstrations.
    """
    from app.db.seed_data import reset_demo_data
    result = reset_demo_data(db)
    event_service.broadcast_sync(
        event_type="DEMO_RESET",
        message="Demo data and simulation environment reset to clean baseline",
        amount=0.0
    )
    return result

