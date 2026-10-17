import logging
from datetime import datetime
from typing import Optional, Tuple, Set, Dict
from sqlalchemy.orm import Session

from app.models.entities import (
    Payment,
    RecoveryCase,
    PaymentStatus,
    RecoveryStatus,
    AgentAction,
    AgentType,
    ActionType,
    ActionStatus
)

logger = logging.getLogger("payrecover.statemachine")


class PaymentStateMachine:
    """
    Deterministic payment state machine enforcing valid fintech lifecycle transitions.
    Prevents out-of-order webhook delivery from regressing settled revenue.
    """

    # Explicit directional state transitions
    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        PaymentStatus.PENDING.value: {
            PaymentStatus.SUCCESS.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.ABANDONED.value,
            PaymentStatus.RECOVERED.value,
        },
        PaymentStatus.FAILED.value: {
            PaymentStatus.RECOVERED.value,
            PaymentStatus.SUCCESS.value,
        },
        PaymentStatus.ABANDONED.value: {
            PaymentStatus.RECOVERED.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.SUCCESS.value,
        },
        # Terminal states: Once money is captured or recovered, it cannot be reversed by late events!
        PaymentStatus.SUCCESS.value: set(),
        PaymentStatus.RECOVERED.value: set(),
    }

    @classmethod
    def can_transition(cls, current_status: str, target_status: str) -> bool:
        """Check if transition from current_status to target_status is permitted."""
        if current_status == target_status:
            return True  # Idempotent no-op is always valid
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def transition_payment(
        cls,
        db: Session,
        payment: Payment,
        target_status: str,
        failure_reason: Optional[str] = None,
        source_event: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Safely apply state transition to a Payment entity and reconcile associated RecoveryCase.
        Returns: (success: bool, message: str)
        """
        curr = payment.status

        # 1. Idempotent check
        if curr == target_status:
            logger.info(f"[StateMachine] Payment {payment.id} already in target status '{target_status}'. Idempotent no-op.")
            return True, f"Payment already in state '{target_status}'"

        # 2. Check if trying to downgrade a settled payment
        if curr in (PaymentStatus.SUCCESS.value, PaymentStatus.RECOVERED.value):
            if target_status in (PaymentStatus.FAILED.value, PaymentStatus.PENDING.value, PaymentStatus.ABANDONED.value):
                msg = (
                    f"Out-of-order event rejected: Payment {payment.id} is already settled ({curr}). "
                    f"Refusing downgrade to '{target_status}'."
                )
                logger.warning(f"[StateMachine] {msg}")
                return False, msg

        # 3. Check allowed transition rules
        if not cls.can_transition(curr, target_status):
            msg = f"Invalid state transition: Payment {payment.id} cannot transition from '{curr}' to '{target_status}'."
            logger.warning(f"[StateMachine] {msg}")
            return False, msg

        # 4. Apply transition to Payment
        payment.status = target_status
        if failure_reason and target_status == PaymentStatus.FAILED.value:
            payment.failure_reason = failure_reason
        payment.updated_at = datetime.utcnow()

        # 5. Synchronize associated RecoveryCase
        if payment.recovery_case:
            case = payment.recovery_case
            if target_status in (PaymentStatus.SUCCESS.value, PaymentStatus.RECOVERED.value):
                case.status = RecoveryStatus.RECOVERED.value
                case.recovered_amount = payment.amount
                case.completed_at = datetime.utcnow()
                if payment.customer:
                    payment.customer.total_successful_payments += 1
            elif target_status == PaymentStatus.FAILED.value:
                # If case was already recovered, do NOT downgrade
                if case.status != RecoveryStatus.RECOVERED.value:
                    case.status = RecoveryStatus.IDENTIFIED.value

        logger.info(f"[StateMachine] Successfully transitioned Payment {payment.id} from '{curr}' to '{target_status}'.")
        return True, f"Transitioned from '{curr}' to '{target_status}'"


payment_state_machine = PaymentStateMachine()
