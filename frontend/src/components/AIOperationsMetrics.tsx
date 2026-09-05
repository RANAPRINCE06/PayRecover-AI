import React, { useEffect, useState } from 'react';
import { Bot, Zap, Clock, ShieldAlert, CheckCircle2, Cpu } from 'lucide-react';
import { api } from '../services/api';
import { AIOperationsMetrics as AIOpsType } from '../types';

export const AIOperationsMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<AIOpsType | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = () => {
    api.getAIOperationsMetrics()
      .then(data => setMetrics(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 20000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !metrics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 animate-pulse">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-20 bg-slate-900/60 rounded-xl border border-slate-800" />
        ))}
      </div>
    );
  }

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-400" />
          <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">AI Autonomous Operations Telemetry</h4>
        </div>
        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" /> Live Telemetry
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {/* Decisions Count */}
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>AI Decisions</span>
            <Bot className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <span className="text-lg font-bold text-white font-mono">
            {metrics?.ai_decisions_count ?? 0}
          </span>
          <p className="text-[10px] text-slate-400 mt-0.5">Autonomous evaluations</p>
        </div>

        {/* AI Success Rate */}
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>AI Success Rate</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <span className="text-lg font-bold text-emerald-400 font-mono">
            {metrics?.ai_success_rate ?? 0}%
          </span>
          <p className="text-[10px] text-slate-400 mt-0.5">Recovered vs total</p>
        </div>

        {/* Average Latency */}
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>Average Latency</span>
            <Clock className="w-3.5 h-3.5 text-blue-400" />
          </div>
          <span className="text-lg font-bold text-white font-mono">
            {metrics?.average_ai_latency_ms ?? 0}ms
          </span>
          <p className="text-[10px] text-slate-400 mt-0.5">Per multi-agent run</p>
        </div>

        {/* Escalation Rate */}
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>Human Escalation</span>
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <span className="text-lg font-bold text-amber-400 font-mono">
            {metrics?.human_escalation_rate ?? 0}%
          </span>
          <p className="text-[10px] text-slate-400 mt-0.5">Guardrail review rate</p>
        </div>

        {/* Tool Success Rate */}
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>Tool Success</span>
            <Zap className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <span className="text-lg font-bold text-white font-mono">
            {metrics?.tool_success_rate ?? 100}%
          </span>
          <p className="text-[10px] text-slate-400 mt-0.5">Execution reliability</p>
        </div>
      </div>
    </div>
  );
};
