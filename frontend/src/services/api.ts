import {
  DashboardMetrics,
  Payment,
  RecoveryCase,
  AgentAction,
  Guardrails,
  CopilotResponse,
  RecoveryStrategyResult
} from '../types';

const API_BASE = '/api';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errBody.detail || `Request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (err: any) {
    console.error(`API Error on [${options.method || 'GET'}] ${url}:`, err);
    throw err;
  }
}

export const api = {
  // Health
  getHealth: () => request<{ status: string; service: string; redis_connected: boolean }>('/health'),

  // Dashboard
  getMetrics: () => request<DashboardMetrics>('/dashboard/metrics'),

  // Payments
  getPayments: (params: { status?: string; method?: string; search?: string; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.method) query.append('method', params.method);
    if (params.search) query.append('search', params.search);
    if (params.limit) query.append('limit', params.limit.toString());
    return request<Payment[]>(`/payments?${query.toString()}`);
  },

  getPayment: (id: string) => request<Payment>(`/payments/${id}`),

  // Recovery Cases
  getRecoveryCases: (status?: string) => {
    const query = status ? `?status=${status}` : '';
    return request<RecoveryCase[]>(`/recovery/cases${query}`);
  },

  getRecoveryCase: (id: string) => request<RecoveryCase>(`/recovery/cases/${id}`),

  // Agent Activity
  getAgentActivity: (limit: number = 50) => request<AgentAction[]>(`/agent/activity?limit=${limit}`),

  // Guardrails
  getGuardrails: () => request<Guardrails>('/guardrails'),
  updateGuardrails: (guardrails: Partial<Guardrails>) =>
    request<Guardrails>('/guardrails', {
      method: 'PUT',
      body: JSON.stringify(guardrails)
    }),

  // AI & Simulation
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

  executeRecovery: (caseId: string) =>
    request<any>(`/recovery/${caseId}/execute`, { method: 'POST' }),

  approveCase: (caseId: string) =>
    request<any>(`/recovery/${caseId}/approve`, { method: 'POST' }),

  rejectCase: (caseId: string, reason?: string) =>
    request<any>(`/recovery/${caseId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Merchant rejected' })
    }),

  confirmSettlement: (caseId: string) =>
    request<any>(`/recovery/${caseId}/confirm-settlement`, { method: 'POST' })
};
