import React from 'react';
import { ShieldCheck, Activity, RefreshCw, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from './Toast';

interface TopbarProps {
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({ onRefresh, isRefreshing }) => {
  const { user, logout } = useAuth();
  const { showInfo } = useToast();

  const handleLogout = () => {
    logout();
    showInfo('Logged Out', 'You have been signed out of PayRecover AI.');
  };

  const getRoleBadgeStyle = (role?: string) => {
    switch (role) {
      case 'ADMIN':
        return 'border-brand-cyan/40 bg-brand-cyan/10 text-brand-cyan';
      case 'OPERATOR':
        return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400';
      case 'ANALYST':
        return 'border-brand-indigo/40 bg-brand-indigo/10 text-indigo-300';
      default:
        return 'border-slate-600 bg-dark-700 text-slate-400';
    }
  };

  const getInitials = (name?: string) => {
    if (!name) return 'PR';
    const parts = name.split(' ');
    return parts.length > 1 ? `${parts[0][0]}${parts[1][0]}`.toUpperCase() : name.substring(0, 2).toUpperCase();
  };

  return (
    <header className="h-16 px-6 md:px-8 bg-dark-850/80 backdrop-blur-md border-b border-dark-700 flex items-center justify-between sticky top-0 z-30">
      {/* Merchant Context */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-800 border border-dark-700">
          <div className="w-2 h-2 rounded-full bg-brand-emerald animate-ping" />
          <span className="text-xs font-semibold text-slate-300">BharatTech Commerce Ltd.</span>
          <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 bg-dark-700 text-slate-400 rounded">
            RZP Test Mode
          </span>
        </div>

        <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-brand-emerald" />
          <span>Guardrails: <strong className="text-emerald-400">Enforced</strong></span>
        </div>
      </div>

      {/* Actions & User Profile */}
      <div className="flex items-center gap-3">
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-xs font-medium text-slate-300 transition"
          title="Refresh Data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-brand-cyan' : 'text-slate-400'}`} />
          <span className="hidden sm:inline">{isRefreshing ? 'Syncing...' : 'Sync Telemetry'}</span>
        </button>

        <div className="h-4 w-px bg-dark-700" />

        {/* Authenticated User Capsule */}
        {user ? (
          <div className="flex items-center gap-2.5 pl-1">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-indigo to-brand-cyan flex items-center justify-center text-xs font-bold text-dark-900 shadow-sm font-mono">
              {getInitials(user.name)}
            </div>

            <div className="hidden lg:block text-left">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold text-slate-200 truncate max-w-[130px]">{user.name}</span>
                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${getRoleBadgeStyle(user.role)}`}>
                  {user.role}
                </span>
              </div>
              <div className="text-[10px] text-slate-500 truncate max-w-[140px] font-mono">{user.email}</div>
            </div>

            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg bg-dark-800 hover:bg-rose-500/10 border border-dark-700 hover:border-rose-500/30 text-slate-400 hover:text-rose-400 transition"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="text-xs text-slate-500 font-mono">Guest</div>
        )}
      </div>
    </header>
  );
};
