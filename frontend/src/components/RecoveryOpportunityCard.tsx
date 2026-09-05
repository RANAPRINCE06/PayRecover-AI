import React from 'react';
import { Target, CheckCircle2, AlertCircle, ArrowRight, Zap, Info } from 'lucide-react';
import { OpportunityScore } from '../types';

interface RecoveryOpportunityCardProps {
  opportunity: OpportunityScore;
  onSelectAction?: (caseId: string, strategy: string) => void;
  onViewExplanation?: (caseId: string) => void;
}

export const RecoveryOpportunityCard: React.FC<RecoveryOpportunityCardProps> = ({
  opportunity,
  onSelectAction,
  onViewExplanation
}) => {
  const formatCurrency = (val: number) => `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30';
    if (score >= 65) return 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30';
    if (score >= 45) return 'text-amber-400 bg-amber-500/15 border-amber-500/30';
    return 'text-rose-400 bg-rose-500/15 border-rose-500/30';
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'HIGH':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      default:
        return 'bg-slate-700/40 text-slate-300 border-slate-600/40';
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 transition-all duration-300 shadow-lg hover:shadow-cyan-500/5 group">
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-slate-400">#{opportunity.case_id.slice(0, 8)}</span>
            <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-md border ${getPriorityBadge(opportunity.priority)}`}>
              {opportunity.priority}
            </span>
            <span className="text-[10px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">
              {opportunity.customer_tier}
            </span>
          </div>
          <h4 className="text-base font-semibold text-white">{opportunity.customer_name}</h4>
          <p className="text-xs text-slate-400">{opportunity.failure_reason || 'Technical drop-off'}</p>
        </div>

        {/* Opportunity Score Meter */}
        <div className="flex flex-col items-end">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border font-mono font-bold text-sm ${getScoreColor(opportunity.score)}`}>
            <Target className="w-4 h-4" />
            <span>{opportunity.score}</span>
            <span className="text-[10px] font-normal opacity-70">/100</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1 font-mono">Opportunity Score</span>
        </div>
      </div>

      {/* Amount & Heuristic Probability */}
      <div className="grid grid-cols-2 gap-2 my-3 p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/60">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-mono">Amount</span>
          <span className="text-base font-bold text-white font-mono">{formatCurrency(opportunity.amount)}</span>
        </div>
        <div>
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
            <span>Heuristic Probability</span>
            <span title="Deterministic estimated probability from multi-factor engine" className="cursor-help">
              <Info className="w-2.5 h-2.5 text-slate-400" />
            </span>
          </div>
          <span className="text-base font-bold text-cyan-400 font-mono">
            {Math.round(opportunity.estimated_recovery_probability * 100)}%
          </span>
        </div>
      </div>

      {/* Key Factors */}
      <div className="space-y-1.5 my-3">
        {opportunity.positive_factors.slice(0, 2).map((factor, idx) => (
          <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <span className="line-clamp-1">{factor}</span>
          </div>
        ))}
        {opportunity.negative_factors.slice(0, 1).map((factor, idx) => (
          <div key={idx} className="flex items-start gap-2 text-xs text-slate-400">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <span className="line-clamp-1">{factor}</span>
          </div>
        ))}
      </div>

      {/* Action Footer */}
      <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2 mt-4">
        {onViewExplanation && (
          <button
            onClick={() => onViewExplanation(opportunity.case_id)}
            className="text-xs text-slate-400 hover:text-cyan-400 transition-colors flex items-center gap-1 font-medium"
          >
            Explain AI Decision
          </button>
        )}
        {onSelectAction && (
          <button
            onClick={() => onSelectAction(opportunity.case_id, opportunity.recommended_strategy)}
            className="px-3 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-cyan-500/20 transition-all ml-auto"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Apply {opportunity.recommended_strategy.replace(/_/g, ' ')}</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  );
};
