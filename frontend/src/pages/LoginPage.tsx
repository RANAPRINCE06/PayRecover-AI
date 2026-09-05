import React, { useState } from 'react';
import {
  Zap,
  Lock,
  Mail,
  Shield,
  ArrowRight,
  AlertCircle,
  Loader2,
  CheckCircle2,
  KeyRound
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/Toast';

const DEMO_ACCOUNTS = [
  {
    role: 'ADMIN',
    label: 'Sarah Chen (Admin)',
    email: 'admin@payrecover.ai',
    password: 'Admin@123',
    badge: 'FULL ACCESS',
    badgeColor: 'border-brand-cyan/40 bg-brand-cyan/10 text-brand-cyan',
    desc: 'Manage users, guardrails, approvals, recovery execution'
  },
  {
    role: 'OPERATOR',
    label: 'Priya Nair (Operator)',
    email: 'operator@payrecover.ai',
    password: 'Operator@123',
    badge: 'RECOVERY OPS',
    badgeColor: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
    desc: 'Execute recovery tools, inspect cases, view audit trails'
  },
  {
    role: 'ANALYST',
    label: 'Dev Sharma (Analyst)',
    email: 'analyst@payrecover.ai',
    password: 'Analyst@123',
    badge: 'ANALYTICS READ-ONLY',
    badgeColor: 'border-brand-indigo/40 bg-brand-indigo/10 text-indigo-300',
    desc: 'Explore intelligence charts, failure telemetry, recovery trends'
  },
  {
    role: 'VIEWER',
    label: 'Rohan Mehta (Viewer)',
    email: 'viewer@payrecover.ai',
    password: 'Viewer@123',
    badge: 'READ-ONLY',
    badgeColor: 'border-slate-600 bg-dark-700 text-slate-400',
    desc: 'General monitoring, view payments & dashboard KPIs'
  }
];

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { showSuccess, showError } = useToast();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setErrorMessage('Both email and password are required.');
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const loggedUser = await login({ email: email.trim(), password: password.trim() });
      showSuccess('Signed In', `Welcome back, ${loggedUser.name} (${loggedUser.role})`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Invalid credentials. Please verify and try again.');
      showError('Authentication Failed', err.message || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDemo = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setErrorMessage(null);
  };

  return (
    <div className="min-h-screen w-screen bg-dark-900 flex flex-col justify-center items-center p-6 select-none relative overflow-hidden font-sans">
      {/* Background radial glow */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-cyan/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-brand-indigo/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-md w-full space-y-6 relative z-10 animate-fadeIn">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-cyan to-brand-indigo shadow-glow-cyan mb-2">
            <Zap className="w-6 h-6 fill-dark-900 text-dark-900" />
          </div>
          <div className="text-2xl font-black text-white tracking-tight flex items-center justify-center gap-1.5">
            PAYRECOVER
            <span className="text-brand-cyan font-mono text-xs px-1.5 py-0.5 rounded bg-brand-cyan/10 border border-brand-cyan/30">
              AI
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Enterprise Autonomous Revenue Recovery Platform
          </p>
        </div>

        {/* Login Card */}
        <div className="p-6 rounded-2xl bg-dark-850 border border-dark-700 shadow-2xl space-y-5">
          <div>
            <h2 className="text-sm font-bold text-white">Merchant Console Sign In</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">Enter your credentials to access recovery operations.</p>
          </div>

          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2 text-xs text-rose-300 animate-shake">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Work Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Account Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-brand-cyan to-brand-indigo text-dark-900 font-bold text-xs rounded-xl shadow-glow-cyan hover:opacity-95 transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Verifying Credentials...
                </>
              ) : (
                <>
                  <span>Sign In to Console</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Role Switcher */}
          <div className="pt-4 border-t border-dark-700/60 space-y-2.5">
            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span className="flex items-center gap-1">
                <KeyRound className="w-3 h-3 text-brand-cyan" />
                QUICK DEMO ROLES
              </span>
              <span>1-Click Switch</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.role}
                  type="button"
                  onClick={() => handleSelectDemo(acc.email, acc.password)}
                  className={`p-2 rounded-xl text-left border transition ${
                    email === acc.email
                      ? 'bg-dark-800 border-brand-cyan shadow-glow-cyan/20'
                      : 'bg-dark-800/60 border-dark-700 hover:border-dark-600 hover:bg-dark-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-bold text-white truncate">{acc.label.split(' ')[0]}</span>
                    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border ${acc.badgeColor}`}>
                      {acc.role}
                    </span>
                  </div>
                  <p className="text-[9px] text-slate-500 leading-tight truncate">
                    {acc.email}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Security badge footer */}
        <div className="text-center text-[10px] text-slate-500 flex items-center justify-center gap-1.5 font-mono">
          <Shield className="w-3.5 h-3.5 text-brand-emerald" />
          <span>Secured via bcrypt + HS256 JWT RBAC Authorization</span>
        </div>
      </div>
    </div>
  );
};
