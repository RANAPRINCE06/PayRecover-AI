import React, { useState } from 'react';
import { X, Play, Zap, CheckCircle2, ShieldAlert, Sparkles, ArrowRight } from 'lucide-react';
import { api } from '../services/api';

interface SimulateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSimulationSuccess: () => void;
}

export const SimulateModal: React.FC<SimulateModalProps> = ({ isOpen, onClose, onSimulationSuccess }) => {
  const [scenario, setScenario] = useState('DEMO_CARD_DECLINE_UPI');
  const [amount, setAmount] = useState(12999);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  if (!isOpen) return null;

  const scenarios = [
    {
      id: 'DEMO_CARD_DECLINE_UPI',
      title: 'Exact Demo: Returning Customer (Card Declined -> UPI Recovery)',
      desc: 'Customer with 10 past success orders. 3DS failure on ₹12,999 card payment -> AI switches to 1-click WhatsApp UPI link.',
      defaultAmount: 12999,
      badge: 'RECOMMENDED'
    },
    {
      id: 'UPI_TIMEOUT',
      title: 'UPI PSP Request Timeout',
      desc: 'UPI application timed out during MPIN entry. Instant recovery prefilled deep-link dispatched via WhatsApp.',
      defaultAmount: 2499,
      badge: '94% RECOVERY'
    },
    {
      id: 'INSUFFICIENT_FUNDS',
      title: 'Insufficient Balance / Salary Cycle Wait',
      desc: 'Issuing bank returns insufficient balance. Intent AI detects customer requests pay later -> Schedules reminder.',
      defaultAmount: 8999,
      badge: 'INTENT AI'
    },
    {
      id: 'CHECKOUT_ABANDONED',
      title: 'Checkout Cart Abandoned',
      desc: 'Customer abandoned OTP screen. Strategist triggers 5% smart discount incentive to recover revenue.',
      defaultAmount: 4999,
      badge: 'DISCOUNT NUDGE'
    },
    {
      id: 'HIGH_VALUE_APPROVAL',
      title: 'High-Value Payment Guardrail Escalation',
      desc: 'Payment of ₹75,000 exceeds ₹50,000 merchant threshold. Autonomous flow pauses and queues for human review.',
      defaultAmount: 75000,
      badge: 'GUARDRAIL BLOCKED'
    }
  ];

  const handleRun = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.simulateScenario(scenario, amount);
      setResult(res);
      onSimulationSuccess();
    } catch (err) {
      alert(`Simulation failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulatePayment = async () => {
    if (!result?.case_id) return;
    setLoading(true);
    try {
      await api.confirmSettlement(result.case_id);
      setResult({
        ...result,
        recovered: true
      });
      onSimulationSuccess();
    } catch (err) {
      alert(`Settlement failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-2xl bg-dark-850 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-dark-700 flex items-center justify-between bg-dark-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-cyan to-brand-blue flex items-center justify-center text-dark-900 font-bold">
              <Zap className="w-4 h-4 fill-dark-900" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Live Payment Recovery Sandbox</h3>
              <p className="text-xs text-slate-400">Trigger deterministic Razorpay Test failure scenarios</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-dark-700 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Scenario Selection */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Select Failure Scenario</label>
            <div className="space-y-2">
              {scenarios.map((sc) => {
                const isSelected = scenario === sc.id;
                return (
                  <div
                    key={sc.id}
                    onClick={() => {
                      setScenario(sc.id);
                      setAmount(sc.defaultAmount);
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-brand-cyan/10 border-brand-cyan/50 shadow-glow-cyan/10'
                        : 'bg-dark-800 border-dark-700 hover:border-dark-600'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-bold ${isSelected ? 'text-brand-cyan' : 'text-slate-200'}`}>
                        {sc.title}
                      </span>
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-dark-700 text-slate-300 border border-dark-600">
                        {sc.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{sc.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Amount input */}
          <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-slate-300">Transaction Amount (INR)</span>
              <p className="text-[10px] text-slate-500">Threshold guardrail triggers at ₹50,000</p>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-brand-cyan font-mono">₹</span>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                className="w-28 px-2 py-1 bg-dark-900 border border-dark-700 rounded text-sm font-mono text-white text-right focus:outline-none focus:border-brand-cyan"
              />
            </div>
          </div>

          {/* Simulation Output */}
          {result && (
            <div className="p-4 rounded-xl bg-dark-900 border border-brand-cyan/30 space-y-3 animate-fadeIn">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-cyan flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4" /> Orchestration Chain Completed
                </span>
                <span className="text-[10px] font-mono text-slate-400">Case ID: {result.case_id}</span>
              </div>

              <div className="text-xs space-y-1 text-slate-300 font-mono">
                <div>• Calculated Recovery Score: <strong className="text-emerald-400">{result.orchestration_result?.score}%</strong></div>
                <div>• Selected Strategy: <strong className="text-brand-cyan">{result.orchestration_result?.strategy}</strong></div>
                {result.orchestration_result?.payment_link && (
                  <div>• Recovery Payment Link: <span className="text-blue-400">{result.orchestration_result.payment_link}</span></div>
                )}
              </div>

              {!result.recovered ? (
                <button
                  onClick={handleSimulatePayment}
                  disabled={loading}
                  className="w-full py-2 px-3 bg-gradient-to-r from-brand-emerald to-emerald-600 text-dark-900 font-bold text-xs rounded-lg transition shadow-glow-emerald flex items-center justify-center gap-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Simulate Customer Completing UPI Payment (Recover ₹{amount.toLocaleString()})
                </button>
              ) : (
                <div className="p-2.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 text-xs font-bold text-center flex items-center justify-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  Payment Recovered! Dashboard Updated (+₹{amount.toLocaleString()})
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-dark-800 border-t border-dark-700 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-slate-300 text-xs font-semibold rounded-lg transition">
            Close
          </button>
          <button
            onClick={handleRun}
            disabled={loading}
            className="px-5 py-2 bg-gradient-to-r from-brand-cyan to-brand-blue text-dark-900 font-bold text-xs rounded-lg shadow-glow-cyan hover:opacity-90 transition flex items-center gap-1.5"
          >
            <Play className={`w-3.5 h-3.5 fill-dark-900 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Running Multi-Agent Flow...' : 'Execute Recovery Flow'}
          </button>
        </div>
      </div>
    </div>
  );
};
