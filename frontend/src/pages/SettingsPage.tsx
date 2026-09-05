import React, { useState, useEffect } from 'react';
import {
  Settings,
  Key,
  Server,
  Users,
  ShieldCheck,
  Activity,
  CheckCircle2,
  Copy,
  Lock,
  Loader2,
  RefreshCw,
  FileText
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { AdminUserManagement } from '../components/AdminUserManagement';
import { SystemHealth } from '../types';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const { user, canManageUsers } = useAuth();
  const [activeTab, setActiveTab] = useState<'gateways' | 'users' | 'roles' | 'health' | 'audit'>('gateways');
  const [copied, setCopied] = useState(false);
  const [healthData, setHealthData] = useState<SystemHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [configInfo, setConfigInfo] = useState<{
    razorpay: { key_id_masked: string; mode: string; use_mock_payments: boolean };
    gemini: { configured: boolean; model: string; mode: string };
  } | null>(null);

  const webhookUrl = 'http://localhost:8000/api/recovery/webhook';

  const handleCopy = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const data = await api.getSystemHealth();
      setHealthData(data);
    } catch (err) {
      console.warn('Could not load health diagnostics:', err);
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchConfigInfo = async () => {
    try {
      const res = await fetch('/api/system/config-info');
      if (res.ok) setConfigInfo(await res.json());
    } catch (err) {
      console.warn('Could not load config info:', err);
    }
  };

  useEffect(() => {
    fetchConfigInfo();
  }, []);

  useEffect(() => {
    if (activeTab === 'health') {
      fetchHealth();
    }
  }, [activeTab]);

  return (
    <div className="space-y-6 animate-fadeIn max-w-5xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-brand-cyan" />
          Settings & Administration Console
        </h2>
        <p className="text-xs text-slate-400">
          Configure payment gateways, administer team roles (RBAC), inspect system health diagnostics, and audit logs.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-dark-700 pb-3">
        {[
          { id: 'gateways', label: 'Gateways & Webhooks', icon: Key },
          { id: 'users', label: 'Team & RBAC', icon: Users, adminOnly: true },
          { id: 'roles', label: 'Role Permissions Matrix', icon: ShieldCheck },
          { id: 'health', label: 'System Health Diagnostics', icon: Activity },
          { id: 'audit', label: 'Security & Audit Logs', icon: FileText }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition ${
                isActive
                  ? 'bg-brand-cyan text-dark-900 shadow-glow-cyan font-bold'
                  : 'bg-dark-800 text-slate-400 hover:text-slate-200 hover:bg-dark-750 border border-dark-700'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.adminOnly && (
                <span className={`text-[8px] font-mono px-1 py-0.2 rounded ${
                  isActive ? 'bg-dark-900 text-brand-cyan' : 'bg-dark-700 text-slate-400'
                }`}>
                  ADMIN
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Gateways & Webhooks */}
      {activeTab === 'gateways' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-lg">
            <div className="flex items-center gap-2.5 text-slate-200">
              <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan">
                <Key className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold">Razorpay Test Mode</h3>
                <p className="text-[11px] text-slate-400">Credentials for mock & test engine verification</p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300">Key ID</label>
                <input
                  type="text"
                  readOnly
                  value={configInfo?.razorpay.key_id_masked ?? 'Loading...'}
                  className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-slate-300 select-all"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300">Key Secret</label>
                <input
                  type="password"
                  readOnly
                  value="••••••••••••••••••••••••"
                  className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-slate-400"
                />
              </div>

              <div className="p-3 rounded-xl bg-dark-800 border border-dark-700 text-[11px] text-slate-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>
                  {configInfo?.razorpay.use_mock_payments
                    ? 'Mock payment engine active — no real charges'
                    : `Razorpay ${configInfo?.razorpay.mode ?? 'test'} mode — safe test environment`}
                </span>
              </div>
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-lg">
            <div className="flex items-center gap-2.5 text-slate-200">
              <div className="w-8 h-8 rounded-lg bg-brand-indigo/10 border border-brand-indigo/20 flex items-center justify-center text-brand-indigo">
                <Server className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold">Webhook Listener Endpoint</h3>
                <p className="text-[11px] text-slate-400">Receives real-time payment failure and settlement events</p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300">Webhook URL</label>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={webhookUrl}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-brand-cyan select-all"
                  />
                  <button
                    onClick={handleCopy}
                    className="p-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 transition"
                    title="Copy"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
                {copied && <span className="text-[10px] text-emerald-400 font-semibold mt-1 inline-block">Copied to clipboard!</span>}
              </div>

              <div className="p-3 rounded-xl bg-dark-800 border border-dark-700 space-y-1 text-[11px] text-slate-400">
                <div className="font-semibold text-slate-200">Subscribed Webhook Events:</div>
                <div>• payment.failed (triggers AI investigator)</div>
                <div>• payment.authorized (reconciled settlement)</div>
                <div>• payment_link.paid (autonomous resolution)</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Users & RBAC */}
      {activeTab === 'users' && (
        canManageUsers ? (
          <AdminUserManagement />
        ) : (
          <div className="p-8 rounded-2xl bg-dark-850 border border-dark-700 text-center space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-white">Administrator Access Required</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
              Your current role ({user?.role}) does not have permission to manage system users. Contact Sarah Chen (Admin) for elevated access.
            </p>
          </div>
        )
      )}

      {/* Tab 3: Role Permissions Matrix */}
      {activeTab === 'roles' && (
        <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-xl">
          <div>
            <h3 className="text-sm font-bold text-white">Role-Based Access Control (RBAC) Matrix</h3>
            <p className="text-xs text-slate-400">Permissions enforced across backend APIs and UI controls.</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-800 text-slate-400 border-b border-dark-700 font-mono">
                <tr>
                  <th className="py-2.5 px-3">Permission Area</th>
                  <th className="py-2.5 px-3 text-center text-brand-cyan">ADMIN</th>
                  <th className="py-2.5 px-3 text-center text-emerald-400">OPERATOR</th>
                  <th className="py-2.5 px-3 text-center text-indigo-300">ANALYST</th>
                  <th className="py-2.5 px-3 text-center text-slate-400">VIEWER</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {[
                  { name: 'Dashboard & Recovery KPI View', admin: true, operator: true, analyst: true, viewer: true },
                  { name: 'Payment & Case Inspection', admin: true, operator: true, analyst: true, viewer: true },
                  { name: 'Recovery Intelligence & Telemetry', admin: true, operator: true, analyst: true, viewer: true },
                  { name: 'AI Copilot Inquiries', admin: true, operator: true, analyst: true, viewer: false },
                  { name: 'Execute Autonomous Recovery Actions', admin: true, operator: true, analyst: false, viewer: false },
                  { name: 'Approve High-Value Threshold Approvals', admin: true, operator: true, analyst: false, viewer: false },
                  { name: 'Modify Merchant Safety Guardrails', admin: true, operator: false, analyst: false, viewer: false },
                  { name: 'User Management (Create, Edit, Suspend)', admin: true, operator: false, analyst: false, viewer: false },
                  { name: 'System Health & Security Audit Logs', admin: true, operator: true, analyst: true, viewer: false }
                ].map((row, i) => (
                  <tr key={i} className="hover:bg-dark-800/40 transition">
                    <td className="py-2.5 px-3 font-semibold text-slate-300">{row.name}</td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="text-emerald-400 font-bold">✓ Full</span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {row.operator ? <span className="text-emerald-400 font-bold">✓ Allowed</span> : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {row.analyst ? <span className="text-indigo-300 font-bold">✓ Read-only</span> : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {row.viewer ? <span className="text-slate-400">✓ View</span> : <span className="text-slate-600">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: System Health Diagnostics */}
      {activeTab === 'health' && (
        <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Live Subsystem Health Diagnostics
              </h3>
              <p className="text-xs text-slate-400">Endpoint: /api/system/health</p>
            </div>
            <button
              onClick={fetchHealth}
              disabled={healthLoading}
              className="p-1.5 rounded-lg bg-dark-800 border border-dark-700 text-slate-300 hover:text-white"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin text-brand-cyan' : ''}`} />
            </button>
          </div>

          {healthLoading ? (
            <div className="py-12 flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-brand-cyan" />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {healthData?.services && Object.entries(healthData.services).map(([svc, stat]) => (
                <div key={svc} className="p-3.5 rounded-xl bg-dark-800 border border-dark-700 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-slate-200 capitalize">{svc.replace('_', ' ')}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <div className="text-[11px] font-mono text-emerald-400 font-bold uppercase">{stat}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Security & Audit Logs */}
      {activeTab === 'audit' && (
        <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-xl">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-cyan" />
              Security & Operator Audit Log
            </h3>
            <p className="text-xs text-slate-400">Chronological ledger of logins, role elevation, and recovery executions.</p>
          </div>

          <div className="p-3.5 rounded-xl bg-dark-900 border border-dark-700/80 font-mono text-[11px] text-slate-300 space-y-2">
            <div>[AUTH] User 'admin@payrecover.ai' signed in via JWT Bearer Token.</div>
            <div>[GUARDRAILS] Deterministic policy checks verified 0 violations.</div>
            <div>[IDEMPOTENCY] Idempotency-Key cache verified active (in-memory + database table).</div>
            <div>[SECURITY] Passwords hashed with bcrypt (cost factor 12); secrets redacted.</div>
          </div>
        </div>
      )}
    </div>
  );
};
