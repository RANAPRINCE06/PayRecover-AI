from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# AI Structured Output Contracts
# -------------------------------------------------------------

class PaymentInvestigationResult(BaseModel):
    payment_id: str
    failure_category: str  # temporary, customer_action_required, payment_method_issue, insufficient_funds, technical, unknown
    failure_explanation: str
    customer_profile_summary: str
    payment_history_summary: str
    recovery_probability: float = Field(..., ge=0.0, le=1.0)
    recovery_score: int = Field(..., ge=0, le=100)
    risk_level: str  # LOW, MEDIUM, HIGH
    recommended_next_action: str  # RETRY, ALTERNATE_PAYMENT_METHOD, PAYMENT_LINK, FOLLOW_UP, INCENTIVE_REVIEW, HUMAN_ESCALATION, STOP_RECOVERY
    reasoning_summary: str
    contributing_factors: List[str] = Field(default_factory=list)
    negative_factors: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)


class RecoveryStrategy(BaseModel):
    strategy: str
    priority: str  # IMMEDIATE, HIGH, STANDARD, LOW
    expected_recovery_probability: float = Field(..., ge=0.0, le=1.0)
    estimated_revenue_recovery: float
    recommended_channel: str  # WHATSAPP, SMS, EMAIL, VOICE
    retry_payment: bool
    create_payment_link: bool
    offer_discount: bool
    discount_percentage: float = 0.0
    schedule_followup: bool
    escalate_to_human: bool
    reasoning: str


class CustomerIntentRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, description="Customer ID")
    recovery_case_id: Optional[str] = Field(default=None, description="Optional associated recovery case ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Customer inbound or chat message")
    channel: str = Field(default="WHATSAPP", description="Interaction channel (WHATSAPP, SMS, EMAIL, VOICE)")

    model_config = ConfigDict(str_strip_whitespace=True)


class CustomerIntentResult(BaseModel):
    customer_id: str
    recovery_case_id: Optional[str] = None
    intent: str  # ALTERNATE_PAYMENT_METHOD, WILL_PAY_LATER, PAYMENT_PROBLEM, PRICE_CONCERN, CANCEL_REQUEST, ALREADY_PAID, NEEDS_ASSISTANCE, NOT_INTERESTED, PAYMENT_LINK_REQUEST, RETRY_REQUEST, UNKNOWN
    confidence: float = Field(..., ge=0.0, le=1.0)
    sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE, FRUSTRATED
    urgency: str  # LOW, MEDIUM, HIGH
    intent_summary: str
    evidence: List[str] = Field(default_factory=list)
    recommended_channel: str  # WHATSAPP, SMS, EMAIL, VOICE, NONE
    recommended_action: str  # OFFER_ALTERNATE_PAYMENT, WAIT_AND_FOLLOW_UP, INVESTIGATE_PAYMENT, PROVIDE_PAYMENT_LINK, REVIEW_PAYMENT_STATUS, OFFER_ASSISTANCE, STOP_CONTACT, RETRY_PAYMENT, HUMAN_ESCALATION
    reasoning_summary: str

    model_config = ConfigDict(from_attributes=True)


class RecoveryStrategyType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    ALTERNATE_PAYMENT_METHOD = "ALTERNATE_PAYMENT_METHOD"
    PAYMENT_LINK = "PAYMENT_LINK"
    FOLLOW_UP = "FOLLOW_UP"
    INCENTIVE = "INCENTIVE"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    STOP_RECOVERY = "STOP_RECOVERY"
    VERIFY_PAYMENT = "VERIFY_PAYMENT"


class GuardrailStatusType(str, Enum):
    SAFE = "SAFE"
    CAPPED = "CAPPED"
    BLOCKED = "BLOCKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class RecoveryStrategyProposal(BaseModel):
    """Raw AI strategy proposal before deterministic backend guardrail enforcement."""
    primary_strategy: str = Field(..., min_length=1)
    secondary_strategy: Optional[str] = None
    recommended_channel: str = Field(default="WHATSAPP", min_length=1)
    recommended_payment_method: Optional[str] = None
    proposed_discount_percentage: float = Field(default=0.0, ge=0.0)
    proposed_retry_count: int = Field(default=0, ge=0)
    expected_recovery_probability: float = Field(..., ge=0.0, le=1.0)
    strategy_confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_delay_minutes: int = Field(default=0, ge=0)
    human_approval_required: bool = False
    approval_reason: Optional[str] = None
    strategy_summary: str = Field(..., min_length=1)
    reasoning_summary: str = Field(..., min_length=1)
    supporting_factors: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    rejected_strategies: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class RecoveryStrategyRequest(BaseModel):
    recovery_case_id: str = Field(..., min_length=1, max_length=100, description="Target recovery case ID")

    model_config = ConfigDict(str_strip_whitespace=True)


class RecoveryStrategyResult(BaseModel):
    """Final, policy-enforced safe recovery strategy."""
    recovery_case_id: str = Field(..., min_length=1)
    payment_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    primary_strategy: str = Field(..., min_length=1)
    secondary_strategy: Optional[str] = None
    recommended_channel: str = Field(..., min_length=1)
    recommended_payment_method: Optional[str] = None
    discount_percentage: float = Field(default=0.0, ge=0.0)
    discount_amount: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="INR", min_length=1)
    expected_recovery_probability: float = Field(..., ge=0.0, le=1.0)
    strategy_confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_delay_minutes: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    human_approval_required: bool = False
    approval_reason: Optional[str] = None
    strategy_summary: str = Field(..., min_length=1)
    reasoning_summary: str = Field(..., min_length=1)
    supporting_factors: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    rejected_strategies: List[str] = Field(default_factory=list)
    guardrail_status: str = Field(..., min_length=1)  # SAFE, CAPPED, BLOCKED, APPROVAL_REQUIRED
    guardrail_constraints: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# -------------------------------------------------------------
# Entity Schemas & API Responses
# -------------------------------------------------------------

class CustomerSchema(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    customer_value: str
    preferred_payment_method: str
    total_successful_payments: int
    total_failed_payments: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentSchema(BaseModel):
    id: str
    razorpay_payment_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    customer: Optional[CustomerSchema] = None

    model_config = ConfigDict(from_attributes=True)


class AgentActionSchema(BaseModel):
    id: str
    recovery_case_id: str
    agent_type: str
    action_type: str
    reasoning_summary: str
    status: str
    action_metadata: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerInteractionSchema(BaseModel):
    id: str
    customer_id: str
    recovery_case_id: Optional[str] = None
    channel: str
    direction: str
    message: str
    detected_intent: Optional[str] = None
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryCaseSchema(BaseModel):
    id: str
    payment_id: str
    recovery_score: float
    recovery_probability: float
    customer_intent: Optional[str] = None
    current_strategy: Optional[str] = None
    status: str
    retry_count: int
    recovered_amount: float
    payment_link_url: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    payment: Optional[PaymentSchema] = None
    actions: List[AgentActionSchema] = []
    interactions: List[CustomerInteractionSchema] = []

    model_config = ConfigDict(from_attributes=True)


class GuardrailSchema(BaseModel):
    id: Optional[str] = None
    merchant_id: str
    max_retries: int = 3
    max_discount_percentage: float = 10.0
    max_campaign_days: int = 3
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    high_value_threshold: float = 50000.0
    human_approval_required: bool = True
    max_contact_attempts: int = 4

    model_config = ConfigDict(from_attributes=True)


class GuardrailUpdateSchema(BaseModel):
    max_retries: Optional[int] = None
    max_discount_percentage: Optional[float] = None
    max_campaign_days: Optional[int] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    high_value_threshold: Optional[float] = None
    human_approval_required: Optional[bool] = None
    max_contact_attempts: Optional[int] = None


class DashboardMetrics(BaseModel):
    revenue_processed: float
    revenue_at_risk: float
    predicted_recoverable: float
    revenue_recovered: float
    recovery_rate: float
    failed_payments_count: int
    active_recoveries_count: int
    human_review_queue_count: int
    monthly_trend: List[Dict[str, Any]]
    recovery_by_method: List[Dict[str, Any]]
    recovery_by_reason: List[Dict[str, Any]]
    recovery_pipeline: List[Dict[str, Any]]


class CopilotRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None


class CopilotResponse(BaseModel):
    reply: str
    insights: List[str] = []
    recommended_actions: List[Dict[str, Any]] = []
    data_snapshot: Optional[Dict[str, Any]] = None


class SimulateRecoveryRequest(BaseModel):
    scenario_type: str = "DEMO_CARD_DECLINE_UPI"  # DEMO_CARD_DECLINE_UPI, UPI_TIMEOUT, INSUFFICIENT_FUNDS, HIGH_VALUE_APPROVAL
    amount: float = 12999.0
    customer_id: Optional[str] = None
