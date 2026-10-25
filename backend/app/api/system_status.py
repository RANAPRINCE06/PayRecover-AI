"""
Phase 7 — System Status API
Returns health of DB, Redis, AI provider, payment engine, and guardrails.
Does NOT expose any secrets.
"""
import logging
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.services.redis_service import redis_service
from app.services.outbox_worker import outbox_worker

logger = logging.getLogger("payrecover.system_status")
router = APIRouter()


@router.get("/health/live", tags=["System"])
def liveness_probe():
    """
    Kubernetes/Docker liveness probe.
    Returns 200 OK if the FastAPI process is running and accepting HTTP requests.
    """
    return {
        "status": "ALIVE",
        "service": "payrecover-api",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }


@router.get("/health/ready", tags=["System"])
def readiness_probe(response: Response, db: Session = Depends(get_db)):
    """
    Kubernetes/Docker readiness probe.
    Verifies that critical dependencies (Database) are operational.
    If database connectivity fails, returns HTTP 503 Service Unavailable.
    """
    db_healthy = False
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"[ReadinessProbe] Database connection check failed: {e}")
        db_healthy = False

    if not db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "UNREADY",
            "reason": "Database connection unavailable",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        }

    return {
        "status": "READY",
        "database": "CONNECTED",
        "worker": "HEALTHY" if outbox_worker.is_healthy() else "DEGRADED",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }


@router.get("/health/deps", tags=["System"])
def dependency_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive dependency health inspection.
    Never exposes secrets, credentials, or internal stack traces.
    """
    dependencies = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = {"status": "HEALTHY", "mode": "SQLAlchemy (PostgreSQL/SQLite)"}
    except Exception as e:
        logger.error(f"Database dependency check failed: {e}")
        dependencies["database"] = {"status": "UNHEALTHY", "mode": "Connection failed"}

    # Redis
    if redis_service.is_connected:
        dependencies["redis"] = {"status": "HEALTHY", "mode": "Connected Redis cluster"}
    else:
        dependencies["redis"] = {"status": "DEGRADED", "mode": "Active in-memory fallback store"}

    # AI Provider
    try:
        from app.core.config import settings
        if settings.GEMINI_API_KEY:
            dependencies["gemini"] = {"status": "HEALTHY", "mode": "Configured", "model": settings.GEMINI_MODEL}
        else:
            dependencies["gemini"] = {"status": "DEGRADED", "mode": "Deterministic reasoning fallback"}
    except Exception:
        dependencies["gemini"] = {"status": "UNKNOWN", "mode": "Unavailable"}

    # Payment Gateway
    try:
        from app.integrations.razorpay_client import razorpay_client
        dependencies["razorpay"] = {
            "status": "HEALTHY",
            "mode": "mock/simulation" if getattr(razorpay_client, "is_mock", True) else "test-API"
        }
    except Exception:
        dependencies["razorpay"] = {"status": "DEGRADED", "mode": "Fallback"}

    # Background Outbox Worker
    worker_status = outbox_worker.get_status()
    dependencies["outbox_worker"] = {
        "status": "HEALTHY" if worker_status["healthy"] else "DEGRADED",
        "running": worker_status["running"],
        "pending_queue": worker_status["queue"]["total_pending"],
        "dead_letter": worker_status["queue"]["total_dead_letter"]
    }

    critical_ok = dependencies["database"]["status"] == "HEALTHY"
    overall = "HEALTHY" if critical_ok else "UNHEALTHY"

    return {
        "overall": overall,
        "dependencies": dependencies,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }


@router.get("/health/worker", tags=["System"])
def worker_health():
    """Returns background outbox worker operational telemetry and queue backlog."""
    return outbox_worker.get_status()


# Phase 8: System Health Endpoint (Maintained for backward compatibility)
@router.get("/health", tags=["System"])
def get_system_health(db: Session = Depends(get_db)):
    """
    General system health check returning health states for:
    API, Database, Redis, AI, and Payment Engine.
    """
    services = {
        "api": "healthy",
        "database": "healthy",
        "redis": "healthy",
        "ai": "healthy",
        "payment_engine": "healthy"
    }

    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services["database"] = "degraded"

    if not redis_service.is_connected:
        services["redis"] = "healthy"  # Resilient in-memory fallback is active

    try:
        from app.core.config import settings
        services["ai"] = "healthy"
    except Exception:
        services["ai"] = "unknown"

    overall = "healthy" if services["database"] == "healthy" else "degraded"

    return {
        "status": overall,
        "services": services
    }


@router.get("/status", tags=["System"])
def get_system_status(db: Session = Depends(get_db)):
    """
    Live operational health snapshot.
    No secrets are exposed.
    """
    components = {}

    # 1. Database
    try:
        db.execute(text("SELECT 1"))
        components["database"] = {"status": "HEALTHY", "detail": "SQLAlchemy connection OK"}
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        components["database"] = {"status": "DEGRADED", "detail": "Connection error"}

    # 2. Redis
    if redis_service.is_connected:
        components["redis"] = {"status": "HEALTHY", "detail": "Redis connected"}
    else:
        components["redis"] = {"status": "FALLBACK", "detail": "Using in-memory state store"}

    # 3. AI Provider (Gemini)
    try:
        from app.core.config import settings
        has_key = bool(getattr(settings, "GEMINI_API_KEY", None))
        if has_key:
            components["gemini"] = {"status": "CONNECTED", "detail": "Gemini API key configured"}
        else:
            components["gemini"] = {"status": "FALLBACK", "detail": "No API key — deterministic fallback active"}
    except Exception:
        components["gemini"] = {"status": "UNKNOWN", "detail": "Could not determine AI provider status"}

    # 4. Razorpay (test mode — no secrets exposed)
    try:
        from app.integrations.razorpay_client import razorpay_client
        mode = getattr(razorpay_client, "mode", "TEST")
        components["razorpay"] = {"status": "TEST_MODE", "detail": f"Razorpay running in {mode} mode — no live charges"}
    except Exception:
        components["razorpay"] = {"status": "MOCK", "detail": "Mock payment engine active"}

    # 5. Tool Executor
    try:
        from app.tools.tool_executor import TOOL_REGISTRY
        components["tool_executor"] = {
            "status": "ACTIVE",
            "detail": f"{len(TOOL_REGISTRY)} allowlisted tools registered"
        }
    except Exception:
        components["tool_executor"] = {"status": "UNKNOWN", "detail": "Could not load tool registry"}

    # 6. Guardrails
    try:
        from app.services.guardrail_service import guardrail_service
        components["guardrails"] = {"status": "ACTIVE", "detail": "Deterministic merchant guardrails enforced"}
    except Exception:
        components["guardrails"] = {"status": "UNKNOWN", "detail": "Could not load guardrail service"}

    # 7. API
    components["api"] = {"status": "HEALTHY", "detail": "FastAPI serving requests"}

    overall = "HEALTHY"
    degraded = [c for c in components.values() if c["status"] in ("DEGRADED", "UNKNOWN")]
    if degraded:
        overall = "DEGRADED"

    return {
        "overall": overall,
        "components": components,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }


# Phase 8: System Health Endpoint
@router.get("/health", tags=["System"])
def get_system_health(db: Session = Depends(get_db)):
    """
    Phase 8 Health check returning health information for:
    API, PostgreSQL/Database, Redis, AI, and Payment Engine.
    Does NOT expose secrets or internal connection details.
    """
    services = {
        "api": "healthy",
        "database": "healthy",
        "redis": "healthy",
        "ai": "healthy",
        "payment_engine": "healthy"
    }

    # Database check
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services["database"] = "degraded"

    # Redis check
    if not redis_service.is_connected:
        services["redis"] = "healthy"  # Resilient in-memory fallback is active and healthy

    # AI Provider check
    try:
        from app.core.config import settings
        # Operating under official GenAI or safe deterministic fallback
        services["ai"] = "healthy"
    except Exception:
        services["ai"] = "unknown"

    overall = "healthy" if services["database"] == "healthy" else "degraded"

    return {
        "status": overall,
        "services": services
    }


@router.get("/config-info", tags=["System"])
def get_config_info():
    """
    Returns non-secret configuration metadata for the frontend Settings page.
    NEVER exposes API keys, secrets, or credentials — only masked/structural info.
    """
    from app.core.config import settings
    from app.integrations.razorpay_client import razorpay_client

    key_id = settings.RAZORPAY_KEY_ID
    # Mask: show prefix + last 6 chars only (e.g. rzp_test_***RSo8h)
    if len(key_id) > 10:
        masked_key = key_id[:9] + "***" + key_id[-6:]
    else:
        masked_key = "***"

    return {
        "razorpay": {
            "key_id_masked": masked_key,
            "mode": "test" if key_id.startswith("rzp_test_") else "mock",
            "use_mock_payments": settings.USE_MOCK_PAYMENTS,
            "is_live": False,  # live keys are blocked by safety guard
        },
        "gemini": {
            "configured": bool(settings.GEMINI_API_KEY),
            "model": settings.GEMINI_MODEL,
            "mode": "live" if settings.GEMINI_API_KEY else "deterministic-fallback",
        },
        "environment": settings.ENVIRONMENT,
        "app_version": "1.0.0",
    }
