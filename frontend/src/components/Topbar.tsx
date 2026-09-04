import React from 'react';
import { ShieldCheck, Activity, Bell, RefreshCw } from 'lucide-react';

interface TopbarProps {
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({ onRefresh, isRefreshing }) => {
  return (
    <header className="h-16 px-8 bg-dark-850/80 backdrop-blur-md border-b border-dark-700 flex items-center justify-between sticky top-0 z-30">
      {/* Merchant Context */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-800 border border-dark-700">
          <div className="w-2.5 h-2.5 rounded-full bg-brand-emerald animate-ping" />
          <span className="text-xs font-semibold text-slate-300">BharatTech Commerce Ltd.</span>
          <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 bg-dark-700 text-slate-400 rounded">
            RZP Test Mode
          </span>
        </div>

        <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-brand-emerald" />
          <span>Autonomous Guardrails: <strong className="text-emerald-400">Enforced</strong></span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-xs font-medium text-slate-300 transition"
          title="Refresh Data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-brand-cyan' : 'text-slate-400'}`} />
          <span>{isRefreshing ? 'Syncing...' : 'Sync Telemetry'}</span>
        </button>

        <div className="h-4 w-px bg-dark-700" />

        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-indigo to-brand-cyan flex items-center justify-center text-xs font-bold text-white shadow-sm">
            BC
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-semibold text-slate-200">Merchant Admin</div>
            <div className="text-[10px] text-slate-500">payments@bharattech.in</div>
          </div>
        </div>
      </div>
    </header>
  );
};
