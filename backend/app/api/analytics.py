"""
Phase 7 Analytics API
All queries run against existing SQLAlchemy models.
Results are cached in Redis where applicable.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, case as sa_case

from app.db.session import get_db
from app.models.entities import (
    Payment, RecoveryCase, AgentAction, Customer,
    ToolExecution, HumanApproval,
    PaymentStatus, RecoveryStatus, ActionStatus
)
from app.services.redis_service import redis_service

logger = logging.getLogger("payrecover.analytics")
router = APIRouter()


# ─── helpers ─────────────────────────────────────────────────────────────────

def _cached(key: str, ttl: int = 30):
    """Return cached value or None."""
    return redis_service.get(key)


def _set_cache(key: str, value: Any, ttl: int = 30):
    redis_service.set(key, value, expire_seconds=ttl)


# ─── 1. Overview ─────────────────────────────────────────────────────────────

@router.get("/overview", tags=["Analytics"])
def get_analytics_overview(db: Session = Depends(get_db)):
    """
    Aggregated KPIs computed from the live database.
    Cached for 30 seconds.
    """
    cached = _cached("analytics:overview")
    if cached:
        return cached

    all_payments = db.query(Payment).all()
    failed_payments = [p for p in all_payments if p.status == PaymentStatus.FAILED.value]
    recovered_payments = [p for p in all_payments if p.status == PaymentStatus.RECOVERED.value]

    total_volume = sum(p.amount for p in all_payments)
    revenue_at_risk = sum(p.amount for p in failed_payments)

    all_cases = db.query(RecoveryCase).all()
    recovered_cases = [c for c in all_cases if c.status == RecoveryStatus.RECOVERED.value]
    active_cases = [
        c for c in all_cases
        if c.status not in (
            RecoveryStatus.RECOVERED.value,
            RecoveryStatus.FAILED.value,
            RecoveryStatus.EXPIRED.value
        )
    ]
    awaiting_approval = [c for c in all_cases if c.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value]

    revenue_recovered = sum(
        (c.recovered_amount or (c.payment.amount if c.payment else 0))
        for c in recovered_cases
    )
    predicted_recoverable = sum(
        (c.recovery_probability * c.payment.amount)
        for c in active_cases
        if c.payment and c.recovery_probability
    )

    total_at_risk_and_recovered = revenue_at_risk + revenue_recovered
    recovery_rate = (
        (revenue_recovered / total_at_risk_and_recovered * 100)
        if total_at_risk_and_recovered > 0 else 0.0
    )

    scores = [c.recovery_score for c in all_cases if c.recovery_score and c.recovery_score > 0]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    total_actions = db.query(AgentAction).count()
    executed_actions = db.query(AgentAction).filter(
        AgentAction.status == ActionStatus.EXECUTED.value
    ).count()
    automation_rate = (executed_actions / total_actions * 100) if total_actions > 0 else 0.0

    all_retries = sum(c.retry_count for c in all_cases)

    result = {
        "revenue_processed": round(total_volume, 2),
        "revenue_at_risk": round(revenue_at_risk, 2),
        "revenue_recovered": round(revenue_recovered, 2),
        "predicted_recoverable": round(predicted_recoverable, 2),
        "recovery_rate": round(recovery_rate, 1),
        "failed_payments_count": len(failed_payments),
        "recovered_payments_count": len(recovered_payments),
        "active_cases_count": len(active_cases),
        "recovered_cases_count": len(recovered_cases),
        "awaiting_approval_count": len(awaiting_approval),
        "total_cases": len(all_cases),
        "average_recovery_score": round(avg_score, 1),
        "total_recovery_attempts": all_retries,
        "ai_automation_rate": round(automation_rate, 1),
        "total_agent_actions": total_actions,
    }

    _set_cache("analytics:overview", result, ttl=30)
    return result


# ─── 2. Trends ────────────────────────────────────────────────────────────────

@router.get("/trends", tags=["Analytics"])
def get_analytics_trends(
    period: str = Query("7d", description="7d, 30d, or 90d"),
    db: Session = Depends(get_db)
):
    """
    Recovery trend grouped by day for the requested period.
    """
    cache_key = f"analytics:trends:{period}"
    cached = _cached(cache_key)
    if cached:
        return cached

    days_map = {"7d": 7, "30d": 30, "90d": 90}
    num_days = days_map.get(period, 7)
    since = datetime.utcnow() - timedelta(days=num_days)

    payments = db.query(Payment).filter(Payment.created_at >= since).all()

    daily: Dict[str, Dict] = {}
    for i in range(num_days):
        day = (datetime.utcnow() - timedelta(days=num_days - 1 - i)).strftime("%Y-%m-%d")
        daily[day] = {"date": day, "failed": 0, "recovered": 0, "at_risk": 0.0, "recovered_amount": 0.0}

    for p in payments:
        day = p.created_at.strftime("%Y-%m-%d")
        if day not in daily:
            continue
        if p.status == PaymentStatus.FAILED.value:
            daily[day]["failed"] += 1
            daily[day]["at_risk"] = round(daily[day]["at_risk"] + p.amount, 2)
        elif p.status == PaymentStatus.RECOVERED.value:
            daily[day]["recovered"] += 1
            daily[day]["recovered_amount"] = round(daily[day]["recovered_amount"] + p.amount, 2)

    result = {"period": period, "days": num_days, "data": list(daily.values())}
    _set_cache(cache_key, result, ttl=60)
    return result


# ─── 3. Failure Breakdown ─────────────────────────────────────────────────────

@router.get("/failures", tags=["Analytics"])
def get_failure_analytics(db: Session = Depends(get_db)):
    """
    Failure breakdown by reason and payment method.
    """
    cached = _cached("analytics:failures")
    if cached:
        return cached

    failed_payments = db.query(Payment).filter(Payment.status == PaymentStatus.FAILED.value).all()
    recovered_payments = db.query(Payment).filter(Payment.status == PaymentStatus.RECOVERED.value).all()

    # Group by failure reason
    reason_stats: Dict[str, Dict] = {}
    for p in failed_payments:
        reason = p.failure_reason or "UNKNOWN"
        if reason not in reason_stats:
            reason_stats[reason] = {"reason": reason, "count": 0, "amount": 0.0, "recovered": 0, "recovered_amount": 0.0}
        reason_stats[reason]["count"] += 1
        reason_stats[reason]["amount"] = round(reason_stats[reason]["amount"] + p.amount, 2)

    for p in recovered_payments:
        reason = p.failure_reason or "UNKNOWN"
        if reason not in reason_stats:
            reason_stats[reason] = {"reason": reason, "count": 0, "amount": 0.0, "recovered": 0, "recovered_amount": 0.0}
        reason_stats[reason]["recovered"] += 1
        reason_stats[reason]["recovered_amount"] = round(reason_stats[reason]["recovered_amount"] + p.amount, 2)

    by_reason = []
    for r, s in reason_stats.items():
        total = s["count"] + s["recovered"]
        rate = round((s["recovered"] / total * 100) if total > 0 else 0, 1)
        by_reason.append({**s, "recovery_rate": rate, "total_transactions": total})

    by_reason.sort(key=lambda x: x["count"], reverse=True)

    # Group by payment method
    method_stats: Dict[str, Dict] = {}
    for p in failed_payments + recovered_payments:
        method = p.payment_method or "UNKNOWN"
        if method not in method_stats:
            method_stats[method] = {"method": method, "failed": 0, "recovered": 0, "failed_amount": 0.0, "recovered_amount": 0.0}
        if p.status == PaymentStatus.FAILED.value:
            method_stats[method]["failed"] += 1
            method_stats[method]["failed_amount"] = round(method_stats[method]["failed_amount"] + p.amount, 2)
        else:
            method_stats[method]["recovered"] += 1
            method_stats[method]["recovered_amount"] = round(method_stats[method]["recovered_amount"] + p.amount, 2)

    by_method = []
    for m, s in method_stats.items():
        total = s["failed"] + s["recovered"]
        rate = round((s["recovered"] / total * 100) if total > 0 else 0, 1)
        by_method.append({**s, "recovery_rate": rate, "total": total})
    by_method.sort(key=lambda x: x["failed"], reverse=True)

    result = {"by_reason": by_reason, "by_method": by_method}
    _set_cache("analytics:failures", result, ttl=60)
    return result


# ─── 4. Payment Method Analytics ──────────────────────────────────────────────

@router.get("/payment-methods", tags=["Analytics"])
def get_payment_method_analytics(db: Session = Depends(get_db)):
    """Recovery metrics grouped by payment method."""
    cached = _cached("analytics:payment_methods")
    if cached:
        return cached

    all_payments = db.query(Payment).all()
    stats: Dict[str, Dict] = {}

    for p in all_payments:
        method = p.payment_method or "UNKNOWN"
        if method not in stats:
            stats[method] = {
                "method": method, "total": 0, "failed": 0, "recovered": 0,
                "total_amount": 0.0, "failed_amount": 0.0, "recovered_amount": 0.0
            }
        stats[method]["total"] += 1
        stats[method]["total_amount"] = round(stats[method]["total_amount"] + p.amount, 2)
        if p.status == PaymentStatus.FAILED.value:
            stats[method]["failed"] += 1
            stats[method]["failed_amount"] = round(stats[method]["failed_amount"] + p.amount, 2)
        elif p.status == PaymentStatus.RECOVERED.value:
            stats[method]["recovered"] += 1
            stats[method]["recovered_amount"] = round(stats[method]["recovered_amount"] + p.amount, 2)

    result_list = []
    for s in stats.values():
        total_fail_rec = s["failed"] + s["recovered"]
        rate = round((s["recovered"] / total_fail_rec * 100) if total_fail_rec > 0 else 0, 1)
        result_list.append({**s, "recovery_rate": rate})

    result_list.sort(key=lambda x: x["failed"], reverse=True)
    result = {"methods": result_list}
    _set_cache("analytics:payment_methods", result, ttl=60)
    return result


# ─── 5. Customer Segment Analytics ───────────────────────────────────────────

@router.get("/customer-segments", tags=["Analytics"])
def get_customer_segment_analytics(db: Session = Depends(get_db)):
    """Analytics grouped by customer_value segment."""
    cached = _cached("analytics:customer_segments")
    if cached:
        return cached

    customers = db.query(Customer).all()
    segments: Dict[str, Dict] = {}

    for c in customers:
        seg = c.customer_value or "STANDARD"
        if seg not in segments:
            segments[seg] = {
                "segment": seg, "customer_count": 0, "failed_payments": 0,
                "total_failed_amount": 0.0, "recovered_amount": 0.0, "recovered_count": 0
            }
        segments[seg]["customer_count"] += 1

        for p in c.payments:
            if p.status == PaymentStatus.FAILED.value:
                segments[seg]["failed_payments"] += 1
                segments[seg]["total_failed_amount"] = round(
                    segments[seg]["total_failed_amount"] + p.amount, 2
                )
            elif p.status == PaymentStatus.RECOVERED.value:
                segments[seg]["recovered_count"] += 1
                segments[seg]["recovered_amount"] = round(
                    segments[seg]["recovered_amount"] + p.amount, 2
                )

    result_list = []
    for s in segments.values():
        total = s["failed_payments"] + s["recovered_count"]
        rate = round((s["recovered_count"] / total * 100) if total > 0 else 0, 1)
        result_list.append({**s, "recovery_rate": rate})

    result_list.sort(key=lambda x: x["total_failed_amount"], reverse=True)
    result = {"segments": result_list}
    _set_cache("analytics:customer_segments", result, ttl=60)
    return result


# ─── 6. Strategy Performance ──────────────────────────────────────────────────

@router.get("/strategies", tags=["Analytics"])
def get_strategy_analytics(db: Session = Depends(get_db)):
    """Performance analytics for each recovery strategy type."""
    cached = _cached("analytics:strategies")
    if cached:
        return cached

    cases = db.query(RecoveryCase).all()
    strategies: Dict[str, Dict] = {}

    for c in cases:
        strat = c.current_strategy or "UNKNOWN"
        if strat not in strategies:
            strategies[strat] = {
                "strategy": strat,
                "attempts": 0,
                "recovered": 0,
                "recovered_amount": 0.0,
                "total_recovery_probability": 0.0
            }
        strategies[strat]["attempts"] += 1
        strategies[strat]["total_recovery_probability"] += (c.recovery_probability or 0)

        if c.status == RecoveryStatus.RECOVERED.value:
            strategies[strat]["recovered"] += 1
            if c.payment:
                amt = c.recovered_amount or c.payment.amount
                strategies[strat]["recovered_amount"] = round(
                    strategies[strat]["recovered_amount"] + amt, 2
                )

    result_list = []
    for s in strategies.values():
        rate = round((s["recovered"] / s["attempts"] * 100) if s["attempts"] > 0 else 0, 1)
        avg_prob = round(
            (s["total_recovery_probability"] / s["attempts"] * 100) if s["attempts"] > 0 else 0, 1
        )
        result_list.append({
            "strategy": s["strategy"],
            "attempts": s["attempts"],
            "recovered": s["recovered"],
            "success_rate": rate,
            "recovered_amount": s["recovered_amount"],
            "avg_recovery_probability": avg_prob
        })

    result_list.sort(key=lambda x: x["attempts"], reverse=True)
    result = {"strategies": result_list}
    _set_cache("analytics:strategies", result, ttl=60)
    return result


# ─── 7. Recovery Opportunities ────────────────────────────────────────────────

@router.get("/opportunities", tags=["Analytics"])
def get_recovery_opportunities(
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db)
):
    """
    High-probability recovery opportunities from active cases.
    Sorted by (recovery_probability * amount) descending.
    """
    cached = _cached("analytics:opportunities")
    if cached:
        cached_list = cached.get("opportunities", [])
        return {"opportunities": cached_list[:limit]}

    active_cases = db.query(RecoveryCase).filter(
        RecoveryCase.status.notin_([
            RecoveryStatus.RECOVERED.value,
            RecoveryStatus.FAILED.value,
            RecoveryStatus.EXPIRED.value
        ])
    ).all()

    opportunities = []
    for c in active_cases:
        if not c.payment:
            continue
        p = c.payment
        customer = p.customer
        prob = float(c.recovery_probability or 0)
        score = float(c.recovery_score or 0)
        expected_value = round(prob * p.amount, 2)

        # Determine guardrail status hint
        guardrail_hint = "SAFE"
        if c.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value:
            guardrail_hint = "APPROVAL_REQUIRED"

        opportunities.append({
            "case_id": c.id,
            "payment_id": p.id,
            "customer_id": customer.id if customer else None,
            "customer_name": customer.name if customer else "Unknown",
            "amount": p.amount,
            "currency": p.currency,
            "payment_method": p.payment_method,
            "failure_reason": p.failure_reason,
            "recovery_probability": prob,
            "recovery_score": score,
            "expected_recovery_value": expected_value,
            "current_strategy": c.current_strategy,
            "customer_intent": c.customer_intent,
            "status": c.status,
            "guardrail_hint": guardrail_hint,
            "started_at": c.started_at.isoformat() if c.started_at else None,
        })

    opportunities.sort(key=lambda x: x["expected_recovery_value"], reverse=True)
    result = {"opportunities": opportunities}
    _set_cache("analytics:opportunities", result, ttl=30)
    return {"opportunities": opportunities[:limit]}
