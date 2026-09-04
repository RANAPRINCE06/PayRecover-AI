import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "PayRecover AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    SECRET_KEY: str = "payrecover-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "sqlite:///./payrecover.db"
    POSTGRES_URL: str = "postgresql://postgres:postgres@localhost:5432/payrecover_db"

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
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
