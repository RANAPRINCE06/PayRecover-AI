import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.rbac import require_roles
from app.models.entities import (
    User,
    UserRole,
    RecoveryCase,
    Payment,
    RecoveryOutcome,
    RecoveryOutcomeStatus,
    MerchantGuardrail
)
from app.schemas.contracts import (
    OutcomeRecordResponse,
    OutcomeRecordListResponse,
    OutcomeSummaryStats,
    StrategyEvaluationResponse,
    CalibrationMetricsResponse,
    ExplainabilityResponse,
    StrategyCandidateEvaluation
)
from app.services.intelligence_service import (
    probability_estimator,
    strategy_evaluation_engine,
    outcome_service,
    HistoricalOutcomeEngine,
    normalize_strategy_name,
    amount_to_range
)
from app.services.guardrail_service import guardrail_service

logger = logging.getLogger("payrecover.api.intelligence")

router = APIRouter(prefix="/api/intelligence", tags=["Recovery Intelligence Engine"])


@router.get("/outcomes", response_model=OutcomeRecordListResponse)
def list_recovery_outcomes(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by outcome status (RECOVERED, UNSUCCESSFUL, PENDING, UNKNOWN)"),
    failure_category: Optional[str] = Query(None, description="Filter by failure category"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Paginated list of historical recovery attempts and verified outcomes.
    Sanitized: customer names and raw payment secrets are excluded to preserve customer privacy.
    """
    query = db.query(RecoveryOutcome)

    if status:
        query = query.filter(RecoveryOutcome.outcome_status == status.upper())
    if failure_category:
        query = query.filter(RecoveryOutcome.failure_category == failure_category.upper())
    if strategy:
        strat_canon = normalize_strategy_name(strategy)
        query = query.filter(RecoveryOutcome.selected_strategy == strat_canon)

    total = query.count()
    offset = (page - 1) * limit
    items = query.order_by(desc(RecoveryOutcome.decision_timestamp)).offset(offset).limit(limit).all()

    # Aggregate verified recovered count and volume
    verified_recovered = (
        db.query(RecoveryOutcome)
        .filter(RecoveryOutcome.outcome_status == RecoveryOutcomeStatus.RECOVERED.value)
        .all()
    )
    tot_rec_amount = sum(o.recovered_amount for o in verified_recovered)

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return OutcomeRecordListResponse(
        items=[OutcomeRecordResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        verified_recovered_count=len(verified_recovered),
        total_recovered_amount=round(tot_rec_amount, 2)
    )


@router.get("/outcomes/summary", response_model=OutcomeSummaryStats)
def get_outcomes_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns aggregated metrics over verified historical recovery outcomes.
    Clearly distinguishes observed recovery rates from model probability forecasts.
    """
    return outcome_service.get_summary_stats(db)


@router.get("/evaluate/{case_id}", response_model=StrategyEvaluationResponse)
def evaluate_case_strategies(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates all eligible recovery strategies for a specific case using historical evidence,
    Wilson confidence intervals, and calibrated model probabilities.
    Strictly enforces merchant guardrails.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")
    if not case.payment:
        raise HTTPException(status_code=400, detail=f"Case '{case_id}' has no associated payment record")

    # Ensure estimator is trained on available historical outcomes
    if not probability_estimator.is_trained:
        all_outcomes = db.query(RecoveryOutcome).all()
        probability_estimator.train_and_evaluate(all_outcomes)

    eval_result = strategy_evaluation_engine.evaluate_candidates(
        db=db,
        payment=case.payment,
        recovery_case=case,
        customer_intent=case.customer_intent
    )
    return eval_result


@router.get("/explain/{case_id}", response_model=ExplainabilityResponse)
def explain_case_decision(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explainability API endpoint.
    Provides transparent audit trail explaining why the strategy was chosen,
    relevant historical cohort sample size, observed vs estimated probabilities,
    alternative strategy comparisons, and active guardrails.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")
    if not case.payment:
        raise HTTPException(status_code=400, detail=f"Case '{case_id}' has no associated payment record")

    # Ensure estimator is trained
    if not probability_estimator.is_trained:
        all_outcomes = db.query(RecoveryOutcome).all()
        probability_estimator.train_and_evaluate(all_outcomes)

    eval_result = strategy_evaluation_engine.evaluate_candidates(
        db=db,
        payment=case.payment,
        recovery_case=case,
        customer_intent=case.customer_intent
    )

    top_candidate = eval_result.candidates[0] if eval_result.candidates else None
    recommended_strat = eval_result.recommended_strategy

    # Guardrails check
    guardrail: MerchantGuardrail = guardrail_service.get_or_create_guardrails(db)
    is_high_value = case.payment.amount >= guardrail.high_value_threshold
    approval_reason = None
    if is_high_value:
        approval_reason = f"Payment amount (₹{case.payment.amount:,.2f}) exceeds high-value threshold (₹{guardrail.high_value_threshold:,.2f}). Human authorization is mandatory."

    # Top contributing & risk factors
    top_contributing = []
    top_risks = []
    if case.payment.failure_reason in ("UPI_TIMEOUT", "TEMPORARY", "TECHNICAL"):
        top_contributing.append("Failure category indicates transient gateway latency rather than account insolvency.")
    elif case.payment.failure_reason in ("CARD_DECLINED", "AUTHENTICATION_FAILED"):
        top_risks.append("Issuing bank rejected card 3DS authentication.")

    if case.customer_intent:
        top_contributing.append(f"Inbound intent confirmed: '{case.customer_intent}'.")

    if case.retry_count and case.retry_count > 1:
        top_risks.append(f"Customer has already experienced {case.retry_count} failed retries.")

    disclaimer = (
        "Calibrated probabilities are generated via regularized logistic calibration and Wilson score confidence bounds "
        "trained strictly on chronological prior outcomes. Correlation does not imply guaranteed recovery."
    )

    return ExplainabilityResponse(
        recovery_case_id=case.id,
        payment_id=case.payment.id,
        recommended_strategy=recommended_strat,
        calibrated_probability=top_candidate.estimated_probability if top_candidate else eval_result.calibrated_probability,
        baseline_probability=eval_result.baseline_probability,
        historical_sample_size=top_candidate.sample_size if top_candidate else 0,
        observed_historical_rate=top_candidate.observed_recovery_rate if top_candidate else None,
        confidence_interval_95=top_candidate.confidence_interval_95 if top_candidate else [0.0, 0.0],
        uncertainty_level=top_candidate.uncertainty_level if top_candidate else "INSUFFICIENT_DATA",
        top_contributing_factors=top_contributing,
        top_risk_factors=top_risks,
        guardrails_active=eval_result.guardrail_details,
        human_approval_required=is_high_value,
        approval_reason=approval_reason,
        candidates_comparison=eval_result.candidates,
        model_version=probability_estimator.MODEL_VERSION,
        methodology_disclaimer=disclaimer,
        decision_timestamp=case.started_at or datetime.utcnow()
    )


@router.get("/calibration", response_model=CalibrationMetricsResponse)
def get_calibration_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns reproducible calibration and ranking evaluation metrics:
    Brier score against simple baseline, Brier Skill Score, ROC-AUC (Wilcoxon-Mann-Whitney),
    Expected Calibration Error (ECE), temporal holdout split, sample sizes, and limitations.
    """
    all_outcomes = db.query(RecoveryOutcome).all()
    metrics = probability_estimator.train_and_evaluate(all_outcomes)
    return metrics


@router.post("/recalibrate", response_model=CalibrationMetricsResponse)
def recalibrate_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.ANALYST]))
):
    """
    Triggers re-estimation of model weights and calibration curves using all available
    verified historical outcomes. Restricted to ADMIN and ANALYST roles.
    """
    all_outcomes = db.query(RecoveryOutcome).all()
    metrics = probability_estimator.train_and_evaluate(all_outcomes)
    logger.info(f"Model recalibration completed by {current_user.email}. Skill score: {metrics.brier_skill_score}")
    return metrics
