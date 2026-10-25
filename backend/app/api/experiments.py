"""
PayRecover AI — Strategy Experimentation & Optimization REST API (Phase 6)
Provides complete lifecycle management, deterministic assignment inspection,
verified outcome metrics, hypothesis testing comparisons, offline simulations,
and audit exports with RBAC and pagination.
"""
import io
import csv
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.rbac import require_operator, require_viewer
from app.models.entities import (
    User,
    UserRole,
    RecoveryExperiment,
    ExperimentAssignment,
    ExperimentOutcomeAttribution,
    ExperimentStatus
)
from app.schemas.contracts import (
    ExperimentArmConfig,
    ExperimentCreateRequest,
    ExperimentUpdateRequest,
    ExperimentStatusTransitionRequest,
    ExperimentValidationResponse,
    ExperimentItemResponse,
    ExperimentAssignmentResponse,
    ExperimentMetricsResponse,
    OfflineSimulationRequest,
    OfflineSimulationResponse
)
from app.services.experiment_service import experiment_service

logger = logging.getLogger("payrecover.api.experiments")

router = APIRouter(prefix="/experiments", tags=["Recovery Strategy Experimentation"])


def _exp_to_response(exp: RecoveryExperiment) -> ExperimentItemResponse:
    """Helper to convert RecoveryExperiment ORM model to Pydantic schema."""
    arms_data = json.loads(exp.candidate_strategies_json or "[]")
    arms = [ExperimentArmConfig(**a) for a in arms_data]

    total_assignments = len(exp.assignments) if exp.assignments else 0
    terminal_outcomes = sum(
        1 for att in (exp.attributions or [])
        if att.outcome_status in ("RECOVERED", "UNSUCCESSFUL")
    )

    return ExperimentItemResponse(
        id=exp.id,
        name=exp.name,
        objective=exp.objective,
        hypothesis=exp.hypothesis,
        status=exp.status,
        version=exp.version,
        merchant_id=exp.merchant_id,
        owner_email=exp.owner_email,
        primary_metric=exp.primary_metric,
        is_sandbox_only=exp.is_sandbox_only,
        target_failure_categories=json.loads(exp.target_failure_categories_json or "[]"),
        target_payment_methods=json.loads(exp.target_payment_methods_json or "[]"),
        min_amount=exp.min_amount,
        max_amount=exp.max_amount,
        target_customer_intent=json.loads(exp.target_customer_intent_json or "[]"),
        candidate_strategies=arms,
        max_sample_size=exp.max_sample_size,
        min_observation_count=exp.min_observation_count,
        start_time=exp.start_time,
        end_time=exp.end_time,
        total_assignments=total_assignments,
        total_terminal_outcomes=terminal_outcomes,
        created_at=exp.created_at,
        updated_at=exp.updated_at
    )


# ============================================================================
# 1. LIST & QUERY EXPERIMENTS
# ============================================================================

@router.get("", response_model=Dict[str, Any])
def list_experiments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: DRAFT, READY, RUNNING, PAUSED, COMPLETED"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """List experiments with optional status and merchant filtering and pagination."""
    query = db.query(RecoveryExperiment)

    if status_filter:
        norm_status = status_filter.strip().upper()
        query = query.filter(RecoveryExperiment.status == norm_status)

    if merchant_id:
        query = query.filter(RecoveryExperiment.merchant_id == merchant_id)

    total = query.count()
    items = query.order_by(desc(RecoveryExperiment.created_at)).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
        "experiments": [_exp_to_response(exp) for exp in items]
    }


# ============================================================================
# 2. CREATE EXPERIMENT
# ============================================================================

@router.post("", response_model=ExperimentItemResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    request: ExperimentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Create a new recovery strategy experiment in DRAFT status.
    Requires ADMIN or OPERATOR role. Validates candidate arms, traffic sums, and criteria.
    """
    try:
        exp = experiment_service.create_experiment(
            db=db,
            request=request,
            owner_email=current_user.email
        )
        return _exp_to_response(exp)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"[API] Error creating experiment: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create experiment.")


# ============================================================================
# 3. GET EXPERIMENT BY ID
# ============================================================================

@router.get("/{experiment_id}", response_model=ExperimentItemResponse)
def get_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """Retrieve detailed experiment configuration and status."""
    exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment '{experiment_id}' not found.")
    return _exp_to_response(exp)


# ============================================================================
# 4. UPDATE EXPERIMENT
# ============================================================================

@router.put("/{experiment_id}", response_model=ExperimentItemResponse)
def update_experiment(
    experiment_id: str,
    request: ExperimentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Update configuration of a DRAFT or READY experiment.
    Increments experiment version. Requires ADMIN or OPERATOR role.
    """
    try:
        exp = experiment_service.update_experiment(
            db=db,
            experiment_id=experiment_id,
            request=request,
            updater_email=current_user.email
        )
        return _exp_to_response(exp)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"[API] Error updating experiment {experiment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update experiment.")


# ============================================================================
# 5. VALIDATE EXPERIMENT CONFIGURATION
# ============================================================================

@router.post("/{experiment_id}/validate", response_model=ExperimentValidationResponse)
def validate_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Validate experiment configuration and detect potential conflicts
    with other active RUNNING experiments before activation.
    """
    exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment '{experiment_id}' not found.")

    arms_raw = json.loads(exp.candidate_strategies_json or "[]")
    arms = [ExperimentArmConfig(**a) for a in arms_raw]

    return experiment_service.validate_configuration(
        db=db,
        candidate_strategies=arms,
        target_failure_categories=json.loads(exp.target_failure_categories_json or "[]"),
        target_payment_methods=json.loads(exp.target_payment_methods_json or "[]"),
        min_amount=exp.min_amount,
        max_amount=exp.max_amount,
        merchant_id=exp.merchant_id,
        exclude_experiment_id=exp.id
    )


# ============================================================================
# 6. STATUS TRANSITIONS (ACTIVATE / PAUSE / COMPLETE)
# ============================================================================

@router.post("/{experiment_id}/status", response_model=ExperimentItemResponse)
def transition_experiment_status(
    experiment_id: str,
    request: ExperimentStatusTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Transition experiment status (READY, RUNNING, PAUSED, COMPLETED).
    Requires ADMIN or OPERATOR role. Validates pre-conditions and conflict prevention.
    """
    try:
        exp = experiment_service.transition_status(
            db=db,
            experiment_id=experiment_id,
            target_status_str=request.target_status,
            operator_email=current_user.email,
            reason=request.reason
        )
        return _exp_to_response(exp)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"[API] Error transitioning status for experiment {experiment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to transition experiment status.")


# ============================================================================
# 7. ASSIGNMENTS INSPECTION
# ============================================================================

@router.get("/{experiment_id}/assignments", response_model=Dict[str, Any])
def get_experiment_assignments(
    experiment_id: str,
    arm_id: Optional[str] = Query(None, description="Filter assignments by arm ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """List paginated assignment records and attributed outcomes for an experiment."""
    exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment '{experiment_id}' not found.")

    query = db.query(ExperimentAssignment).filter(ExperimentAssignment.experiment_id == experiment_id)
    if arm_id:
        query = query.filter(ExperimentAssignment.arm_id == arm_id.strip())

    total = query.count()
    assignments = query.order_by(desc(ExperimentAssignment.assigned_at)).offset((page - 1) * limit).limit(limit).all()

    # Join attributions
    att_list = db.query(ExperimentOutcomeAttribution).filter(
        ExperimentOutcomeAttribution.experiment_id == experiment_id
    ).all()
    att_map = {att.assignment_id: att for att in att_list}

    results: List[ExperimentAssignmentResponse] = []
    for asgn in assignments:
        att = att_map.get(asgn.id)
        results.append(ExperimentAssignmentResponse(
            assignment_id=asgn.id,
            experiment_id=asgn.experiment_id,
            experiment_name=exp.name,
            experiment_version=asgn.experiment_version,
            recovery_case_id=asgn.recovery_case_id,
            payment_id=asgn.payment_id,
            arm_id=asgn.arm_id,
            assigned_strategy=asgn.assigned_strategy,
            is_control=asgn.is_control,
            hash_bucket=asgn.hash_bucket,
            assigned_at=asgn.assigned_at,
            actual_executed_strategy=att.actual_executed_strategy if att else None,
            is_strategy_deviated=att.is_strategy_deviated if att else False,
            deviation_reason=att.deviation_reason if att else None,
            outcome_status=att.outcome_status if att else "PENDING",
            is_verified=att.is_verified if att else False,
            recovered_amount=att.recovered_amount if att else 0.0,
            time_to_recovery_seconds=att.time_to_recovery_seconds if att else None,
            attributed_at=att.attributed_at if att else None
        ))

    return {
        "experiment_id": experiment_id,
        "total": total,
        "page": page,
        "limit": limit,
        "assignments": results
    }


# ============================================================================
# 8. EXPERIMENT STATISTICAL METRICS & COMPARISONS
# ============================================================================

@router.get("/{experiment_id}/metrics", response_model=ExperimentMetricsResponse)
def get_experiment_metrics(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve comprehensive statistical metrics comparing treatment arms vs control.
    Provides Wilson 95% confidence intervals, two-proportion hypothesis tests,
    sample-size integrity warnings, and guardrail deviation telemetry.
    """
    try:
        return experiment_service.calculate_experiment_metrics(db=db, experiment_id=experiment_id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as e:
        logger.error(f"[API] Error computing experiment metrics: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to calculate metrics.")


# ============================================================================
# 9. OFFLINE EXPERIMENT SIMULATION
# ============================================================================

@router.post("/{experiment_id}/simulate", response_model=OfflineSimulationResponse)
def simulate_experiment(
    experiment_id: str,
    request: OfflineSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Execute deterministic offline simulation for policy evaluation.
    Compares fixed-split allocation against adaptive Multi-Armed Bandit (Thompson Sampling).
    Clearly disclaimed as synthetic evaluation fixtures; never exposes real customers.
    """
    try:
        return experiment_service.run_offline_simulation(
            db=db,
            experiment_id=experiment_id,
            request=request
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as e:
        logger.error(f"[API] Error running offline simulation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute simulation.")


# ============================================================================
# 10. EXPORT EXPERIMENT TELEMETRY (CSV / JSON)
# ============================================================================

@router.get("/{experiment_id}/export")
def export_experiment_telemetry(
    experiment_id: str,
    format_type: str = Query("json", alias="format", description="Export format: json or csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Export sanitized experiment assignment and outcome telemetry.
    Excludes customer-sensitive PII. Useful for offline causal inference or audit.
    """
    exp = db.query(RecoveryExperiment).filter(RecoveryExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment '{experiment_id}' not found.")

    assignments = db.query(ExperimentAssignment).filter(ExperimentAssignment.experiment_id == experiment_id).all()
    attributions = {att.assignment_id: att for att in db.query(ExperimentOutcomeAttribution).filter(ExperimentOutcomeAttribution.experiment_id == experiment_id).all()}

    rows = []
    for asgn in assignments:
        att = attributions.get(asgn.id)
        rows.append({
            "assignment_id": asgn.id,
            "experiment_id": asgn.experiment_id,
            "experiment_version": asgn.experiment_version,
            "recovery_case_id": asgn.recovery_case_id,
            "arm_id": asgn.arm_id,
            "assigned_strategy": asgn.assigned_strategy,
            "is_control": asgn.is_control,
            "hash_bucket": asgn.hash_bucket,
            "assigned_at": asgn.assigned_at.isoformat(),
            "actual_executed_strategy": att.actual_executed_strategy if att else asgn.assigned_strategy,
            "is_strategy_deviated": att.is_strategy_deviated if att else False,
            "deviation_reason": att.deviation_reason if att else None,
            "outcome_status": att.outcome_status if att else "PENDING",
            "is_verified": att.is_verified if att else False,
            "recovered_amount": att.recovered_amount if att else 0.0,
            "time_to_recovery_seconds": att.time_to_recovery_seconds if att else None,
            "human_escalated": att.human_escalated if att else False,
            "retry_count": att.retry_count if att else 0
        })

    if format_type.lower() == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=experiment_{experiment_id}_export.csv"}
        )

    return {
        "experiment_id": exp.id,
        "experiment_name": exp.name,
        "exported_at": datetime.utcnow().isoformat(),
        "total_records": len(rows),
        "records": rows
    }
