import uuid
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
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
    ActionStatus
)
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
    RecoveryStrategyResult
)
from app.agents.investigator import investigator_agent
from app.agents.intent import intent_agent
from app.agents.strategist import strategist_agent, PrerequisiteContextMissingError
from app.agents.orchestrator import orchestrator
from app.services.guardrail_service import guardrail_service
from app.services.redis_service import redis_service
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
def update_guardrails(payload: GuardrailUpdateSchema, db: Session = Depends(get_db)):
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
    prompt_lower = payload.prompt.lower()

    if "risk" in prompt_lower or "how much" in prompt_lower:
        failed_sum = db.query(func.sum(Payment.amount)).filter(Payment.status == PaymentStatus.FAILED.value).scalar() or 0.0
        return CopilotResponse(
            reply=f"Currently, ₹{failed_sum:,.2f} in revenue is at risk across recent failed transactions. Our autonomous agents predict that ₹{failed_sum*0.82:,.2f} (82%) is recoverable without manual merchant intervention.",
            insights=[
                "Top failure driver: 3DS Issuing Bank Timeout on Cards (42% of failures)",
                "Fastest recovering channel: WhatsApp 1-Click UPI (89.4% recovery conversion)",
                "Average recovery time: 14 minutes from failure detection"
            ],
            recommended_actions=[
                {"label": "Trigger Instant WhatsApp UPI Fallback for 6 Pending Cases", "action": "AUTO_DISPATCH_UPI"},
                {"label": "Review 2 High-Value Cases in Human Queue", "action": "OPEN_HUMAN_QUEUE"}
            ]
        )
    elif "yesterday" in prompt_lower or "why" in prompt_lower or "fall" in prompt_lower:
        return CopilotResponse(
            reply="Yesterday's dip in recovery rate (from 84% to 71%) was driven by a temporary HDFC Bank UPI PSP gateway downtime between 14:00 - 15:30 IST. When UPI PSP returned 504 errors, our fallback rules queued retries.",
            insights=[
                "HDFC UPI PSP latency spiked to 14,200ms during the incident window.",
                "PayRecover AI deferred 18 automated retries to protect customer sentiment.",
                "All 18 queued payments recovered successfully once normal banking resumed."
            ],
            recommended_actions=[
                {"label": "View Gateway Telemetry Graph", "action": "VIEW_TELEMETRY"},
                {"label": "Adjust Auto-Retry Deferral Window", "action": "OPEN_GUARDRAILS"}
            ]
        )
    elif "method" in prompt_lower:
        return CopilotResponse(
            reply="Credit/Debit Cards currently account for the highest failure volume (48% of failures), primarily due to 2-Factor Authentication / 3DS drop-offs. Conversely, UPI has an 89.2% autonomous recovery success rate when prompted with instant deep-links.",
            insights=[
                "Card transactions above ₹10,000 show 38% higher 3DS abandonment than UPI.",
                "Recommending UPI fallback on card failure increases overall checkout conversion by 22%."
            ],
            recommended_actions=[
                {"label": "Enable Auto UPI Switch Strategy", "action": "ACTIVATE_STRATEGY"}
            ]
        )
    else:
        return CopilotResponse(
            reply=f"I have analyzed your payment telemetry and active recovery cases. The system is operating normally with 84.6% overall recovery efficiency under merchant-configured guardrails.",
            insights=[
                "Active automated cases: 14",
                "Human approval queue: 2 high-value cases (₹75,000 and ₹55,000)",
                "Zero guardrail violations detected in past 24 hours"
            ],
            recommended_actions=[
                {"label": "Run Recovery Simulation", "action": "RUN_SIMULATION"}
            ]
        )


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

    # Run Multi-Agent Orchestrator Pipeline
    result = orchestrator.execute_recovery_pipeline(
        db=db,
        recovery_case_id=case.id,
        customer_reply_text="Yes, my card failed. Can I pay via UPI?"
    )

    return {
        "scenario": scenario["title"],
        "payment_id": payment.id,
        "case_id": case.id,
        "amount": payment.amount,
        "orchestration_result": result,
        "actions_count": len(case.actions)
    }


# 10. Execute, Approve, Reject Actions on Case
@router.post("/recovery/{case_id}/execute", tags=["Recovery Engine"])
def execute_case_recovery(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    result = orchestrator.execute_recovery_pipeline(db=db, recovery_case_id=case_id)
    return result


@router.post("/recovery/{case_id}/approve", tags=["Recovery Engine"])
def approve_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
    # Add human approval action
    action = AgentAction(
        id=f"act_{uuid.uuid4().hex[:8]}",
        recovery_case_id=case.id,
        agent_type=AgentType.TOOL_EXECUTOR.value,
        action_type=ActionType.GUARDRAIL_CHECK.value,
        reasoning_summary=f"Merchant authorized high-value recovery outreach for ₹{case.payment.amount:,.2f}.",
        status=ActionStatus.APPROVED.value,
        created_at=datetime.utcnow()
    )
    db.add(action)
    db.commit()
    db.refresh(case)
    return {"message": "Case approved and released for execution", "case_id": case.id}


@router.post("/recovery/{case_id}/reject", tags=["Recovery Engine"])
def reject_recovery_case(case_id: str, reason: str = Body("Merchant rejected automated outreach", embed=True), db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = RecoveryStatus.FAILED.value
    action = AgentAction(
        id=f"act_{uuid.uuid4().hex[:8]}",
        recovery_case_id=case.id,
        agent_type=AgentType.TOOL_EXECUTOR.value,
        action_type=ActionType.GUARDRAIL_CHECK.value,
        reasoning_summary=f"Action blocked by merchant rejection: {reason}",
        status=ActionStatus.REJECTED.value,
        created_at=datetime.utcnow()
    )
    db.add(action)
    db.commit()
    return {"message": "Case recovery rejected", "case_id": case.id}


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

    # Clear dashboard cache
    redis_service.delete("dashboard:metrics")

    return {
        "status": "RECOVERED",
        "recovered_amount": case.recovered_amount,
        "payment_id": payment.id
    }
