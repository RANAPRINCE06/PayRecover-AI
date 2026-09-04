import React, { useState, useEffect, useCallback } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
  AreaChart,
  Area
} from 'recharts';
import {
  LineChart,
  PieChart as PieIcon,
  Layers,
  Shield,
  IndianRupee,
  TrendingUp,
  AlertTriangle,
  Sparkles,
  Zap,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Loader2,
  ArrowUpRight,
  Target,
  BrainCircuit,
  MessageSquare
} from 'lucide-react';
import {
  AnalyticsOverview,
  TrendDay,
  FailureByReason,
  PaymentMethodStat,
  CustomerSegmentStat,
  StrategyStat,
  RecoveryOpportunity,
  DashboardMetrics
} from '../types';
import { api } from '../services/api';

interface RecoveryIntelligenceProps {
  metrics?: DashboardMetrics | null;
  onSelectPaymentId?: (paymentId: string) => void;
}

const SEGMENT_COLORS = ['#10B981', '#00F0FF', '#6366F1', '#F59E0B', '#EC4899'];

export const RecoveryIntelligence: React.FC<RecoveryIntelligenceProps> = ({
  metrics: initialMetrics,
  onSelectPaymentId
}) => {
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('30d');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [trendDays, setTrendDays] = useState<TrendDay[]>([]);
  const [failures, setFailures] = useState<FailureByReason[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodStat[]>([]);
  const [customerSegments, setCustomerSegments] = useState<CustomerSegmentStat[]>([]);
  const [strategies, setStrategies] = useState<StrategyStat[]>([]);
  const [opportunities, setOpportunities] = useState<RecoveryOpportunity[]>([]);

  const fetchAnalytics = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const [
        overviewData,
        trendRes,
        failureRes,
        methodRes,
        segmentRes,
        strategyRes,
        oppRes
      ] = await Promise.all([
        api.getAnalyticsOverview(),
        api.getRecoveryTrends(period),
        api.getFailureAnalytics(),
        api.getPaymentMethodAnalytics(),
        api.getCustomerSegmentAnalytics(),
        api.getStrategyAnalytics(),
        api.getRecoveryOpportunities()
      ]);

      setOverview(overviewData);
      setTrendDays(trendRes?.data || []);
      setFailures(failureRes?.by_reason || []);
      setPaymentMethods(methodRes?.methods || []);
      setCustomerSegments(segmentRes?.segments || []);
      setStrategies(strategyRes?.strategies || []);
      setOpportunities(oppRes?.opportunities || []);
    } catch (err) {
      console.error('Failed fetching recovery intelligence data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [period]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <LineChart className="w-5 h-5 text-brand-cyan" />
            Recovery Intelligence & Analytics 2.0
          </h2>
          <p className="text-xs text-slate-400">
            Deep telemetry correlation across payment rails, AI strategist recommendations, and automated conversion channels.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Period Selector */}
          <div className="flex items-center bg-dark-800 p-0.5 rounded-lg border border-dark-700 text-xs">
            {(['7d', '30d', '90d'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  period === p
                    ? 'bg-brand-cyan text-dark-900 font-bold shadow-glow-cyan'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={() => fetchAnalytics(true)}
            disabled={refreshing || loading}
            className="p-2 bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-300 hover:text-white rounded-lg transition disabled:opacity-50"
            title="Refresh analytics telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-brand-cyan' : ''}`} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-brand-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-medium">Computing Recovery Intelligence & Strategy Telemetry...</p>
        </div>
      ) : (
        <>
          {/* Summary KPI Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Revenue Recovered</span>
              <div className="text-xl font-extrabold text-brand-emerald font-mono mt-1">
                {formatCurrency(overview?.revenue_recovered || 0)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
                <span className="text-emerald-400 font-bold">{(overview?.recovery_rate || 0).toFixed(1)}%</span> of total at-risk
              </div>
            </div>

            <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Predicted Recoverable</span>
              <div className="text-xl font-extrabold text-brand-cyan font-mono mt-1">
                {formatCurrency(overview?.predicted_recoverable || 0)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                Active in pipeline: {overview?.active_cases_count || 0} cases
              </div>
            </div>

            <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Payments Recovered</span>
              <div className="text-xl font-extrabold text-white font-mono mt-1">
                {overview?.recovered_payments_count || 0}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                Out of {overview?.failed_payments_count || 0} failed payments
              </div>
            </div>

            <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Human Approvals</span>
              <div className="text-xl font-extrabold text-amber-400 font-mono mt-1">
                {overview?.awaiting_approval_count || 0}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                High-value / high-discount cases
              </div>
            </div>
          </div>

          {/* Trend & Volume Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recovery Volume Curve */}
            <div className="lg:col-span-2 p-5 rounded-2xl bg-dark-850 border border-dark-700">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-brand-cyan" />
                    Recovery Trajectory ({period.toUpperCase()})
                  </h3>
                  <p className="text-xs text-slate-400">At-risk volume vs successfully captured recoveries</p>
                </div>
                <div className="flex items-center gap-3 text-[11px]">
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> At Risk
                  </span>
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Recovered
                  </span>
                </div>
              </div>

              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendDays}>
                    <defs>
                      <linearGradient id="colorRec" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" vertical={false} />
                    <XAxis dataKey="date" stroke="#64748B" fontSize={11} tickLine={false} />
                    <YAxis
                      stroke="#64748B"
                      fontSize={11}
                      tickLine={false}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                      formatter={(val: any) => [`₹${Number(val).toLocaleString('en-IN')}`, '']}
                    />
                    <Area type="monotone" dataKey="at_risk" stroke="#F43F5E" fillOpacity={1} fill="url(#colorRisk)" name="At Risk" />
                    <Area type="monotone" dataKey="recovered_amount" stroke="#10B981" strokeWidth={2} fillOpacity={1} fill="url(#colorRec)" name="Recovered" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Payment Method Performance */}
            <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-bold text-white mb-1">Conversion by Payment Rail</h3>
                <p className="text-xs text-slate-400 mb-4">Autonomous success rates per instrument</p>

                <div className="space-y-3.5">
                  {paymentMethods.map((pm) => (
                    <div key={pm.method} className="p-2.5 rounded-xl bg-dark-800/80 border border-dark-700/80">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-bold text-slate-200">{pm.method}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400 font-mono">
                            ₹{(pm.recovered_amount / 1000).toFixed(0)}k
                          </span>
                          <span className="font-mono text-emerald-400 font-bold">
                            {pm.recovery_rate.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 bg-dark-900 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-brand-cyan to-brand-emerald rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(100, pm.recovery_rate)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[9px] text-slate-500 mt-1">
                        <span>{pm.failed} failures</span>
                        <span>{pm.recovered} recovered</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Failure Reasons & Customer Segments Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Failure Root Cause Analysis */}
            <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
              <h3 className="text-sm font-bold text-white mb-1">Failure Reasons & Telemetry Attribution</h3>
              <p className="text-xs text-slate-400 mb-4">Volume breakdown and recovery conversion per failure root cause</p>

              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={failures}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" vertical={false} />
                    <XAxis dataKey="reason" stroke="#64748B" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748B" fontSize={11} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                    />
                    <Bar dataKey="count" fill="#F43F5E" name="Failed Orders" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="recovered" fill="#10B981" name="Recovered" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Customer Segment Breakdown */}
            <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
              <h3 className="text-sm font-bold text-white mb-1">Recovery by Customer Segment</h3>
              <p className="text-xs text-slate-400 mb-4">VIP & returning cohorts demonstrate highest conversion loyalty</p>

              <div className="h-64 w-full flex items-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={customerSegments}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="total_failed_amount"
                      nameKey="segment"
                    >
                      {customerSegments.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={SEGMENT_COLORS[index % SEGMENT_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                      formatter={(val: any, name: any) => [`₹${Number(val).toLocaleString('en-IN')}`, name]}
                    />
                    <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* AI Strategy Performance Matrix */}
          <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-brand-cyan" />
                  AI Recovery Strategy Efficacy Matrix
                </h3>
                <p className="text-xs text-slate-400">
                  Performance across autonomous decision pathways and recovery values
                </p>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {strategies.length} Tracked Strategies
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-dark-800 text-slate-400 border-b border-dark-700">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Strategy</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Attempts</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Recovered Count</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Recovered Amount</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Success Rate</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Avg Probability</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {strategies.map((strat) => (
                    <tr key={strat.strategy} className="hover:bg-dark-800/50 transition">
                      <td className="py-3 px-3">
                        <span className="font-mono font-semibold text-slate-200">
                          {strat.strategy.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">
                        {strat.attempts}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-300">
                        {strat.recovered}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-brand-emerald font-bold">
                        ₹{(strat.recovered_amount / 1000).toFixed(0)}k
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span className={`font-mono font-bold ${
                          strat.success_rate >= 80
                            ? 'text-emerald-400'
                            : strat.success_rate >= 60
                            ? 'text-brand-cyan'
                            : 'text-amber-400'
                        }`}>
                          {strat.success_rate.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-500">
                        {(strat.avg_recovery_probability * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* High-Probability Recovery Opportunities */}
          {opportunities.length > 0 && (
            <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Target className="w-4 h-4 text-emerald-400" />
                    High-Probability Recovery Opportunities
                  </h3>
                  <p className="text-xs text-slate-400">
                    Highest-scoring unrecovered payments ready for immediate autonomous trigger
                  </p>
                </div>
                <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  {opportunities.length} Immediate Targets
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {opportunities.slice(0, 6).map((opp) => (
                  <div
                    key={opp.payment_id}
                    onClick={() => onSelectPaymentId && onSelectPaymentId(opp.payment_id)}
                    className="p-3 rounded-xl bg-dark-800 border border-dark-700 hover:border-brand-cyan/40 cursor-pointer transition space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white text-xs">{opp.customer_name}</span>
                      <span className="font-mono text-brand-cyan text-xs font-bold">
                        {formatCurrency(opp.amount)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>{(opp.payment_method || 'CARD')} · {(opp.failure_reason || '').replace(/_/g, ' ')}</span>
                      <span className="text-emerald-400 font-mono font-bold">
                        {(opp.recovery_probability * 100).toFixed(0)}% Prob
                      </span>
                    </div>

                    <div className="p-1.5 rounded bg-dark-900 text-[10px] text-slate-300 font-mono truncate">
                      Strategy: {(opp.current_strategy || 'AUTONOMOUS_LINK').replace(/_/g, ' ')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
