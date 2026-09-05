import os
import logging
from typing import List, Union, Any
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("payrecover.config")


class Settings(BaseSettings):
    APP_NAME: str = "PayRecover AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8001

    # JWT Secret — also accepts JWT_SECRET alias from .env
    SECRET_KEY: str = Field(
        "payrecover-secret-key-change-in-production",
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET")
    )

    # Database
    DATABASE_URL: str = "sqlite:///./payrecover.db"
    SQLITE_FALLBACK_URL: str = "sqlite:///./payrecover.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Razorpay Test Mode
    RAZORPAY_KEY_ID: str = "rzp_test_sample_key_12345"
    RAZORPAY_KEY_SECRET: str = "rzp_test_sample_secret_67890"
    USE_MOCK_PAYMENTS: bool = True

    # AI (Gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return []

    model_config = SettingsConfigDict(
        # Resolve .env from the project root regardless of working directory
        env_file=[
            ".env",                            # CWD (works when run from project root)
            "../.env",                         # CWD/backend → project root
            "../../.env",                      # CWD/backend/app → project root
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_startup(self) -> None:
        """
        Validate critical configuration at startup.
        Logs warnings for missing/weak settings but never crashes —
        the system gracefully degrades (mock payments, no-AI mode).
        """
        warnings = []

        # JWT secret strength check
        if self.SECRET_KEY in (
            "payrecover-secret-key-change-in-production",
            "change-this-in-production-to-a-secure-random-string-at-least-32-chars",
        ):
            warnings.append(
                "SECRET_KEY is using the default placeholder. "
                "Set a strong random value in .env for secure JWT signing."
            )
        elif len(self.SECRET_KEY) < 32:
            warnings.append(
                f"SECRET_KEY is only {len(self.SECRET_KEY)} chars — "
                "use at least 32 chars for security."
            )

        # Razorpay live-mode safety guard
        if self.RAZORPAY_KEY_ID.startswith("rzp_live_"):
            raise RuntimeError(
                "SAFETY GUARD: RAZORPAY_KEY_ID starts with 'rzp_live_'. "
                "Live-mode Razorpay keys are FORBIDDEN in this demo environment. "
                "Use rzp_test_ keys only. Aborting startup."
            )

        if self.RAZORPAY_KEY_SECRET and not self.USE_MOCK_PAYMENTS:
            if "sample" in self.RAZORPAY_KEY_ID:
                warnings.append(
                    "USE_MOCK_PAYMENTS=False but RAZORPAY_KEY_ID looks like a sample key. "
                    "Real Razorpay API calls will likely fail — falling back to mock engine."
                )

        # Gemini API key
        if not self.GEMINI_API_KEY:
            warnings.append(
                "GEMINI_API_KEY not set. AI Recovery Copilot will use deterministic "
                "fallback engine instead of live Gemini inference."
            )

        for w in warnings:
            logger.warning(f"[CONFIG] {w}")

        if not warnings:
            logger.info(
                f"[CONFIG] Startup validation passed — "
                f"Env={self.ENVIRONMENT}, Razorpay={'mock' if self.USE_MOCK_PAYMENTS else 'test-live'}, "
                f"Gemini={'enabled' if self.GEMINI_API_KEY else 'fallback'}"
            )


settings = Settings()
