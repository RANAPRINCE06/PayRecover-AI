import React, { useEffect, useState } from 'react';
import {
  X,
  FileText,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  User,
  ArrowRight,
  Sparkles,
  Loader2
} from 'lucide-react';
import { api } from '../services/api';
import { DecisionExplanation } from '../types';

interface DecisionExplanationModalProps {
  caseId: string | null;
  onClose: () => void;
}

export const DecisionExplanationModal: React.FC<DecisionExplanationModalProps> = ({
  caseId,
  onClose
}) => {
  const [data, setData] = useState<DecisionExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    api.getDecisionExplanation(caseId)
      .then(res => setData(res))
      .catch(err => setError(err.message || 'Failed to load explanation'))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (!caseId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-800/80 flex items-center justify-between sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">AI Decision Explanation</h3>
              <p className="text-xs text-slate-400 font-mono">Case #{caseId.slice(0, 10)} • Audit Trail & Evidence</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-850 hover:bg-slate-800 border border-slate-700/60 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6 flex-1">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
              <span className="text-sm">Synthesizing AI Decision Rationale...</span>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm">
              {error}
            </div>
          ) : data ? (
            <>
              {/* Decision Hero Banner */}
              <div className="p-4 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-blue-950/40 border border-cyan-500/30 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block">Proposed Decision</span>
                  <h4 className="text-base font-bold text-white mt-0.5">{data.decision.replace(/_/g, ' ')}</h4>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <span className="text-[10px] text-slate-400 block font-mono">Confidence</span>
                    <span className="text-xs font-bold text-emerald-400 font-mono">{Math.round(data.confidence * 100)}% ({data.confidence_level})</span>
                  </div>
                  <div className="w-10 h-10 rounded-full border-2 border-emerald-500/40 flex items-center justify-center text-emerald-400 font-mono text-xs font-bold">
                    {Math.round(data.confidence * 100)}
                  </div>
                </div>
              </div>

              {/* Rationale */}
              <div>
                <h5 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Decision Rationale</h5>
                <p className="text-sm text-slate-200 bg-slate-950/50 p-3.5 rounded-xl border border-slate-800 leading-relaxed">
                  {data.reason}
                </p>
              </div>

              {/* Observable Evidence */}
              <div>
                <h5 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Observable Evidence</h5>
                <div className="space-y-2">
                  {data.evidence.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-slate-300 bg-slate-950/30 p-2.5 rounded-lg border border-slate-850">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Customer Context & Risk Factors */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-3.5">
                  <h6 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-cyan-400" /> Customer Context
                  </h6>
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>Tier:</span>
                      <span className="text-white font-medium">{data.customer_context.tier || 'STANDARD'}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Prior Successful:</span>
                      <span className="text-emerald-400 font-mono">{data.customer_context.prior_successful || 0} orders</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Preferred Channel:</span>
                      <span className="text-cyan-400 font-medium">{data.customer_context.preferred_method || 'UPI'}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-3.5">
                  <h6 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Risk Factors
                  </h6>
                  <div className="space-y-1.5">
                    {data.risk_factors.slice(0, 3).map((r, i) => (
                      <p key={i} className="text-xs text-slate-400 leading-snug line-clamp-2">
                        • {r}
                      </p>
                    ))}
                  </div>
                </div>
              </div>

              {/* Guardrails Check */}
              <div className="p-3.5 bg-slate-950/40 border border-slate-800 rounded-xl">
                <h6 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" /> Merchant Policy & Guardrails
                </h6>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    Policy Status: <strong className={data.guardrail_result.requires_human_approval ? 'text-amber-400' : 'text-emerald-400'}>
                      {data.guardrail_result.guardrail_status}
                    </strong>
                  </span>
                  <span className="text-slate-500 font-mono">
                    High-Value Threshold: ₹{data.guardrail_result.high_value_threshold?.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              {/* Recommended Next Step */}
              <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl flex items-center gap-2.5 text-xs text-cyan-300">
                <ArrowRight className="w-4 h-4 shrink-0 text-cyan-400" />
                <span><strong>Recommended Action:</strong> {data.recommended_next_step}</span>
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
