import React from 'react';
import { AlertTriangle, TrendingUp, ShieldAlert, ArrowUpRight, DollarSign } from 'lucide-react';
import { RevenueAtRisk } from '../types';

interface RevenueRiskCardProps {
  data: RevenueAtRisk | null;
  loading?: boolean;
}

export const RevenueRiskCard: React.FC<RevenueRiskCardProps> = ({ data, loading }) => {
  if (loading || !data) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 animate-pulse">
        <div className="h-4 bg-slate-800 rounded w-1/3 mb-4" />
        <div className="h-8 bg-slate-800 rounded w-1/2 mb-6" />
        <div className="grid grid-cols-2 gap-4">
          <div className="h-16 bg-slate-800/60 rounded-xl" />
          <div className="h-16 bg-slate-800/60 rounded-xl" />
        </div>
      </div>
    );
  }

  const formatCurrency = (val: number) => `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const total = data.total || 1; // avoid division by zero
  const critPct = Math.round((data.critical / total) * 100);
  const highPct = Math.round((data.high / total) * 100);
  const medPct = Math.round((data.medium / total) * 100);
  const lowPct = Math.round((data.low / total) * 100);

  return (
    <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-sm relative overflow-hidden shadow-xl">
      {/* Background ambient glow */}
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-rose-500/15 border border-rose-500/20 flex items-center justify-center text-rose-400">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Revenue at Risk</h3>
            <p className="text-xs text-slate-400">Real-time pipeline exposure across {data.case_count} cases</p>
          </div>
        </div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center gap-1">
          <ShieldAlert className="w-3.5 h-3.5" /> High Priority
        </span>
      </div>

      {/* Hero total metric */}
      <div className="mb-6">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight text-white">{formatCurrency(data.total)}</span>
          <span className="text-xs font-medium text-rose-400 flex items-center">
            <ArrowUpRight className="w-3 h-3" /> Unrecovered
          </span>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          {data.case_count} payment failure drops awaiting or currently in recovery
        </p>
      </div>

      {/* Multi-segment visual risk bar */}
      <div className="mb-5">
        <div className="h-2.5 w-full bg-slate-800/80 rounded-full overflow-hidden flex gap-0.5">
          {critPct > 0 && <div style={{ width: `${critPct}%` }} className="bg-rose-500 transition-all duration-500" title={`Critical: ${formatCurrency(data.critical)}`} />}
          {highPct > 0 && <div style={{ width: `${highPct}%` }} className="bg-amber-500 transition-all duration-500" title={`High: ${formatCurrency(data.high)}`} />}
          {medPct > 0 && <div style={{ width: `${medPct}%` }} className="bg-blue-500 transition-all duration-500" title={`Medium: ${formatCurrency(data.medium)}`} />}
          {lowPct > 0 && <div style={{ width: `${lowPct}%` }} className="bg-emerald-500 transition-all duration-500" title={`Low: ${formatCurrency(data.low)}`} />}
        </div>
        <div className="flex justify-between items-center text-[10px] text-slate-400 mt-1.5 font-mono">
          <span>Critical {critPct}%</span>
          <span>High {highPct}%</span>
          <span>Medium {medPct}%</span>
          <span>Low {lowPct}%</span>
        </div>
      </div>

      {/* Tier breakdown grid */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-950/40 border border-rose-500/20 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs text-rose-400 mb-1">
            <span className="font-medium">Critical Tier</span>
            <span className="text-[10px] bg-rose-500/20 px-1.5 py-0.5 rounded font-mono">{data.critical_count}</span>
          </div>
          <p className="text-base font-bold text-white">{formatCurrency(data.critical)}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">&gt; ₹10k or VIP urgent</p>
        </div>

        <div className="bg-slate-950/40 border border-amber-500/20 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs text-amber-400 mb-1">
            <span className="font-medium">High Tier</span>
            <span className="text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded font-mono">{data.high_count}</span>
          </div>
          <p className="text-base font-bold text-white">{formatCurrency(data.high)}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">₹5k – ₹10k</p>
        </div>

        <div className="bg-slate-950/40 border border-blue-500/20 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs text-blue-400 mb-1">
            <span className="font-medium">Medium Tier</span>
            <span className="text-[10px] bg-blue-500/20 px-1.5 py-0.5 rounded font-mono">{data.medium_count}</span>
          </div>
          <p className="text-base font-bold text-white">{formatCurrency(data.medium)}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">₹1.5k – ₹5k</p>
        </div>

        <div className="bg-slate-950/40 border border-emerald-500/20 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs text-emerald-400 mb-1">
            <span className="font-medium">Low Tier</span>
            <span className="text-[10px] bg-emerald-500/20 px-1.5 py-0.5 rounded font-mono">{data.low_count}</span>
          </div>
          <p className="text-base font-bold text-white">{formatCurrency(data.low)}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">&lt; ₹1.5k</p>
        </div>
      </div>
    </div>
  );
};
