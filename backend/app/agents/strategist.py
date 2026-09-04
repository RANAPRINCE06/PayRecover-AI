import logging
from app.schemas.contracts import PaymentInvestigationResult, RecoveryStrategy
from app.models.entities import Payment

logger = logging.getLogger("payrecover.strategist")


class RecoveryStrategistAgent:
    """
    AI Strategist Agent.
    Evaluates investigation results and selects the optimal recovery strategy,
    channel, discount policy, and automated or human workflow.
    """

    @classmethod
    def formulate_strategy(cls, investigation: PaymentInvestigationResult, payment: Payment) -> RecoveryStrategy:
        amount = payment.amount
        prob = investigation.recovery_probability
        failure = investigation.failure_category

        # Formulate optimal strategy
        if failure == "CARD_DECLINED":
            strategy_name = "UPI_FALLBACK_LINK"
            channel = "WHATSAPP"
            reasoning = "Do not retry failed card. Issuing bank 3DS is blocked. Recommend instant UPI payment link via WhatsApp for highest completion rate."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = amount >= 50000.0

        elif failure == "UPI_TIMEOUT":
            strategy_name = "INSTANT_WHATSAPP_ONE_CLICK_UPI"
            channel = "WHATSAPP"
            reasoning = "UPI PSP timed out. Send instant prefilled VPA link to WhatsApp immediately while intent is fresh."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = False

        elif failure == "INSUFFICIENT_FUNDS":
            strategy_name = "SCHEDULED_PAY_LATER_REMINDER"
            channel = "SMS"
            reasoning = "Customer balance issue. Offer scheduled reminder for next business day."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = False

        elif failure == "CHECKOUT_ABANDONED":
            strategy_name = "SMART_DISCOUNT_NUDGE"
            channel = "WHATSAPP"
            reasoning = "High cart drop-off probability. Offer 5% recovery incentive to seal the purchase within 2 hours."
            discount_pct = 5.0
            retry_payment = False
            create_link = True
            escalate = False

        else:
            strategy_name = "STANDARD_RECOVERY_OMNICHANNEL"
            channel = "EMAIL"
            reasoning = "Standard automated recovery flow across active channels."
            discount_pct = 0.0
            retry_payment = False
            create_link = True
            escalate = amount >= 50000.0

        estimated_recovery = round(amount * prob * (1.0 - (discount_pct / 100.0)), 2)

        return RecoveryStrategy(
            strategy=strategy_name,
            priority="IMMEDIATE" if prob > 0.8 else "STANDARD",
            expected_recovery_probability=prob,
            estimated_revenue_recovery=estimated_recovery,
            recommended_channel=channel,
            retry_payment=retry_payment,
            create_payment_link=create_link,
            offer_discount=discount_pct > 0,
            discount_percentage=discount_pct,
            schedule_followup=True,
            escalate_to_human=escalate,
            reasoning=reasoning
        )


strategist_agent = RecoveryStrategistAgent()
