import React, { useState, useEffect } from 'react';
import { ShieldCheck, AlertCircle, Save, CheckCircle2, Lock, Sliders, Moon, Ban } from 'lucide-react';
import { Guardrails } from '../types';
import { api } from '../services/api';

export const GuardrailsPage: React.FC = () => {
  const [guardrails, setGuardrails] = useState<Guardrails>({
    merchant_id: 'merchant_primary',
    max_retries: 3,
    max_discount_percentage: 10,
    max_campaign_days: 3,
    quiet_hours_start: '22:00',
    quiet_hours_end: '08:00',
    high_value_threshold: 50000,
    human_approval_required: true,
    max_contact_attempts: 4
  });

  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getGuardrails().then((res) => {
      if (res) setGuardrails(res);
    });
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      const updated = await api.updateGuardrails(guardrails);
      setGuardrails(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert(`Failed to save guardrails: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-brand-emerald" />
            Merchant Recovery Guardrails
          </h2>
          <p className="text-xs text-slate-400">
            Define strict autonomous boundaries. The Tool Executor enforces these rules before executing any AI agent action.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          className="px-5 py-2.5 bg-gradient-to-r from-brand-emerald to-emerald-600 text-dark-900 font-bold text-xs rounded-xl shadow-glow-emerald hover:opacity-90 transition flex items-center gap-2"
        >
          {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          <span>{saved ? 'Guardrails Saved!' : 'Save Changes'}</span>
        </button>
      </div>

      {/* Guardrail Policy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 1. High-Value Threshold & Human Approval */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">High-Value Approval Threshold</h3>
              <p className="text-[11px] text-slate-400">Escalate large transactions to human merchant review</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-300">Transaction Threshold (INR)</label>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-sm font-mono font-bold text-brand-cyan">₹</span>
                <input
                  type="number"
                  value={guardrails.high_value_threshold}
                  onChange={(e) => setGuardrails({ ...guardrails, high_value_threshold: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-brand-cyan"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-dark-800 border border-dark-700">
              <span className="text-xs text-slate-300 font-medium">Require Human Review & Approval</span>
              <input
                type="checkbox"
                checked={guardrails.human_approval_required}
                onChange={(e) => setGuardrails({ ...guardrails, human_approval_required: e.target.checked })}
                className="w-4 h-4 accent-brand-cyan rounded cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* 2. Maximum Discount Guardrail */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-rose/10 border border-brand-rose/20 flex items-center justify-center text-brand-rose">
              <Ban className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Maximum Discount Limit</h3>
              <p className="text-[11px] text-slate-400">Cap autonomous recovery incentive discounts</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 font-medium">Max Allowable Discount:</span>
                <span className="font-mono font-bold text-brand-rose">{guardrails.max_discount_percentage}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="25"
                step="1"
                value={guardrails.max_discount_percentage}
                onChange={(e) => setGuardrails({ ...guardrails, max_discount_percentage: Number(e.target.value) })}
                className="w-full accent-brand-rose cursor-pointer"
              />
            </div>

            <div className="p-3 rounded-xl bg-dark-800 text-[11px] text-slate-400 leading-relaxed border border-dark-700">
              Discounts proposed by AI Strategist above this ceiling are automatically blocked by the Tool Executor.
            </div>
          </div>
        </div>

        {/* 3. Retries & Contact Limits */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-indigo/10 border border-brand-indigo/20 flex items-center justify-center text-brand-indigo">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Retry & Frequency Controls</h3>
              <p className="text-[11px] text-slate-400">Prevent customer fatigue and repeated spam</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-slate-400">Max Gateway Retries</label>
              <input
                type="number"
                min="1"
                max="5"
                value={guardrails.max_retries}
                onChange={(e) => setGuardrails({ ...guardrails, max_retries: Number(e.target.value) })}
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-brand-indigo"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400">Max Customer Messages</label>
              <input
                type="number"
                min="1"
                max="6"
                value={guardrails.max_contact_attempts}
                onChange={(e) => setGuardrails({ ...guardrails, max_contact_attempts: Number(e.target.value) })}
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-brand-indigo"
              />
            </div>
          </div>
        </div>

        {/* 4. Quiet Hours */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-amber/10 border border-brand-amber/20 flex items-center justify-center text-brand-amber">
              <Moon className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Customer Quiet Hours</h3>
              <p className="text-[11px] text-slate-400">Halt outbound WhatsApp/SMS during late night hours</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-slate-400">Quiet Hours Start</label>
              <input
                type="time"
                value={guardrails.quiet_hours_start}
                onChange={(e) => setGuardrails({ ...guardrails, quiet_hours_start: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-brand-amber"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400">Quiet Hours End</label>
              <input
                type="time"
                value={guardrails.quiet_hours_end}
                onChange={(e) => setGuardrails({ ...guardrails, quiet_hours_end: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-brand-amber"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
