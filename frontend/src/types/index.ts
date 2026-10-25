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
  answer?: string;
  insights: string[];
  recommended_actions: Array<{
    label: string;
    action: string;
    case_id?: string;
  }>;
  confidence?: number;
  confidence_level?: 'HIGH' | 'MEDIUM' | 'LOW';
  data_sources?: string[];
  data_snapshot?: Record<string, any>;
}


export type ToolType =
  | 'RETRY_PAYMENT'
  | 'CREATE_PAYMENT_LINK'
  | 'OFFER_ALTERNATE_PAYMENT'
  | 'SEND_RECOVERY_MESSAGE'
  | 'SCHEDULE_FOLLOW_UP'
  | 'VERIFY_PAYMENT'
  | 'ESCALATE_TO_HUMAN';

export type ToolExecutionStatus =
  | 'PROPOSED'
  | 'APPROVAL_REQUIRED'
  | 'APPROVED'
  | 'EXECUTING'
  | 'SUCCESS'
  | 'FAILED'
  | 'BLOCKED'
  | 'CANCELLED';

export interface ToolProposal {
  tool_type: ToolType;
  recovery_case_id: string;
  payment_id: string;
  customer_id: string;
  parameters: Record<string, any>;
  reason: string;
  strategy_source?: string;
  requires_approval: boolean;
}

export interface ToolExecutionRequest {
  recovery_case_id: string;
  tool_type?: ToolType;
  parameters?: Record<string, any>;
  idempotency_key?: string;
  approval_token?: string;
}

export interface ToolExecutionResult {
  execution_id: string;
  recovery_case_id: string;
  payment_id: string;
  customer_id: string;
  tool_type: string;
  status: ToolExecutionStatus | string;
  success: boolean;
  message: string;
  provider_reference?: string | null;
  previous_payment_status?: string | null;
  new_payment_status?: string | null;
  retry_count: number;
  amount: number;
  currency: string;
  created_at: string;
  guardrail_status: string;
  guardrail_constraints: string[];
  requires_human_approval: boolean;
  approval_id?: string | null;
  payment_link_url?: string | null;
  scheduled_at?: string | null;
}

export interface HumanApproval {
  id: string;
  recovery_case_id: string;
  execution_id?: string;
  tool_type: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reason: string;
  amount: number;
  created_at: string;
  approved_at?: string;
  rejected_at?: string;
}


// ─── Phase 6: Autonomous Recovery Orchestrator ────────────────────────────────

export type AutonomousPipelineStepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'SKIPPED'
  | 'BLOCKED'
  | 'FAILED';

export interface AutonomousPipelineStep {
  step_index: number;
  stage_name: string;
  agent: string;
  status: AutonomousPipelineStepStatus | string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  summary: string;
  output?: Record<string, any> | null;
  guardrail_applied: boolean;
  guardrail_constraints: string[];
}

export interface AutonomousRecoveryResult {
  run_id: string;
  case_id: string;
  payment_id: string;
  customer_id: string;
  customer_name: string;
  amount: number;
  currency: string;
  steps: AutonomousPipelineStep[];
  total_steps: number;
  completed_steps: number;
  final_status: 'RECOVERED' | 'AWAITING_HUMAN_APPROVAL' | 'IN_PROGRESS' | 'BLOCKED' | 'FAILED' | string;
  recovery_score: number;
  recovery_probability: number;
  strategy_selected?: string | null;
  tool_executed?: string | null;
  payment_link_url?: string | null;
  tool_execution_result?: Record<string, any> | null;
  guardrail_status: string;
  requires_human_approval: boolean;
  started_at: string;
  completed_at?: string | null;
  total_duration_ms?: number | null;
  executive_summary: string;
}


// Phase 7: Analytics Types

export interface AnalyticsOverview {
  revenue_processed: number;
  revenue_at_risk: number;
  revenue_recovered: number;
  predicted_recoverable: number;
  recovery_rate: number;
  failed_payments_count: number;
  recovered_payments_count: number;
  active_cases_count: number;
  recovered_cases_count: number;
  awaiting_approval_count: number;
  total_cases: number;
  average_recovery_score: number;
  total_recovery_attempts: number;
  ai_automation_rate: number;
  total_agent_actions: number;
}

export interface TrendDay {
  date: string;
  failed: number;
  recovered: number;
  at_risk: number;
  recovered_amount: number;
}

export interface RecoveryTrend {
  period: string;
  days: number;
  data: TrendDay[];
}

export interface FailureByReason {
  reason: string;
  count: number;
  amount: number;
  recovered: number;
  recovered_amount: number;
  recovery_rate: number;
  total_transactions: number;
}

export interface FailureByMethod {
  method: string;
  failed: number;
  recovered: number;
  failed_amount: number;
  recovered_amount: number;
  recovery_rate: number;
  total: number;
}

export interface FailureAnalytics {
  by_reason: FailureByReason[];
  by_method: FailureByMethod[];
}

export interface PaymentMethodStat {
  method: string;
  total: number;
  failed: number;
  recovered: number;
  total_amount: number;
  failed_amount: number;
  recovered_amount: number;
  recovery_rate: number;
}

export interface CustomerSegmentStat {
  segment: string;
  customer_count: number;
  failed_payments: number;
  total_failed_amount: number;
  recovered_amount: number;
  recovered_count: number;
  recovery_rate: number;
}

export interface StrategyStat {
  strategy: string;
  attempts: number;
  recovered: number;
  success_rate: number;
  recovered_amount: number;
  avg_recovery_probability: number;
}

export interface RecoveryOpportunity {
  case_id: string;
  payment_id: string;
  customer_id?: string | null;
  customer_name: string;
  amount: number;
  currency: string;
  payment_method?: string;
  failure_reason?: string;
  recovery_probability: number;
  recovery_score: number;
  expected_recovery_value: number;
  current_strategy?: string | null;
  customer_intent?: string | null;
  status: string;
  guardrail_hint: string;
  started_at?: string | null;
}



// Phase 7: Analytics Types

export interface AnalyticsOverview {
  revenue_processed: number;
  revenue_at_risk: number;
  revenue_recovered: number;
  predicted_recoverable: number;
  recovery_rate: number;
  failed_payments_count: number;
  recovered_payments_count: number;
  active_cases_count: number;
  recovered_cases_count: number;
  awaiting_approval_count: number;
  total_cases: number;
  average_recovery_score: number;
  total_recovery_attempts: number;
  ai_automation_rate: number;
  total_agent_actions: number;
}

export interface TrendDay {
  date: string;
  failed: number;
  recovered: number;
  at_risk: number;
  recovered_amount: number;
}

export interface RecoveryTrend {
  period: string;
  days: number;
  data: TrendDay[];
}

export interface FailureByReason {
  reason: string;
  count: number;
  amount: number;
  recovered: number;
  recovered_amount: number;
  recovery_rate: number;
  total_transactions: number;
}

export interface FailureByMethod {
  method: string;
  failed: number;
  recovered: number;
  failed_amount: number;
  recovered_amount: number;
  recovery_rate: number;
  total: number;
}

export interface FailureAnalytics {
  by_reason: FailureByReason[];
  by_method: FailureByMethod[];
}

export interface PaymentMethodStat {
  method: string;
  total: number;
  failed: number;
  recovered: number;
  total_amount: number;
  failed_amount: number;
  recovered_amount: number;
  recovery_rate: number;
}

export interface CustomerSegmentStat {
  segment: string;
  customer_count: number;
  failed_payments: number;
  total_failed_amount: number;
  recovered_amount: number;
  recovered_count: number;
  recovery_rate: number;
}

export interface StrategyStat {
  strategy: string;
  attempts: number;
  recovered: number;
  success_rate: number;
  recovered_amount: number;
  avg_recovery_probability: number;
}

export interface RecoveryOpportunity {
  case_id: string;
  payment_id: string;
  customer_id?: string | null;
  customer_name: string;
  amount: number;
  currency: string;
  payment_method?: string;
  failure_reason?: string;
  recovery_probability: number;
  recovery_score: number;
  expected_recovery_value: number;
  current_strategy?: string | null;
  customer_intent?: string | null;
  status: string;
  guardrail_hint: string;
  started_at?: string | null;
}

export interface SystemComponentStatus {
  status: string;
  detail: string;
}

export interface SystemStatus {
  overall: string;
  components: Record<string, SystemComponentStatus>;
  timestamp: string;
}

// ─── Phase 8: Auth, RBAC & Realtime Types ─────────────────────────

export type UserRole = 'ADMIN' | 'ANALYST' | 'OPERATOR' | 'VIEWER';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  merchant_id?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserCreatePayload {
  email: string;
  name: string;
  role: UserRole;
  password: string;
  merchant_id?: string | null;
}

export interface UserUpdatePayload {
  name?: string;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
}

export interface SystemHealth {
  status: string;
  services: {
    api: string;
    database: string;
    redis: string;
    ai: string;
    payment_engine: string;
    [key: string]: string;
  };
  timestamp?: string;
}

export interface RealtimeEvent {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  case_id?: string | null;
  payment_id?: string | null;
  amount?: number | null;
  status?: string | null;
  agent_type?: string | null;
  tool_type?: string | null;
  data?: Record<string, any>;
  correlation_id?: string | null;
}

// -------------------------------------------------------------
// Phase 9 - AI Copilot, Opportunity Scoring, Risk, Trace & Metrics
// -------------------------------------------------------------


export interface OpportunityScore {
  case_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  customer_name: string;
  customer_tier: string;
  failure_reason?: string | null;
  score: number;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  positive_factors: string[];
  negative_factors: string[];
  recommended_strategy: string;
  estimated_recovery_probability: number;
  is_heuristic: boolean;
}

export interface RevenueAtRisk {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  case_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  trend: Array<{
    date: string;
    amount_at_risk: number;
  }>;
}

export interface DecisionExplanation {
  case_id: string;
  payment_id: string;
  decision: string;
  reason: string;
  evidence: string[];
  customer_context: Record<string, any>;
  risk_factors: string[];
  guardrail_result: Record<string, any>;
  confidence: number;
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW';
  recommended_next_step: string;
}

export interface AgentTraceStep {
  step_index: number;
  stage_name: string;
  agent: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'SKIPPED' | 'BLOCKED' | 'FAILED';
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  summary: string;
  output?: Record<string, any>;
  tool_used?: string | null;
  guardrail_applied: boolean;
  error_message?: string | null;
}

export interface AgentTrace {
  run_id: string;
  case_id: string;
  payment_id: string;
  request_id?: string;
  correlation_id?: string;
  timeline: string[];
  steps: AgentTraceStep[];
  total_steps: number;
  completed_steps: number;
  final_status: string;
  started_at?: string;
  completed_at?: string;
  total_duration_ms?: number;
}

export interface AIRecommendation {
  case_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  customer_name: string;
  customer_id: string;
  failure_reason: string;
  intent?: string;
  opportunity_score: number;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  recommended_strategy: string;
  confidence: number;
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW';
  expected_recovery: number;
  action_type: string;
  requires_human_approval: boolean;
}

export interface AIOperationsMetrics {
  ai_decisions_count: number;
  ai_success_rate: number;
  average_ai_latency_ms: number;
  human_escalation_rate: number;
  tool_success_rate: number;
  active_agents: number;
  period: string;
}

export interface WebhookEventItem {
  id: string;
  provider: string;
  provider_event_id: string;
  event_type: string;
  status: 'RECEIVED' | 'PROCESSING' | 'PROCESSED' | 'RETRY_PENDING' | 'FAILED' | 'DEAD_LETTER';
  entity_id?: string | null;
  internal_payment_id?: string | null;
  internal_case_id?: string | null;
  attempt_count: number;
  max_attempts: number;
  next_retry_at?: string | null;
  last_error?: string | null;
  correlation_id?: string | null;
  received_at: string;
  processed_at?: string | null;
  updated_at: string;
  sanitized_payload?: Record<string, any>;
}

export interface WebhookEventListResponse {
  items: WebhookEventItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface WebhookHealth {
  status: 'healthy' | 'degraded';
  total_received: number;
  total_processed: number;
  total_pending: number;
  total_failed: number;
  total_dead_letter: number;
  secret_configured: boolean;
  mode: string;
}

// -------------------------------------------------------------
// PHASE 4 — RECOVERY INTELLIGENCE & HISTORICAL ENGINE
// -------------------------------------------------------------

export interface OutcomeRecordItem {
  id: string;
  recovery_case_id: string;
  payment_id: string;
  customer_id: string;
  failure_category: string;
  payment_method: string;
  amount: number;
  amount_range: string;
  customer_intent?: string | null;
  selected_strategy: string;
  communication_channel: string;
  retry_count: number;
  discount_offered_percent: number;
  human_approval_required: boolean;
  processing_latency_ms: number;
  outcome_status: 'RECOVERED' | 'UNSUCCESSFUL' | 'PENDING' | 'UNKNOWN';
  recovered_amount: number;
  is_verified: boolean;
  verification_source?: string | null;
  time_to_recovery_seconds?: number | null;
  decision_timestamp: string;
  outcome_timestamp?: string | null;
  created_at: string;
}

export interface OutcomeRecordListResponse {
  items: OutcomeRecordItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  verified_recovered_count: number;
  total_recovered_amount: number;
}

export interface OutcomeSummaryStats {
  total_attempts: number;
  verified_recovered: number;
  unsuccessful: number;
  pending: number;
  unknown: number;
  recovery_rate_observed: number;
  total_amount_recovered: number;
  average_time_to_recovery_sec: number;
  sample_size_evaluated: number;
}

export interface StrategyCandidateEvaluation {
  strategy: string;
  is_eligible: boolean;
  rank: number;
  observed_recovery_rate: number | null;
  sample_size: number;
  recovered_count: number;
  unsuccessful_count: number;
  confidence_interval_95: [number, number];
  laplace_smoothed_rate: number;
  estimated_probability: number;
  uncertainty_level: 'INSUFFICIENT_DATA' | 'HIGH_UNCERTAINTY' | 'MODERATE' | 'LOW_UNCERTAINTY';
  recommendation_reason: string;
  alternative_reasons: string[];
  guardrail_overrides: string[];
}

export interface StrategyEvaluationResponse {
  recovery_case_id: string;
  payment_id: string;
  failure_category: string;
  payment_method: string;
  amount: number;
  amount_range: string;
  customer_intent?: string | null;
  recommended_strategy: string;
  calibrated_probability: number;
  baseline_probability: number;
  uncertainty_level: string;
  sample_size_total: number;
  evaluation_timestamp: string;
  candidates: StrategyCandidateEvaluation[];
  guardrail_applied: boolean;
  guardrail_details: string[];
  data_limitations_warning?: string | null;
}

export interface CalibrationMetrics {
  sample_size_total: number;
  sample_size_labeled: number;
  recovered_count: number;
  unsuccessful_count: number;
  baseline_recovery_rate: number;
  baseline_brier_score: number;
  model_brier_score: number;
  brier_skill_score: number;
  roc_auc: number | null;
  expected_calibration_error: number | null;
  train_sample_size: number;
  test_sample_size: number;
  data_quality_status: string;
  model_version: string;
  limitations: string[];
  evaluation_timestamp: string;
}

export interface ExplainabilityResponse {
  recovery_case_id: string;
  payment_id: string;
  recommended_strategy: string;
  calibrated_probability: number;
  baseline_probability: number;
  historical_sample_size: number;
  observed_historical_rate: number | null;
  confidence_interval_95: [number, number];
  uncertainty_level: string;
  top_contributing_factors: string[];
  top_risk_factors: string[];
  guardrails_active: string[];
  human_approval_required: boolean;
  approval_reason?: string | null;
  candidates_comparison: StrategyCandidateEvaluation[];
  model_version: string;
  methodology_disclaimer: string;
  decision_timestamp: string;
}

// ─── Phase 5: RAG Knowledge Engine & Grounded Recommendations ───

export type KnowledgeCategory = 'MERCHANT_POLICY' | 'FAILURE_KNOWLEDGE' | 'RECOVERY_PLAYBOOK' | 'HISTORICAL_INSIGHT';
export type VerificationStatus = 'VERIFIED' | 'DRAFT' | 'DEPRECATED' | 'CONFLICTED';

export interface KnowledgeChunkItem {
  id: string;
  document_id: string;
  chunk_index: number;
  heading: string;
  content: string;
  content_hash: string;
  token_count: number;
  chunk_metadata?: Record<string, any> | null;
  created_at: string;
}

export interface KnowledgeDocumentItem {
  id: string;
  title: string;
  category: KnowledgeCategory | string;
  source_type: string;
  source_reference: string;
  merchant_id?: string | null;
  version: number;
  verification_status: VerificationStatus | string;
  effective_date?: string | null;
  expiration_date?: string | null;
  content_hash: string;
  raw_content: string;
  doc_metadata?: Record<string, any> | null;
  chunk_count: number;
  chunks?: KnowledgeChunkItem[] | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentCreate {
  title: string;
  category: string;
  source_type: string;
  source_reference: string;
  merchant_id?: string | null;
  raw_content: string;
  verification_status?: string;
  effective_date?: string | null;
  expiration_date?: string | null;
  doc_metadata?: Record<string, any> | null;
}

export interface KnowledgeDocumentUpdate {
  title?: string;
  category?: string;
  source_type?: string;
  source_reference?: string;
  merchant_id?: string | null;
  raw_content?: string;
  verification_status?: string;
  effective_date?: string | null;
  expiration_date?: string | null;
  doc_metadata?: Record<string, any> | null;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocumentItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  category_counts: Record<string, number>;
}

export interface KnowledgeQueryRequest {
  query: string;
  category?: string | null;
  merchant_id?: string | null;
  limit?: number;
  relevance_threshold?: number;
}

export interface RetrievedPassage {
  chunk_id: string;
  document_id: string;
  document_title: string;
  category: string;
  source_type: string;
  source_reference: string;
  merchant_id?: string | null;
  heading: string;
  content: string;
  similarity_score: number;
  lexical_score: number;
  combined_score: number;
  verification_status: string;
  version: number;
  is_merchant_specific: boolean;
  retrieval_method: 'semantic' | 'lexical' | 'hybrid' | string;
  detected_conflicts: string[];
}

export interface KnowledgeQueryResponse {
  query: string;
  total_retrieved: number;
  is_sufficient: boolean;
  highest_score: number;
  passages: RetrievedPassage[];
  policy_conflicts_detected: string[];
  latency_ms: number;
}

export interface EvidenceGroundedRecommendation {
  recovery_case_id: string;
  payment_id: string;
  recommended_strategy: string;
  recommendation_summary: string;
  reasoning_summary: string;
  verified_facts: string[];
  approved_policies: string[];
  observed_statistics?: {
    cohort_sample_size?: number;
    empirical_recovery_rate?: number;
    successful_recoveries?: number;
    mean_recovered_amount?: number;
    data_source?: string;
    [key: string]: any;
  } | null;
  probability_estimates?: {
    calibrated_recovery_probability?: number;
    confidence_interval_95?: [number, number];
    wilson_lower_bound?: number;
    wilson_upper_bound?: number;
    uncertainty_level?: string;
    calibration_method?: string;
    [key: string]: any;
  } | null;
  ai_generated_rationales: string[];
  supporting_citations: RetrievedPassage[];
  rejected_alternatives: Array<{ strategy: string; rejection_reason: string }>;
  missing_evidence: string[];
  evidence_sufficiency: 'SUFFICIENT' | 'PARTIAL' | 'INSUFFICIENT' | string;
  policy_conflicts: string[];
  guardrails_enforced: string[];
  human_approval_required: boolean;
  approval_reason?: string | null;
  created_at: string;
}

export interface RAGHealthResponse {
  status: string;
  total_documents: number;
  total_chunks: number;
  category_distribution: Record<string, number>;
  embedding_model: string;
  embedding_dimension: number;
  vector_search_mode: string;
  hybrid_ranking_active: boolean;
  last_indexed_at?: string | null;
}

// -------------------------------------------------------------
// PHASE 6 — EXPERIMENTATION & OPTIMIZATION TYPES
// -------------------------------------------------------------

export interface ExperimentArmConfig {
  arm_id: string;
  strategy: string;
  traffic_percentage: number;
  is_control: boolean;
  description?: string;
}

export interface RecoveryExperimentItem {
  id: string;
  name: string;
  objective: string;
  hypothesis?: string;
  status: 'DRAFT' | 'READY' | 'RUNNING' | 'PAUSED' | 'COMPLETED';
  version: number;
  merchant_id?: string;
  owner_email: string;
  primary_metric: string;
  is_sandbox_only: boolean;
  target_failure_categories: string[];
  target_payment_methods: string[];
  min_amount?: number;
  max_amount?: number;
  target_customer_intent: string[];
  candidate_strategies: ExperimentArmConfig[];
  max_sample_size?: number;
  min_observation_count: number;
  start_time?: string;
  end_time?: string;
  total_assignments: number;
  total_terminal_outcomes: number;
  created_at: string;
  updated_at: string;
}

export interface ExperimentAssignmentItem {
  assignment_id: string;
  experiment_id: string;
  experiment_name: string;
  experiment_version: number;
  recovery_case_id: string;
  payment_id: string;
  arm_id: string;
  assigned_strategy: string;
  is_control: boolean;
  hash_bucket: number;
  assigned_at: string;
  actual_executed_strategy?: string;
  is_strategy_deviated: boolean;
  deviation_reason?: string;
  outcome_status?: 'RECOVERED' | 'UNSUCCESSFUL' | 'PENDING' | 'UNKNOWN';
  is_verified: boolean;
  recovered_amount: number;
  time_to_recovery_seconds?: number;
  attributed_at?: string;
}

export interface ExperimentArmMetrics {
  arm_id: string;
  strategy: string;
  is_control: boolean;
  traffic_percentage: number;
  description?: string;
  assigned_count: number;
  eligible_count: number;
  pending_count: number;
  unknown_count: number;
  recovered_count: number;
  unsuccessful_count: number;
  recovery_rate: number;
  wilson_ci_95: [number, number];
  total_recovered_amount: number;
  revenue_per_eligible_case: number;
  avg_time_to_recovery_seconds?: number;
  avg_retry_count: number;
  avg_discount_cost: number;
  human_escalation_count: number;
  human_escalation_rate: number;
  strategy_deviation_count: number;
  strategy_deviation_rate: number;
  sample_size_adequate: boolean;
}

export interface HypothesisComparisonResult {
  treatment_arm_id: string;
  control_arm_id: string;
  treatment_strategy: string;
  control_strategy: string;
  treatment_rate: number;
  control_rate: number;
  absolute_lift: number;
  relative_lift?: number;
  ci_difference_95: [number, number];
  z_score: number;
  p_value: number;
  is_statistically_significant: boolean;
  treatment_rev_per_case: number;
  control_rev_per_case: number;
  revenue_difference: number;
  revenue_p_value?: number;
  recommendation: 'WINNER_TREATMENT' | 'INCONCLUSIVE_INSUFFICIENT_SAMPLE' | 'NO_SIGNIFICANT_DIFFERENCE' | 'WINNER_CONTROL' | string;
  statistical_rationale: string;
}

export interface ExperimentMetricsResponse {
  experiment_id: string;
  experiment_name: string;
  status: string;
  version: number;
  primary_metric: string;
  is_sandbox_only: boolean;
  total_assigned: number;
  total_eligible: number;
  total_pending: number;
  total_unknown: number;
  total_recovered: number;
  total_revenue_recovered: number;
  overall_recovery_rate: number;
  arm_metrics: ExperimentArmMetrics[];
  comparisons: HypothesisComparisonResult[];
  methodological_safeguards: Record<string, any>;
  sample_size_warnings: string[];
  guardrail_deviation_warnings: string[];
  as_of_timestamp: string;
}

export interface OfflineSimulationRequest {
  cohort_size: number;
  failure_category: string;
  payment_method: string;
  base_amount?: number;
  random_seed?: number;
  enable_thompson_sampling?: boolean;
}

export interface OfflineSimulationResponse {
  simulation_id: string;
  experiment_id: string;
  cohort_size: number;
  failure_category: string;
  payment_method: string;
  allocation_method: string;
  arm_results: Array<{
    arm_id: string;
    strategy: string;
    is_control: boolean;
    assigned: number;
    recovered: number;
    recovery_rate: number;
    revenue_recovered: number;
    revenue_per_case: number;
  }>;
  winner_arm_id?: string;
  simulated_absolute_lift: number;
  simulated_revenue_gain: number;
  mab_regret_reduction_percent?: number;
  methodology_disclaimer: string;
}

export interface ExperimentCreateRequest {
  name: string;
  objective: string;
  hypothesis?: string;
  merchant_id?: string;
  primary_metric?: string;
  is_sandbox_only?: boolean;
  target_failure_categories?: string[];
  target_payment_methods?: string[];
  min_amount?: number;
  max_amount?: number;
  target_customer_intent?: string[];
  candidate_strategies: ExperimentArmConfig[];
  max_sample_size?: number;
  min_observation_count?: number;
  start_time?: string;
  end_time?: string;
}


