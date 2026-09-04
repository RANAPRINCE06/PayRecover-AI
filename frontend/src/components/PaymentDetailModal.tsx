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
  Loader2,
  MessageSquare,
  Send,
  UserCheck,
  Compass,
  ShieldCheck,
  Lock,
  Scale
} from 'lucide-react';
import {
  Payment,
  RecoveryCase,
  PaymentInvestigationResult,
  CustomerIntentResult,
  RecoveryStrategyResult
} from '../types';
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
  const [intentResult, setIntentResult] = useState<CustomerIntentResult | null>(null);
  const [strategyResult, setStrategyResult] = useState<RecoveryStrategyResult | null>(null);
  
  // Inputs & loaders
  const [customerMessage, setCustomerMessage] = useState("My card isn't working. Can I use UPI?");
  const [selectedChannel, setSelectedChannel] = useState("WHATSAPP");
  const [loading, setLoading] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [intentLoading, setIntentLoading] = useState(false);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [intentError, setIntentError] = useState<string | null>(null);
  const [strategyError, setStrategyError] = useState<string | null>(null);

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
    setIntentResult(null);
    setStrategyResult(null);
    setInvestigationError(null);
    setIntentError(null);
    setStrategyError(null);
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

  const handleAnalyzeIntent = async (overrideMessage?: string) => {
    if (!payment || !payment.customer_id) return;
    const msg = overrideMessage || customerMessage;
    if (!msg.trim()) return;

    setIntentLoading(true);
    setIntentError(null);
    try {
      const result: CustomerIntentResult = await api.analyzeCustomerIntent({
        customer_id: payment.customer_id,
        recovery_case_id: recoveryCase?.id,
        message: msg.trim(),
        channel: selectedChannel
      });
      setIntentResult(result);
      loadCaseData();
      onRefresh();
    } catch (err: any) {
      setIntentError(err.message || 'Intent analysis failed');
    } finally {
      setIntentLoading(false);
    }
  };

  const handleGenerateStrategy = async () => {
    if (!recoveryCase) {
      setStrategyError("Recovery case not found. Please run payment investigation first.");
      return;
    }
    setStrategyLoading(true);
    setStrategyError(null);
    try {
      const result: RecoveryStrategyResult = await api.generateRecoveryStrategy(recoveryCase.id);
      setStrategyResult(result);
      loadCaseData();
      onRefresh();
    } catch (err: any) {
      setStrategyError(err.message || 'Strategy generation failed');
    } finally {
      setStrategyLoading(false);
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

  const sampleMessages = [
    "My card isn't working. Can I use UPI?",
    "I don't have enough balance right now. Remind me tomorrow.",
    "I already completed the payment. Please verify.",
    "Please cancel this. I don't want it.",
    "Can you send me a payment link?"
  ];

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
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Active Intent</span>
              <div className="mt-1">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
                  {intentResult?.intent || recoveryCase?.customer_intent || 'ALTERNATE_PAYMENT_METHOD'}
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

          {/* 1. AI Payment Investigator Section */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-dark-800 via-dark-750 to-dark-800 border border-brand-cyan/30 shadow-glow-cyan/10 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-center text-brand-cyan">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    AI Payment Investigator
                    <span className="text-[10px] font-mono px-1.5 py-0.2 bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 rounded">
                      Structured Output
                    </span>
                  </h4>
                  <p className="text-[11px] text-slate-400">Deep failure telemetry analysis grounded on historical behavior</p>
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

            {investigation && (
              <div className="space-y-4 pt-1 animate-fadeIn">
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

                <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 space-y-2 text-xs">
                  <span className="font-bold text-slate-300 uppercase tracking-wide text-[11px]">
                    Contributing & Risk Factors
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
                    <ul className="space-y-1 text-slate-400 pt-1 border-t border-dark-800">
                      {investigation.negative_factors.map((neg, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-rose-400 font-bold">•</span>
                          <span>{neg}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 2. Customer Intent AI Section (PHASE 3) */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-dark-800 via-dark-750 to-dark-800 border border-brand-indigo/30 shadow-glow-indigo/10 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-indigo/10 border border-brand-indigo/30 flex items-center justify-center text-brand-indigo">
                  <MessageSquare className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    Customer Intent AI Engine
                    <span className="text-[10px] font-mono px-1.5 py-0.2 bg-brand-indigo/20 text-indigo-300 border border-brand-indigo/30 rounded">
                      Gemini Intent Analyst
                    </span>
                  </h4>
                  <p className="text-[11px] text-slate-400">Classify inbound messages, sentiment, urgency & recovery action</p>
                </div>
              </div>
            </div>

            {/* Inbound Customer Message Input Simulator */}
            <div className="p-4 rounded-xl bg-dark-900/90 border border-dark-700 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-300 uppercase tracking-wide">
                  Customer Message Input
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400">Channel:</span>
                  <select
                    value={selectedChannel}
                    onChange={(e) => setSelectedChannel(e.target.value)}
                    className="px-2 py-1 bg-dark-800 border border-dark-700 rounded text-xs text-brand-cyan font-mono focus:outline-none"
                  >
                    <option value="WHATSAPP">WhatsApp</option>
                    <option value="SMS">SMS</option>
                    <option value="EMAIL">Email</option>
                    <option value="VOICE">Voice</option>
                  </select>
                </div>
              </div>

              <textarea
                value={customerMessage}
                onChange={(e) => setCustomerMessage(e.target.value)}
                placeholder="Type customer message..."
                rows={2}
                className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-indigo font-sans"
              />

              {/* Sample Quick Prompts */}
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-[10px] font-semibold text-slate-500 uppercase">Quick Samples:</span>
                {sampleMessages.map((msg, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setCustomerMessage(msg);
                      handleAnalyzeIntent(msg);
                    }}
                    className="text-[10px] px-2 py-0.5 rounded-full bg-dark-800 hover:bg-dark-750 text-slate-400 hover:text-brand-cyan border border-dark-700 transition"
                  >
                    {msg.length > 28 ? `${msg.slice(0, 28)}...` : msg}
                  </button>
                ))}
              </div>

              <div className="flex justify-end pt-1">
                <button
                  onClick={() => handleAnalyzeIntent()}
                  disabled={intentLoading || !customerMessage.trim()}
                  className="px-4 py-2 bg-gradient-to-r from-brand-indigo to-indigo-600 text-white font-bold text-xs rounded-lg shadow-glow-indigo hover:opacity-90 transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {intentLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Classifying Intent...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>[ Analyze Intent ]</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {intentError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
                <span>{intentError}</span>
                <button onClick={() => handleAnalyzeIntent()} className="underline text-white font-semibold">
                  Retry
                </button>
              </div>
            )}

            {/* Display Structured Intent Result */}
            {intentResult && (
              <div className="space-y-4 pt-1 animate-fadeIn">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Detected Intent</span>
                    <div className="text-xs font-bold font-mono text-brand-cyan mt-1">
                      {intentResult.intent}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Confidence</span>
                    <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">
                      {(intentResult.confidence * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Sentiment</span>
                    <div className={`text-xs font-bold font-mono mt-1 ${
                      intentResult.sentiment === 'POSITIVE' ? 'text-emerald-400' : intentResult.sentiment === 'FRUSTRATED' || intentResult.sentiment === 'NEGATIVE' ? 'text-rose-400' : 'text-slate-300'
                    }`}>
                      {intentResult.sentiment}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Urgency</span>
                    <div className={`text-xs font-bold font-mono mt-1 ${
                      intentResult.urgency === 'HIGH' ? 'text-rose-400' : intentResult.urgency === 'MEDIUM' ? 'text-amber-400' : 'text-slate-400'
                    }`}>
                      {intentResult.urgency}
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 space-y-2 text-xs">
                  <div className="text-slate-200">
                    <span className="text-slate-400 font-semibold">Intent Summary:</span> {intentResult.intent_summary}
                  </div>
                  <div className="grid grid-cols-2 gap-3 pt-1 border-t border-dark-800">
                    <div>
                      <span className="text-slate-400 font-semibold">Recommended Action:</span>
                      <div className="font-bold text-brand-indigo font-mono mt-0.5">{intentResult.recommended_action}</div>
                    </div>
                    <div>
                      <span className="text-slate-400 font-semibold">Recommended Channel:</span>
                      <div className="font-bold text-emerald-400 font-mono mt-0.5">{intentResult.recommended_channel}</div>
                    </div>
                  </div>
                </div>

                {intentResult.evidence && intentResult.evidence.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 space-y-1.5 text-xs">
                    <span className="font-bold text-slate-300 uppercase tracking-wide text-[11px]">
                      Intent Evidence & Signals:
                    </span>
                    <ul className="space-y-1 text-slate-300">
                      {intentResult.evidence.map((ev, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-brand-indigo font-bold">•</span>
                          <span>{ev}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-3.5 rounded-xl bg-dark-900/50 border border-dark-750 text-xs text-slate-300 leading-relaxed font-sans">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Reasoning Narrative:</span>
                  {intentResult.reasoning_summary}
                </div>
              </div>
            )}
          </div>

          {/* 3. AI Recovery Strategist Section (PHASE 4) */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-dark-800 via-dark-750 to-dark-800 border border-emerald-500/30 shadow-glow-emerald/10 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <Compass className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    AI Recovery Strategist
                    <span className="text-[10px] font-mono px-1.5 py-0.2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">
                      Advisory Only
                    </span>
                  </h4>
                  <p className="text-[11px] text-slate-400">Synthesizes investigation, intent & deterministic guardrails</p>
                </div>
              </div>

              <button
                onClick={handleGenerateStrategy}
                disabled={strategyLoading}
                className="px-3.5 py-1.5 bg-gradient-to-r from-emerald-400 to-teal-500 text-dark-900 font-bold text-xs rounded-lg shadow-glow-emerald hover:opacity-90 transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {strategyLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Formulating Strategy...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 fill-dark-900" />
                    <span>{strategyResult ? 'Re-Generate Strategy' : 'Generate Recovery Strategy'}</span>
                  </>
                )}
              </button>
            </div>

            {strategyError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
                <span>{strategyError}</span>
                <button onClick={handleGenerateStrategy} className="underline text-white font-semibold">
                  Retry
                </button>
              </div>
            )}

            {strategyResult && (
              <div className="space-y-4 pt-1 animate-fadeIn">
                {/* 4 Core Decision Highlight Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Primary Strategy</span>
                    <div className="text-xs font-bold font-mono text-emerald-400 mt-1">
                      {strategyResult.primary_strategy}
                    </div>
                    {strategyResult.secondary_strategy && (
                      <span className="text-[10px] text-slate-500 block mt-0.5">
                        Fallback: {strategyResult.secondary_strategy}
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Channel & Method</span>
                    <div className="text-xs font-bold font-mono text-brand-cyan mt-1">
                      {strategyResult.recommended_channel} • {strategyResult.recommended_payment_method || 'UPI'}
                    </div>
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      Delay: {strategyResult.recommended_delay_minutes}m
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Recovery Probability</span>
                    <div className="text-lg font-bold font-mono text-white mt-0.5">
                      {(strategyResult.expected_recovery_probability * 100).toFixed(0)}%
                    </div>
                    <span className="text-[10px] text-slate-400 block">
                      Confidence: {(strategyResult.strategy_confidence * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Guardrail Status</span>
                    <div className="mt-1">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${
                        strategyResult.guardrail_status === 'SAFE'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : strategyResult.guardrail_status === 'CAPPED'
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                          : strategyResult.guardrail_status === 'APPROVAL_REQUIRED'
                          ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      }`}>
                        {strategyResult.guardrail_status}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[10px] font-semibold text-slate-400">
                      Approval: {strategyResult.human_approval_required ? (
                        <span className="text-rose-400 font-bold">REQUIRED</span>
                      ) : (
                        <span className="text-emerald-400 font-bold">NOT REQUIRED</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Guardrail Policy Evaluation Comparison Grid */}
                <div className="p-4 rounded-xl bg-dark-900/90 border border-dark-700 space-y-3">
                  <div className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Guardrail Policy Evaluation & Enforcement
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div className="p-2.5 rounded-lg bg-dark-800 border border-dark-700">
                      <span className="text-[10px] text-slate-400 uppercase block mb-1">Discount Policy</span>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-semibold">Final Discount:</span>
                        <span className="font-mono font-bold text-emerald-400">{strategyResult.discount_percentage}% (₹{strategyResult.discount_amount.toLocaleString()})</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-dark-800 border border-dark-700">
                      <span className="text-[10px] text-slate-400 uppercase block mb-1">Retry Quota</span>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-semibold">Retry Count:</span>
                        <span className="font-mono font-bold text-white">{strategyResult.retry_count}</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-dark-800 border border-dark-700">
                      <span className="text-[10px] text-slate-400 uppercase block mb-1">High-Value Check</span>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-semibold">Human Gated:</span>
                        <span className={`font-mono font-bold ${strategyResult.human_approval_required ? 'text-amber-400' : 'text-emerald-400'}`}>
                          {strategyResult.human_approval_required ? 'YES (APPROVAL_REQUIRED)' : 'NO'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Active Constraints */}
                  {strategyResult.guardrail_constraints && strategyResult.guardrail_constraints.length > 0 && (
                    <div className="p-3 rounded-lg bg-dark-850 border border-dark-750 space-y-1.5">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        Active Guardrail Constraints Enforced:
                      </span>
                      <ul className="space-y-1 text-xs text-slate-300">
                        {strategyResult.guardrail_constraints.map((c, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-emerald-400 font-bold">•</span>
                            <span>{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Strategy Narrative & Reasoning */}
                <div className="p-3.5 rounded-xl bg-dark-900/80 border border-dark-700 space-y-2 text-xs">
                  <div className="text-slate-200">
                    <span className="text-slate-400 font-semibold">Strategy Summary:</span> {strategyResult.strategy_summary}
                  </div>
                  {strategyResult.approval_reason && (
                    <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px]">
                      <strong>Approval Reason:</strong> {strategyResult.approval_reason}
                    </div>
                  )}
                </div>

                {/* Supporting Factors, Risk Factors & Rejected Strategies */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {strategyResult.supporting_factors && strategyResult.supporting_factors.length > 0 && (
                    <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700 space-y-1.5 text-xs">
                      <span className="font-bold text-slate-300 uppercase tracking-wide text-[10px]">
                        Supporting Factors
                      </span>
                      <ul className="space-y-1 text-slate-300">
                        {strategyResult.supporting_factors.map((f, idx) => (
                          <li key={idx} className="flex items-start gap-1.5">
                            <span className="text-emerald-400 font-bold">•</span>
                            <span>{f}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {strategyResult.risk_factors && strategyResult.risk_factors.length > 0 && (
                    <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700 space-y-1.5 text-xs">
                      <span className="font-bold text-slate-300 uppercase tracking-wide text-[10px]">
                        Identified Risk Factors
                      </span>
                      <ul className="space-y-1 text-slate-300">
                        {strategyResult.risk_factors.map((rf, idx) => (
                          <li key={idx} className="flex items-start gap-1.5">
                            <span className="text-rose-400 font-bold">•</span>
                            <span>{rf}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {strategyResult.rejected_strategies && strategyResult.rejected_strategies.length > 0 && (
                  <div className="p-3 rounded-xl bg-dark-900/80 border border-dark-700 space-y-1.5 text-xs">
                    <span className="font-bold text-slate-300 uppercase tracking-wide text-[10px]">
                      Rejected Alternative Strategies
                    </span>
                    <ul className="space-y-1 text-slate-400">
                      {strategyResult.rejected_strategies.map((rej, idx) => (
                        <li key={idx} className="flex items-start gap-1.5">
                          <span className="text-slate-500 font-bold">•</span>
                          <span>{rej}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-3 rounded-xl bg-dark-900/50 border border-dark-750 text-xs text-slate-300 leading-relaxed font-sans">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Reasoning Analysis:</span>
                  {strategyResult.reasoning_summary}
                </div>
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
