import React, { useState } from 'react';
import { Settings, Key, Shield, Database, Server, CheckCircle2, Copy } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [copied, setCopied] = useState(false);

  const webhookUrl = 'http://localhost:8000/api/recovery/webhook';

  const handleCopy = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl space-y-6 animate-fadeIn">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-brand-cyan" />
          Integration Settings & Gateway Configuration
        </h2>
        <p className="text-xs text-slate-400">
          Manage Razorpay Test Mode keys, API webhooks, and backend infrastructure status.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Razorpay Test Config */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan">
              <Key className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Razorpay Test Mode</h3>
              <p className="text-[11px] text-slate-400">API credentials for payment verification</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-300">Key ID</label>
              <input
                type="text"
                readOnly
                value="rzp_test_sample_key_12345"
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-slate-300 select-all"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300">Key Secret</label>
              <input
                type="password"
                readOnly
                value="••••••••••••••••••••••••"
                className="mt-1 w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-slate-400"
              />
            </div>

            <div className="p-3 rounded-xl bg-dark-800 border border-dark-700 text-[11px] text-slate-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Safe sandbox mock engine active when keys are unset</span>
            </div>
          </div>
        </div>

        {/* Webhook Configuration */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
          <div className="flex items-center gap-2.5 text-slate-200">
            <div className="w-8 h-8 rounded-lg bg-brand-indigo/10 border border-brand-indigo/20 flex items-center justify-center text-brand-indigo">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold">Webhook Listener Endpoint</h3>
              <p className="text-[11px] text-slate-400">Receives real-time payment failure and settlement events</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-300">Webhook URL</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={webhookUrl}
                  className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-xs font-mono text-brand-cyan select-all"
                />
                <button
                  onClick={handleCopy}
                  className="p-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 transition"
                  title="Copy"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              {copied && <span className="text-[10px] text-emerald-400 font-semibold mt-1 inline-block">Copied to clipboard!</span>}
            </div>

            <div className="p-3 rounded-xl bg-dark-800 border border-dark-700 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold text-slate-200">Subscribed Events:</div>
              <div>• payment.failed</div>
              <div>• payment.authorized</div>
              <div>• payment_link.paid</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
