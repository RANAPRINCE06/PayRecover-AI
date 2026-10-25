import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_structured_logging
from app.db.session import engine, Base
import app.models.entities  # Ensure all SQLAlchemy models are registered
from app.db.seed_data import seed_database
from app.core.middleware import CorrelationIdMiddleware, SecurityHeadersMiddleware
from app.services.outbox_worker import outbox_worker
from app.api.routes import router as api_router
from app.api.analytics import router as analytics_router
from app.api.system_status import router as system_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.events import router as events_router
from app.api.webhooks import router as webhooks_router
from app.api.intelligence import router as intelligence_router
from app.api.knowledge import router as knowledge_router
from app.api.experiments import router as experiments_router
from app.api.bandits import router as bandits_router
from app.api.metrics import router as metrics_router

# Setup structured logging with sensitive data sanitization
setup_structured_logging(
    service_name="payrecover-api",
    environment=settings.ENVIRONMENT,
    log_format=getattr(settings, "LOG_FORMAT", "text")
)
logger = logging.getLogger("payrecover.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    # ── Validate critical configuration (safety guard for live keys, JWT, Gemini) ──
    settings.validate_startup()
    # Initialize DB schema
    Base.metadata.create_all(bind=engine)
    # Seed initial data
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Error seeding database on startup: {e}")

    # Start resilient background outbox worker
    await outbox_worker.start()

    yield

    logger.info("Shutting down PayRecover AI...")
    # Gracefully drain background worker
    await outbox_worker.stop(drain_timeout=5.0)


app = FastAPI(
    title="PayRecover AI API",
    description="Autonomous Revenue Recovery & Customer Intent Engine for Razorpay Merchants",
    version="1.0.0",
    lifespan=lifespan
)

# Custom Middlewares (Correlation ID and Security Headers)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "req_unknown")
    logger.error(f"[{req_id}] Unhandled Exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "request_id": req_id
            },
            "detail": "An internal server error occurred."
        }
    )


# Mount API routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(users_router, prefix="/api/users")
app.include_router(events_router, prefix="/api/events")
app.include_router(webhooks_router, prefix="/api/webhooks")
app.include_router(api_router, prefix="/api")
app.include_router(analytics_router, prefix="/api/analytics")
app.include_router(system_router, prefix="/api/system")
app.include_router(intelligence_router)
app.include_router(knowledge_router, prefix="/api/knowledge")
app.include_router(experiments_router, prefix="/api")
app.include_router(bandits_router, prefix="/api")

# Observability & Metrics (Prometheus standard endpoint)
app.include_router(metrics_router)  # Mounted at /metrics
app.include_router(metrics_router, prefix="/api")  # Mounted at /api/metrics

# Standard Health Probes (Kubernetes / Docker convention: /health/live, /health/ready, /health/deps)
app.include_router(system_router)  # Mounted directly at /health/live, /health/ready, etc.


@app.get("/")
def root():
    return {
        "service": "PayRecover AI API",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
