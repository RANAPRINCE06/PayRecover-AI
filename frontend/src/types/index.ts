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
