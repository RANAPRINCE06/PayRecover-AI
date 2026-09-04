import logging
from typing import Optional
from app.schemas.contracts import CustomerIntentResult

logger = logging.getLogger("payrecover.intent")


class CustomerIntentAgent:
    """
    AI Intent Agent.
    Interprets customer replies, message signals, and payment interaction telemetry
    to classify intent, sentiment, and urgency.
    """

    @classmethod
    def detect_intent(
        cls,
        message_text: Optional[str] = None,
        failure_context: Optional[str] = None
    ) -> CustomerIntentResult:
        if not message_text:
            if failure_context == "CARD_DECLINED":
                return CustomerIntentResult(
                    intent="ALTERNATE_PAYMENT_METHOD",
                    confidence=0.91,
                    sentiment="NEUTRAL",
                    urgency="HIGH",
                    recommended_action="PROVIDE_UPI_PAYMENT_LINK"
                )
            return CustomerIntentResult(
                intent="TECH_DIFFICULTY",
                confidence=0.85,
                sentiment="NEUTRAL",
                urgency="MEDIUM",
                recommended_action="DISPATCH_INSTANT_RETRY"
            )

        text_lower = message_text.lower()

        if any(w in text_lower for w in ["upi", "gpay", "phonepe", "paytm", "other way", "another method", "link"]):
            return CustomerIntentResult(
                intent="ALTERNATE_PAYMENT_METHOD",
                confidence=0.95,
                sentiment="POSITIVE",
                urgency="HIGH",
                recommended_action="SEND_UPI_DIRECT_LINK"
            )
        elif any(w in text_lower for w in ["later", "tomorrow", "evening", "salary", "wait"]):
            return CustomerIntentResult(
                intent="PAY_LATER",
                confidence=0.92,
                sentiment="POSITIVE",
                urgency="LOW",
                recommended_action="SCHEDULE_CALENDAR_REMINDER"
            )
        elif any(w in text_lower for w in ["discount", "expensive", "offer", "coupon", "cheaper"]):
            return CustomerIntentResult(
                intent="PRICE_OBJECTION",
                confidence=0.88,
                sentiment="NEUTRAL",
                urgency="MEDIUM",
                recommended_action="OFFER_AUTHORIZED_DISCOUNT"
            )
        elif any(w in text_lower for w in ["failed", "stuck", "error", "otp", "declined"]):
            return CustomerIntentResult(
                intent="TECH_DIFFICULTY",
                confidence=0.90,
                sentiment="FRUSTRATED",
                urgency="HIGH",
                recommended_action="RESOLVE_GATEWAY_INTERRUPT"
            )
        else:
            return CustomerIntentResult(
                intent="ALTERNATE_PAYMENT_METHOD",
                confidence=0.80,
                sentiment="NEUTRAL",
                urgency="MEDIUM",
                recommended_action="PROVIDE_STANDARD_LINK"
            )


intent_agent = CustomerIntentAgent()
