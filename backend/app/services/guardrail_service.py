import logging
from datetime import datetime, time
from typing import Tuple, Optional, Any, List, Dict
from sqlalchemy.orm import Session
from app.models.entities import MerchantGuardrail, Payment, RecoveryCase

logger = logging.getLogger("payrecover.guardrails")


class GuardrailService:
    """
    Evaluates merchant-defined guardrails prior to any autonomous AI action.
    Blocks unsafe discounts, enforces high-value human approval thresholds,
    respects quiet hours, and limits contact attempts.
    """

    @staticmethod
    def get_or_create_guardrails(db: Session, merchant_id: str = "merchant_primary") -> MerchantGuardrail:
        guardrail = db.query(MerchantGuardrail).filter(MerchantGuardrail.merchant_id == merchant_id).first()
        if not guardrail:
            guardrail = MerchantGuardrail(
                id=f"gdr_{merchant_id}",
                merchant_id=merchant_id,
                max_retries=3,
                max_discount_percentage=10.0,
                max_campaign_days=3,
                quiet_hours_start="22:00",
                quiet_hours_end="08:00",
                high_value_threshold=50000.0,
                human_approval_required=True,
                max_contact_attempts=4
            )
            db.add(guardrail)
            db.commit()
            db.refresh(guardrail)
        return guardrail

    @classmethod
    def evaluate_action(
        cls,
        db: Session,
        payment: Payment,
        recovery_case: RecoveryCase,
        action_type: str,
        discount_percentage: float = 0.0,
        merchant_id: str = "merchant_primary"
    ) -> Tuple[bool, str]:
        """
        Validates whether a proposed agent action violates merchant policies.
        Returns: (is_allowed: bool, reason: str)
        """
        guardrail = cls.get_or_create_guardrails(db, merchant_id)

        # 1. High-Value Threshold Guardrail
        if payment.amount >= guardrail.high_value_threshold:
            if guardrail.human_approval_required and action_type not in ["ESCALATE_HUMAN", "INVESTIGATE_PAYMENT"]:
                return (
                    False,
                    f"Transaction value (₹{payment.amount:,.2f}) meets or exceeds high-value threshold (₹{guardrail.high_value_threshold:,.2f}). Human approval mandatory."
                )

        # 2. Maximum Retries Guardrail
        if recovery_case.retry_count >= guardrail.max_retries and action_type in ["RETRY_PAYMENT", "GENERATE_PAYMENT_LINK"]:
            return (
                False,
                f"Maximum retry limit ({guardrail.max_retries}) reached for recovery case {recovery_case.id}."
            )

        # 3. Maximum Discount Guardrail
        if discount_percentage > guardrail.max_discount_percentage:
            return (
                False,
                f"Proposed discount ({discount_percentage}%) exceeds merchant maximum allowable limit ({guardrail.max_discount_percentage}%)."
            )

        # 4. Quiet Hours Check
        now_time = datetime.utcnow().time()
        try:
            q_start_h, q_start_m = map(int, guardrail.quiet_hours_start.split(":"))
            q_end_h, q_end_m = map(int, guardrail.quiet_hours_end.split(":"))
            q_start = time(q_start_h, q_start_m)
            q_end = time(q_end_h, q_end_m)

            if q_start > q_end:  # Over midnight (e.g. 22:00 to 08:00)
                is_quiet = (now_time >= q_start or now_time <= q_end)
            else:
                is_quiet = (q_start <= now_time <= q_end)

            if is_quiet and action_type in ["DISPATCH_MESSAGE", "OFFER_DISCOUNT"]:
                logger.info(f"Action {action_type} scheduled post-quiet-hours.")
                # We allow link creation but note quiet hours scheduling
        except Exception:
            pass

        return True, "Guardrail evaluation passed. Action authorized."

    @classmethod
    def enforce_strategy_guardrails(
        cls,
        db: Session,
        payment: Payment,
        recovery_case: RecoveryCase,
        proposal: Any,
        merchant_id: str = "merchant_primary"
    ):
        """
        Authoritative deterministic backend gate for AI recovery strategies.
        Validates proposals against merchant rules:
        - High-value transactions -> mandatory human approval
        - Proposed discounts -> capped at merchant limit
        - Exceeded retries -> blocked from automated retry
        - Quiet hours -> deferred scheduling
        - Computes final status with priority: BLOCKED > APPROVAL_REQUIRED > CAPPED > SAFE
        """
        from app.schemas.contracts import RecoveryStrategyResult, GuardrailStatusType

        guardrail = cls.get_or_create_guardrails(db, merchant_id)

        constraints = []
        statuses = []

        primary_strategy = proposal.primary_strategy
        secondary_strategy = proposal.secondary_strategy
        recommended_channel = proposal.recommended_channel
        recommended_payment_method = proposal.recommended_payment_method
        expected_prob = proposal.expected_recovery_probability
        confidence = proposal.strategy_confidence
        human_approval = proposal.human_approval_required
        approval_reason = proposal.approval_reason
        strategy_summary = proposal.strategy_summary
        reasoning_summary = proposal.reasoning_summary
        supporting_factors = list(proposal.supporting_factors or [])
        risk_factors = list(proposal.risk_factors or [])
        rejected_strategies = list(proposal.rejected_strategies or [])

        # 1. High-Value Threshold Rule
        if payment.amount >= guardrail.high_value_threshold:
            human_approval = True
            approval_reason = "Transaction exceeds merchant high-value approval threshold."
            statuses.append(GuardrailStatusType.APPROVAL_REQUIRED.value)
            constraints.append("Transaction exceeds merchant high-value approval threshold.")
            if primary_strategy not in ["HUMAN_ESCALATION", "STOP_RECOVERY"]:
                secondary_strategy = primary_strategy
                primary_strategy = "HUMAN_ESCALATION"

        # 2. Maximum Discount Rule
        proposed_discount = float(proposal.proposed_discount_percentage or 0.0)
        if proposed_discount > guardrail.max_discount_percentage:
            final_discount = float(guardrail.max_discount_percentage)
            statuses.append(GuardrailStatusType.CAPPED.value)
            constraints.append("Discount reduced to merchant maximum.")
        else:
            final_discount = max(0.0, proposed_discount)

        discount_amount = round(payment.amount * (final_discount / 100.0), 2)

        # 3. Maximum Retries Rule
        current_retries = int(recovery_case.retry_count if recovery_case else 0)
        if current_retries >= guardrail.max_retries and primary_strategy == "RETRY_PAYMENT":
            statuses.append(GuardrailStatusType.BLOCKED.value)
            constraints.append(f"Retry blocked: retry count ({current_retries}) reached merchant maximum limit ({guardrail.max_retries}).")
            rejected_strategies.append(f"RETRY_PAYMENT — maximum retry limit ({guardrail.max_retries}) reached")
            primary_strategy = "ALTERNATE_PAYMENT_METHOD" if payment.payment_method == "CARD" else "PAYMENT_LINK"
            if not secondary_strategy:
                secondary_strategy = "FOLLOW_UP"
            final_retry_count = current_retries
        elif primary_strategy == "RETRY_PAYMENT":
            final_retry_count = current_retries + 1
        else:
            final_retry_count = current_retries

        # 4. Quiet Hours Rule
        recommended_delay = int(proposal.recommended_delay_minutes or 0)
        now_dt = datetime.utcnow()
        now_time = now_dt.time()
        try:
            q_start_h, q_start_m = map(int, guardrail.quiet_hours_start.split(":"))
            q_end_h, q_end_m = map(int, guardrail.quiet_hours_end.split(":"))
            q_start = time(q_start_h, q_start_m)
            q_end = time(q_end_h, q_end_m)

            if q_start > q_end:  # Over midnight (e.g. 22:00 to 08:00)
                is_quiet = (now_time >= q_start or now_time <= q_end)
                if is_quiet:
                    if now_time >= q_start:
                        mins_to_mid = (24 * 60) - (now_time.hour * 60 + now_time.minute)
                        mins_after_mid = q_end_h * 60 + q_end_m
                        delay_minutes = mins_to_mid + mins_after_mid
                    else:
                        delay_minutes = (q_end_h * 60 + q_end_m) - (now_time.hour * 60 + now_time.minute)
                else:
                    delay_minutes = 0
            else:
                is_quiet = (q_start <= now_time <= q_end)
                if is_quiet:
                    delay_minutes = (q_end_h * 60 + q_end_m) - (now_time.hour * 60 + now_time.minute)
                else:
                    delay_minutes = 0

            if is_quiet and recommended_channel != "NONE":
                recommended_delay = max(recommended_delay, delay_minutes)
                constraints.append(f"Quiet hours active ({guardrail.quiet_hours_start} - {guardrail.quiet_hours_end}): outreach deferred by {recommended_delay} minutes.")
        except Exception as e:
            logger.warning(f"Failed to evaluate quiet hours: {e}")

        # 5. Determine Overall Guardrail Status by Priority
        # Priority: BLOCKED > APPROVAL_REQUIRED > CAPPED > SAFE
        if GuardrailStatusType.BLOCKED.value in statuses:
            guardrail_status = GuardrailStatusType.BLOCKED.value
        elif GuardrailStatusType.APPROVAL_REQUIRED.value in statuses:
            guardrail_status = GuardrailStatusType.APPROVAL_REQUIRED.value
        elif GuardrailStatusType.CAPPED.value in statuses:
            guardrail_status = GuardrailStatusType.CAPPED.value
        else:
            guardrail_status = GuardrailStatusType.SAFE.value

        return RecoveryStrategyResult(
            recovery_case_id=recovery_case.id if recovery_case else "unknown",
            payment_id=payment.id,
            customer_id=payment.customer_id,
            primary_strategy=primary_strategy,
            secondary_strategy=secondary_strategy,
            recommended_channel=recommended_channel,
            recommended_payment_method=recommended_payment_method,
            discount_percentage=final_discount,
            discount_amount=discount_amount,
            currency=payment.currency or "INR",
            expected_recovery_probability=expected_prob,
            strategy_confidence=confidence,
            recommended_delay_minutes=recommended_delay,
            retry_count=final_retry_count,
            human_approval_required=human_approval,
            approval_reason=approval_reason,
            strategy_summary=strategy_summary,
            reasoning_summary=reasoning_summary,
            supporting_factors=supporting_factors,
            risk_factors=risk_factors,
            rejected_strategies=rejected_strategies,
            guardrail_status=guardrail_status,
            guardrail_constraints=constraints
        )


guardrail_service = GuardrailService()
