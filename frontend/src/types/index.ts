export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  customer_value: 'STANDARD' | 'HIGH_VALUE' | 'VIP' | 'CHURN_RISK';
  preferred_payment_method: string;
  total_successful_payments: number;
  total_failed_payments: number;
  created_at: string;
}

export interface Payment {
  id: string;
  razorpay_payment_id: string;
  customer_id: string;
  amount: number;
  currency: string;
  payment_method: 'UPI' | 'CARD' | 'NETBANKING' | 'WALLET' | 'EMI';
  status: 'PENDING' | 'SUCCESS' | 'FAILED' | 'RECOVERED' | 'ABANDONED';
  failure_reason?: string;
  created_at: string;
  updated_at: string;
  customer?: Customer;
}

export interface PaymentInvestigationResult {
  payment_id: string;
  failure_category: string;
  failure_explanation: string;
  customer_profile_summary: string;
  payment_history_summary: string;
  recovery_probability: number;
  recovery_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  recommended_next_action: string;
  reasoning_summary: string;
  contributing_factors: string[];
  negative_factors: string[];
  confidence: number;
}

export interface CustomerIntentRequest {
  customer_id: string;
  recovery_case_id?: string;
  message: string;
  channel: string;
}

export interface CustomerIntentResult {
  customer_id: string;
  recovery_case_id?: string;
  intent: string;
  confidence: number;
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | 'FRUSTRATED';
  urgency: 'LOW' | 'MEDIUM' | 'HIGH';
  intent_summary: string;
  evidence: string[];
  recommended_channel: string;
  recommended_action: string;
  reasoning_summary: string;
}

export type RecoveryStrategyType =
  | 'RETRY_PAYMENT'
  | 'ALTERNATE_PAYMENT_METHOD'
  | 'PAYMENT_LINK'
  | 'FOLLOW_UP'
  | 'INCENTIVE'
  | 'HUMAN_ESCALATION'
  | 'STOP_RECOVERY'
  | 'VERIFY_PAYMENT';

export type GuardrailStatusType = 'SAFE' | 'CAPPED' | 'BLOCKED' | 'APPROVAL_REQUIRED';

export interface RecoveryStrategyRequest {
  recovery_case_id: string;
}

export interface RecoveryStrategyProposal {
  primary_strategy: string;
  secondary_strategy?: string | null;
  recommended_channel: string;
  recommended_payment_method?: string | null;
  proposed_discount_percentage: number;
  proposed_retry_count: number;
  expected_recovery_probability: number;
  strategy_confidence: number;
  recommended_delay_minutes: number;
  human_approval_required: boolean;
  approval_reason?: string | null;
  strategy_summary: string;
  reasoning_summary: string;
  supporting_factors: string[];
  risk_factors: string[];
  rejected_strategies: string[];
}

export interface RecoveryStrategyResult {
  recovery_case_id: string;
  payment_id: string;
  customer_id: string;
  primary_strategy: string;
  secondary_strategy?: string | null;
  recommended_channel: string;
  recommended_payment_method?: string | null;
  discount_percentage: number;
  discount_amount: number;
  currency: string;
  expected_recovery_probability: number;
  strategy_confidence: number;
  recommended_delay_minutes: number;
  retry_count: number;
  human_approval_required: boolean;
  approval_reason?: string | null;
  strategy_summary: string;
  reasoning_summary: string;
  supporting_factors: string[];
  risk_factors: string[];
  rejected_strategies: string[];
  guardrail_status: GuardrailStatusType | string;
  guardrail_constraints: string[];
}

export interface AgentAction {
  id: string;
  recovery_case_id: string;
  agent_type: 'INVESTIGATOR' | 'STRATEGIST' | 'INTENT_AI' | 'ORCHESTRATOR' | 'TOOL_EXECUTOR';
  action_type: string;
  reasoning_summary: string;
  status: 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'BLOCKED_BY_GUARDRAIL' | 'REJECTED' | 'FAILED';
  action_metadata?: string;
  created_at: string;
}

export interface CustomerInteraction {
  id: string;
  customer_id: string;
  recovery_case_id?: string;
  channel: 'WHATSAPP' | 'SMS' | 'EMAIL' | 'VOICE';
  direction: 'OUTBOUND' | 'INBOUND';
  message: string;
  detected_intent?: string;
  confidence: number;
  created_at: string;
}

export interface RecoveryCase {
  id: string;
  payment_id: string;
  recovery_score: number;
  recovery_probability: number;
  customer_intent?: string;
  current_strategy?: string;
  status: 'IDENTIFIED' | 'INVESTIGATING' | 'STRATEGY_SELECTED' | 'ACTION_IN_PROGRESS' | 'AWAITING_CUSTOMER' | 'AWAITING_HUMAN_APPROVAL' | 'RECOVERED' | 'FAILED' | 'EXPIRED';
  retry_count: number;
  recovered_amount: number;
  payment_link_url?: string;
  started_at: string;
  completed_at?: string;
  payment?: Payment;
  actions: AgentAction[];
  interactions: CustomerInteraction[];
}

export interface Guardrails {
  id?: string;
  merchant_id: string;
  max_retries: number;
  max_discount_percentage: number;
  max_campaign_days: number;
  quiet_hours_start: string;
  quiet_hours_end: string;
  high_value_threshold: number;
  human_approval_required: boolean;
  max_contact_attempts: number;
}

export interface DashboardMetrics {
  revenue_processed: number;
  revenue_at_risk: number;
  predicted_recoverable: number;
  revenue_recovered: number;
  recovery_rate: number;
  failed_payments_count: number;
  active_recoveries_count: number;
  human_review_queue_count: number;
  monthly_trend: Array<{ day: string; at_risk: number; recovered: number; prevented_churn: number }>;
  recovery_by_method: Array<{ method: string; failed: number; recovered: number; recovery_rate: number }>;
  recovery_by_reason: Array<{ reason: string; count: number; recovered: number; rate: number }>;
  recovery_pipeline: Array<{ stage: string; count: number; value: number }>;
}

export interface CopilotResponse {
  reply: string;
  insights: string[];
  recommended_actions: Array<{ label: string; action: string }>;
  data_snapshot?: Record<string, any>;
}
