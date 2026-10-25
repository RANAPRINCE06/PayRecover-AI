import os
import re
import json
import time
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime

# Context variables for request tracing across async and sync call stacks
current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)
current_correlation_id: ContextVar[Optional[str]] = ContextVar("current_correlation_id", default=None)

# Patterns for redacting sensitive credentials and PII
SENSITIVE_PATTERNS = [
    # Authorization tokens / Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    # JWT tokens
    (re.compile(r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+"), "[REDACTED_JWT]"),
    # Razorpay API keys & secrets
    (re.compile(r"rzp_(test|live)_[A-Za-z0-9]{10,}"), r"rzp_\1_[REDACTED_KEY]"),
    (re.compile(r"(\"?(?:key_secret|secret|password|api_key|token|access_token|jwt_secret)\"?\s*[:=]\s*\"?)[^\"'\s,]+(\"?)", re.IGNORECASE), r"\1[REDACTED_SECRET]\2"),
    # Credit Card numbers (13-19 digits, with optional hyphens/spaces)
    (re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b|\b\d{13,19}\b"), "[REDACTED_CARD_NUMBER]"),
    # CVV (3-4 digits in cvv/cvc context)
    (re.compile(r"(\"?(?:cvv|cvc|card_code)\"?\s*[:=]\s*\"?)\d{3,4}(\"?)", re.IGNORECASE), r"\1[REDACTED_CVV]\2"),
]


def sanitize_log_message(msg: str) -> str:
    """Sanitizes sensitive financial, authentication, and credential data from log messages."""
    if not isinstance(msg, str):
        msg = str(msg)
    for pattern, replacement in SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg


class SensitiveDataFilter(logging.Filter):
    """Logging filter that sanitizes record messages and attaches trace context."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (sanitize_log_message(v) if isinstance(v, str) else v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_log_message(a) if isinstance(a, str) else a for a in record.args)

        # Attach context variables if not already present
        if not hasattr(record, "request_id") or not record.request_id:
            record.request_id = current_request_id.get() or "-"
        if not hasattr(record, "correlation_id") or not record.correlation_id:
            record.correlation_id = current_correlation_id.get() or "-"

        return True


class StructuredJsonFormatter(logging.Formatter):
    """
    Production-grade JSON log formatter for structured observability.
    Conforms to OpenTelemetry and cloud log aggregator (e.g. Datadog, GCP Cloud Logging) standards.
    """

    def __init__(self, service_name: str = "payrecover-api", environment: str = "production"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "environment": self.environment,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }

        # Include location details for WARN/ERROR
        if record.levelno >= logging.WARNING:
            log_entry["source_location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName
            }

        # Include exception traceback if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom extra metadata if supplied
        extra_keys = set(record.__dict__.keys()) - {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "request_id", "correlation_id"
        }
        if extra_keys:
            log_entry["extra"] = {k: getattr(record, k) for k in extra_keys}

        return json.dumps(log_entry, default=str)


def setup_structured_logging(service_name: str = "payrecover-api", environment: str = "development", log_format: str = "text"):
    """
    Configures the root and application loggers with sensitive data filtering
    and either structured JSON or human-readable console formatting.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.addFilter(SensitiveDataFilter())

    if log_format.lower() == "json" or environment.lower() == "production":
        console_handler.setFormatter(StructuredJsonFormatter(service_name=service_name, environment=environment))
    else:
        text_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] [req:%(request_id)s] %(message)s"
        )
        console_handler.setFormatter(text_formatter)

    root_logger.addHandler(console_handler)

    # Set specific log levels for third-party libraries to prevent noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
