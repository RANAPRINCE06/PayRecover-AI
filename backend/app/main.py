import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import engine, Base
from app.db.seed_data import seed_database
from app.core.middleware import CorrelationIdMiddleware, SecurityHeadersMiddleware
from app.api.routes import router as api_router
from app.api.analytics import router as analytics_router
from app.api.system_status import router as system_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.events import router as events_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("payrecover.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    # Initialize DB schema
    Base.metadata.create_all(bind=engine)
    # Seed initial data
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Error seeding database on startup: {e}")
    yield
    logger.info("Shutting down PayRecover AI...")


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
    allow_origins=["*"],
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
app.include_router(api_router, prefix="/api")
app.include_router(analytics_router, prefix="/api/analytics")
app.include_router(system_router, prefix="/api/system")


@app.get("/")
def root():
    return {
        "service": "PayRecover AI API",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
