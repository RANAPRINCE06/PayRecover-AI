import React, { useState, useEffect, useCallback } from 'react';
import {
  IndianRupee, AlertTriangle, Sparkles, CheckCircle2,
  Bot, Zap, Loader2, ChevronDown, ChevronUp,
  TrendingUp, TrendingDown, Target, Shield,
  Activity, Clock, Users, BarChart3, RefreshCw
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, BarChart, Bar
} from 'recharts';
import {
  DashboardMetrics, Payment, RecoveryCase,
  AutonomousRecoveryResult, AnalyticsOverview,
  RecoveryTrend, RecoveryOpportunity, SystemStatus
} from '../types';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { RecoveryScore } from '../components/RecoveryScore';
import { AutonomousPipelinePanel } from '../components/AutonomousPipelinePanel';
import { api } from '../services/api';
import { useToast } from '../components/Toast';

interface CommandCenterProps {
  metrics: DashboardMetrics | null;
  payments: Payment[];
  recoveryCases: RecoveryCase[];
  onSelectPayment: (p: Payment) => void;
  onOpenSimulate: () => void;
  onRefresh?: () => void;
  onNavigate?: (tab: string) => void;
}

type TrendPeriod = '7d' | '30d' | '90d';

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  label, value, sub, icon: Icon, accent = 'cyan', loading = false, trend
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.FC<any>;
  accent?: 'cyan' | 'emerald' | 'rose' | 'amber' | 'indigo' | 'violet';
  loading?: boolean;
  trend?: { value: number; label: string };
}) {
  const colors = {
    cyan:    { icon: 'text-brand-cyan',    border: 'border-brand-cyan/20',    bg: 'bg-brand-cyan/5',    badge: 'text-brand-cyan bg-brand-cyan/10' },
    emerald: { icon: 'text-emerald-400',   border: 'border-emerald-500/20',   bg: 'bg-emerald-500/5',   badge: 'text-emerald-400 bg-emerald-500/10' },
    rose:    { icon: 'text-rose-400',      border: 'border-rose-500/20',      bg: 'bg-rose-500/5',      badge: 'text-rose-400 bg-rose-500/10' },
    amber:   { icon: 'text-amber-400',     border: 'border-amber-500/20',     bg: 'bg-amber-500/5',     badge: 'text-amber-400 bg-amber-500/10' },
    indigo:  { icon: 'text-indigo-400',    border: 'border-indigo-500/20',    bg: 'bg-indigo-500/5',    badge: 'text-indigo-400 bg-indigo-500/10' },
    violet:  { icon: 'text-violet-400',    border: 'border-violet-500/20',    bg: 'bg-violet-500/5',    badge: 'text-violet-400 bg-violet-500/10' },
  };
  const c = colors[accent];

  return (
    <div className={`p-4 rounded-xl border ${c.border} bg-dark-850 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">{label}</span>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${c.bg} border ${c.border}`}>
          <Icon className={`w-3.5 h-3.5 ${c.icon}`} />
        </div>
      </div>
      {loading ? (
        <div className="h-7 w-24 bg-dark-700 rounded animate-pulse" />
      ) : (
        <div className="text-2xl font-black font-mono text-white tracking-tight">{value}</div>
      )}
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
      {trend && !loading && (
        <div className={`flex items-center gap-1 text-[10px] font-semibold ${trend.value >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          {trend.value >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trend.label}
        </div>
      )}
    </div>
  );
}

// ─── System Status Bar ─────────────────────────────────────────────────────────

function SystemStatusBar({ status }: { status: SystemStatus | null }) {
  if (!status) return null;

  const compLabels: Record<string, string> = {
    api: 'API', database: 'Database', redis: 'Redis',
    gemini: 'Gemini', razorpay: 'Razorpay', tool_executor: 'Tool Executor', guardrails: 'Guardrails'
  };

  const statusColor = (s: string) => {
    if (s === 'HEALTHY' || s === 'ACTIVE' || s === 'CONNECTED') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (s === 'TEST_MODE' || s === 'FALLBACK') return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    if (s === 'DEGRADED' || s === 'UNKNOWN') return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
    return 'text-slate-400 bg-dark-700 border-dark-600';
  };

  return (
    <div className="p-3 rounded-xl bg-dark-850 border border-dark-700 flex flex-wrap gap-1.5 items-center">
      <span className="text-[9px] text-slate-600 uppercase tracking-widest font-bold mr-1">System</span>
      {Object.entries(status.components).map(([key, comp]) => (
        <div
          key={key}
          title={comp.detail}
          className={`flex items-center gap-1 text-[9px] font-mono font-bold px-2 py-0.5 rounded border ${statusColor(comp.status)}`}
        >
          {compLabels[key] || key} · {comp.status}
        </div>
      ))}
    </div>
  );
}

// ─── Recovery Funnel ──────────────────────────────────────────────────────────

function RecoveryFunnel({
  overview, onFilter
}: {
  overview: AnalyticsOverview | null;
  onFilter?: (stage: string) => void;
}) {
  if (!overview) return <div className="h-32 bg-dark-800 animate-pulse rounded-xl" />;

  const total = overview.failed_payments_count + overview.recovered_payments_count;
  const stages = [
    { label: 'Failed Payments',         count: overview.failed_payments_count,    amt: overview.revenue_at_risk,      pct: 100, filter: 'FAILED' },
    { label: 'Recoverable (AI Scored)', count: Math.round(overview.total_cases * 0.85 + overview.active_cases_count), amt: overview.predicted_recoverable + overview.revenue_recovered, pct: total > 0 ? Math.round(((overview.total_cases) / total) * 100) : 0, filter: '' },
    { label: 'AI Strategies Generated', count: overview.total_cases,              amt: overview.predicted_recoverable, pct: total > 0 ? Math.round((overview.total_cases / total) * 100) : 0, filter: '' },
    { label: 'Recovery Actions',        count: overview.total_recovery_attempts,  amt: overview.predicted_recoverable * 0.75, pct: total > 0 ? Math.round((overview.total_recovery_attempts / Math.max(1, total)) * 100) : 0, filter: '' },
    { label: 'Revenue Recovered',       count: overview.recovered_cases_count,    amt: overview.revenue_recovered,    pct: total > 0 ? Math.round((overview.recovered_cases_count / total) * 100) : 0, filter: 'RECOVERED' },
  ];

  const maxCount = Math.max(...stages.map(s => s.count), 1);

  return (
    <div className="space-y-1">
      {stages.map((s, i) => {
        const width = Math.max(25, Math.round((s.count / maxCount) * 100));
        return (
          <div key={s.label} className="flex items-center gap-3">
            <div className="w-36 flex-shrink-0 text-[10px] text-slate-400 text-right">{s.label}</div>
            <div className="flex-1 h-8 bg-dark-800 rounded-lg overflow-hidden border border-dark-700 relative">
              <div
                className="h-full bg-gradient-to-r from-brand-cyan/40 to-brand-cyan/20 flex items-center px-3 transition-all"
                style={{ width: `${width}%` }}
              >
                <span className="text-[11px] font-bold text-brand-cyan whitespace-nowrap">{s.count.toLocaleString()}</span>
              </div>
            </div>
            <div className="w-24 flex-shrink-0 text-[10px] text-slate-500 font-mono">
              ₹{Math.round(s.amt / 1000)}k
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Opportunity Card ─────────────────────────────────────────────────────────

function OpportunityCard({ opp, onView }: { opp: RecoveryOpportunity; onView: (id: string) => void }) {
  const probColor = opp.recovery_probability >= 0.85 ? 'text-emerald-400' : opp.recovery_probability >= 0.70 ? 'text-amber-400' : 'text-rose-400';
  const guardrailBadge = opp.guardrail_hint === 'SAFE'
    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : 'bg-amber-500/10 text-amber-400 border-amber-500/20';

  return (
    <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700 hover:border-brand-cyan/30 transition">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="text-xs font-bold text-white">{opp.customer_name}</div>
          <div className="text-[10px] text-slate-500 font-mono">{opp.payment_method} · {opp.failure_reason}</div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-sm font-black font-mono text-white">₹{opp.amount.toLocaleString()}</div>
          <div className={`text-[10px] font-bold ${probColor}`}>{Math.round(opp.recovery_probability * 100)}% recovery</div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          {opp.current_strategy && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
              {opp.current_strategy}
            </span>
          )}
          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${guardrailBadge}`}>
            {opp.guardrail_hint}
          </span>
        </div>
        <button
          onClick={() => onView(opp.case_id)}
          className="text-[10px] font-bold text-brand-cyan hover:text-white px-2 py-1 rounded bg-brand-cyan/10 hover:bg-brand-cyan/20 transition"
        >
          VIEW
        </button>
      </div>
    </div>
  );
}

// ─── Main Command Center 2.0 ─────────────────────────────────────────────────

export const CommandCenter: React.FC<CommandCenterProps> = ({
  metrics, payments, recoveryCases,
  onSelectPayment, onOpenSimulate, onRefresh, onNavigate
}) => {
  const { success, error: showError } = useToast();

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [trend, setTrend] = useState<RecoveryTrend | null>(null);
  const [trendPeriod, setTrendPeriod] = useState<TrendPeriod>('7d');
  const [opportunities, setOpportunities] = useState<RecoveryOpportunity[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(true);
  const [autoRunning, setAutoRunning] = useState(false);
  const [autoResult, setAutoResult] = useState<AutonomousRecoveryResult | null>(null);
  const [autoError, setAutoError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const loadAnalytics = useCallback(async () => {
    try {
      const [ov, opps, sys] = await Promise.all([
        api.getAnalyticsOverview(),
        api.getRecoveryOpportunities(5),
        api.getSystemStatus()
      ]);
      setOverview(ov);
      setOpportunities(opps.opportunities);
      setSystemStatus(sys);
    } catch {
      // non-fatal
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const loadTrend = useCallback(async () => {
    setTrendLoading(true);
    try {
      const t = await api.getRecoveryTrends(trendPeriod);
      setTrend(t);
    } catch {
      // non-fatal
    } finally {
      setTrendLoading(false);
    }
  }, [trendPeriod]);

  useEffect(() => { loadAnalytics(); }, [loadAnalytics]);
  useEffect(() => { loadTrend(); }, [loadTrend]);

  const bestCase = recoveryCases
    .filter(rc => !['RECOVERED', 'FAILED', 'EXPIRED'].includes(rc.status))
    .sort((a, b) => (b.recovery_score ?? 0) - (a.recovery_score ?? 0))[0];

  const handleRunAutonomous = async () => {
    if (!bestCase) {
      setAutoError('No active recovery case. Run a demo simulation first.');
      setPanelOpen(true);
      return;
    }
    setAutoRunning(true);
    setAutoError(null);
    setAutoResult(null);
    setPanelOpen(true);
    try {
      const result = await api.runAutonomousRecovery(bestCase.id);
      setAutoResult(result);
      success('Autonomous recovery pipeline completed');
      onRefresh?.();
      loadAnalytics();
    } catch (err: any) {
      showError(err.message || 'Autonomous recovery failed');
      setAutoError(err.message || 'Pipeline failed');
    } finally {
      setAutoRunning(false);
    }
  };

  const handleApprove = async () => {
    if (!autoResult) return;
    try {
      await api.approveCase(autoResult.case_id);
      success('Recovery approved');
      setAutoResult(prev => prev ? { ...prev, requires_human_approval: false } : prev);
      onRefresh?.();
    } catch (err: any) { showError(err.message); }
  };

  const handleReject = async () => {
    if (!autoResult) return;
    try {
      await api.rejectCase(autoResult.case_id, 'Rejected from dashboard');
      setAutoResult(prev => prev ? { ...prev, final_status: 'FAILED', requires_human_approval: false } : prev);
      onRefresh?.();
    } catch (err: any) { showError(err.message); }
  };

  const handleSettle = async () => {
    if (!autoResult) return;
    try {
      await api.confirmSettlement(autoResult.case_id);
      success('Settlement confirmed — revenue recovered!');
      setAutoResult(prev => prev ? { ...prev, final_status: 'RECOVERED' } : prev);
      onRefresh?.();
      loadAnalytics();
    } catch (err: any) { showError(err.message); }
  };

  const ov = overview;
  const isLoading = overviewLoading;

  return (
    <div className="space-y-5 animate-fadeIn">

      {/* System Status */}
      <SystemStatusBar status={systemStatus} />

      {/* Top Actions Banner */}
      <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center">
            <Bot className="w-4 h-4 text-brand-cyan" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white">
              Autonomous Recovery Engine
              <span className="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {ov ? `${ov.ai_automation_rate.toFixed(0)}% Automation` : 'ACTIVE'}
              </span>
            </h2>
            <p className="text-xs text-slate-400">Multi-agent pipeline monitoring Razorpay Test webhooks.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunAutonomous}
            disabled={autoRunning}
            className="px-3.5 py-2 bg-gradient-to-r from-violet-600 to-brand-cyan text-white font-bold text-xs rounded-lg hover:opacity-90 transition flex items-center gap-1.5 disabled:opacity-60"
          >
            {autoRunning ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Running…</> : <><Zap className="w-3.5 h-3.5" />⚡ Autonomous Recovery</>}
          </button>
          <button
            onClick={onOpenSimulate}
            className="px-3.5 py-2 bg-dark-800 border border-dark-600 hover:border-brand-cyan/40 text-slate-200 font-bold text-xs rounded-lg transition flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5 text-brand-cyan" />
            Demo Simulation
          </button>
          <button onClick={() => { onRefresh?.(); loadAnalytics(); }} className="p-2 text-slate-400 hover:text-brand-cyan rounded-lg hover:bg-dark-800 transition">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Autonomous Recovery Panel */}
      {panelOpen && (
        <div className="rounded-xl border border-brand-cyan/20 bg-dark-900 overflow-hidden">
          <button onClick={() => setPanelOpen(p => !p)}
            className="w-full flex items-center justify-between px-5 py-3 border-b border-dark-700 hover:bg-dark-800/50 transition">
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-brand-cyan" />
              <span className="text-xs font-bold text-white">Autonomous Recovery Engine</span>
              {autoRunning && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 animate-pulse">RUNNING</span>}
              {autoResult && !autoRunning && (
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                  autoResult.final_status === 'RECOVERED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                  autoResult.final_status === 'AWAITING_HUMAN_APPROVAL' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                  'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/20'
                }`}>{autoResult.final_status}</span>
              )}
            </div>
            {panelOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          <div className="p-5">
            {autoRunning && !autoResult && (
              <div className="flex flex-col items-center py-10 gap-3">
                <Loader2 className="w-7 h-7 animate-spin text-brand-cyan" />
                <div className="text-sm font-bold text-white">Running 6-Stage Pipeline…</div>
                <div className="flex gap-1 mt-1">
                  {['INVESTIGATE','INTENT','STRATEGY','GUARDRAIL','EXECUTE','SETTLE'].map((s, i) => (
                    <span key={s} className="text-[9px] font-mono px-1 py-0.5 rounded bg-dark-800 border border-dark-700 text-slate-500 animate-pulse" style={{ animationDelay: `${i * 120}ms` }}>{s}</span>
                  ))}
                </div>
              </div>
            )}
            {autoError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300">
                <div className="font-bold mb-1">Error</div>{autoError}
              </div>
            )}
            {autoResult && (
              <AutonomousPipelinePanel result={autoResult} isLoading={autoRunning}
                onApprove={handleApprove} onReject={handleReject} onConfirmSettlement={handleSettle} />
            )}
          </div>
        </div>
      )}

      {/* 8 KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="Revenue at Risk" value={ov ? `₹${(ov.revenue_at_risk/1000).toFixed(1)}k` : '—'} icon={AlertTriangle} accent="rose" loading={isLoading} sub={ov ? `${ov.failed_payments_count} failed payments` : undefined} />
        <KpiCard label="Recovered" value={ov ? `₹${(ov.revenue_recovered/1000).toFixed(1)}k` : '—'} icon={CheckCircle2} accent="emerald" loading={isLoading} trend={ov ? { value: 1, label: `${ov.recovery_rate.toFixed(1)}% rate` } : undefined} />
        <KpiCard label="Predicted Recoverable" value={ov ? `₹${(ov.predicted_recoverable/1000).toFixed(1)}k` : '—'} icon={Sparkles} accent="cyan" loading={isLoading} sub={ov ? `${ov.active_cases_count} active cases` : undefined} />
        <KpiCard label="Processed" value={metrics ? `₹${(metrics.revenue_processed/1000).toFixed(1)}k` : '—'} icon={IndianRupee} accent="indigo" loading={!metrics} />
        <KpiCard label="Avg Recovery Score" value={ov ? `${ov.average_recovery_score.toFixed(0)}/100` : '—'} icon={Target} accent="amber" loading={isLoading} />
        <KpiCard label="Active Cases" value={ov ? ov.active_cases_count : '—'} icon={Activity} accent="violet" loading={isLoading} sub={ov ? `${ov.awaiting_approval_count} awaiting approval` : undefined} />
        <KpiCard label="Recovery Attempts" value={ov ? ov.total_recovery_attempts : '—'} icon={BarChart3} accent="indigo" loading={isLoading} />
        <KpiCard label="AI Automation" value={ov ? `${ov.ai_automation_rate.toFixed(0)}%` : '—'} icon={Bot} accent="cyan" loading={isLoading} sub={ov ? `${ov.total_agent_actions} agent actions` : undefined} />
      </div>

      {/* Trend Chart + Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Trend Chart */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">Recovery Trend</h3>
              <p className="text-[11px] text-slate-500">Failed vs recovered revenue over time</p>
            </div>
            <div className="flex gap-1">
              {(['7d', '30d', '90d'] as TrendPeriod[]).map(p => (
                <button key={p} onClick={() => setTrendPeriod(p)}
                  className={`text-[10px] font-mono px-2 py-1 rounded transition ${trendPeriod === p ? 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/30' : 'text-slate-500 hover:text-slate-300'}`}>
                  {p}
                </button>
              ))}
            </div>
          </div>
          {trendLoading ? (
            <div className="h-56 bg-dark-800 animate-pulse rounded-xl" />
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend?.data || []}>
                  <defs>
                    <linearGradient id="cg1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#00F0FF" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="cg2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#F43F5E" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" vertical={false} />
                  <XAxis dataKey="date" stroke="#475569" fontSize={10} tickLine={false}
                    tickFormatter={d => d.slice(5)} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false}
                    tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '11px' }}
                    formatter={(v: any) => [`₹${Number(v).toLocaleString()}`, '']} labelFormatter={l => `Date: ${l}`} />
                  <Area type="monotone" dataKey="at_risk" name="At Risk" stroke="#F43F5E" fill="url(#cg2)" strokeWidth={1.5} />
                  <Area type="monotone" dataKey="recovered_amount" name="Recovered" stroke="#00F0FF" fill="url(#cg1)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="flex gap-4 mt-2">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400"><div className="w-2.5 h-0.5 bg-rose-500" />At Risk</div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400"><div className="w-2.5 h-0.5 bg-brand-cyan" />Recovered</div>
          </div>
        </div>

        {/* Recovery Funnel */}
        <div className="p-5 rounded-xl bg-dark-850 border border-dark-700">
          <h3 className="text-sm font-bold text-white mb-1">Recovery Funnel</h3>
          <p className="text-[11px] text-slate-500 mb-4">Pipeline conversion stages</p>
          <RecoveryFunnel overview={ov} onFilter={f => onNavigate?.(f === 'RECOVERED' ? 'recovery-cases' : 'recovery-cases')} />
        </div>
      </div>

      {/* Opportunities + High Priority */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* AI Opportunities */}
        <div className="p-5 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                AI Recovery Opportunities
                {opportunities.length > 0 && (
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
                    {opportunities.length} detected
                  </span>
                )}
              </h3>
              <p className="text-[11px] text-slate-500">Highest-value active cases by AI score</p>
            </div>
            <button onClick={() => onNavigate?.('recovery-cases')} className="text-[10px] text-brand-cyan hover:underline">View all →</button>
          </div>
          {opportunities.length === 0 ? (
            <div className="text-center py-8">
              <Sparkles className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <div className="text-xs text-slate-500">No opportunities detected.<br />Run a simulation to create cases.</div>
            </div>
          ) : (
            <div className="space-y-2">
              {opportunities.map(opp => (
                <OpportunityCard key={opp.case_id} opp={opp}
                  onView={() => {
                    const payment = payments.find(p => p.id === opp.payment_id);
                    if (payment) onSelectPayment(payment);
                  }} />
              ))}
            </div>
          )}
        </div>

        {/* High Priority Queue */}
        <div className="p-5 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">Priority Queue</h3>
              <p className="text-[11px] text-slate-500">Cases requiring immediate attention</p>
            </div>
            <button onClick={() => onNavigate?.('recovery-cases')} className="text-[10px] text-brand-cyan hover:underline">Manage →</button>
          </div>
          <div className="space-y-2">
            {recoveryCases
              .filter(rc => !['RECOVERED','FAILED','EXPIRED'].includes(rc.status))
              .sort((a, b) => (b.recovery_score ?? 0) - (a.recovery_score ?? 0))
              .slice(0, 5)
              .map(rc => {
                const payment = rc.payment || payments.find(p => p.id === rc.payment_id);
                return (
                  <div key={rc.id} onClick={() => payment && onSelectPayment(payment)}
                    className="p-3 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 hover:border-brand-cyan/30 cursor-pointer transition flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <RecoveryScore score={rc.recovery_score} size="md" />
                      <div>
                        <div className="text-xs font-bold text-white">{payment?.customer?.name || 'Customer'}</div>
                        <div className="text-[10px] text-slate-500 font-mono">{payment?.failure_reason} · {rc.customer_intent || '—'}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-mono font-bold text-white">₹{payment?.amount.toLocaleString()}</div>
                      <StatusBadge status={rc.status} />
                    </div>
                  </div>
                );
              })}
            {recoveryCases.filter(rc => !['RECOVERED','FAILED','EXPIRED'].includes(rc.status)).length === 0 && (
              <div className="text-center py-8 text-xs text-slate-500">
                <CheckCircle2 className="w-7 h-7 text-emerald-400 mx-auto mb-2" />
                No active cases. Run a simulation to begin.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
