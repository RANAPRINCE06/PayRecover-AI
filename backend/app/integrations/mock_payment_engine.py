import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.models.entities import (
    PaymentMethod,
    FailureReason,
    PaymentStatus,
    RecoveryStatus
)


class MockPaymentEngine:
    """
    Realistic simulation engine for Indian fintech payment scenarios.
    Generates deterministic data and simulates recovery workflows.
    """

    SCENARIOS = {
        "DEMO_CARD_DECLINE_UPI": {
            "title": "Exact Demo: Returning Customer Card Declined -> UPI Recovery",
            "amount": 12999.0,
            "payment_method": PaymentMethod.CARD.value,
            "failure_reason": FailureReason.CARD_DECLINED.value,
            "customer_type": "VIP",
            "history_success": 10,
            "history_failed": 1,
            "expected_recovery_prob": 0.89,
            "recommended_strategy": "UPI_FALLBACK_LINK",
            "detected_intent": "ALTERNATE_PAYMENT_METHOD",
            "description": "Customer attempted 3DS card verification which failed at issuing bank; customer has high lifetime value and active UPI."
        },
        "UPI_TIMEOUT": {
            "title": "UPI Request Timeout (PSP Latency)",
            "amount": 2499.0,
            "payment_method": PaymentMethod.UPI.value,
            "failure_reason": FailureReason.UPI_TIMEOUT.value,
            "customer_type": "STANDARD",
            "history_success": 4,
            "history_failed": 1,
            "expected_recovery_prob": 0.94,
            "recommended_strategy": "INSTANT_WHATSAPP_ONE_CLICK_UPI",
            "detected_intent": "TECH_DIFFICULTY",
            "description": "UPI PSP app timed out during MPIN entry. Instant recovery link with prefilled VPA recovers payment seamlessly."
        },
        "INSUFFICIENT_FUNDS": {
            "title": "Insufficient Balance / Salary Cycle Delay",
            "amount": 8999.0,
            "payment_method": PaymentMethod.CARD.value,
            "failure_reason": FailureReason.INSUFFICIENT_FUNDS.value,
            "customer_type": "HIGH_VALUE",
            "history_success": 6,
            "history_failed": 2,
            "expected_recovery_prob": 0.65,
            "recommended_strategy": "SCHEDULED_PAY_LATER_REMINDER",
            "detected_intent": "PAY_LATER",
            "description": "Issuing bank returned insufficient balance code. Intent engine detects customer awaiting salary cycle."
        },
        "CHECKOUT_ABANDONED": {
            "title": "Checkout Abandoned at Final Step",
            "amount": 4999.0,
            "payment_method": PaymentMethod.NETBANKING.value,
            "failure_reason": FailureReason.CHECKOUT_ABANDONED.value,
            "customer_type": "STANDARD",
            "history_success": 1,
            "history_failed": 1,
            "expected_recovery_prob": 0.72,
            "recommended_strategy": "DISCOUNT_INCENTIVE_SMS",
            "detected_intent": "PRICE_OBJECTION",
            "description": "User abandoned cart during OTP entry. Small smart discount (5%) nudges completion."
        },
        "SUBSCRIPTION_FAILED": {
            "title": "Recurring Auto-Debit Mandate Failure",
            "amount": 999.0,
            "payment_method": PaymentMethod.CARD.value,
            "failure_reason": FailureReason.SUBSCRIPTION_FAILED.value,
            "customer_type": "VIP",
            "history_success": 12,
            "history_failed": 0,
            "expected_recovery_prob": 0.96,
            "recommended_strategy": "AUTO_RETRY_MANDATE_UPDATE",
            "detected_intent": "TECH_DIFFICULTY",
            "description": "RBI e-mandate authentication expired on card. AI sends update mandate link via WhatsApp."
        },
        "HIGH_VALUE_APPROVAL": {
            "title": "High Value Transaction (Guardrail Human Approval)",
            "amount": 75000.0,
            "payment_method": PaymentMethod.NETBANKING.value,
            "failure_reason": FailureReason.BANK_SERVER_DOWN.value,
            "customer_type": "VIP",
            "history_success": 15,
            "history_failed": 2,
            "expected_recovery_prob": 0.82,
            "recommended_strategy": "EXECUTIVE_CONCIERGE_CALL",
            "detected_intent": "ALTERNATE_PAYMENT_METHOD",
            "description": "Amount exceeds ₹50,000 threshold. Guardrails mandate merchant human review before automated outreach."
        }
    }

    @classmethod
    def generate_random_payment_data(cls, count: int = 50) -> List[Dict[str, Any]]:
        """Generate realistic mock payments for seeding and live simulation"""
        amounts = [999.0, 1499.0, 2499.0, 3999.0, 4999.0, 8999.0, 12999.0, 25000.0, 49999.0, 75000.0]
        methods = [PaymentMethod.UPI.value, PaymentMethod.CARD.value, PaymentMethod.NETBANKING.value]
        reasons = [
            FailureReason.UPI_TIMEOUT.value,
            FailureReason.CARD_DECLINED.value,
            FailureReason.INSUFFICIENT_FUNDS.value,
            FailureReason.CHECKOUT_ABANDONED.value,
            FailureReason.AUTHENTICATION_FAILED.value,
            FailureReason.BANK_SERVER_DOWN.value
        ]

        items = []
        for i in range(count):
            amount = random.choice(amounts)
            method = random.choice(methods)
            is_failed = (i % 3 != 0)  # ~66% failed/at-risk for recovery demo
            reason = random.choice(reasons) if is_failed else None

            items.append({
                "amount": amount,
                "payment_method": method,
                "status": PaymentStatus.FAILED.value if is_failed else PaymentStatus.SUCCESS.value,
                "failure_reason": reason,
                "currency": "INR"
            })
        return items


mock_payment_engine = MockPaymentEngine()
