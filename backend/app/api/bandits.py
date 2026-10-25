"""PayRecover AI — Contextual Multi-Armed Bandits REST API (Phase 7).

Provides model inspection, shadow-mode decision audit telemetry,
interactive recommendation previews with feature attributions,
and off-policy evaluation (OPE) endpoints with strict RBAC.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.rbac import require_viewer, require_operator, require_admin
from app.models.entities import (
    User,
    UserRole,
    BanditPolicyConfig,
    BanditShadowDecision,
    Payment,
    RecoveryCase,
    MerchantGuardrail,
    Merchant
)
from app.schemas.contracts import (
    BanditPolicyStatusResponse,
    BanditRecommendationRequest,
    BanditRecommendationResponse,
    BanditShadowDecisionItem,
    BanditShadowDecisionsListResponse,
    BanditOfflineEvaluationRequest,
    BanditOfflineEvaluationResponse
)
from app.services.bandit_service import bandit_service, FEATURE_NAMES

logger = logging.getLogger("payrecover.api.bandits")

router = APIRouter(prefix="/bandits", tags=["Contextual Bandits"])


@router.get("/status", response_model=BanditPolicyStatusResponse)
def get_bandit_policy_status(
    merchant_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """Inspect active Contextual Bandit policy state, learned arm weights, and agreement metrics."""
    mid = merchant_id or getattr(current_user, "merchant_id", None) or "merch_demo_fintech"
    try:
        return bandit_service.get_policy_status(db, mid)
    except Exception as e:
        logger.exception(f"Error fetching bandit policy status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bandit status: {str(e)}"
        )


@router.get("/shadow-decisions", response_model=BanditShadowDecisionsListResponse)
def list_shadow_decisions(
    policy_version: Optional[str] = Query(default=None),
    is_agreement: Optional[bool] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """Retrieve paginated audit log of shadow-mode bandit decisions and agreement with production."""
    query = db.query(BanditShadowDecision)
    if policy_version:
        query = query.filter(BanditShadowDecision.policy_version == policy_version)
    if is_agreement is not None:
        query = query.filter(BanditShadowDecision.is_agreement == is_agreement)
    if outcome:
        query = query.filter(BanditShadowDecision.eventual_outcome == outcome.upper())

    total = query.count()
    total_all = db.query(BanditShadowDecision).count()
    agreed_all = db.query(BanditShadowDecision).filter(BanditShadowDecision.is_agreement.is_(True)).count()
    agreement_rate = (agreed_all / total_all * 100.0) if total_all > 0 else 100.0

    offset = (page - 1) * page_size
    records = query.order_by(desc(BanditShadowDecision.decision_timestamp)).offset(offset).limit(page_size).all()

    items = [
        BanditShadowDecisionItem(
            id=r.id,
            recovery_case_id=r.recovery_case_id,
            payment_id=r.payment_id,
            policy_version=r.policy_version,
            selected_action=r.selected_action,
            production_strategy=r.production_strategy,
            is_agreement=r.is_agreement,
            predicted_reward=r.predicted_reward,
            confidence_width=r.confidence_width,
            selection_reason=r.selection_reason,
            eventual_outcome=r.eventual_outcome,
            actual_reward=r.actual_reward,
            decision_timestamp=r.decision_timestamp
        )
        for r in records
    ]

    return BanditShadowDecisionsListResponse(
        items=items,
        total=total,
        agreement_rate=round(agreement_rate, 2),
        page=page,
        page_size=page_size
    )


@router.post("/recommend", response_model=BanditRecommendationResponse)
def get_bandit_recommendation(
    request: BanditRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """Interactive preview: queries LinUCB contextual recommendation for a case context
    without executing any action on live customers.
    """
    mid = getattr(current_user, "merchant_id", None) or "merch_demo_fintech"
    policy = bandit_service.get_or_create_policy(db, mid)

    # Mock or load payment entity for feature extraction
    payment = None
    case = None
    if request.case_id:
        case = db.query(RecoveryCase).filter(RecoveryCase.id == request.case_id).first()
        if case:
            payment = case.payment

    if not payment:
        payment = Payment(
            id="pay_preview_bandit",
            razorpay_payment_id="pay_rzp_preview",
            customer_id=request.customer_id or "cust_preview",
            amount=request.amount,
            currency="INR",
            payment_method=request.payment_method,
            failure_reason=request.failure_category
        )

    from app.services.guardrail_service import guardrail_service
    guardrail = guardrail_service.get_or_create_guardrails(db)

    # 1. Feature extraction
    feat_vec = bandit_service.extract_context_features(db, payment, case)
    x = bandit_service.context_vector_to_numpy(feat_vec)

    # 2. Safe action envelope
    eligible_actions, guardrail_overrides = bandit_service.get_safe_eligible_actions(payment, guardrail, case)

    # 3. LinUCB prediction
    predictions = bandit_service.predict_ucb(policy, x, eligible_actions)
    best_action = max(eligible_actions, key=lambda a: (predictions[a]["ucb_score"], a))
    pred_meta = predictions[best_action]

    # Feature attributions
    theta = pred_meta["theta"]
    x_flat = x.flatten()
    contributions = {FEATURE_NAMES[i]: round(float(theta[i] * x_flat[i]), 4) for i in range(len(FEATURE_NAMES))}

    reason = (
        f"LinUCB selected {best_action} with expected reward {pred_meta['expected_reward']:.2f} "
        f"and exploration width {pred_meta['confidence_width']:.2f} (UCB: {pred_meta['ucb_score']:.2f})."
    )
    if guardrail_overrides:
        reason += f" Enforced guardrails: {'; '.join(guardrail_overrides)}"

    return BanditRecommendationResponse(
        policy_version=policy.version,
        selected_action=best_action,
        predicted_reward=pred_meta["expected_reward"],
        confidence_width=pred_meta["confidence_width"],
        ucb_score=pred_meta["ucb_score"],
        eligible_actions=eligible_actions,
        selection_reason=reason,
        feature_attributions=contributions,
        is_shadow_mode=policy.is_shadow_mode,
        guardrail_overrides=guardrail_overrides
    )


@router.post("/evaluate", response_model=BanditOfflineEvaluationResponse)
def evaluate_bandit_offline(
    request: BanditOfflineEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """Runs offline policy evaluation (OPE) comparing LinUCB vs Historical-Best vs Epsilon-Greedy vs Oracle
    over verified historical outcomes using temporal split.
    """
    try:
        return bandit_service.run_offline_evaluation(db, request)
    except Exception as e:
        logger.exception(f"Error in offline evaluation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Offline evaluation failed: {str(e)}"
        )


@router.post("/parameters")
def update_policy_parameters(
    alpha: float = Query(default=1.0, ge=0.0, le=5.0),
    ridge_lambda: float = Query(default=1.0, ge=0.1, le=10.0),
    merchant_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin-only: updates exploration parameter alpha and ridge regularization lambda."""
    mid = merchant_id or getattr(current_user, "merchant_id", None) or "merch_demo_fintech"
    policy = bandit_service.get_or_create_policy(db, mid)
    policy.alpha_exploration = alpha
    policy.ridge_lambda = ridge_lambda
    policy.updated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Updated policy {policy.id} parameters: alpha={alpha}, ridge_lambda={ridge_lambda}",
        "policy_id": policy.id,
        "alpha_exploration": alpha,
        "ridge_lambda": ridge_lambda
    }
