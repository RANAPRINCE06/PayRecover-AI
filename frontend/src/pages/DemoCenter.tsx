import React, { useState } from 'react';
import {
  FlaskConical,
  Play,
  CheckCircle2,
  AlertTriangle,
  Shield,
  Bot,
  Zap,
  Clock,
  ArrowRight,
  ExternalLink,
  Loader2,
  Sparkles,
  RefreshCw,
  Eye,
  CreditCard,
  Smartphone,
  Layers,
  RotateCcw,
  Check
} from 'lucide-react';
import { api } from '../services/api';
import { useToast } from '../components/Toast';

interface DemoScenario {
  id: string;
  title: string;
  subtitle: string;
  amount: number;
  paymentMethod: string;
  failureReason: string;
  customerProfile: string;
  expectedStrategy: string;
  guardrailBehavior: string;
  tag: string;
  color: string;
  description: string;
}

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'DEMO_CARD_DECLINE_UPI',
    title: 'Flagship ₹12,999 Card Decline -> UPI Conversion',
    subtitle: 'VIP Customer card 3DS drop-off rescued with instant UPI payment link via WhatsApp',
    amount: 12999,
    paymentMethod: 'CARD',
    failureReason: 'CARD_DECLINED',
    customerProfile: 'VIP · 10 Successful Orders · LTV ₹85,000',
    expectedStrategy: 'UPI_FALLBACK_LINK via WhatsApp',
    guardrailBehavior: 'PASS — Autonomous link generated instantly',
    tag: 'FLAGSHIP DEMO',
    color: 'border-brand-cyan/40 bg-brand-cyan/5 text-brand-cyan',
    description: 'Customer attempted a high-value card checkout which failed at bank OTP verification. Intent AI detects customer is ready to complete via UPI. Strategist formulates instant deep-link.'
  },
  {
    id: 'HIGH_VALUE_APPROVAL',
    title: 'High-Value Order (₹75,000 Guardrail Human Queue)',
    subtitle: 'Exceeds merchant ₹50,000 autonomous threshold requiring human signoff',
    amount: 75000,
    paymentMethod: 'NETBANKING',
    failureReason: 'BANK_SERVER_DOWN',
    customerProfile: 'VIP · 15 Successful Orders · LTV ₹320,000',
    expectedStrategy: 'EXECUTIVE_CONCIERGE_CALL',
    guardrailBehavior: 'REQUIRES APPROVAL — Held safely in merchant queue',
    tag: 'SAFETY GUARDRAIL',
    color: 'border-amber-500/40 bg-amber-500/5 text-amber-400',
    description: 'Transaction exceeds ₹50,000 maximum autonomous execution threshold. The autonomous pipeline halts before any customer message is dispatched and places the case into the human approval queue.'
  },
  {
    id: 'UPI_TIMEOUT',
    title: 'UPI PSP Timeout (₹2,499 Instant Retry Link)',
    subtitle: 'NPCI/PSP bank latency during MPIN entry recovered seamlessly',
    amount: 2499,
    paymentMethod: 'UPI',
    failureReason: 'UPI_TIMEOUT',
    customerProfile: 'STANDARD · 4 Successful Orders · LTV ₹12,500',
    expectedStrategy: 'INSTANT_WHATSAPP_ONE_CLICK_UPI',
    guardrailBehavior: 'PASS — Sub-second autonomous dispatch',
    tag: 'LATENCY RECOVERY',
    color: 'border-brand-emerald/40 bg-brand-emerald/5 text-emerald-400',
    description: 'UPI transaction timed out due to bank-side MPIN gateway response delay. Intent AI recognizes technical frustration and delivers a prefilled UPI Intent link.'
  },
  {
    id: 'CHECKOUT_ABANDONED',
    title: 'Cart Abandonment with Guardrail Discount Cap (₹4,999)',
    subtitle: 'Proposes smart discount incentive; guardrail verifies merchant cap compliance',
    amount: 4999,
    paymentMethod: 'NETBANKING',
    failureReason: 'CHECKOUT_ABANDONED',
    customerProfile: 'STANDARD · 1 Previous Order',
    expectedStrategy: 'DISCOUNT_INCENTIVE_SMS',
    guardrailBehavior: 'CAPPED — AI proposal adjusted to merchant maximum 10%',
    tag: 'GUARDRAIL CAP',
    color: 'border-indigo-500/40 bg-indigo-500/5 text-indigo-400',
    description: 'User abandoned final payment screen. Recovery Strategist tests a small 5-10% discount offer to incentivize immediate completion within guardrail bounds.'
  },
  {
    id: 'SUBSCRIPTION_FAILED',
    title: 'RBI E-Mandate Auto-Debit Expired (₹999)',
    subtitle: 'Recurring subscription mandate expired on card; WhatsApp mandate renewal',
    amount: 999,
    paymentMethod: 'CARD',
    failureReason: 'SUBSCRIPTION_FAILED',
    customerProfile: 'VIP · 12 Month Retention',
    expectedStrategy: 'AUTO_RETRY_MANDATE_UPDATE',
    guardrailBehavior: 'PASS — Direct WhatsApp e-mandate refresh',
    tag: 'RECURRING SAAS',
    color: 'border-fuchsia-500/40 bg-fuchsia-500/5 text-fuchsia-400',
    description: 'Recurring auto-debit subscription mandate expired at issuing bank. System routes directly to customer WhatsApp with 1-tap card mandate re-authentication.'
  }
];

interface DemoCenterProps {
  onSelectPaymentId?: (id: string) => void;
  onRefreshAll?: () => void;
}

export const DemoCenter: React.FC<DemoCenterProps> = ({ onSelectPaymentId, onRefreshAll }) => {
  const { showSuccess, showError, showInfo } = useToast();
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('DEMO_CARD_DECLINE_UPI');
  const [executing, setExecuting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any | null>(null);
  const [executionStep, setExecutionStep] = useState<number>(0);

  const currentScenario = DEMO_SCENARIOS.find((s) => s.id === selectedScenarioId) || DEMO_SCENARIOS[0];

  const handleResetDemo = async () => {
    if (!window.confirm('Reset demo simulations and restore baseline test environment?')) return;
    setResetting(true);
    try {
      const res = await api.resetDemoData();
      showSuccess('Sandbox Reset Complete', res?.message || 'Demo simulations cleared successfully.');
      setExecutionResult(null);
      setExecutionStep(0);
      if (onRefreshAll) onRefreshAll();
    } catch (err: any) {
      showError('Reset Failed', err?.message || 'Could not reset demo environment');
    } finally {
      setResetting(false);
    }
  };

  const handleRunDemo = async () => {
    setExecuting(true);
    setExecutionResult(null);
    setExecutionStep(1);

    try {
      // Step progression simulation for rich UX feedback
      const stepTimer1 = setTimeout(() => setExecutionStep(2), 300);
      const stepTimer2 = setTimeout(() => setExecutionStep(3), 600);
      const stepTimer3 = setTimeout(() => setExecutionStep(4), 900);

      const res = await api.simulateRecovery(currentScenario.id, currentScenario.amount);

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);
      setExecutionStep(5);
      setExecutionResult(res);

      if (res?.orchestration_result?.guardrail_status === 'VIOLATION_BLOCKED' || res?.orchestration_result?.requires_human_approval) {
        showInfo('Safety Guardrail Activated', 'High-value transaction held safely in human approval queue.');
      } else {
        showSuccess('Autonomous Recovery Complete', `Successfully recovered via ${res?.orchestration_result?.strategy_selected || 'AI Strategy'}`);
      }

      if (onRefreshAll) onRefreshAll();
    } catch (err: any) {
      console.error('Demo execution failed:', err);
      showError('Demo Execution Failed', err?.message || 'Failed running simulation scenario');
    } finally {
      setExecuting(false);
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-brand-cyan" />
            Live Demo Center & Recovery Sandbox
          </h2>
          <p className="text-xs text-slate-400">
            Execute deterministic Indian fintech failure recovery scenarios through the full autonomous multi-agent pipeline.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleResetDemo}
            disabled={resetting || executing}
            className="px-3 py-1.5 rounded-xl text-xs font-medium bg-dark-800 border border-dark-600 hover:border-red-500/50 hover:bg-red-500/10 text-slate-300 hover:text-red-300 transition-all flex items-center gap-1.5 disabled:opacity-50"
            title="Clean up simulated demo cases and reset guardrails"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin text-red-400' : ''}`} />
            {resetting ? 'Resetting...' : 'Reset Sandbox'}
          </button>
          <span className="px-2.5 py-1.5 rounded-xl text-[11px] font-mono font-bold bg-brand-cyan/10 border border-brand-cyan/30 text-brand-cyan flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-brand-cyan animate-pulse" />
            LIVE PIPELINE READY
          </span>
        </div>
      </div>

      {/* Scenario Selector Carousel/Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {DEMO_SCENARIOS.map((sc) => {
          const isSelected = sc.id === selectedScenarioId;
          return (
            <div
              key={sc.id}
              onClick={() => {
                setSelectedScenarioId(sc.id);
                setExecutionResult(null);
                setExecutionStep(0);
              }}
              className={`p-4 rounded-2xl cursor-pointer border transition-all relative flex flex-col justify-between ${
                isSelected
                  ? 'bg-dark-800 border-brand-cyan shadow-glow-cyan/20'
                  : 'bg-dark-850 border-dark-700 hover:border-dark-600 hover:bg-dark-800/60'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded border ${sc.color}`}>
                    {sc.tag}
                  </span>
                  <span className="text-xs font-mono font-bold text-white">
                    {formatCurrency(sc.amount)}
                  </span>
                </div>

                <h3 className="text-xs font-bold text-slate-100 leading-snug mb-1">
                  {sc.title}
                </h3>
                <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
                  {sc.subtitle}
                </p>
              </div>

              <div className="pt-2 border-t border-dark-700/60 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                <span>{sc.paymentMethod}</span>
                <span className={isSelected ? 'text-brand-cyan font-bold' : ''}>
                  {isSelected ? 'SELECTED' : 'Click to select'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Scenario Execution Console */}
      <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 border-b border-dark-700">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${currentScenario.color}`}>
                {currentScenario.tag}
              </span>
              <h3 className="text-base font-bold text-white">
                {currentScenario.title}
              </h3>
            </div>
            <p className="text-xs text-slate-300 max-w-2xl">
              {currentScenario.description}
            </p>
          </div>

          <button
            onClick={handleRunDemo}
            disabled={executing}
            className="px-5 py-2.5 bg-gradient-to-r from-brand-cyan to-brand-indigo text-dark-900 font-bold text-xs rounded-xl shadow-glow-cyan hover:opacity-95 transition flex items-center justify-center gap-2 disabled:opacity-50 shrink-0"
          >
            {executing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Executing Pipeline...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-dark-900" />
                Run Autonomous Demo
              </>
            )}
          </button>
        </div>

        {/* Live Pipeline Steps Visualizer */}
        <div>
          <h4 className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wider">
            Pipeline Execution Flow
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
            {[
              { step: 1, name: '1. Ingest Failure', desc: 'Mock Engine / Razorpay' },
              { step: 2, name: '2. Investigator', desc: 'Root Cause Telemetry' },
              { step: 3, name: '3. Intent AI', desc: 'Buyer Propensity Analysis' },
              { step: 4, name: '4. Guardrails', desc: 'Policy & Cap Validation' },
              { step: 5, name: '5. Tool Execution', desc: 'Link / WhatsApp / Queue' }
            ].map((s) => {
              const isDone = executionStep >= s.step;
              const isCurrent = executionStep === s.step && executing;
              return (
                <div
                  key={s.step}
                  className={`p-3 rounded-xl border transition-all ${
                    isCurrent
                      ? 'bg-brand-cyan/10 border-brand-cyan text-brand-cyan shadow-glow-cyan/20'
                      : isDone
                      ? 'bg-dark-800 border-emerald-500/40 text-emerald-400'
                      : 'bg-dark-900 border-dark-700 text-slate-500'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-bold mb-1">
                    <span>{s.name}</span>
                    {isCurrent ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : isDone ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-dark-700" />
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 truncate">{s.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Execution Output Panel */}
        {executionResult && (
          <div className="p-5 rounded-xl bg-dark-800 border border-dark-700 space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold text-white">Pipeline Execution Result</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-slate-400 bg-dark-900 px-2 py-0.5 rounded border border-dark-700">
                  Case ID: {executionResult.case_id}
                </span>
                <span className="text-[10px] font-mono text-slate-400 bg-dark-900 px-2 py-0.5 rounded border border-dark-700">
                  Payment ID: {executionResult.payment_id}
                </span>
              </div>
            </div>

            {/* Results Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-dark-900 border border-dark-700">
                <span className="text-[10px] font-mono text-slate-500 uppercase">Selected Strategy</span>
                <div className="text-xs font-bold text-brand-cyan font-mono mt-1 truncate">
                  {executionResult.orchestration_result?.strategy_selected || 'N/A'}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-dark-900 border border-dark-700">
                <span className="text-[10px] font-mono text-slate-500 uppercase">Guardrail Status</span>
                <div className="text-xs font-bold font-mono mt-1">
                  <span className={`px-2 py-0.5 rounded text-[10px] ${
                    executionResult.orchestration_result?.guardrail_status === 'APPROVED' || executionResult.orchestration_result?.guardrail_status === 'PASSED'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  }`}>
                    {executionResult.orchestration_result?.guardrail_status || 'CHECKED'}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-dark-900 border border-dark-700">
                <span className="text-[10px] font-mono text-slate-500 uppercase">Tool Executed</span>
                <div className="text-xs font-bold text-brand-indigo font-mono mt-1 truncate">
                  {executionResult.orchestration_result?.tool_executed || 'DISPATCH_COMPLETE'}
                </div>
              </div>
            </div>

            {/* Executive Summary */}
            {executionResult.orchestration_result?.executive_summary && (
              <div className="p-3 rounded-lg bg-dark-900 border border-dark-700 text-xs text-slate-300 leading-relaxed font-sans">
                <span className="font-bold text-slate-200">AI Summary: </span>
                {executionResult.orchestration_result.executive_summary}
              </div>
            )}

            {/* Payment Link Demonstration */}
            {executionResult.orchestration_result?.payment_link_url && (
              <div className="p-3 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-brand-cyan">
                  <Zap className="w-4 h-4" />
                  <span>Autonomous Recovery Link Ready:</span>
                  <span className="font-mono font-bold">{executionResult.orchestration_result.payment_link_url}</span>
                </div>
                <a
                  href={executionResult.orchestration_result.payment_link_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2.5 py-1 bg-brand-cyan text-dark-900 font-bold text-[11px] rounded flex items-center gap-1 hover:opacity-90 transition"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open Link
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
