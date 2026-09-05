import React, { useEffect, useState } from 'react';
import {
  X,
  Activity,
  CheckCircle2,
  Clock,
  ShieldCheck,
  AlertCircle,
  Wrench,
  Loader2,
  GitCommit,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';
import { AgentTrace } from '../types';

interface AgentTraceViewerProps {
  caseId: string | null;
  onClose: () => void;
}

export const AgentTraceViewer: React.FC<AgentTraceViewerProps> = ({ caseId, onClose }) => {
  const [trace, setTrace] = useState<AgentTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    api.getCaseTrace(caseId)
      .then(res => setTrace(res))
      .catch(err => setError(err.message || 'Failed to load trace'))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (!caseId) return null;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'BLOCKED':
        return <ShieldCheck className="w-4 h-4 text-amber-400" />;
      case 'RUNNING':
        return <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />;
      case 'FAILED':
        return <AlertCircle className="w-4 h-4 text-rose-400" />;
      default:
        return <Clock className="w-4 h-4 text-slate-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'BLOCKED':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'RUNNING':
        return 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30';
      case 'FAILED':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-800/80 flex items-center justify-between sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Multi-Agent Execution Trace</h3>
              <p className="text-xs text-slate-400 font-mono">
                {trace ? `${trace.run_id} • ${trace.completed_steps}/${trace.total_steps} stages • ${trace.total_duration_ms || 0}ms` : `Case #${caseId.slice(0, 8)}`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-850 hover:bg-slate-800 border border-slate-700/60 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 flex-1">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
              <span className="text-sm">Fetching Autonomous Agent Trace...</span>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm">
              {error}
            </div>
          ) : trace ? (
            <>
              {/* Correlation meta row */}
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Req ID: <strong className="text-slate-300">{trace.request_id}</strong></span>
                <span>Corr ID: <strong className="text-slate-300">{trace.correlation_id}</strong></span>
                <span>Status: <strong className="text-cyan-400">{trace.final_status}</strong></span>
              </div>

              {/* Stage Progress Pills */}
              <div className="flex items-center gap-1.5 overflow-x-auto py-2">
                {trace.timeline.map((stage, idx) => {
                  const step = trace.steps.find(s => s.stage_name === stage);
                  const isDone = step && step.status === 'SUCCESS';
                  const isBlocked = step && step.status === 'BLOCKED';

                  return (
                    <React.Fragment key={stage}>
                      <div className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-semibold border flex items-center gap-1 shrink-0 ${
                        isDone ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : (
                          isBlocked ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' : 'bg-slate-800/60 text-slate-500 border-slate-700/60'
                        )
                      }`}>
                        <span>{idx + 1}.</span>
                        <span>{stage}</span>
                      </div>
                      {idx < trace.timeline.length - 1 && (
                        <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>

              {/* Vertical Step Timeline */}
              <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                {trace.steps.map((step) => (
                  <div key={step.step_index} className="relative group">
                    {/* Circle Node */}
                    <div className="absolute -left-6 top-1 w-5 h-5 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center">
                      {getStatusIcon(step.status)}
                    </div>

                    {/* Step Card */}
                    <div className="p-4 bg-slate-950/50 border border-slate-800 rounded-xl space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">{step.stage_name}</span>
                          <span className="text-[10px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded font-mono">
                            {step.agent}
                          </span>
                          {step.tool_used && (
                            <span className="text-[10px] text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20 font-mono flex items-center gap-1">
                              <Wrench className="w-2.5 h-2.5" /> {step.tool_used}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${getStatusBadge(step.status)}`}>
                            {step.status}
                          </span>
                          <span className="text-xs font-mono text-slate-500">{step.duration_ms || 0}ms</span>
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed">
                        {step.summary}
                      </p>

                      {step.output && Object.keys(step.output).length > 0 && (
                        <div className="pt-2 border-t border-slate-850">
                          <div className="text-[10px] font-mono text-slate-400 bg-slate-900 p-2 rounded-lg overflow-x-auto max-h-24">
                            {JSON.stringify(step.output, null, 2)}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800/80 flex justify-end bg-slate-900/90">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
