import React from 'react';
import {
  Search,
  Brain,
  Target,
  ShieldCheck,
  Zap,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Loader2,
  ExternalLink,
  IndianRupee,
  ChevronRight,
  UserCheck,
  Shield
} from 'lucide-react';
import { AutonomousRecoveryResult, AutonomousPipelineStep } from '../types';

// ─── Stage metadata ──────────────────────────────────────────────────────────

interface StageMetadata {
  label: string;
  icon: React.FC<any>;
  color: string;
  bgColor: string;
  borderColor: string;
  agentLabel: string;
}

const STAGE_META: Record<string, StageMetadata> = {
  INVESTIGATE: {
    label: 'Investigate',
    icon: Search,
    color: 'text-brand-cyan',
    bgColor: 'bg-brand-cyan/10',
    borderColor: 'border-brand-cyan/30',
    agentLabel: 'Payment Investigator AI'
  },
  INTENT: {
    label: 'Detect Intent',
    icon: Brain,
    color: 'text-violet-400',
    bgColor: 'bg-violet-500/10',
    borderColor: 'border-violet-500/30',
    agentLabel: 'Customer Intent AI'
  },
  STRATEGY: {
    label: 'Select Strategy',
    icon: Target,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    agentLabel: 'Recovery Strategist AI'
  },
  GUARDRAIL: {
    label: 'Guardrail Gate',
    icon: Shield,
    color: 'text-rose-400',
    bgColor: 'bg-rose-500/10',
    borderColor: 'border-rose-500/30',
    agentLabel: 'Deterministic Guardrail Engine'
  },
  EXECUTE: {
    label: 'Execute Tool',
    icon: Zap,
    color: 'text-brand-emerald',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    agentLabel: 'Allowlisted Tool Executor'
  },
  SETTLE: {
    label: 'Settle',
    icon: CheckCircle2,
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    borderColor: 'border-indigo-500/30',
    agentLabel: 'Orchestrator'
  }
};

// ─── Status helpers ──────────────────────────────────────────────────────────

function StepStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'SUCCESS':
      return <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
    case 'FAILED':
      return <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />;
    case 'BLOCKED':
      return <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />;
    case 'RUNNING':
      return <Loader2 className="w-4 h-4 text-brand-cyan flex-shrink-0 animate-spin" />;
    case 'SKIPPED':
      return <Clock className="w-4 h-4 text-slate-500 flex-shrink-0" />;
    default:
      return <Clock className="w-4 h-4 text-slate-600 flex-shrink-0" />;
  }
}

function StepStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    SUCCESS: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
    FAILED: 'bg-rose-500/15 text-rose-400 border-rose-500/25',
    BLOCKED: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
    RUNNING: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/25',
    SKIPPED: 'bg-slate-700/40 text-slate-500 border-slate-600/25',
    PENDING: 'bg-slate-700/40 text-slate-600 border-slate-600/20',
  };
  return (
    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${map[status] || 'bg-slate-700/40 text-slate-500 border-slate-600'}`}>
      {status}
    </span>
  );
}

function FinalStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    RECOVERED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    AWAITING_HUMAN_APPROVAL: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    IN_PROGRESS: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    BLOCKED: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    FAILED: 'bg-rose-700/20 text-rose-400 border-rose-700/30',
  };
  const labels: Record<string, string> = {
    RECOVERED: '✅ Recovered',
    AWAITING_HUMAN_APPROVAL: '⏳ Awaiting Approval',
    IN_PROGRESS: '⚡ In Progress',
    BLOCKED: '🛡 Guardrail Blocked',
    FAILED: '❌ Failed',
  };
  return (
    <span className={`text-xs font-bold px-3 py-1 rounded-lg border ${map[status] || 'bg-slate-700 text-slate-400 border-slate-600'}`}>
      {labels[status] || status}
    </span>
  );
}

// ─── Single pipeline step card ───────────────────────────────────────────────

function PipelineStepCard({ step, isLast }: { step: AutonomousPipelineStep; isLast: boolean }) {
  const meta = STAGE_META[step.stage_name] || {
    label: step.stage_name,
    icon: Zap,
    color: 'text-slate-400',
    bgColor: 'bg-slate-800',
    borderColor: 'border-slate-700',
    agentLabel: step.agent
  };
  const Icon = meta.icon;

  return (
    <div className="flex gap-3">
      {/* Left rail */}
      <div className="flex flex-col items-center flex-shrink-0" style={{ minWidth: 32 }}>
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center border ${meta.bgColor} ${meta.borderColor}`}>
          <Icon className={`w-4 h-4 ${meta.color}`} />
        </div>
        {!isLast && <div className="w-px flex-1 mt-1 bg-dark-700" style={{ minHeight: 16 }} />}
      </div>

      {/* Content */}
      <div className={`flex-1 mb-3 p-3 rounded-xl border ${meta.bgColor} ${meta.borderColor} bg-opacity-30`}>
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <StepStatusIcon status={step.status} />
            <span className="text-xs font-bold text-white">{meta.label}</span>
            <StepStatusBadge status={step.status} />
          </div>
          {step.duration_ms != null && (
            <span className="text-[10px] font-mono text-slate-500">{step.duration_ms}ms</span>
          )}
        </div>
        <div className="text-[11px] text-slate-300 leading-relaxed mb-1.5">{step.summary}</div>
        {/* Agent badge */}
        <div className="text-[9px] text-slate-500 font-mono">{meta.agentLabel}</div>

        {/* Guardrail constraints */}
        {step.guardrail_constraints.length > 0 && (
          <div className="mt-2 space-y-1">
            {step.guardrail_constraints.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px] text-amber-400 font-mono">
                <ShieldCheck className="w-3 h-3 flex-shrink-0" />
                {c}
              </div>
            ))}
          </div>
        )}

        {/* Key output fields */}
        {step.output && step.stage_name === 'INVESTIGATE' && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {step.output.recovery_score != null && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 font-mono">
                Score {step.output.recovery_score}/100
              </span>
            )}
            {step.output.failure_category && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-400 border border-dark-600">
                {step.output.failure_category}
              </span>
            )}
            {step.output.risk_level && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-400 border border-dark-600">
                {step.output.risk_level} RISK
              </span>
            )}
          </div>
        )}

        {step.output && step.stage_name === 'INTENT' && step.output.intent && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 font-mono">
              {step.output.intent}
            </span>
            {step.output.sentiment && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-400 border border-dark-600">
                {step.output.sentiment}
              </span>
            )}
          </div>
        )}

        {step.output && step.stage_name === 'STRATEGY' && step.output.strategy && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
              {step.output.strategy}
            </span>
            {step.output.recommended_channel && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-700 text-slate-400 border border-dark-600">
                via {step.output.recommended_channel}
              </span>
            )}
          </div>
        )}

        {step.output && step.stage_name === 'EXECUTE' && step.output.payment_link_url && (
          <a
            href={step.output.payment_link_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1 text-[10px] text-brand-cyan hover:text-brand-cyan/80 font-mono"
          >
            <ExternalLink className="w-3 h-3" />
            {step.output.payment_link_url}
          </a>
        )}
      </div>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

interface AutonomousPipelinePanelProps {
  result: AutonomousRecoveryResult;
  isLoading?: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  onConfirmSettlement?: () => void;
}

export const AutonomousPipelinePanel: React.FC<AutonomousPipelinePanelProps> = ({
  result,
  isLoading = false,
  onApprove,
  onReject,
  onConfirmSettlement
}) => {
  const isApprovalPending = result.final_status === 'AWAITING_HUMAN_APPROVAL' || result.requires_human_approval;
  const isRecovered = result.final_status === 'RECOVERED';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-brand-cyan/10 via-dark-800 to-dark-800 border border-brand-cyan/25 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {isLoading ? (
            <Loader2 className="w-5 h-5 text-brand-cyan animate-spin flex-shrink-0" />
          ) : (
            <Zap className="w-5 h-5 text-brand-cyan flex-shrink-0" />
          )}
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              Autonomous Recovery Pipeline
              {isLoading && (
                <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 animate-pulse">
                  RUNNING
                </span>
              )}
              {!isLoading && <FinalStatusBadge status={result.final_status} />}
            </div>
            <div className="text-[10px] text-slate-400 font-mono mt-0.5">
              Run ID: {result.run_id}
              {result.total_duration_ms != null && ` · ${result.total_duration_ms}ms total`}
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-base font-black font-mono text-white">
            ₹{result.amount.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400">
            {result.completed_steps}/{result.total_steps} stages
          </div>
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="p-4 rounded-2xl bg-dark-850 border border-dark-700">
        <h4 className="text-xs font-bold text-slate-300 mb-4 uppercase tracking-wider">Pipeline Execution</h4>
        {result.steps.length === 0 && isLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin text-brand-cyan" />
            Initialising autonomous pipeline...
          </div>
        ) : (
          <div>
            {result.steps.map((step, idx) => (
              <PipelineStepCard
                key={`${step.stage_name}-${step.step_index}`}
                step={step}
                isLast={idx === result.steps.length - 1}
              />
            ))}
          </div>
        )}
      </div>

      {/* Executive Summary */}
      {result.executive_summary && (
        <div className="p-4 rounded-2xl bg-dark-850 border border-dark-700">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Executive Summary</h4>
          <p className="text-xs text-slate-200 leading-relaxed">{result.executive_summary}</p>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="p-2 rounded-lg bg-dark-800 border border-dark-700">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">Recovery Score</div>
              <div className="text-sm font-black font-mono text-brand-cyan">{result.recovery_score}/100</div>
            </div>
            <div className="p-2 rounded-lg bg-dark-800 border border-dark-700">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">Probability</div>
              <div className="text-sm font-black font-mono text-emerald-400">{Math.round(result.recovery_probability * 100)}%</div>
            </div>
            {result.strategy_selected && (
              <div className="p-2 rounded-lg bg-dark-800 border border-dark-700 col-span-2">
                <div className="text-[9px] text-slate-500 uppercase tracking-wider">Strategy Selected</div>
                <div className="text-xs font-bold text-amber-400 font-mono">{result.strategy_selected}</div>
              </div>
            )}
            {result.tool_executed && (
              <div className="p-2 rounded-lg bg-dark-800 border border-dark-700 col-span-2">
                <div className="text-[9px] text-slate-500 uppercase tracking-wider">Tool Executed</div>
                <div className="text-xs font-bold text-emerald-400 font-mono">{result.tool_executed}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Payment Link */}
      {result.payment_link_url && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold">Payment Link Generated</div>
            <div className="text-xs font-mono text-emerald-300 truncate max-w-xs">{result.payment_link_url}</div>
          </div>
          <a
            href={result.payment_link_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Open
          </a>
        </div>
      )}

      {/* Guardrail Constraints */}
      {result.guardrail_status !== 'SAFE' && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 space-y-1.5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold text-amber-400">Guardrail: {result.guardrail_status}</span>
          </div>
          {(result as any).guardrail_constraints?.map((c: string, i: number) => (
            <div key={i} className="text-[11px] text-amber-300 font-mono">• {c}</div>
          ))}
        </div>
      )}

      {/* Human Approval Actions */}
      {isApprovalPending && !isRecovered && onApprove && onReject && (
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/25 space-y-3">
          <div className="flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold text-amber-300">Merchant Approval Required</span>
          </div>
          <p className="text-[11px] text-amber-200 leading-relaxed">
            This recovery action requires explicit merchant approval before execution. Review and approve or reject below.
          </p>
          <div className="flex gap-2">
            <button
              onClick={onApprove}
              className="flex-1 py-2 text-xs font-bold rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition"
            >
              ✅ Approve Recovery
            </button>
            <button
              onClick={onReject}
              className="flex-1 py-2 text-xs font-bold rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 transition"
            >
              ✗ Reject
            </button>
          </div>
        </div>
      )}

      {/* Confirm Settlement (after link is sent) */}
      {result.final_status === 'IN_PROGRESS' && result.payment_link_url && onConfirmSettlement && (
        <button
          onClick={onConfirmSettlement}
          className="w-full py-2.5 text-xs font-bold rounded-lg bg-gradient-to-r from-emerald-500 to-brand-cyan text-dark-900 hover:opacity-90 transition flex items-center justify-center gap-2"
        >
          <IndianRupee className="w-3.5 h-3.5" />
          Simulate Payment Completion
        </button>
      )}

      {/* Success state */}
      {isRecovered && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-center">
          <div className="text-lg font-black text-emerald-400">
            ₹{result.amount.toLocaleString()} Recovered!
          </div>
          <div className="text-[11px] text-emerald-300 mt-0.5">
            Revenue successfully recovered via autonomous pipeline.
          </div>
        </div>
      )}
    </div>
  );
};
