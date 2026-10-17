import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger("payrecover.webhook.verifier")


class RazorpayWebhookVerifier:
    """
    Cryptographic verification and payload sanitization for Razorpay webhooks.
    Enforces HMAC-SHA256 signature verification over exact raw request body bytes.
    """

    @classmethod
    def verify_signature(
        cls,
        raw_body: bytes,
        signature_header: Optional[str],
        secret: Optional[str] = None
    ) -> bool:
        """
        Verify the Razorpay webhook signature against the raw body bytes.
        
        Uses constant-time comparison to prevent timing side-channel attacks.
        Returns False if secret or signature is missing, empty, or mismatched.
        """
        if not signature_header or not signature_header.strip():
            logger.warning("[Webhook Security] Missing or empty X-Razorpay-Signature header.")
            return False

        webhook_secret = secret or getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        if not webhook_secret or not webhook_secret.strip():
            logger.error("[Webhook Security] RAZORPAY_WEBHOOK_SECRET is not configured.")
            return False

        if not raw_body:
            logger.warning("[Webhook Security] Empty request body received for signature verification.")
            return False

        try:
            expected_signature = hmac.new(
                key=webhook_secret.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha256
            ).hexdigest()

            # Constant-time comparison
            is_valid = hmac.compare_digest(expected_signature, signature_header.strip())
            if not is_valid:
                logger.warning("[Webhook Security] Signature mismatch detected. Possible tampering or invalid secret.")
            return is_valid
        except Exception as e:
            logger.error(f"[Webhook Security] Unexpected error during HMAC computation: {e}")
            return False

    @classmethod
    def sanitize_payload(cls, data: Any) -> Any:
        """
        Recursively redact payment credentials, card numbers, CVVs, tokens, and secrets
        before persisting metadata or logging.
        """
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                lower_k = k.lower()
                if any(sensitive in lower_k for sensitive in ["cvv", "card_number", "pan", "token", "secret", "password", "key"]):
                    sanitized[k] = "[REDACTED]"
                elif lower_k in ["email", "contact", "phone"] and isinstance(v, str):
                    # Mask PII
                    if "@" in v:
                        parts = v.split("@")
                        sanitized[k] = f"{parts[0][:2]}***@{parts[1]}" if len(parts[0]) > 2 else f"*@{parts[1]}"
                    elif len(v) >= 10:
                        sanitized[k] = f"{v[:3]}****{v[-3:]}"
                    else:
                        sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = cls.sanitize_payload(v)
            return sanitized
        elif isinstance(data, list):
            return [cls.sanitize_payload(item) for item in data]
        return data


webhook_verifier = RazorpayWebhookVerifier()
