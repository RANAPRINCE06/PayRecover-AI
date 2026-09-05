import {
  DashboardMetrics,
  Payment,
  RecoveryCase,
  AgentAction,
  Guardrails,
  CopilotResponse,
  RecoveryStrategyResult,
  ToolExecutionRequest,
  ToolExecutionResult,
  AutonomousRecoveryResult,
  AnalyticsOverview,
  RecoveryTrend,
  FailureAnalytics,
  PaymentMethodStat,
  CustomerSegmentStat,
  StrategyStat,
  RecoveryOpportunity,
  SystemStatus,
  User,
  TokenResponse,
  UserCreatePayload,
  UserUpdatePayload,
  SystemHealth,
  RealtimeEvent,
  OpportunityScore,
  RevenueAtRisk,
  DecisionExplanation,
  AgentTrace,
  AIRecommendation,
  AIOperationsMetrics
} from '../types';

const API_BASE = '/api';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  // Automatically attach Bearer token if present
  const token = localStorage.getItem('payrecover_token');
  const reqId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Request-ID': reqId,
    ...(options.headers as Record<string, string> || {})
  };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      if (res.status === 401 && !endpoint.includes('/auth/login')) {
        // Session expired or invalid
        localStorage.removeItem('payrecover_token');
        localStorage.removeItem('payrecover_user');
        window.dispatchEvent(new CustomEvent('payrecover:unauthorized'));
      }
      const errBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errBody.detail || errBody.error?.message || `Request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (err: any) {
    console.error(`API Error on [${options.method || 'GET'}] ${url}:`, err);
    throw err;
  }
}

export const api = {
  // ─── Authentication (Phase 8) ──────────────────────────────────
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }),

  logout: () =>
    request<{ message: string }>('/auth/logout', { method: 'POST' }),

  getMe: () =>
    request<User>('/auth/me'),

  // ─── User Management (Phase 8 Admin) ──────────────────────────
  getUsers: () =>
    request<User[]>('/users'),

  createUser: (payload: UserCreatePayload) =>
    request<User>('/users', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  getUser: (userId: string) =>
    request<User>(`/users/${userId}`),

  updateUser: (userId: string, payload: UserUpdatePayload) =>
    request<User>(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),

  toggleUserActive: (userId: string) =>
    request<User>(`/users/${userId}/toggle-active`, { method: 'POST' }),

  // ─── Real-Time Operations (Phase 8) ───────────────────────────
  getRecentEvents: (limit: number = 50) =>
    request<RealtimeEvent[]>(`/events/recent?limit=${limit}`),

  // ─── System Health & Status ───────────────────────────────────
  getHealth: () =>
    request<{ status: string; service: string; redis_connected: boolean }>('/health'),

  getSystemStatus: () =>
    request<SystemStatus>('/system/status'),

  getSystemHealth: () =>
    request<SystemHealth>('/system/health'),

  // ─── Dashboard Metrics ────────────────────────────────────────
  getMetrics: () =>
    request<DashboardMetrics>('/dashboard/metrics'),

  // ─── Payments & Cases ─────────────────────────────────────────
  getPayments: (params: { status?: string; method?: string; search?: string; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.method) query.append('method', params.method);
    if (params.search) query.append('search', params.search);
    if (params.limit) query.append('limit', params.limit.toString());
    return request<Payment[]>(`/payments?${query.toString()}`);
  },

  getPayment: (id: string) =>
    request<Payment>(`/payments/${id}`),

  getRecoveryCases: (params: string | { status?: string; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (typeof params === 'string') {
      if (params) query.append('status', params);
    } else {
      if (params.status) query.append('status', params.status);
      if (params.limit) query.append('limit', params.limit.toString());
    }
    return request<RecoveryCase[]>(`/recovery/cases?${query.toString()}`);
  },

  getRecoveryCase: (id: string) =>
    request<RecoveryCase>(`/recovery/cases/${id}`),

  getAgentActivity: (limit: number = 50) =>
    request<AgentAction[]>(`/agent/activity?limit=${limit}`),

  // ─── Guardrails ───────────────────────────────────────────────
  getGuardrails: () =>
    request<Guardrails>('/guardrails'),

  updateGuardrails: (guardrails: Partial<Guardrails>) =>
    request<Guardrails>('/guardrails', {
      method: 'PUT',
      body: JSON.stringify(guardrails)
    }),

  // ─── AI & Simulation ──────────────────────────────────────────
  analyzePayment: (paymentId: string) =>
    request<any>('/ai/analyze-payment', {
      method: 'POST',
      body: JSON.stringify({ payment_id: paymentId })
    }),

  analyzeCustomerIntent: (payload: { customer_id: string; message: string; channel: string; recovery_case_id?: string }) =>
    request<any>('/ai/analyze-intent', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  generateRecoveryStrategy: (recoveryCaseId: string) =>
    request<RecoveryStrategyResult>('/ai/generate-strategy', {
      method: 'POST',
      body: JSON.stringify({ recovery_case_id: recoveryCaseId })
    }),

  askCopilot: (prompt: string, context?: any) =>
    request<CopilotResponse>('/ai/copilot', {
      method: 'POST',
      body: JSON.stringify({ prompt, context })
    }),

  simulateScenario: (scenarioType: string = 'DEMO_CARD_DECLINE_UPI', amount: number = 12999) =>
    request<any>('/recovery/simulate', {
      method: 'POST',
      body: JSON.stringify({ scenario_type: scenarioType, amount })
    }),

  simulateRecovery: (scenarioType: string = 'DEMO_CARD_DECLINE_UPI', amount: number = 12999) =>
    request<any>('/recovery/simulate', {
      method: 'POST',
      body: JSON.stringify({ scenario_type: scenarioType, amount })
    }),

  executeRecovery: (caseId: string, payload?: ToolExecutionRequest, idempotencyKey?: string) =>
    request<ToolExecutionResult>(`/recovery/${caseId}/execute`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: payload ? JSON.stringify(payload) : undefined
    }),

  executeRecoveryAction: (caseId: string, payload?: any, idempotencyKey?: string) =>
    request<ToolExecutionResult>(`/recovery/${caseId}/execute`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: payload ? JSON.stringify(payload) : undefined
    }),

  approveCase: (caseId: string, idempotencyKey?: string) =>
    request<ToolExecutionResult>(`/recovery/${caseId}/approve`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined
    }),

  rejectCase: (caseId: string, reason?: string) =>
    request<{ message: string; case_id: string; status: string }>(`/recovery/${caseId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Merchant rejected' })
    }),

  confirmSettlement: (caseId: string) =>
    request<any>(`/recovery/${caseId}/confirm-settlement`, { method: 'POST' }),

  // ─── Phase 6: Autonomous Recovery ─────────────────────────────
  runAutonomousRecovery: (caseId: string, customerMessage?: string) =>
    request<AutonomousRecoveryResult>(`/recovery/${caseId}/autonomous`, {
      method: 'POST',
      body: customerMessage ? JSON.stringify({ customer_message: customerMessage }) : undefined
    }),

  getAutonomousStatus: (caseId: string) =>
    request<Record<string, any>>(`/recovery/${caseId}/autonomous/status`),

  // ─── Phase 7: Analytics ───────────────────────────────────────
  getAnalyticsOverview: () => request<AnalyticsOverview>('/analytics/overview'),

  getRecoveryTrends: (period: '7d' | '30d' | '90d' = '7d') =>
    request<RecoveryTrend>(`/analytics/trends?period=${period}`),

  getFailureAnalytics: () => request<FailureAnalytics>('/analytics/failures'),

  getPaymentMethodAnalytics: () =>
    request<{ methods: PaymentMethodStat[] }>('/analytics/payment-methods'),

  getCustomerSegmentAnalytics: () =>
    request<{ segments: CustomerSegmentStat[] }>('/analytics/customer-segments'),

  getStrategyAnalytics: () =>
    request<{ strategies: StrategyStat[] }>('/analytics/strategies'),

  getRecoveryOpportunities: (limit = 10) =>
    request<{ opportunities: RecoveryOpportunity[] }>(`/analytics/opportunities?limit=${limit}`),

  // ─── Phase 9: Copilot, Explainability & Traces ────────────────
  getRevenueAtRisk: () => request<RevenueAtRisk>('/analytics/revenue-at-risk'),

  getAIOperationsMetrics: () => request<AIOperationsMetrics>('/analytics/ai-metrics'),

  getDecisionExplanation: (caseId: string) =>
    request<DecisionExplanation>(`/recovery/${caseId}/explanation`),

  getCaseOpportunity: (caseId: string) =>
    request<OpportunityScore>(`/recovery/${caseId}/opportunity`),

  getCaseTrace: (caseId: string) =>
    request<AgentTrace>(`/recovery/${caseId}/trace`),

  getRecentTraces: (limit = 10) =>
    request<AgentTrace[]>(`/recovery/traces?limit=${limit}`),

  getAIRecommendations: (limit = 6) =>
    request<AIRecommendation[]>(`/recovery/recommendations?limit=${limit}`)
};
