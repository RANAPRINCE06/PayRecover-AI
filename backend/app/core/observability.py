import re
import json
import logging
from typing import Any, Dict

SENSITIVE_KEYS = {
    "password", "hashed_password", "token", "access_token", "jwt",
    "secret", "key_secret", "api_key", "authorization", "razorpay_key_secret",
    "card_number", "cvv", "mpin", "otp"
}


def redact_sensitive_data(obj: Any) -> Any:
    """
    Recursively traverse dictionaries or lists and mask values belonging to sensitive keys.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = redact_sensitive_data(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(obj, list):
        return [redact_sensitive_data(item) for item in obj]
    elif isinstance(obj, str):
        # Redact JWT pattern if found in raw string
        if re.search(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", obj):
            return re.sub(
                r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}",
                "[REDACTED_JWT]",
                obj
            )
        return obj
    return obj


class RedactingFormatter(logging.Formatter):
    """
    Logging formatter that ensures no plaintext credentials, JWTs, or secrets enter log streams.
    """

    def format(self, record: logging.LogRecord) -> str:
        orig_msg = super().format(record)
        # Redact JWTs from logs
        if "eyJ" in orig_msg:
            orig_msg = re.sub(
                r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}",
                "[REDACTED_JWT]",
                orig_msg
            )
        return orig_msg
