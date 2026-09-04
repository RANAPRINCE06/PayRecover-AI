import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, Callable
from sqlalchemy.orm import Session

from app.models.entities import (
    Payment,
    RecoveryCase,
    AgentAction,
    CustomerInteraction,
    ToolExecution,
    HumanApproval,
    AgentType,
    ActionType,
    ActionStatus,
    PaymentStatus,
    RecoveryStatus,
    InteractionChannel,
    InteractionDirection
)
from app.schemas.contracts import (
    ToolType,
    ToolExecutionStatus,
    ToolProposal,
    ToolExecutionRequest,
    ToolExecutionResult
)
from app.services.guardrail_service import guardrail_service
from app.integrations.razorpay_client import razorpay_client
from app.services.redis_service import redis_service

logger = logging.getLogger("payrecover.tool_executor")

# Allowlisted payment methods
ALLOWLISTED_PAYMENT_METHODS = {"UPI", "CARD", "NETBANKING", "WALLET"}

# Allowlisted messaging channels
ALLOWLISTED_CHANNELS = {"WHATSAPP", "SMS", "EMAIL", "NONE"}


class ToolExecutor:
    """
    Phase 5 Allowlisted Deterministic Tool Executor.
    
    The AI Agent proposes tools, but only the backend ToolExecutor can execute
    registered, strictly allowlisted operations under merchant guardrail constraints.
    Never executes arbitrary code, never uses eval(), never bypasses guardrails.
    """

    @classmethod
    def execute(
        cls,
        db: Session,
        recovery_case_id: str,
        tool_type: Optional[ToolType] = None,
        parameters: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        approval_token: Optional[str] = None
    ) -> ToolExecutionResult:
        """
        Main entry point for executing an allowlisted recovery tool.
        """
        parameters = parameters or {}
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        # 1. Check Idempotency
        if idempotency_key:
            existing_exec = db.query(ToolExecution).filter(
                ToolExecution.idempotency_key == idempotency_key
            ).first()
            if existing_exec:
                logger.info(f"Idempotent execution hit for key '{idempotency_key}' (execution {existing_exec.execution_id})")
                parsed_res = json.loads(existing_exec.result_json) if existing_exec.result_json else {}
                return ToolExecutionResult(
                    execution_id=existing_exec.execution_id,
                    recovery_case_id=existing_exec.recovery_case_id,
                    payment_id=existing_exec.payment_id,
                    customer_id=existing_exec.customer_id,
                    tool_type=existing_exec.tool_type,
                    status=existing_exec.status,
                    success=existing_exec.status == ToolExecutionStatus.SUCCESS.value,
                    message=parsed_res.get("message", "Idempotent response retrieved from previous execution."),
                    provider_reference=existing_exec.provider_reference,
                    previous_payment_status=parsed_res.get("previous_payment_status"),
                    new_payment_status=parsed_res.get("new_payment_status"),
                    retry_count=parsed_res.get("retry_count", 0),
                    amount=parsed_res.get("amount", 0.0),
                    currency=parsed_res.get("currency", "INR"),
                    created_at=existing_exec.created_at,
                    guardrail_status=parsed_res.get("guardrail_status", "SAFE"),
                    guardrail_constraints=parsed_res.get("guardrail_constraints", []),
                    requires_human_approval=parsed_res.get("requires_human_approval", False),
                    approval_id=parsed_res.get("approval_id"),
                    payment_link_url=parsed_res.get("payment_link_url"),
                    scheduled_at=parsed_res.get("scheduled_at")
                )

        # 2. Validate Recovery Case and Payment
        case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not case:
            raise ValueError(f"Recovery case with ID '{recovery_case_id}' not found.")

        payment = case.payment
        if not payment:
            raise ValueError(f"Associated payment for case '{recovery_case_id}' not found.")

        customer = payment.customer
        if not customer:
            raise ValueError(f"Associated customer for payment '{payment.id}' not found.")

        # 3. Resolve Tool Type (from parameter, strategy proposal, or case intent)
        resolved_tool_type = cls._resolve_tool_type(case, tool_type, parameters)

        # 4. Strict Tool Allowlist Validation
        if resolved_tool_type not in TOOL_REGISTRY:
            error_msg = f"Tool '{resolved_tool_type}' is not an allowlisted executable recovery tool."
            logger.error(error_msg)
            cls._record_agent_action(
                db=db,
                case_id=case.id,
                action_type=ActionType.GUARDRAIL_CHECK.value,
                summary=f"REJECTED: {error_msg}",
                status=ActionStatus.BLOCKED_BY_GUARDRAIL.value,
                metadata={"tool_type": str(resolved_tool_type), "error": error_msg}
            )
            raise ValueError(error_msg)

        # 5. Evaluate Merchant Guardrails
        guardrails = guardrail_service.get_or_create_guardrails(db)
        guardrail_status, constraints, needs_approval = cls._evaluate_pre_execution_guardrails(
            guardrails=guardrails,
            payment=payment,
            case=case,
            tool_type=resolved_tool_type,
            parameters=parameters
        )

        # 6. Check High-Value Approval Gating
        if needs_approval and not approval_token:
            return cls._handle_approval_required(
                db=db,
                case=case,
                payment=payment,
                customer=customer,
                tool_type=resolved_tool_type,
                parameters=parameters,
                constraints=constraints,
                execution_id=execution_id,
                idempotency_key=idempotency_key
            )

        # 7. Check Guardrail Block
        if guardrail_status == "BLOCKED":
            reason = "; ".join(constraints) if constraints else "Blocked by merchant guardrail policy."
            return cls._handle_guardrail_blocked(
                db=db,
                case=case,
                payment=payment,
                customer=customer,
                tool_type=resolved_tool_type,
                parameters=parameters,
                constraints=constraints,
                reason=reason,
                execution_id=execution_id,
                idempotency_key=idempotency_key
            )

        # 8. Execute Allowlisted Tool Handler
        tool_handler = TOOL_REGISTRY[resolved_tool_type]
        case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
        db.commit()

        try:
            result = tool_handler(
                db=db,
                case=case,
                payment=payment,
                customer=customer,
                parameters=parameters,
                guardrails=guardrails,
                execution_id=execution_id
            )
        except Exception as exec_err:
            logger.exception(f"Execution failed for tool {resolved_tool_type}: {exec_err}")
            return cls._handle_execution_failure(
                db=db,
                case=case,
                payment=payment,
                customer=customer,
                tool_type=resolved_tool_type,
                parameters=parameters,
                error_msg=str(exec_err),
                execution_id=execution_id,
                idempotency_key=idempotency_key
            )

        # 9. Persist ToolExecution Record
        db_exec = ToolExecution(
            id=f"te_{uuid.uuid4().hex[:10]}",
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=resolved_tool_type.value,
            status=result.status,
            parameters_json=json.dumps(cls._sanitize_metadata(parameters)),
            result_json=json.dumps(result.model_dump(mode="json")),
            provider_reference=result.provider_reference,
            idempotency_key=idempotency_key,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(db_exec)

        # 10. Persist AgentAction Audit Record
        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=cls._map_tool_to_action_type(resolved_tool_type),
            summary=result.message,
            status=ActionStatus.EXECUTED.value if result.success else ActionStatus.FAILED.value,
            metadata={
                "execution_id": execution_id,
                "tool_type": resolved_tool_type.value,
                "provider_reference": result.provider_reference,
                "success": result.success,
                "guardrail_status": guardrail_status,
                "retry_count": result.retry_count
            }
        )

        db.commit()
        db.refresh(case)

        # Invalidate dashboard cache
        redis_service.delete("dashboard:metrics")

        return result

    # -------------------------------------------------------------
    # Tool Handler Implementations
    # -------------------------------------------------------------

    @classmethod
    def retry_payment(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: RETRY_PAYMENT
        Enforces retry limits, calls mock/test payment provider, updates state.
        """
        prev_status = payment.status

        # Verify retry limit before making provider call
        if case.retry_count >= guardrails.max_retries:
            return ToolExecutionResult(
                execution_id=execution_id,
                recovery_case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id,
                tool_type=ToolType.RETRY_PAYMENT.value,
                status=ToolExecutionStatus.BLOCKED.value,
                success=False,
                message=f"Retry blocked: Case has reached max allowed retries ({guardrails.max_retries}).",
                previous_payment_status=prev_status,
                new_payment_status=prev_status,
                retry_count=case.retry_count,
                amount=payment.amount,
                currency=payment.currency,
                guardrail_status="BLOCKED",
                guardrail_constraints=[f"Max retries limit ({guardrails.max_retries}) reached"]
            )

        # Increment retry count only on authorized execution
        case.retry_count += 1

        # Execute Test / Mock Provider charge attempt
        provider_ref = f"pay_retry_{uuid.uuid4().hex[:10]}"
        simulated_success = parameters.get("simulated_success", True)

        if simulated_success:
            payment.status = PaymentStatus.RECOVERED.value
            case.status = RecoveryStatus.RECOVERED.value
            case.recovered_amount = payment.amount
            case.completed_at = datetime.utcnow()
            customer.total_successful_payments += 1
            msg = f"Payment retry succeeded via Razorpay Test Mode for ₹{payment.amount:,.2f}. Reference: {provider_ref}."
            new_status = PaymentStatus.RECOVERED.value
            tool_status = ToolExecutionStatus.SUCCESS.value
            exec_success = True
        else:
            payment.status = PaymentStatus.FAILED.value
            new_status = PaymentStatus.FAILED.value
            msg = f"Payment retry attempt failed via issuing bank. Retry count is now {case.retry_count}."
            tool_status = ToolExecutionStatus.FAILED.value
            exec_success = False

        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.RETRY_PAYMENT.value,
            status=tool_status,
            success=exec_success,
            message=msg,
            provider_reference=provider_ref,
            previous_payment_status=prev_status,
            new_payment_status=new_status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="SAFE"
        )

    @classmethod
    def create_payment_link(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: CREATE_PAYMENT_LINK
        Generates a test/mock Razorpay payment link. Does NOT mark payment as recovered
        merely because a link was created.
        """
        prev_status = payment.status
        discount_pct = min(
            parameters.get("discount_percentage", 0.0),
            guardrails.max_discount_percentage
        )
        effective_amount = payment.amount * (1.0 - (discount_pct / 100.0))

        description = parameters.get("description", f"PayRecover payment link for #{payment.razorpay_payment_id}")
        link_res = razorpay_client.create_payment_link(
            amount_inr=effective_amount,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            description=description,
            preferred_method=parameters.get("preferred_method", "upi")
        )

        link_url = link_res.get("short_url", f"https://rzp.io/i/{uuid.uuid4().hex[:8]}")
        provider_ref = link_res.get("id", f"plink_{uuid.uuid4().hex[:8]}")

        case.payment_link_url = link_url
        case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.CREATE_PAYMENT_LINK.value,
            status=ToolExecutionStatus.SUCCESS.value,
            success=True,
            message=f"Payment link generated successfully. URL: {link_url}",
            provider_reference=provider_ref,
            previous_payment_status=prev_status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=effective_amount,
            currency=payment.currency,
            guardrail_status="SAFE",
            payment_link_url=link_url
        )

    @classmethod
    def offer_alternate_payment(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: OFFER_ALTERNATE_PAYMENT
        Validates method against allowlist (UPI, CARD, NETBANKING, WALLET) and prepares recovery flow.
        """
        prev_status = payment.status
        method = str(parameters.get("payment_method", "UPI")).upper()

        if method not in ALLOWLISTED_PAYMENT_METHODS:
            raise ValueError(f"Invalid payment method '{method}'. Allowed methods: {sorted(list(ALLOWLISTED_PAYMENT_METHODS))}")

        discount_pct = min(
            parameters.get("discount_percentage", 0.0),
            guardrails.max_discount_percentage
        )
        effective_amount = payment.amount * (1.0 - (discount_pct / 100.0))

        # Generate alternate method test reference
        provider_ref = f"alt_flow_{method.lower()}_{uuid.uuid4().hex[:8]}"
        link_url = f"https://rzp.io/i/alt_{method.lower()}_{uuid.uuid4().hex[:6]}"

        case.payment_link_url = link_url
        case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.OFFER_ALTERNATE_PAYMENT.value,
            status=ToolExecutionStatus.SUCCESS.value,
            success=True,
            message=f"Alternate payment method '{method}' prepared successfully with 1-click fallback link.",
            provider_reference=provider_ref,
            previous_payment_status=prev_status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=effective_amount,
            currency=payment.currency,
            guardrail_status="SAFE",
            payment_link_url=link_url
        )

    @classmethod
    def send_recovery_message(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: SEND_RECOVERY_MESSAGE
        Mock messaging service only. Validates quiet hours and records interaction.
        """
        prev_status = payment.status
        channel = str(parameters.get("channel", "WHATSAPP")).upper()
        if channel not in ALLOWLISTED_CHANNELS:
            channel = "WHATSAPP"

        # Check quiet hours
        if guardrail_service.is_in_quiet_hours(guardrails.quiet_hours_start, guardrails.quiet_hours_end):
            return ToolExecutionResult(
                execution_id=execution_id,
                recovery_case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id,
                tool_type=ToolType.SEND_RECOVERY_MESSAGE.value,
                status=ToolExecutionStatus.BLOCKED.value,
                success=False,
                message=f"Message outreach blocked: Current time is within quiet hours ({guardrails.quiet_hours_start} - {guardrails.quiet_hours_end}).",
                previous_payment_status=prev_status,
                new_payment_status=prev_status,
                retry_count=case.retry_count,
                amount=payment.amount,
                currency=payment.currency,
                guardrail_status="BLOCKED",
                guardrail_constraints=["Quiet hours active"]
            )

        message_text = parameters.get(
            "message",
            f"Hi {customer.name}, your payment of ₹{payment.amount:,.2f} for order #{payment.razorpay_payment_id} was unsuccessful. Complete it seamlessly here: {case.payment_link_url or 'https://rzp.io/i/demo'}"
        )

        # Log mock customer interaction
        interaction = CustomerInteraction(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            customer_id=customer.id,
            recovery_case_id=case.id,
            channel=channel,
            direction=InteractionDirection.OUTBOUND.value,
            message=message_text,
            detected_intent="RECOVERY_OUTREACH",
            confidence=1.0,
            created_at=datetime.utcnow()
        )
        db.add(interaction)
        db.commit()

        provider_ref = f"mock_msg_{uuid.uuid4().hex[:8]}"

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.SEND_RECOVERY_MESSAGE.value,
            status=ToolExecutionStatus.SUCCESS.value,
            success=True,
            message=f"Mock recovery message dispatched to {customer.phone or customer.email} via {channel}.",
            provider_reference=provider_ref,
            previous_payment_status=prev_status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="SAFE"
        )

    @classmethod
    def schedule_follow_up(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: SCHEDULE_FOLLOW_UP
        Schedules a delayed follow-up check.
        """
        delay_minutes = int(parameters.get("delay_minutes", 120))
        scheduled_time = datetime.utcnow() + timedelta(minutes=delay_minutes)
        scheduled_str = scheduled_time.isoformat()
        reason = parameters.get("reason", "Scheduled recovery re-engagement follow-up.")

        case.status = RecoveryStatus.AWAITING_CUSTOMER.value
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.SCHEDULE_FOLLOW_UP.value,
            status=ToolExecutionStatus.SUCCESS.value,
            success=True,
            message=f"Recovery follow-up scheduled in {delay_minutes} minutes ({scheduled_str}). Reason: {reason}",
            provider_reference=f"sched_{uuid.uuid4().hex[:8]}",
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="SAFE",
            scheduled_at=scheduled_str
        )

    @classmethod
    def verify_payment(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: VERIFY_PAYMENT
        Queries test/mock gateway status. If payment has been captured, reconciles state to RECOVERED.
        Prevents double-charging when customer intent indicates ALREADY_PAID.
        """
        prev_status = payment.status
        verification_status = parameters.get("simulated_status")
        
        if not verification_status:
            # Query Razorpay test mode / mock client
            provider_res = razorpay_client.fetch_payment(payment.razorpay_payment_id)
            verification_status = provider_res.get("status", "failed")

        provider_ref = f"verify_{uuid.uuid4().hex[:8]}"

        if verification_status in ["captured", "success", "paid"]:
            payment.status = PaymentStatus.RECOVERED.value
            case.status = RecoveryStatus.RECOVERED.value
            case.recovered_amount = payment.amount
            case.completed_at = datetime.utcnow()
            customer.total_successful_payments += 1
            db.commit()

            return ToolExecutionResult(
                execution_id=execution_id,
                recovery_case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id,
                tool_type=ToolType.VERIFY_PAYMENT.value,
                status=ToolExecutionStatus.SUCCESS.value,
                success=True,
                message=f"Payment verified as captured on gateway. Reconciled and marked RECOVERED for ₹{payment.amount:,.2f}.",
                provider_reference=provider_ref,
                previous_payment_status=prev_status,
                new_payment_status=PaymentStatus.RECOVERED.value,
                retry_count=case.retry_count,
                amount=payment.amount,
                currency=payment.currency,
                guardrail_status="SAFE"
            )
        else:
            return ToolExecutionResult(
                execution_id=execution_id,
                recovery_case_id=case.id,
                payment_id=payment.id,
                customer_id=customer.id,
                tool_type=ToolType.VERIFY_PAYMENT.value,
                status=ToolExecutionStatus.SUCCESS.value,
                success=True,
                message=f"Gateway verification complete: Payment #{payment.razorpay_payment_id} is not captured (status: {verification_status}).",
                provider_reference=provider_ref,
                previous_payment_status=prev_status,
                new_payment_status=payment.status,
                retry_count=case.retry_count,
                amount=payment.amount,
                currency=payment.currency,
                guardrail_status="SAFE"
            )

    @classmethod
    def escalate_to_human(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        parameters: Dict[str, Any],
        guardrails: Any,
        execution_id: str
    ) -> ToolExecutionResult:
        """
        Tool: ESCALATE_TO_HUMAN
        Creates human approval record and holds recovery case in AWAITING_HUMAN_APPROVAL.
        """
        reason = parameters.get("reason", f"High-value transaction ₹{payment.amount:,.2f} exceeds merchant threshold ₹{guardrails.high_value_threshold:,.2f}.")
        
        approval = db.query(HumanApproval).filter(
            HumanApproval.recovery_case_id == case.id,
            HumanApproval.status == "PENDING"
        ).first()

        if not approval:
            approval = HumanApproval(
                id=f"appr_{uuid.uuid4().hex[:10]}",
                recovery_case_id=case.id,
                execution_id=execution_id,
                tool_type=parameters.get("target_tool", ToolType.CREATE_PAYMENT_LINK.value),
                status="PENDING",
                reason=reason,
                amount=payment.amount,
                parameters_json=json.dumps(cls._sanitize_metadata(parameters)),
                created_at=datetime.utcnow()
            )
            db.add(approval)

        case.status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=ToolType.ESCALATE_TO_HUMAN.value,
            status=ToolExecutionStatus.APPROVAL_REQUIRED.value,
            success=False,
            message=f"Recovery held for merchant review: {reason}",
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="APPROVAL_REQUIRED",
            guardrail_constraints=[reason],
            requires_human_approval=True,
            approval_id=approval.id
        )

    # -------------------------------------------------------------
    # Approval & Rejection Endpoints Support
    # -------------------------------------------------------------

    @classmethod
    def approve_case(cls, db: Session, case_id: str) -> ToolExecutionResult:
        """
        Validates pending human approval record and executes the approved recovery tool.
        """
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case:
            raise ValueError(f"Recovery case '{case_id}' not found.")

        approval = db.query(HumanApproval).filter(
            HumanApproval.recovery_case_id == case.id,
            HumanApproval.status == "PENDING"
        ).first()

        if not approval:
            if case.status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value:
                approval = HumanApproval(
                    id=f"appr_{uuid.uuid4().hex[:10]}",
                    recovery_case_id=case.id,
                    tool_type=ToolType.CREATE_PAYMENT_LINK.value,
                    status="PENDING",
                    reason="Manual merchant approval override",
                    amount=case.payment.amount if case.payment else 0.0,
                    created_at=datetime.utcnow()
                )
                db.add(approval)
            else:
                raise ValueError(f"No pending human approval found for case '{case_id}'.")

        approval.status = "APPROVED"
        approval.approved_at = datetime.utcnow()
        case.status = RecoveryStatus.STRATEGY_SELECTED.value
        db.commit()

        target_tool = ToolType(approval.tool_type) if approval.tool_type in ToolType.__members__ else ToolType.CREATE_PAYMENT_LINK
        params = json.loads(approval.parameters_json) if approval.parameters_json else {}

        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=ActionType.GUARDRAIL_CHECK.value,
            summary=f"Merchant APPROVED recovery outreach for ₹{case.payment.amount:,.2f}.",
            status=ActionStatus.APPROVED.value,
            metadata={"approval_id": approval.id, "approved_tool": target_tool.value}
        )

        return cls.execute(
            db=db,
            recovery_case_id=case.id,
            tool_type=target_tool,
            parameters=params,
            approval_token=approval.id
        )

    @classmethod
    def reject_case(cls, db: Session, case_id: str, reason: str = "Merchant rejected automated outreach") -> Dict[str, Any]:
        """
        Rejects pending recovery action and blocks further execution.
        """
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case:
            raise ValueError(f"Recovery case '{case_id}' not found.")

        approval = db.query(HumanApproval).filter(
            HumanApproval.recovery_case_id == case.id,
            HumanApproval.status == "PENDING"
        ).first()

        if approval:
            approval.status = "REJECTED"
            approval.rejected_at = datetime.utcnow()

        case.status = RecoveryStatus.FAILED.value
        
        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=ActionType.GUARDRAIL_CHECK.value,
            summary=f"Merchant REJECTED recovery action: {reason}",
            status=ActionStatus.REJECTED.value,
            metadata={"reason": reason}
        )
        db.commit()

        return {"message": "Recovery action rejected by merchant", "case_id": case.id, "status": "REJECTED"}

    # -------------------------------------------------------------
    # Internal Validation and Helper Methods
    # -------------------------------------------------------------

    @classmethod
    def _resolve_tool_type(
        cls,
        case: RecoveryCase,
        tool_type: Optional[ToolType],
        parameters: Dict[str, Any]
    ) -> ToolType:
        if tool_type is not None:
            if isinstance(tool_type, ToolType):
                return tool_type
            if str(tool_type) in ToolType.__members__:
                return ToolType[str(tool_type)]

        strat = (case.current_strategy or "").upper()
        intent = (case.customer_intent or "").upper()

        if "VERIFY" in strat or "ALREADY_PAID" in intent:
            return ToolType.VERIFY_PAYMENT
        if "RETRY" in strat:
            return ToolType.RETRY_PAYMENT
        if "ALTERNATE" in strat or "UPI" in strat:
            return ToolType.OFFER_ALTERNATE_PAYMENT
        if "LINK" in strat:
            return ToolType.CREATE_PAYMENT_LINK
        if "FOLLOW" in strat or "LATER" in intent:
            return ToolType.SCHEDULE_FOLLOW_UP
        if "HUMAN" in strat or "ESCALAT" in strat:
            return ToolType.ESCALATE_TO_HUMAN

        return ToolType.CREATE_PAYMENT_LINK

    @classmethod
    def _evaluate_pre_execution_guardrails(
        cls,
        guardrails: Any,
        payment: Payment,
        case: RecoveryCase,
        tool_type: ToolType,
        parameters: Dict[str, Any]
    ) -> Tuple[str, list, bool]:
        constraints = []
        guardrail_status = "SAFE"
        needs_approval = False

        # 1. High value check
        if guardrails.human_approval_required and payment.amount >= guardrails.high_value_threshold:
            needs_approval = True
            constraints.append(f"High-Value Transaction: ₹{payment.amount:,.2f} exceeds threshold ₹{guardrails.high_value_threshold:,.2f}")
            guardrail_status = "APPROVAL_REQUIRED"

        # 2. Retry limit check
        if tool_type == ToolType.RETRY_PAYMENT and case.retry_count >= guardrails.max_retries:
            guardrail_status = "BLOCKED"
            constraints.append(f"Max Retry Limit Reached ({case.retry_count}/{guardrails.max_retries})")

        # 3. Discount cap check
        discount = parameters.get("discount_percentage", 0.0)
        if discount > guardrails.max_discount_percentage:
            constraints.append(f"Discount {discount}% capped to max policy {guardrails.max_discount_percentage}%")
            parameters["discount_percentage"] = guardrails.max_discount_percentage

        return guardrail_status, constraints, needs_approval

    @classmethod
    def _handle_approval_required(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        tool_type: ToolType,
        parameters: Dict[str, Any],
        constraints: list,
        execution_id: str,
        idempotency_key: Optional[str]
    ) -> ToolExecutionResult:
        reason = "; ".join(constraints) or "Human approval required prior to execution."
        approval = db.query(HumanApproval).filter(
            HumanApproval.recovery_case_id == case.id,
            HumanApproval.status == "PENDING"
        ).first()

        if not approval:
            approval = HumanApproval(
                id=f"appr_{uuid.uuid4().hex[:10]}",
                recovery_case_id=case.id,
                execution_id=execution_id,
                tool_type=tool_type.value,
                status="PENDING",
                reason=reason,
                amount=payment.amount,
                parameters_json=json.dumps(cls._sanitize_metadata(parameters)),
                created_at=datetime.utcnow()
            )
            db.add(approval)

        case.status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
        db.commit()

        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=ActionType.GUARDRAIL_CHECK.value,
            summary=f"Execution held for merchant approval: {reason}",
            status=ActionStatus.PROPOSED.value,
            metadata={"approval_id": approval.id, "tool_type": tool_type.value}
        )
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=tool_type.value,
            status=ToolExecutionStatus.APPROVAL_REQUIRED.value,
            success=False,
            message=f"Human approval required: {reason}",
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="APPROVAL_REQUIRED",
            guardrail_constraints=constraints,
            requires_human_approval=True,
            approval_id=approval.id
        )

    @classmethod
    def _handle_guardrail_blocked(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        tool_type: ToolType,
        parameters: Dict[str, Any],
        constraints: list,
        reason: str,
        execution_id: str,
        idempotency_key: Optional[str]
    ) -> ToolExecutionResult:
        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=ActionType.GUARDRAIL_CHECK.value,
            summary=f"BLOCKED BY GUARDRAIL: {reason}",
            status=ActionStatus.BLOCKED_BY_GUARDRAIL.value,
            metadata={"tool_type": tool_type.value, "reason": reason}
        )
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=tool_type.value,
            status=ToolExecutionStatus.BLOCKED.value,
            success=False,
            message=f"Tool execution blocked by merchant guardrail: {reason}",
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="BLOCKED",
            guardrail_constraints=constraints
        )

    @classmethod
    def _handle_execution_failure(
        cls,
        db: Session,
        case: RecoveryCase,
        payment: Payment,
        customer: Any,
        tool_type: ToolType,
        parameters: Dict[str, Any],
        error_msg: str,
        execution_id: str,
        idempotency_key: Optional[str]
    ) -> ToolExecutionResult:
        cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=cls._map_tool_to_action_type(tool_type),
            summary=f"Tool execution failed: {error_msg}",
            status=ActionStatus.FAILED.value,
            metadata={"error": error_msg, "tool_type": tool_type.value}
        )
        db.commit()

        return ToolExecutionResult(
            execution_id=execution_id,
            recovery_case_id=case.id,
            payment_id=payment.id,
            customer_id=customer.id,
            tool_type=tool_type.value,
            status=ToolExecutionStatus.FAILED.value,
            success=False,
            message=f"Tool execution encountered an error: {error_msg}",
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            retry_count=case.retry_count,
            amount=payment.amount,
            currency=payment.currency,
            guardrail_status="SAFE"
        )

    @classmethod
    def _record_agent_action(
        cls,
        db: Session,
        case_id: str,
        action_type: str,
        summary: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentAction:
        action = AgentAction(
            id=f"act_{uuid.uuid4().hex[:10]}",
            recovery_case_id=case_id,
            agent_type=AgentType.TOOL_EXECUTOR.value,
            action_type=action_type,
            reasoning_summary=summary,
            status=status,
            action_metadata=json.dumps(cls._sanitize_metadata(metadata or {})),
            created_at=datetime.utcnow()
        )
        db.add(action)
        return action

    @classmethod
    def _map_tool_to_action_type(cls, tool_type: ToolType) -> str:
        mapping = {
            ToolType.RETRY_PAYMENT: ActionType.RETRY_PAYMENT.value,
            ToolType.CREATE_PAYMENT_LINK: ActionType.GENERATE_PAYMENT_LINK.value,
            ToolType.OFFER_ALTERNATE_PAYMENT: ActionType.GENERATE_PAYMENT_LINK.value,
            ToolType.SEND_RECOVERY_MESSAGE: ActionType.DISPATCH_MESSAGE.value,
            ToolType.SCHEDULE_FOLLOW_UP: ActionType.SELECT_STRATEGY.value,
            ToolType.VERIFY_PAYMENT: ActionType.PAYMENT_CONFIRMED.value,
            ToolType.ESCALATE_TO_HUMAN: ActionType.ESCALATE_HUMAN.value,
        }
        return mapping.get(tool_type, ActionType.SELECT_STRATEGY.value)

    @classmethod
    def _sanitize_metadata(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip sensitive secrets (API keys, credentials, CVV, tokens)."""
        sensitive_keys = {"secret", "key", "token", "password", "cvv", "card_number", "auth"}
        clean = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys):
                clean[k] = "[REDACTED]"
            elif isinstance(v, dict):
                clean[k] = cls._sanitize_metadata(v)
            else:
                clean[k] = v
        return clean


    @classmethod
    def execute_action(
        cls,
        db: Session,
        recovery_case_id: str,
        agent_type: str,
        action_type: str,
        parameters: Dict[str, Any],
        reasoning: str
    ) -> Dict[str, Any]:
        """
        Legacy/Orchestrator helper for recording agent stage transitions or basic actions.
        """
        case = db.query(RecoveryCase).filter(RecoveryCase.id == recovery_case_id).first()
        if not case:
            return {"success": False, "error": f"Case {recovery_case_id} not found"}

        payment = case.payment
        guardrails = guardrail_service.get_or_create_guardrails(db)
        
        # Guardrail check if payment link is generated
        if action_type == ActionType.GENERATE_PAYMENT_LINK.value and payment:
            if guardrails.human_approval_required and payment.amount >= guardrails.high_value_threshold:
                case.status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
                db.commit()
                cls._record_agent_action(
                    db=db,
                    case_id=case.id,
                    action_type=ActionType.GUARDRAIL_CHECK.value,
                    summary=f"BLOCKED BY GUARDRAIL: High-Value Transaction (₹{payment.amount:,.2f} >= ₹{guardrails.high_value_threshold:,.2f}) requires human approval.",
                    status=ActionStatus.BLOCKED_BY_GUARDRAIL.value,
                    metadata=parameters
                )
                db.commit()
                return {"success": False, "status": ActionStatus.BLOCKED_BY_GUARDRAIL.value, "reason": "High-Value Transaction requires human approval"}

            link_res = razorpay_client.create_payment_link(
                amount_inr=payment.amount * (1 - parameters.get("discount_percentage", 0.0) / 100),
                customer_name=payment.customer.name,
                customer_email=payment.customer.email,
                customer_phone=payment.customer.phone,
                description=f"Recovery for Payment #{payment.razorpay_payment_id}",
                preferred_method=parameters.get("preferred_method", "upi")
            )
            case.payment_link_url = link_res.get("short_url")
            case.status = RecoveryStatus.ACTION_IN_PROGRESS.value
            db.commit()

        action = cls._record_agent_action(
            db=db,
            case_id=case.id,
            action_type=action_type,
            summary=reasoning,
            status=ActionStatus.EXECUTED.value,
            metadata=parameters
        )
        db.commit()
        return {"success": True, "action_id": action.id, "status": ActionStatus.EXECUTED.value}


# Explicit Allowlist Tool Registry
TOOL_REGISTRY: Dict[ToolType, Callable] = {
    ToolType.RETRY_PAYMENT: ToolExecutor.retry_payment,
    ToolType.CREATE_PAYMENT_LINK: ToolExecutor.create_payment_link,
    ToolType.OFFER_ALTERNATE_PAYMENT: ToolExecutor.offer_alternate_payment,
    ToolType.SEND_RECOVERY_MESSAGE: ToolExecutor.send_recovery_message,
    ToolType.SCHEDULE_FOLLOW_UP: ToolExecutor.schedule_follow_up,
    ToolType.VERIFY_PAYMENT: ToolExecutor.verify_payment,
    ToolType.ESCALATE_TO_HUMAN: ToolExecutor.escalate_to_human
}

# Singleton instance for orchestrator and backward compatibility
tool_executor = ToolExecutor()

