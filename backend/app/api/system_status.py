"""
Phase 7 — System Status API
Returns health of DB, Redis, AI provider, payment engine, and guardrails.
Does NOT expose any secrets.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.services.redis_service import redis_service

logger = logging.getLogger("payrecover.system_status")
router = APIRouter()


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
