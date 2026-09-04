import React, { useState } from 'react';
import { Bot, Shield, CheckCircle, Clock, Zap, Filter, Search } from 'lucide-react';
import { AgentAction } from '../types';
import { StatusBadge } from '../components/StatusBadge';

interface AgentActivityPageProps {
  actions: AgentAction[];
}

export const AgentActivityPage: React.FC<AgentActivityPageProps> = ({ actions }) => {
  const [filterType, setFilterType] = useState('ALL');

  const filtered = actions.filter((a) => {
    if (filterType === 'ALL') return true;
    return a.agent_type === filterType;
  });

  const getAgentColor = (type: string) => {
    switch (type) {
      case 'INVESTIGATOR':
        return 'text-brand-cyan bg-brand-cyan/10 border-brand-cyan/30';
      case 'STRATEGIST':
        return 'text-brand-indigo bg-brand-indigo/10 border-brand-indigo/30';
      case 'INTENT_AI':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'TOOL_EXECUTOR':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      default:
        return 'text-slate-400 bg-dark-700 border-dark-600';
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-brand-cyan" />
            AI Multi-Agent Activity & Audit Trail
          </h2>
          <p className="text-xs text-slate-400">
            Real-time chronological timeline of Investigator, Intent AI, Strategist, and Guardrail Tool Executions.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-2">
          {['ALL', 'INVESTIGATOR', 'STRATEGIST', 'INTENT_AI', 'TOOL_EXECUTOR'].map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                filterType === t
                  ? 'bg-brand-cyan text-dark-900 font-bold shadow-glow-cyan'
                  : 'bg-dark-800 hover:bg-dark-750 text-slate-400 border border-dark-700'
              }`}
            >
              {t.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Activity Timeline */}
      <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700">
        <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-dark-700">
          {filtered.map((action, idx) => (
            <div key={action.id || idx} className="relative group">
              {/* Timeline marker node */}
              <div className="absolute -left-[27px] top-1.5 w-3.5 h-3.5 rounded-full bg-dark-900 border-2 border-brand-cyan group-hover:scale-125 transition shadow-glow-cyan" />

              {/* Action Card */}
              <div className="p-4 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 transition space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getAgentColor(action.agent_type)}`}>
                      {action.agent_type}
                    </span>
                    <span className="text-xs font-bold text-slate-200">
                      {action.action_type.replace(/_/g, ' ')}
                    </span>
                    <StatusBadge status={action.status} />
                  </div>

                  <div className="flex items-center gap-1 text-[11px] text-slate-500 font-mono">
                    <Clock className="w-3.5 h-3.5" />
                    {new Date(action.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed font-sans">
                  {action.reasoning_summary}
                </p>

                {action.action_metadata && (
                  <div className="mt-2 p-2 rounded bg-dark-900 text-[10px] font-mono text-slate-400 max-h-20 overflow-y-auto">
                    {action.action_metadata}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
