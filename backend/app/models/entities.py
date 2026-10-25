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
    Index,
    UniqueConstraint
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


class WebhookEventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    RETRY_PENDING = "RETRY_PENDING"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class RecoveryOutcomeStatus(str, enum.Enum):
    RECOVERED = "RECOVERED"
    UNSUCCESSFUL = "UNSUCCESSFUL"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


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
    outcome = relationship("RecoveryOutcome", back_populates="payment", uselist=False)

    __table_args__ = (
        Index("idx_payment_status_created", "status", "created_at"),
        Index("idx_payment_customer_created", "customer_id", "created_at"),
    )


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
    outcome = relationship("RecoveryOutcome", back_populates="recovery_case", uselist=False)

    __table_args__ = (
        Index("idx_case_status_started", "status", "started_at"),
        Index("idx_case_score", "recovery_score"),
    )


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

    __table_args__ = (
        Index("idx_action_case_created", "recovery_case_id", "created_at"),
    )


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


# 12. Webhook Event (Production Webhook Ingestion & Durable Outbox)
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String(50), primary_key=True, index=True)
    provider = Column(String(50), default="razorpay", nullable=False, index=True)
    provider_event_id = Column(String(120), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default=WebhookEventStatus.RECEIVED.value, nullable=False, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    internal_payment_id = Column(String(50), ForeignKey("payments.id"), nullable=True, index=True)
    internal_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=True, index=True)
    payload_json = Column(Text, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    processing_metadata_json = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    payment = relationship("Payment")
    recovery_case = relationship("RecoveryCase")

    __table_args__ = (
        Index("idx_webhook_status_retry", "status", "next_retry_at"),
        Index("idx_webhook_type_received", "event_type", "received_at"),
    )


# 13. Recovery Outcome (Phase 4 AI Recovery Intelligence & Historical Engine)
class RecoveryOutcome(Base):
    __tablename__ = "recovery_outcomes"

    id = Column(String(50), primary_key=True, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), unique=True, nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.id"), nullable=False, index=True)
    customer_id = Column(String(50), ForeignKey("customers.id"), nullable=False, index=True)

    # Failure & Transaction telemetry
    failure_category = Column(String(100), nullable=False, index=True)
    payment_method = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    amount_range = Column(String(50), nullable=False, index=True)  # "<1000", "1000-5000", "5000-25000", ">25000"
    customer_intent = Column(String(100), nullable=True, index=True)

    # Strategy & Decision parameters
    selected_strategy = Column(String(100), nullable=False, index=True)
    communication_channel = Column(String(50), nullable=False, default="WHATSAPP")
    retry_count = Column(Integer, default=0, nullable=False)
    discount_offered_percent = Column(Float, default=0.0, nullable=False)
    human_approval_required = Column(Boolean, default=False, nullable=False)
    processing_latency_ms = Column(Integer, default=0, nullable=False)

    # Verified outcome
    outcome_status = Column(String(50), default=RecoveryOutcomeStatus.PENDING.value, nullable=False, index=True)
    recovered_amount = Column(Float, default=0.0, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_source = Column(String(150), nullable=True)  # e.g., "razorpay_webhook:whe_..."
    time_to_recovery_seconds = Column(Float, nullable=True)

    # Temporal tracking (Prevents data leakage in intelligence models)
    decision_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    outcome_timestamp = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    recovery_case = relationship("RecoveryCase", back_populates="outcome")
    payment = relationship("Payment", back_populates="outcome")
    customer = relationship("Customer")

    __table_args__ = (
        Index("idx_outcome_status_decision", "outcome_status", "decision_timestamp"),
        Index("idx_outcome_strategy_failure", "selected_strategy", "failure_category"),
        Index("idx_outcome_method_amount", "payment_method", "amount_range"),
    )


# -------------------------------------------------------------
# PHASE 5 — RAG KNOWLEDGE ENGINE ENTITIES
# -------------------------------------------------------------

class KnowledgeCategory(str, enum.Enum):
    MERCHANT_POLICY = "MERCHANT_POLICY"
    FAILURE_KNOWLEDGE = "FAILURE_KNOWLEDGE"
    RECOVERY_PLAYBOOK = "RECOVERY_PLAYBOOK"
    HISTORICAL_INSIGHT = "HISTORICAL_INSIGHT"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    DRAFT = "DRAFT"
    DEPRECATED = "DEPRECATED"
    CONFLICTED = "CONFLICTED"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # POLICY, PLAYBOOK, FAILURE_GUIDE, HISTORICAL_REPORT
    source_reference = Column(String(255), nullable=False)
    merchant_id = Column(String(50), ForeignKey("merchants.id"), nullable=True, index=True)  # Null = global platform knowledge
    version = Column(Integer, default=1, nullable=False)
    verification_status = Column(String(50), default=VerificationStatus.VERIFIED.value, nullable=False, index=True)
    effective_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    raw_content = Column(Text, nullable=False)
    doc_metadata_json = Column(Text, nullable=True)  # JSON tags, author, approved_by, rules
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    merchant = relationship("Merchant")
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.chunk_index")

    __table_args__ = (
        Index("idx_kdoc_cat_verif", "category", "verification_status"),
        Index("idx_kdoc_merchant_cat", "merchant_id", "category"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(50), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    heading = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    embedding_json = Column(Text, nullable=False)  # Serialized 768-dim float vector
    token_count = Column(Integer, default=0, nullable=False)
    chunk_metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_kchunk_doc_index", "document_id", "chunk_index"),
    )


# -------------------------------------------------------------
# PHASE 6 — RECOVERY STRATEGY EXPERIMENTATION & OPTIMIZATION
# -------------------------------------------------------------

class ExperimentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class RecoveryExperiment(Base):
    __tablename__ = "recovery_experiments"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    objective = Column(Text, nullable=False)
    hypothesis = Column(Text, nullable=True)
    status = Column(String(50), default=ExperimentStatus.DRAFT.value, nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    merchant_id = Column(String(50), ForeignKey("merchants.id"), nullable=True, index=True)
    owner_email = Column(String(150), nullable=False)
    primary_metric = Column(String(50), default="recovery_rate", nullable=False)
    is_sandbox_only = Column(Boolean, default=True, nullable=False)

    # Eligibility & Targeting Filters (JSON arrays / numeric thresholds)
    target_failure_categories_json = Column(Text, nullable=True)  # JSON list e.g. ["UPI_TIMEOUT", "CARD_DECLINED"]
    target_payment_methods_json = Column(Text, nullable=True)      # JSON list e.g. ["UPI", "CARD"]
    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    target_customer_intent_json = Column(Text, nullable=True)     # JSON list e.g. ["WILL_PAY_LATER"]

    # Candidate Strategy Arms (JSON list of arm configurations)
    # [{"arm_id": "control", "strategy": "PAYMENT_LINK", "traffic_percentage": 50.0, "is_control": True}, ...]
    candidate_strategies_json = Column(Text, nullable=False)

    # Observation Constraints
    max_sample_size = Column(Integer, nullable=True)
    min_observation_count = Column(Integer, default=30, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    merchant = relationship("Merchant")
    assignments = relationship("ExperimentAssignment", back_populates="experiment", cascade="all, delete-orphan")
    attributions = relationship("ExperimentOutcomeAttribution", back_populates="experiment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_exp_status_merchant", "status", "merchant_id"),
        Index("idx_exp_status_created", "status", "created_at"),
    )


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"

    id = Column(String(50), primary_key=True, index=True)
    experiment_id = Column(String(50), ForeignKey("recovery_experiments.id"), nullable=False, index=True)
    experiment_version = Column(Integer, nullable=False)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.id"), nullable=False, index=True)
    arm_id = Column(String(50), nullable=False, index=True)
    assigned_strategy = Column(String(100), nullable=False, index=True)
    is_control = Column(Boolean, default=False, nullable=False)
    hash_bucket = Column(Integer, nullable=False)
    assignment_salt = Column(String(50), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    eligibility_snapshot_json = Column(Text, nullable=True)

    experiment = relationship("RecoveryExperiment", back_populates="assignments")
    recovery_case = relationship("RecoveryCase")
    payment = relationship("Payment")
    attribution = relationship("ExperimentOutcomeAttribution", back_populates="assignment", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("experiment_id", "recovery_case_id", name="uq_exp_case_assignment"),
        Index("idx_exp_assign_arm", "experiment_id", "arm_id"),
    )


class ExperimentOutcomeAttribution(Base):
    __tablename__ = "experiment_outcome_attributions"

    id = Column(String(50), primary_key=True, index=True)
    assignment_id = Column(String(50), ForeignKey("experiment_assignments.id"), unique=True, nullable=False, index=True)
    experiment_id = Column(String(50), ForeignKey("recovery_experiments.id"), nullable=False, index=True)
    recovery_case_id = Column(String(50), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.id"), nullable=False, index=True)
    arm_id = Column(String(50), nullable=False, index=True)

    assigned_strategy = Column(String(100), nullable=False)
    actual_executed_strategy = Column(String(100), nullable=False)
    is_strategy_deviated = Column(Boolean, default=False, nullable=False)
    deviation_reason = Column(String(255), nullable=True)

    outcome_status = Column(String(50), default="PENDING", nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    recovered_amount = Column(Float, default=0.0, nullable=False)
    discount_offered = Column(Float, default=0.0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    human_escalated = Column(Boolean, default=False, nullable=False)
    time_to_recovery_seconds = Column(Float, nullable=True)

    assigned_at = Column(DateTime, nullable=False)
    executed_at = Column(DateTime, nullable=True)
    attributed_at = Column(DateTime, nullable=True)
    verification_source = Column(String(150), nullable=True)
    attribution_window_valid = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    assignment = relationship("ExperimentAssignment", back_populates="attribution")
    experiment = relationship("RecoveryExperiment", back_populates="attributions")
    recovery_case = relationship("RecoveryCase")
    payment = relationship("Payment")

    __table_args__ = (
        Index("idx_att_exp_arm_outcome", "experiment_id", "arm_id", "outcome_status"),
    )



