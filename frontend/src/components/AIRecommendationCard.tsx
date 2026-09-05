import React from 'react';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Clock,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  FileText,
  Activity
} from 'lucide-react';
import { AIRecommendation } from '../types';
import { useAuth } from '../context/AuthContext';

interface AIRecommendationCardProps {
  recommendation: AIRecommendation;
  rank: number;
  onExecute: (rec: AIRecommendation) => void;
  onViewExplanation: (caseId: string) => void;
  onViewTrace: (caseId: string) => void;
  isExecuting?: boolean;
}

export const AIRecommendationCard: React.FC<AIRecommendationCardProps> = ({
  recommendation,
  rank,
  onExecute,
  onViewExplanation,
  onViewTrace,
  isExecuting
}) => {
  const { canExecuteRecovery } = useAuth();
  const formatCurrency = (val: number) => `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const getConfidenceBadge = (level: string, score: number) => {
    if (level === 'HIGH') {
      return (
        <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
          <CheckCircle className="w-3 h-3" /> {Math.round(score * 100)}% High Conf
        </span>
      );
    }
    if (level === 'MEDIUM') {
      return (
        <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1">
          <Clock className="w-3 h-3" /> {Math.round(score * 100)}% Med Conf
        </span>
      );
    }
    return (
      <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" /> {Math.round(score * 100)}% Low Conf
      </span>
    );
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800/90 hover:border-slate-700/80 rounded-2xl p-5 transition-all duration-200 shadow-md hover:shadow-cyan-500/5">
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-full bg-gradient-to-tr from-cyan-500/30 to-blue-500/30 border border-cyan-500/40 text-cyan-300 font-mono text-xs font-bold flex items-center justify-center">
            {rank}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-white">{recommendation.customer_name}</h4>
              <span className="text-[10px] font-mono text-slate-400">#{recommendation.case_id.slice(0, 8)}</span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
              <span>{recommendation.failure_reason}</span>
              <span>•</span>
              <span className="text-cyan-400 font-medium">{recommendation.intent || 'WILL_PAY_LATER'}</span>
            </p>
          </div>
        </div>

        {getConfidenceBadge(recommendation.confidence_level, recommendation.confidence)}
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-3 gap-2 my-3 p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/70">
        <div>
          <span className="text-[10px] uppercase font-mono text-slate-400 block">Amount</span>
          <span className="text-sm font-bold text-white font-mono">{formatCurrency(recommendation.amount)}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-mono text-slate-400 block">Expected Rec.</span>
          <span className="text-sm font-bold text-emerald-400 font-mono">{formatCurrency(recommendation.expected_recovery)}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-mono text-slate-400 block">Opportunity</span>
          <span className="text-sm font-bold text-cyan-400 font-mono">{recommendation.opportunity_score}/100</span>
        </div>
      </div>

      {/* Recommended Strategy Preview */}
      <div className="flex items-center justify-between py-2 px-3 bg-slate-800/40 rounded-xl border border-slate-700/40 mb-4 text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>Strategy: <strong className="text-white">{recommendation.recommended_strategy.replace(/_/g, ' ')}</strong></span>
        </div>
        {recommendation.requires_human_approval ? (
          <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 font-medium">
            Approval Needed
          </span>
        ) : (
          <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-medium flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" /> Auto-Safe
          </span>
        )}
      </div>

      {/* Action and Inspection Toolbar */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800/80">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewExplanation(recommendation.case_id)}
            className="text-xs text-slate-400 hover:text-cyan-400 transition-colors flex items-center gap-1 font-medium p-1 rounded"
            title="Explain AI Decision Rationale"
          >
            <FileText className="w-3.5 h-3.5" /> Explain
          </button>
          <button
            onClick={() => onViewTrace(recommendation.case_id)}
            className="text-xs text-slate-400 hover:text-cyan-400 transition-colors flex items-center gap-1 font-medium p-1 rounded"
            title="View Multi-Agent Trace"
          >
            <Activity className="w-3.5 h-3.5" /> Trace
          </button>
        </div>

        <button
          onClick={() => onExecute(recommendation)}
          disabled={!canExecuteRecovery || isExecuting}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
            recommendation.requires_human_approval
              ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-md shadow-amber-600/20'
              : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-600/20'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <span>{recommendation.requires_human_approval ? 'Review & Approve' : 'Execute Action'}</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
