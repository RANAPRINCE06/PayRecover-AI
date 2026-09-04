import React, { useState, useEffect } from 'react';
import {
  X,
  Bot,
  Shield,
  CheckCircle,
  ExternalLink,
  RefreshCw,
  Sparkles,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  ShieldAlert,
  HelpCircle,
  Loader2
} from 'lucide-react';
import { Payment, RecoveryCase, PaymentInvestigationResult } from '../types';
import { StatusBadge } from './StatusBadge';
import { RecoveryScore } from './RecoveryScore';
import { api } from '../services/api';

interface PaymentDetailModalProps {
  payment: Payment | null;
  onClose: () => void;
  onRefresh: () => void;
}

export const PaymentDetailModal: React.FC<PaymentDetailModalProps> = ({ payment, onClose, onRefresh }) => {
  const [recoveryCase, setRecoveryCase] = useState<RecoveryCase | null>(null);
  const [investigation, setInvestigation] = useState<PaymentInvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState<string | null>(null);

  const loadCaseData = () => {
    if (!payment) return;
    setLoading(true);
    api.getRecoveryCases()
      .then((cases) => {
        const matching = cases.find((c) => c.payment_id === payment.id);
        setRecoveryCase(matching || null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setInvestigation(null);
    setInvestigationError(null);
    loadCaseData();
  }, [payment]);

  if (!payment) return null;

  const handleAnalyzeWithAI = async () => {
    if (!payment) return;
    setInvestigating(true);
    setInvestigationError(null);
    try {
      const result: PaymentInvestigationResult = await api.analyzePayment(payment.id);
      setInvestigation(result);
      loadCaseData();
      onRefresh();
    } catch (err: any) {
      setInvestigationError(err.message || 'Investigation failed');
    } finally {
      setInvestigating(false);
    }
  };

  const handleExecute = async () => {
    if (!recoveryCase) return;
    setActionLoading(true);
    try {
      await api.executeRecovery(recoveryCase.id);
      const updated = await api.getRecoveryCase(recoveryCase.id);
      setRecoveryCase(updated);
      onRefresh();
    } catch (err) {
      alert(`Execution failed: ${err}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSettlement = async () => {
    if (!recoveryCase) return;
    setActionLoading(true);
    try {
      await api.confirmSettlement(recoveryCase.id);
      const updated = await api.getRecoveryCase(recoveryCase.id);
      setRecoveryCase(updated);
      onRefresh();
    } catch (err) {
      alert(`Settlement confirmation failed: ${err}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!recoveryCase) return;
    setActionLoading(true);
    try {
      await api.approveCase(recoveryCase.id);
      const updated = await api.getRecoveryCase(recoveryCase.id);
      setRecoveryCase(updated);
      onRefresh();
    } catch (err) {
      alert(`Approve failed: ${err}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-3xl bg-dark-850 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-dark-700 flex items-center justify-between bg-dark-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan font-bold font-mono text-sm">
              ₹
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white">Payment #{payment.razorpay_payment_id}</h3>
                <StatusBadge status={payment.status} />
              </div>
              <p className="text-xs text-slate-400">Created {new Date(payment.created_at).toLocaleString()}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-dark-700 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-dark-800 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Amount</span>
              <div className="text-xl font-bold font-mono text-white mt-1">₹{payment.amount.toLocaleString()}</div>
              <span className="text-[10px] text-slate-500">Method: {payment.payment_method}</span>
            </div>

            <div className="p-4 rounded-xl bg-dark-800 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Recovery Score</span>
              <div className="mt-1 flex items-center gap-2">
                <RecoveryScore score={investigation?.recovery_score || recoveryCase?.recovery_score || 85} size="lg" />
                <span className="text-xs text-emerald-400 font-semibold">
                  {investigation ? `${investigation.risk_level} Risk` : 'High Potential'}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-dark-800 border border-dark-700">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Customer Intent</span>
              <div className="mt-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
                  {recoveryCase?.customer_intent || 'ALTERNATE_PAYMENT_METHOD'}
                </span>
              </div>
            </div>
          </div>

          {/* Customer & Failure Context */}
          <div className="p-4 rounded-xl bg-dark-800 border border-dark-700 space-y-3">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Customer & Gateway Telemetry</h4>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400">Customer:</span>{' '}
                <strong className="text-slate-200">{payment.customer?.name || 'Customer'}</strong> ({payment.customer?.customer_value || 'VIP'})
              </div>
              <div>
                <span className="text-slate-400">Email:</span>{' '}
                <span className="text-slate-200 font-mono">{payment.customer?.email || 'customer@example.com'}</span>
              </div>
              <div>
                <span className="text-slate-400">Failure Reason:</span>{' '}
                <strong className="text-rose-400 font-mono">{payment.failure_reason || 'CARD_DECLINED'}</strong>
              </div>
              <div>
                <span className="text-slate-400">Past Success Rate:</span>{' '}
                <span className="text-emerald-400 font-semibold">
                  {payment.customer?.total_successful_payments || 10} / {(payment.customer?.total_successful_payments || 10) + (payment.customer?.total_failed_payments || 1)} orders
                </span>
              </div>
            </div>
          </div>

          {/* AI Payment Investigator Section */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-dark-800 via-dark-750 to-dark-800 border border-brand-cyan/30 shadow-glow-cyan/10 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-center text-brand-cyan">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    AI Payment Investigation
                    <span className="text-[10px] font-mono px-1.5 py-0.2 bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 rounded">
                      Structured Output
                    </span>
                  </h4>
                  <p className="text-[11px] text-slate-400">Deep telemetry analysis grounded on customer historical behavior</p>
                </div>
              </div>

              <button
                onClick={handleAnalyzeWithAI}
                disabled={investigating}
                className="px-3.5 py-1.5 bg-gradient-to-r from-brand-cyan to-brand-blue text-dark-900 font-bold text-xs rounded-lg shadow-glow-cyan hover:opacity-90 transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {investigating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Investigating...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 fill-dark-900" />
                    <span>{investigation ? 'Re-Analyze with AI' : 'Analyze with AI'}</span>
                  </>
                )}
              </button>
            </div>

            {investigationError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
                <span>{investigationError}</span>
                <button onClick={handleAnalyzeWithAI} className="underline text-white font-semibold">
                  Retry
                </button>
              </div>
            )}

            {investigation ? (
              <div className="space-y-4 pt-1 animate-fadeIn">
                {/* Metrics row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Recovery Probability</span>
                    <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">
                      {(investigation.recovery_probability * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Recovery Score</span>
                    <div className="text-lg font-bold font-mono text-white mt-0.5">
                      {investigation.recovery_score} <span className="text-xs text-slate-500 font-normal">/ 100</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Risk Level</span>
                    <div className={`text-sm font-bold font-mono mt-1 ${
                      investigation.risk_level === 'LOW' ? 'text-emerald-400' : investigation.risk_level === 'MEDIUM' ? 'text-amber-400' : 'text-rose-400'
                    }`}>
                      {investigation.risk_level}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Confidence</span>
                    <div className="text-lg font-bold font-mono text-brand-cyan mt-0.5">
                      {(investigation.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                {/* Failure Category & Next Action */}
                <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400">Failure Category:</span>
                    <div className="font-semibold text-slate-200 mt-0.5 font-mono capitalize">
                      {investigation.failure_category.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-400">Recommended Next Action:</span>
                    <div className="font-bold text-brand-cyan mt-0.5 font-mono">
                      {investigation.recommended_next_action}
                    </div>
                  </div>
                </div>

                {/* Why? Contributing Factors */}
                <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 space-y-2 text-xs">
                  <span className="font-bold text-slate-300 uppercase tracking-wide text-[11px]">
                    Why? Contributing Factors
                  </span>
                  <ul className="space-y-1 text-slate-300">
                    {investigation.contributing_factors.map((factor, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-emerald-400 font-bold">•</span>
                        <span>{factor}</span>
                      </li>
                    ))}
                  </ul>

                  {investigation.negative_factors && investigation.negative_factors.length > 0 && (
                    <div className="pt-2 border-t border-dark-800">
                      <span className="font-bold text-rose-400 uppercase tracking-wide text-[10px]">
                        Risk / Negative Factors:
                      </span>
                      <ul className="space-y-1 text-slate-400 mt-1">
                        {investigation.negative_factors.map((neg, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className="text-rose-400 font-bold">•</span>
                            <span>{neg}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Reasoning Narrative */}
                <div className="p-3.5 rounded-xl bg-dark-900/50 border border-dark-750 text-xs text-slate-300 leading-relaxed font-sans">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Reasoning Summary:</span>
                  {investigation.reasoning_summary}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-dark-900/60 border border-dark-700 text-center space-y-2">
                <p className="text-xs text-slate-400">
                  Click <strong className="text-brand-cyan">[Analyze with AI]</strong> to trigger the Gemini Payment Investigator and extract structured failure telemetry.
                </p>
              </div>
            )}
          </div>

          {/* Recovery Case Actions & Links if available */}
          {recoveryCase?.payment_link_url && (
            <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">Active Recovery Link:</span>
                <a
                  href={recoveryCase.payment_link_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-brand-cyan font-mono hover:underline flex items-center gap-1"
                >
                  {recoveryCase.payment_link_url}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <span className="text-[10px] text-emerald-400 font-semibold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                Active in WhatsApp
              </span>
            </div>
          )}

          {/* Action History timeline */}
          {recoveryCase && recoveryCase.actions && recoveryCase.actions.length > 0 && (
            <div className="p-4 rounded-xl bg-dark-800 border border-dark-700 space-y-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Agent Audit Trail</span>
              <div className="space-y-1.5 max-h-36 overflow-y-auto pr-2">
                {recoveryCase.actions.map((act) => (
                  <div key={act.id} className="text-[11px] p-2 rounded bg-dark-900/60 border border-dark-700 flex items-start gap-2">
                    <span className="text-brand-cyan font-mono font-bold shrink-0">{act.agent_type}:</span>
                    <span className="text-slate-300 flex-1">{act.reasoning_summary}</span>
                    <span className="text-[10px] text-slate-500 shrink-0">{new Date(act.created_at).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="p-4 bg-dark-800 border-t border-dark-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-slate-400">All actions audited under Merchant Guardrails</span>
          </div>

          <div className="flex items-center gap-2">
            {recoveryCase?.status === 'AWAITING_HUMAN_APPROVAL' && (
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-4 py-2 bg-brand-emerald text-dark-900 font-bold text-xs rounded-lg hover:opacity-90 transition flex items-center gap-1.5"
              >
                <CheckCircle className="w-4 h-4" />
                Approve High-Value Action
              </button>
            )}

            {payment.status !== 'RECOVERED' && (
              <>
                <button
                  onClick={handleExecute}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-slate-200 text-xs font-semibold rounded-lg transition flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                  Re-run Flow
                </button>

                <button
                  onClick={handleSettlement}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-emerald text-dark-900 font-bold text-xs rounded-lg shadow-glow-cyan hover:opacity-90 transition flex items-center gap-1.5"
                >
                  <CheckCircle className="w-4 h-4 fill-dark-900 text-brand-cyan" />
                  Simulate Customer Settlement
                </button>
              </>
            )}

            {payment.status === 'RECOVERED' && (
              <div className="px-4 py-2 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold text-xs rounded-lg flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Revenue Recovered Successfully
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
