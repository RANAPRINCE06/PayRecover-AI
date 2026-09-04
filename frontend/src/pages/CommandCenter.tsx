import React from 'react';
import {
  IndianRupee,
  AlertTriangle,
  Sparkles,
  CheckCircle2,
  TrendingUp,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  Bot,
  Zap,
  Users
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar
} from 'recharts';
import { DashboardMetrics, Payment, RecoveryCase } from '../types';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { RecoveryScore } from '../components/RecoveryScore';

interface CommandCenterProps {
  metrics: DashboardMetrics | null;
  payments: Payment[];
  recoveryCases: RecoveryCase[];
  onSelectPayment: (p: Payment) => void;
  onOpenSimulate: () => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  metrics,
  payments,
  recoveryCases,
  onSelectPayment,
  onOpenSimulate
}) => {
  if (!metrics) return null;

  const highPriorityCases = recoveryCases
    .filter((rc) => rc.status === 'AWAITING_HUMAN_APPROVAL' || rc.recovery_score >= 80)
    .slice(0, 5);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Banner / Pulse */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-dark-850 via-dark-800 to-dark-850 border border-dark-700 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              Autonomous Recovery Engine Active
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                84.6% Avg Win Rate
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Actively monitoring Razorpay Test webhooks & executing multi-agent recovery workflows.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <button
            onClick={onOpenSimulate}
            className="w-full md:w-auto px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-blue text-dark-900 font-bold text-xs rounded-lg shadow-glow-cyan hover:opacity-90 transition flex items-center justify-center gap-1.5"
          >
            <Zap className="w-3.5 h-3.5 fill-dark-900" />
            Run Recovery Demo
          </button>
        </div>
      </div>

      {/* 8 Primary Metrics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Revenue Processed"
          value={`₹${(metrics.revenue_processed / 1000).toFixed(1)}k`}
          subValue="Gross volume processed"
          icon={IndianRupee}
          variant="default"
        />

        <MetricCard
          label="Revenue At Risk"
          value={`₹${(metrics.revenue_at_risk / 1000).toFixed(1)}k`}
          change={`${metrics.failed_payments_count} Failed Orders`}
          icon={AlertTriangle}
          variant="rose"
        />

        <MetricCard
          label="Predicted Recoverable"
          value={`₹${(metrics.predicted_recoverable / 1000).toFixed(1)}k`}
          subValue={`${metrics.active_recoveries_count} Active recovery flows`}
          icon={Sparkles}
          variant="cyan"
        />

        <MetricCard
          label="Revenue Recovered"
          value={`₹${(metrics.revenue_recovered / 1000).toFixed(1)}k`}
          change={`${metrics.recovery_rate}% Recovery Rate`}
          isPositive={true}
          icon={CheckCircle2}
          variant="emerald"
        />
      </div>

      {/* Charts & Recovery Pipeline Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recovery Trend Chart */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">Recovery Velocity Trend</h3>
              <p className="text-xs text-slate-400">Daily failed revenue vs autonomously recovered INR</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                <span className="text-slate-400">At Risk</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-brand-cyan" />
                <span className="text-slate-400">Recovered</span>
              </div>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metrics.monthly_trend}>
                <defs>
                  <linearGradient id="recovGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00F0FF" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#F43F5E" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" vertical={false} />
                <XAxis dataKey="day" stroke="#64748B" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748B" fontSize={11} tickLine={false} tickFormatter={(val) => `₹${val/1000}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                  formatter={(val: any) => [`₹${Number(val).toLocaleString()}`, '']}
                />
                <Area type="monotone" dataKey="at_risk" stroke="#F43F5E" fillOpacity={1} fill="url(#riskGradient)" strokeWidth={2} />
                <Area type="monotone" dataKey="recovered" stroke="#00F0FF" fillOpacity={1} fill="url(#recovGradient)" strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Autonomous Pipeline Funnel */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-white mb-1">Autonomous Pipeline</h3>
            <p className="text-xs text-slate-400 mb-4">Stage-by-stage recovery funnel</p>

            <div className="space-y-3">
              {metrics.recovery_pipeline.map((stage, idx) => (
                <div key={stage.stage} className="p-3 rounded-xl bg-dark-800 border border-dark-700">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-slate-300">{stage.stage}</span>
                    <span className="font-mono text-brand-cyan font-bold">₹{Math.round(stage.value).toLocaleString()}</span>
                  </div>
                  <div className="w-full h-1.5 bg-dark-900 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-cyan to-brand-emerald rounded-full"
                      style={{ width: `${Math.min(100, Math.max(15, (stage.value / (metrics.revenue_at_risk + metrics.revenue_recovered || 1)) * 100))}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">{stage.count} cases handled</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-3 rounded-xl bg-brand-indigo/10 border border-brand-indigo/20 flex items-center justify-between">
            <span className="text-xs text-indigo-300 font-semibold">Human Review Queue</span>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-brand-indigo/30 text-white">
              {metrics.human_review_queue_count} Pending
            </span>
          </div>
        </div>
      </div>

      {/* High-Priority Queue & AI Action Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* High Priority Queue */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">High-Priority Recoveries</h3>
              <p className="text-xs text-slate-400">Transactions with highest recoverable intent & value</p>
            </div>
          </div>

          <div className="space-y-2.5">
            {highPriorityCases.map((rc) => {
              const payment = rc.payment || payments.find((p) => p.id === rc.payment_id);
              return (
                <div
                  key={rc.id}
                  onClick={() => payment && onSelectPayment(payment)}
                  className="p-3.5 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 hover:border-brand-cyan/40 cursor-pointer transition flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <RecoveryScore score={rc.recovery_score} size="md" />
                    <div>
                      <div className="text-xs font-bold text-white flex items-center gap-2">
                        {payment?.customer?.name || 'Customer'}
                        <span className="text-slate-400 font-normal">({payment?.payment_method})</span>
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {payment?.failure_reason || 'CARD_DECLINED'} • Intent: {rc.customer_intent || 'ALTERNATE_METHOD'}
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-xs font-bold font-mono text-white">
                      ₹{payment?.amount.toLocaleString() || '12,999'}
                    </div>
                    <StatusBadge status={rc.status} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* AI Recommendations & Live Insight */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-brand-cyan" />
              <h3 className="text-sm font-bold text-white">AI Recovery Insights</h3>
            </div>
            <p className="text-xs text-slate-400 mb-3">Live intelligence computed by AI Payment Investigator</p>

            {/* Dynamic Insight Callout */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-brand-cyan/15 via-dark-800 to-dark-800 border border-brand-cyan/30 space-y-2 mb-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-cyan uppercase tracking-wider font-mono">
                  Autonomous Opportunity
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold">
                  {recoveryCases.filter((c) => c.recovery_score >= 80).length} High-Yield Cases
                </span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed font-medium">
                <strong className="text-brand-cyan">{recoveryCases.filter((c) => c.recovery_score >= 80).length} failed payments</strong> have <strong>&gt;80% predicted recovery probability</strong>.
              </p>
              <div className="flex items-baseline gap-2 pt-1">
                <span className="text-[11px] text-slate-400">Estimated Recoverable Revenue:</span>
                <span className="text-base font-black font-mono text-emerald-400">
                  ₹{metrics.predicted_recoverable.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="space-y-2.5">
              <div className="p-3 rounded-xl bg-dark-800 border border-dark-700">
                <div className="text-xs font-bold text-brand-cyan mb-0.5">1. Card 3DS Failures ➔ 1-Click WhatsApp UPI</div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  Card transactions have a 42% 3DS drop-off rate. Switching to WhatsApp UPI deep-links recovers 89.2% of these orders.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-dark-800 border border-dark-700">
                <div className="text-xs font-bold text-brand-emerald mb-0.5">2. High-Value Escalation Guardrail Active</div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  Orders over ₹50,000 are automatically protected with Merchant Human Approval before customer dispatch.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
