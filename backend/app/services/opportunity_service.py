import logging
from datetime import datetime
from typing import Dict, Any, List
from app.models.entities import (
    RecoveryCase,
    Payment,
    Customer,
    RecoveryStatus,
    PaymentMethod,
    FailureReason
)
from app.schemas.contracts import OpportunityScoreResponse

logger = logging.getLogger("payrecover.opportunity")


class OpportunityScoringEngine:
    """
    Deterministic and explainable recovery opportunity scoring engine (0-100).
    Evaluates multi-factor signals:
      1. Payment amount & value tier
      2. Failure reason transience
      3. Customer loyalty & payment history
      4. Customer intent signal
      5. Retry count decay
      6. Payment method agility
      7. Time elapsed since failure
      8. Recovery case status gating
    """

    @classmethod
    def calculate_score(cls, case: RecoveryCase) -> OpportunityScoreResponse:
        payment: Payment = case.payment
        customer: Customer = payment.customer if payment else None

        if not payment:
            return OpportunityScoreResponse(
                case_id=case.id,
                payment_id="",
                amount=0.0,
                score=0.0,
                priority="LOW",
                positive_factors=[],
                negative_factors=["No payment record linked to recovery case."],
                recommended_strategy="STOP_RECOVERY",
                estimated_recovery_probability=0.0,
                is_heuristic=True
            )

        # Gating: Completed or Terminated cases
        if case.status in [RecoveryStatus.RECOVERED.value, RecoveryStatus.FAILED.value, RecoveryStatus.EXPIRED.value]:
            is_recovered = case.status == RecoveryStatus.RECOVERED.value
            return OpportunityScoreResponse(
                case_id=case.id,
                payment_id=payment.id,
                amount=payment.amount,
                currency=payment.currency,
                customer_name=customer.name if customer else "Unknown",
                customer_tier=customer.customer_value if customer else "STANDARD",
                failure_reason=payment.failure_reason,
                score=100.0 if is_recovered else 0.0,
                priority="LOW" if not is_recovered else "CRITICAL",
                positive_factors=["Payment already settled successfully."] if is_recovered else [],
                negative_factors=[] if is_recovered else ["Case marked as failed or expired."],
                recommended_strategy="NONE",
                estimated_recovery_probability=1.0 if is_recovered else 0.0,
                is_heuristic=True
            )

        raw_score = 40.0  # Baseline starting point
        positive_factors: List[str] = []
        negative_factors: List[str] = []

        # 1. Failure Reason Factor
        reason = payment.failure_reason or ""
        if reason in [FailureReason.UPI_TIMEOUT.value, FailureReason.BANK_SERVER_DOWN.value]:
            raw_score += 25.0
            positive_factors.append(f"Transient bank/PSP network issue ({reason}): high probability of succeeding on retry or alternate channel (+25 pts)")
        elif reason in [FailureReason.CARD_DECLINED.value, FailureReason.AUTHENTICATION_FAILED.value]:
            raw_score += 18.0
            positive_factors.append(f"Card authorization friction ({reason}): highly recoverable via 1-click UPI fallback (+18 pts)")
        elif reason == FailureReason.CHECKOUT_ABANDONED.value:
            raw_score += 12.0
            positive_factors.append(f"Cart abandonment: warm customer interest, high response to WhatsApp reminders (+12 pts)")
        elif reason == FailureReason.SUBSCRIPTION_FAILED.value:
            raw_score += 10.0
            positive_factors.append(f"Subscription billing failure: active subscriber intent (+10 pts)")
        elif reason == FailureReason.INSUFFICIENT_FUNDS.value:
            raw_score += 5.0
            negative_factors.append(f"Insufficient funds reported: requires delayed retry or salary cycle follow-up (+5 pts)")
        else:
            negative_factors.append("Unspecified payment failure reason")

        # 2. Customer Lifetime History
        if customer:
            success_count = customer.total_successful_payments or 0
            failed_count = customer.total_failed_payments or 0

            if success_count >= 5:
                raw_score += 20.0
                positive_factors.append(f"Loyal customer with {success_count} prior successful payments (+20 pts)")
            elif success_count >= 2:
                raw_score += 12.0
                positive_factors.append(f"Returning customer with {success_count} prior successful payments (+12 pts)")
            elif success_count == 1:
                raw_score += 5.0
                positive_factors.append("Customer has 1 prior verified transaction (+5 pts)")
            else:
                negative_factors.append("First-time customer with no prior transaction history")

            if failed_count > 3:
                raw_score -= 15.0
                negative_factors.append(f"High historical failure record ({failed_count} prior failures) (-15 pts)")
            elif failed_count > 1:
                raw_score -= 5.0
                negative_factors.append(f"Multiple prior failed transactions ({failed_count}) (-5 pts)")

            # Customer Tier
            tier = customer.customer_value or "STANDARD"
            if tier == "VIP":
                raw_score += 10.0
                positive_factors.append("VIP customer tier: maximum retention priority (+10 pts)")
            elif tier == "HIGH_VALUE":
                raw_score += 8.0
                positive_factors.append("High-Value customer tier (+8 pts)")
            elif tier == "CHURN_RISK":
                raw_score -= 10.0
                negative_factors.append("Customer flagged as churn risk (-10 pts)")
        else:
            tier = "STANDARD"

        # 3. Customer Intent Signal
        intent = case.customer_intent or ""
        if intent in ["WILL_PAY_LATER", "RETRY_REQUEST", "PAYMENT_LINK_REQUEST"]:
            raw_score += 25.0
            positive_factors.append(f"Strong positive customer intent '{intent}': customer explicitly indicated willingness to pay (+25 pts)")
        elif intent in ["ALTERNATE_PAYMENT_METHOD", "PAYMENT_PROBLEM"]:
            raw_score += 20.0
            positive_factors.append(f"High engagement intent '{intent}': customer actively troubleshooting (+20 pts)")
        elif intent == "NEEDS_ASSISTANCE":
            raw_score += 15.0
            positive_factors.append("Customer requested support assistance (+15 pts)")
        elif intent == "ALREADY_PAID":
            raw_score += 10.0
            positive_factors.append("Customer claims payment completed: immediate automated verification recommended (+10 pts)")
        elif intent in ["CANCEL_REQUEST", "NOT_INTERESTED"]:
            raw_score -= 40.0
            negative_factors.append(f"Strong negative customer intent '{intent}': customer requested cancellation (-40 pts)")

        # 4. Previous Recovery Attempts (Decay)
        retries = case.retry_count or 0
        if retries == 0:
            raw_score += 10.0
            positive_factors.append("Zero previous recovery attempts: pristine customer attention window (+10 pts)")
        elif retries == 1:
            raw_score += 0.0
        elif retries == 2:
            raw_score -= 15.0
            negative_factors.append(f"2 previous recovery attempts executed without settlement (-15 pts)")
        else:
            raw_score -= 30.0
            negative_factors.append(f"High retry exhaustion ({retries} prior attempts) (-30 pts)")

        # 5. Payment Method Agility
        method = payment.payment_method or ""
        if method == PaymentMethod.UPI.value:
            raw_score += 10.0
            positive_factors.append("Native UPI transaction: instant deep-link and intent resolution supported (+10 pts)")
        elif method == PaymentMethod.CARD.value:
            raw_score += 5.0
            positive_factors.append("Card failure: highly responsive to instant UPI switch (+5 pts)")

        # 6. Time Elapsed Since Failure
        elapsed_hours = 0.0
        if payment.created_at:
            delta = datetime.utcnow() - payment.created_at
            elapsed_hours = delta.total_seconds() / 3600.0

        if elapsed_hours < 1.0:
            raw_score += 15.0
            positive_factors.append(f"Fresh failure ({int(elapsed_hours * 60)} mins ago): immediate intervention window (+15 pts)")
        elif elapsed_hours < 6.0:
            raw_score += 5.0
            positive_factors.append(f"Recent failure ({int(elapsed_hours)} hours ago) (+5 pts)")
        elif elapsed_hours > 24.0:
            raw_score -= 20.0
            negative_factors.append(f"Stale failure (>24 hours elapsed): conversion probability decays sharply (-20 pts)")
        elif elapsed_hours > 12.0:
            raw_score -= 10.0
            negative_factors.append(f"Over 12 hours since initial failure (-10 pts)")

        # 7. Clamp score to 0..100
        clamped_score = max(0.0, min(100.0, round(raw_score, 1)))

        # Priority categorization
        if clamped_score >= 80.0:
            priority = "CRITICAL"
        elif clamped_score >= 65.0:
            priority = "HIGH"
        elif clamped_score >= 45.0:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Strategy recommendation based on factors
        if clamped_score < 30.0:
            strategy = "STOP_RECOVERY"
        elif intent in ["CANCEL_REQUEST", "NOT_INTERESTED"]:
            strategy = "STOP_RECOVERY"
        elif intent == "ALREADY_PAID":
            strategy = "VERIFY_PAYMENT"
        elif payment.amount >= 50000.0:
            strategy = "HUMAN_ESCALATION"
        elif reason in [FailureReason.CARD_DECLINED.value, FailureReason.AUTHENTICATION_FAILED.value]:
            strategy = "ALTERNATE_PAYMENT_METHOD"
        elif reason == FailureReason.INSUFFICIENT_FUNDS.value or intent == "WILL_PAY_LATER":
            strategy = "SCHEDULE_FOLLOW_UP"
        elif reason in [FailureReason.UPI_TIMEOUT.value, FailureReason.BANK_SERVER_DOWN.value]:
            strategy = "RETRY_PAYMENT"
        else:
            strategy = "PAYMENT_LINK"

        heuristic_prob = round(clamped_score / 100.0, 2)

        return OpportunityScoreResponse(
            case_id=case.id,
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            customer_name=customer.name if customer else "Unknown",
            customer_tier=tier,
            failure_reason=payment.failure_reason,
            score=clamped_score,
            priority=priority,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            recommended_strategy=strategy,
            estimated_recovery_probability=heuristic_prob,
            is_heuristic=True
        )


opportunity_scoring_engine = OpportunityScoringEngine()
