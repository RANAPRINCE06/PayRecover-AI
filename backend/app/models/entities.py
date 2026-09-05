import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"
    ABANDONED = "ABANDONED"


class RecoveryStatus(str, enum.Enum):
    IDENTIFIED = "IDENTIFIED"
    INVESTIGATING = "INVESTIGATING"
    STRATEGY_SELECTED = "STRATEGY_SELECTED"
    ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class PaymentMethod(str, enum.Enum):
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"
    EMI = "EMI"


class FailureReason(str, enum.Enum):
    UPI_TIMEOUT = "UPI_TIMEOUT"
    CARD_DECLINED = "CARD_DECLINED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    BANK_SERVER_DOWN = "BANK_SERVER_DOWN"
    SUBSCRIPTION_FAILED = "SUBSCRIPTION_FAILED"


class AgentType(str, enum.Enum):
    INVESTIGATOR = "INVESTIGATOR"
    STRATEGIST = "STRATEGIST"
    INTENT_AI = "INTENT_AI"
    ORCHESTRATOR = "ORCHESTRATOR"
    TOOL_EXECUTOR = "TOOL_EXECUTOR"


class ActionType(str, enum.Enum):
    INVESTIGATE_PAYMENT = "INVESTIGATE_PAYMENT"
    CALCULATE_SCORE = "CALCULATE_SCORE"
    SELECT_STRATEGY = "SELECT_STRATEGY"
    DISPATCH_MESSAGE = "DISPATCH_MESSAGE"
    GENERATE_PAYMENT_LINK = "GENERATE_PAYMENT_LINK"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    OFFER_DISCOUNT = "OFFER_DISCOUNT"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    GUARDRAIL_CHECK = "GUARDRAIL_CHECK"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"


class ActionStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    BLOCKED_BY_GUARDRAIL = "BLOCKED_BY_GUARDRAIL"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class InteractionChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    EMAIL = "EMAIL"
    VOICE = "VOICE"


class InteractionDirection(str, enum.Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


# 1. Merchant
class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    guardrails = relationship("MerchantGuardrail", back_populates="merchant", uselist=False)


# 2. Customer
class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(30), nullable=False)
    customer_value = Column(String(50), default="STANDARD")  # HIGH_VALUE, VIP, STANDARD, CHURN_RISK
    preferred_payment_method = Column(String(50), default="UPI")
    total_successful_payments = Column(Integer, default=0)
    total_failed_payments = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    payments = relationship("Payment", back_populates="customer")
    interactions = relationship("CustomerInteraction", back_populates="customer")


# 3. Payment
class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(50), primary_key=True, index=True)
    razorpay_payment_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(50), ForeignKey("customers.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    payment_method = Column(String(50), nullable=False)
    status = Column(String(50), default=PaymentStatus.PENDING.value, index=True)
    failure_reason = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="payments")
    recovery_case = relationship("RecoveryCase", back_populates="payment", uselist=False)


# 4. Recovery Case
class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(String(50), primary_key=True, index=True)
    payment_id = Column(String(50), ForeignKey("payments.id"), unique=True, nullable=False, index=True)
    recovery_score = Column(Float, default=0.0)  # 0 to 100
    recovery_probability = Column(Float, default=0.0)  # 0.0 to 1.0
    customer_intent = Column(String(100), nullable=True)  # e.g., ALTERNATE_PAYMENT_METHOD, PAY_LATER
    current_strategy = Column(String(100), nullable=True)  # e.g., UPI_FALLBACK_LINK, SMART_DISCOUNT
    status = Column(String(50), default=RecoveryStatus.IDENTIFIED.value, index=True)
    retry_count = Column(Integer, default=0)
    recovered_amount = Column(Float, default=0.0)
    payment_link_url = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    payment = relationship("Payment", back_populates="recovery_case")
    actions = relationship("AgentAction", back_populates="recovery_case", order_by="AgentAction.created_at")
    interactions = relationship("CustomerInteraction", back_populates="recovery_case", order_by="CustomerInteraction.created_at")
    tool_executions = relationship("ToolExecution", back_populates="recovery_case", order_by="ToolExecution.created_at")
    approvals = relationship("HumanApproval", back_populates="recovery_case", order_by="HumanApproval.created_at")


# 5. Agent Action
class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String(50), primary_key=True, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    status = Column(String(50), default=ActionStatus.EXECUTED.value, index=True)
    action_metadata = Column(Text, nullable=True)  # JSON-serialized metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    recovery_case = relationship("RecoveryCase", back_populates="actions")


# 6. Merchant Guardrails
class MerchantGuardrail(Base):
    __tablename__ = "merchant_guardrails"

    id = Column(String(50), primary_key=True, index=True)
    merchant_id = Column(String(50), ForeignKey("merchants.id"), unique=True, nullable=False)
    max_retries = Column(Integer, default=3)
    max_discount_percentage = Column(Float, default=10.0)
    max_campaign_days = Column(Integer, default=3)
    quiet_hours_start = Column(String(10), default="22:00")
    quiet_hours_end = Column(String(10), default="08:00")
    high_value_threshold = Column(Float, default=50000.0)
    human_approval_required = Column(Boolean, default=True)
    max_contact_attempts = Column(Integer, default=4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    merchant = relationship("Merchant", back_populates="guardrails")


# 7. Customer Interactions
class CustomerInteraction(Base):
    __tablename__ = "customer_interactions"

    id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey("customers.id"), nullable=False, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=True, index=True)
    channel = Column(String(50), default=InteractionChannel.WHATSAPP.value)
    direction = Column(String(50), default=InteractionDirection.OUTBOUND.value)
    message = Column(Text, nullable=False)
    detected_intent = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    customer = relationship("Customer", back_populates="interactions")
    recovery_case = relationship("RecoveryCase", back_populates="interactions")


# 8. Tool Executions (Phase 5)
class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String(50), primary_key=True, index=True)
    execution_id = Column(String(100), unique=True, nullable=False, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.id"), nullable=False, index=True)
    customer_id = Column(String(50), ForeignKey("customers.id"), nullable=False, index=True)
    tool_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default="PROPOSED", index=True)
    parameters_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    provider_reference = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    recovery_case = relationship("RecoveryCase", back_populates="tool_executions")
    payment = relationship("Payment")
    customer = relationship("Customer")


# 9. Human Approvals (Phase 5)
class HumanApproval(Base):
    __tablename__ = "human_approvals"

    id = Column(String(50), primary_key=True, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    execution_id = Column(String(100), nullable=True, index=True)
    tool_type = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED
    reason = Column(Text, nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    parameters_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)

    recovery_case = relationship("RecoveryCase", back_populates="approvals")


# 10. User (Phase 8 Authentication & RBAC)
class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(150), nullable=False)
    role = Column(String(50), default=UserRole.VIEWER.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    merchant_id = Column(String(50), ForeignKey("merchants.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    merchant = relationship("Merchant")


# 11. Idempotency Record (Phase 8 Idempotency Protection)
class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String(50), primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False, index=True)
    recovery_case_id = Column(String(50), nullable=True, index=True)
    action_type = Column(String(100), nullable=False)
    status_code = Column(Integer, default=200, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

