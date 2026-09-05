from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_validator


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
# Phase 5 - Tool Calling & Autonomous Execution Contracts
# -------------------------------------------------------------

class ToolType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    OFFER_ALTERNATE_PAYMENT = "OFFER_ALTERNATE_PAYMENT"
    SEND_RECOVERY_MESSAGE = "SEND_RECOVERY_MESSAGE"
    SCHEDULE_FOLLOW_UP = "SCHEDULE_FOLLOW_UP"
    VERIFY_PAYMENT = "VERIFY_PAYMENT"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


class ToolExecutionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class ToolProposal(BaseModel):
    tool_type: ToolType = Field(..., description="Allowlisted recovery tool type")
    recovery_case_id: str = Field(..., min_length=1, description="Associated recovery case ID")
    payment_id: str = Field(..., min_length=1, description="Associated payment ID")
    customer_id: str = Field(..., min_length=1, description="Associated customer ID")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool execution parameters")
    reason: str = Field(..., min_length=1, description="Reasoning for tool recommendation")
    strategy_source: Optional[str] = Field(default=None, description="Originating strategy name")
    requires_approval: bool = Field(default=False, description="Whether human approval is required")

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ToolExecutionRequest(BaseModel):
    recovery_case_id: Optional[str] = Field(default=None, description="Recovery case ID to execute")
    tool_type: Optional[ToolType] = Field(default=None, description="Optional explicit tool override")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional parameters")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Unique idempotency key")
    approval_token: Optional[str] = Field(default=None, description="Approval token reference")

    model_config = ConfigDict(str_strip_whitespace=True)


class ToolExecutionResult(BaseModel):
    execution_id: str = Field(..., min_length=1)
    recovery_case_id: str = Field(..., min_length=1)
    payment_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    tool_type: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)  # SUCCESS, FAILED, BLOCKED, APPROVAL_REQUIRED, CANCELLED
    success: bool = Field(default=False)
    message: str = Field(..., min_length=1)
    provider_reference: Optional[str] = None
    previous_payment_status: Optional[str] = None
    new_payment_status: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    amount: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="INR")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    guardrail_status: str = Field(default="SAFE")
    guardrail_constraints: List[str] = Field(default_factory=list)
    requires_human_approval: bool = Field(default=False)
    approval_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    scheduled_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)



# -------------------------------------------------------------
# Phase 6 - Autonomous Recovery Orchestrator Contracts
# -------------------------------------------------------------

class AutonomousPipelineStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class AutonomousPipelineStep(BaseModel):
    """One stage in the autonomous pipeline execution."""
    step_index: int = Field(..., ge=0)
    stage_name: str = Field(..., min_length=1)  # INVESTIGATE, INTENT, STRATEGY, GUARDRAIL, EXECUTE, SETTLE
    agent: str = Field(..., min_length=1)         # INVESTIGATOR | INTENT_AI | STRATEGIST | GUARDRAIL | TOOL_EXECUTOR
    status: str = Field(..., min_length=1)        # AutonomousPipelineStepStatus value
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    summary: str = Field(default="")
    output: Optional[Dict[str, Any]] = None
    guardrail_applied: bool = False
    guardrail_constraints: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AutonomousRecoveryResult(BaseModel):
    """Full idempotent result of one autonomous recovery pipeline run."""
    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    payment_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    customer_name: str = Field(default="")
    amount: float = Field(..., ge=0.0)
    currency: str = Field(default="INR")
    # Pipeline steps
    steps: List[AutonomousPipelineStep] = Field(default_factory=list)
    total_steps: int = Field(default=0, ge=0)
    completed_steps: int = Field(default=0, ge=0)
    # Outcome
    final_status: str = Field(..., min_length=1)  # RECOVERED | AWAITING_HUMAN_APPROVAL | IN_PROGRESS | BLOCKED | FAILED
    recovery_score: float = Field(default=0.0, ge=0.0, le=100.0)
    recovery_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_selected: Optional[str] = None
    tool_executed: Optional[str] = None
    payment_link_url: Optional[str] = None
    tool_execution_result: Optional[Dict[str, Any]] = None
    guardrail_status: str = Field(default="SAFE")
    requires_human_approval: bool = False
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[int] = None
    # Summary
    executive_summary: str = Field(default="")

    model_config = ConfigDict(from_attributes=True)


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
    prompt: Optional[str] = None
    message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def set_prompt_from_message(cls, values):
        if isinstance(values, dict):
            msg = values.get("message") or values.get("prompt") or ""
            values["prompt"] = msg
            values["message"] = msg
        return values


class CopilotResponse(BaseModel):
    reply: str = ""
    answer: Optional[str] = None
    insights: List[str] = Field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.90)
    confidence_level: str = Field(default="HIGH")
    data_sources: List[str] = Field(default_factory=list)
    data_snapshot: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_answer_reply(cls, values):
        if isinstance(values, dict):
            text = values.get("answer") or values.get("reply") or ""
            values["reply"] = text
            values["answer"] = text
            if "confidence" in values and "confidence_level" not in values:
                c = float(values["confidence"])
                if c >= 0.80:
                    values["confidence_level"] = "HIGH"
                elif c >= 0.60:
                    values["confidence_level"] = "MEDIUM"
                else:
                    values["confidence_level"] = "LOW"
        return values


class SimulateRecoveryRequest(BaseModel):
    scenario_type: str = "DEMO_CARD_DECLINE_UPI"  # DEMO_CARD_DECLINE_UPI, UPI_TIMEOUT, INSUFFICIENT_FUNDS, HIGH_VALUE_APPROVAL
    amount: float = 12999.0
    customer_id: Optional[str] = None


# -------------------------------------------------------------
# PHASE 8 - Authentication, RBAC, Health & Observability Schemas
# -------------------------------------------------------------

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    merchant_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=150)
    password: str = Field(..., min_length=6, max_length=100)
    name: str = Field(..., min_length=2, max_length=150)
    role: str = Field(default="VIEWER")
    merchant_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserResponse


class SystemHealthResponse(BaseModel):
    status: str
    services: Dict[str, str]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None


class StandardErrorResponse(BaseModel):
    error: ErrorDetail


# -------------------------------------------------------------
# PHASE 9 - AI Copilot, Explainability, Opportunity Scoring & Trace Schemas
# -------------------------------------------------------------

class OpportunityScoreResponse(BaseModel):
    case_id: str
    payment_id: str
    amount: float
    currency: str = "INR"
    customer_name: str = "Unknown"
    customer_tier: str = "STANDARD"
    failure_reason: Optional[str] = None
    score: float = Field(..., ge=0.0, le=100.0)
    priority: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    positive_factors: List[str] = Field(default_factory=list)
    negative_factors: List[str] = Field(default_factory=list)
    recommended_strategy: str
    estimated_recovery_probability: float = Field(..., ge=0.0, le=1.0, description="Heuristic probability based on deterministic multi-factor scoring")
    is_heuristic: bool = True

    model_config = ConfigDict(from_attributes=True)


class RevenueAtRiskResponse(BaseModel):
    total: float
    critical: float
    high: float
    medium: float
    low: float
    case_count: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    trend: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DecisionExplanationResponse(BaseModel):
    case_id: str
    payment_id: str
    decision: str
    reason: str
    evidence: List[str] = Field(default_factory=list)
    customer_context: Dict[str, Any] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    guardrail_result: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str = Field(..., description="HIGH, MEDIUM, LOW")
    recommended_next_step: str

    model_config = ConfigDict(from_attributes=True)


class AgentTraceStep(BaseModel):
    step_index: int
    stage_name: str
    agent: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    summary: str = ""
    output: Optional[Dict[str, Any]] = None
    tool_used: Optional[str] = None
    guardrail_applied: bool = False
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AgentTraceResponse(BaseModel):
    run_id: str
    case_id: str
    payment_id: str
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    timeline: List[str] = Field(default_factory=lambda: ["INVESTIGATE", "INTENT", "STRATEGY", "GUARDRAIL", "EXECUTE", "SETTLE"])
    steps: List[AgentTraceStep] = Field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0
    final_status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AIRecommendationItem(BaseModel):
    case_id: str
    payment_id: str
    amount: float
    currency: str = "INR"
    customer_name: str
    customer_id: str
    failure_reason: str
    intent: Optional[str] = None
    opportunity_score: float
    priority: str
    recommended_strategy: str
    confidence: float
    confidence_level: str
    expected_recovery: float
    action_type: str
    requires_human_approval: bool

    model_config = ConfigDict(from_attributes=True)


class AIOperationsMetricsResponse(BaseModel):
    ai_decisions_count: int
    ai_success_rate: float
    average_ai_latency_ms: float
    human_escalation_rate: float
    tool_success_rate: float
    active_agents: int = 4
    period: str = "all_time"

    model_config = ConfigDict(from_attributes=True)


