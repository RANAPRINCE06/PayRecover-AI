import React, { useState, useMemo } from 'react';
import {
  Bot,
  Shield,
  CheckCircle,
  Clock,
  Zap,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  BrainCircuit,
  Terminal,
  RefreshCw
} from 'lucide-react';
import { AgentAction } from '../types';
import { StatusBadge } from '../components/StatusBadge';

interface AgentActivityPageProps {
  actions: AgentAction[];
  onRefresh?: () => void;
}

export const AgentActivityPage: React.FC<AgentActivityPageProps> = ({ actions, onRefresh }) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedActionId, setExpandedActionId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return actions.filter((a) => {
      const matchType = filterType === 'ALL' || a.agent_type === filterType;
      const matchSearch =
        !searchQuery ||
        a.reasoning_summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.action_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (a.recovery_case_id && a.recovery_case_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (a.action_metadata && a.action_metadata.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchType && matchSearch;
    });
  }, [actions, filterType, searchQuery]);

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

  const getAgentIcon = (type: string) => {
    switch (type) {
      case 'INVESTIGATOR':
        return <Search className="w-3.5 h-3.5 text-brand-cyan" />;
      case 'STRATEGIST':
        return <BrainCircuit className="w-3.5 h-3.5 text-brand-indigo" />;
      case 'INTENT_AI':
        return <Bot className="w-3.5 h-3.5 text-amber-400" />;
      case 'TOOL_EXECUTOR':
        return <Zap className="w-3.5 h-3.5 text-emerald-400" />;
      default:
        return <Terminal className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-brand-cyan" />
            AI Multi-Agent Activity & Audit Trail 2.0
          </h2>
          <p className="text-xs text-slate-400">
            Real-time chronological timeline of Investigator, Intent AI, Strategist, and Guardrail Tool Executions.
          </p>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            className="self-start sm:self-auto px-3 py-1.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 transition flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh Trail
          </button>
        )}
      </div>

      {/* Controls: Search and Filters */}
      <div className="p-4 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search action reasoning, case ID, tool..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-dark-800 border border-dark-700 rounded-xl pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-cyan transition"
          />
        </div>

        {/* Filter buttons */}
        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          {['ALL', 'INVESTIGATOR', 'INTENT_AI', 'STRATEGIST', 'TOOL_EXECUTOR'].map((t) => (
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
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-semibold text-slate-400">
            Showing <span className="text-white font-bold">{filtered.length}</span> recorded agent actions
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No agent activities found matching current search/filter criteria.
          </div>
        ) : (
          <div className="relative pl-6 space-y-5 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-dark-700">
            {filtered.map((action, idx) => {
              const isExpanded = expandedActionId === (action.id || `idx-${idx}`);
              return (
                <div key={action.id || idx} className="relative group">
                  {/* Timeline marker node */}
                  <div className="absolute -left-[27px] top-2 w-3.5 h-3.5 rounded-full bg-dark-900 border-2 border-brand-cyan group-hover:scale-125 transition shadow-glow-cyan flex items-center justify-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan" />
                  </div>

                  {/* Action Card */}
                  <div className="p-4 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 transition space-y-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="p-1 rounded bg-dark-900 border border-dark-700">
                          {getAgentIcon(action.agent_type)}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getAgentColor(action.agent_type)}`}>
                          {action.agent_type}
                        </span>
                        <span className="text-xs font-bold text-slate-200 font-mono">
                          {action.action_type.replace(/_/g, ' ')}
                        </span>
                        <StatusBadge status={action.status} />
                      </div>

                      <div className="flex items-center gap-3">
                        {action.recovery_case_id && (
                          <span className="text-[10px] font-mono text-slate-500 bg-dark-900 px-2 py-0.5 rounded border border-dark-700">
                            {action.recovery_case_id}
                          </span>
                        )}
                        <div className="flex items-center gap-1 text-[11px] text-slate-500 font-mono">
                          <Clock className="w-3.5 h-3.5" />
                          {new Date(action.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                          })}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed font-sans">
                      {action.reasoning_summary}
                    </p>

                    {action.action_metadata && (
                      <div>
                        <button
                          onClick={() =>
                            setExpandedActionId(isExpanded ? null : action.id || `idx-${idx}`)
                          }
                          className="text-[10px] font-mono text-brand-cyan hover:underline flex items-center gap-1 mt-1"
                        >
                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          {isExpanded ? 'Hide Raw Metadata Payload' : 'View Raw Metadata Payload'}
                        </button>

                        {isExpanded && (
                          <pre className="mt-2 p-3 rounded-lg bg-dark-900 text-[10px] font-mono text-slate-400 overflow-x-auto border border-dark-700/60 max-h-48">
                            {typeof action.action_metadata === 'string'
                              ? (() => {
                                  try {
                                    return JSON.stringify(JSON.parse(action.action_metadata), null, 2);
                                  } catch {
                                    return action.action_metadata;
                                  }
                                })()
                              : JSON.stringify(action.action_metadata, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
