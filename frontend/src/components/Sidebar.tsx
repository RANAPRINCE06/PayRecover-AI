import React from 'react';
import {
  LayoutDashboard,
  LineChart,
  CreditCard,
  Bot,
  MessageSquareCode,
  ShieldCheck,
  Settings,
  Sparkles,
  Zap
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onOpenSimulate: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, onOpenSimulate }) => {
  const navItems = [
    { id: 'command-center', label: 'Command Center', icon: LayoutDashboard },
    { id: 'intelligence', label: 'Recovery Intelligence', icon: LineChart },
    { id: 'payments', label: 'Payments', icon: CreditCard },
    { id: 'agent-activity', label: 'AI Agent Activity', icon: Bot, badge: 'LIVE' },
    { id: 'copilot', label: 'AI Copilot', icon: MessageSquareCode, badge: 'AI' },
    { id: 'guardrails', label: 'Guardrails', icon: ShieldCheck },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-dark-850 border-r border-dark-700 flex flex-col justify-between shrink-0 select-none">
      {/* Brand Header */}
      <div>
        <div className="h-16 px-6 flex items-center gap-3 border-b border-dark-700">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-cyan to-brand-indigo flex items-center justify-center shadow-glow-cyan text-dark-900 font-bold">
            <Zap className="w-5 h-5 fill-dark-900 text-dark-900" />
          </div>
          <div>
            <div className="font-extrabold tracking-tight text-white flex items-center gap-1.5 text-base">
              PAYRECOVER<span className="text-brand-cyan font-mono text-xs px-1.5 py-0.5 rounded bg-brand-cyan/10 border border-brand-cyan/30">AI</span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">Autonomous Revenue Recovery</p>
          </div>
        </div>

        {/* Navigation items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20 shadow-glow-cyan/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-brand-cyan' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    item.badge === 'LIVE' ? 'bg-emerald-500/20 text-emerald-400 animate-pulse' : 'bg-brand-indigo/30 text-indigo-300'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Sandbox / Demo CTA */}
      <div className="p-4 border-t border-dark-700">
        <div className="bg-gradient-to-b from-dark-800 to-dark-750 p-3.5 rounded-xl border border-dark-600">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-brand-cyan" />
            <span className="text-xs font-semibold text-white">Interactive Sandbox</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
            Run realistic Razorpay Test failure scenarios & watch autonomous multi-agent recovery.
          </p>
          <button
            onClick={onOpenSimulate}
            className="w-full py-2 px-3 bg-gradient-to-r from-brand-cyan to-brand-blue hover:opacity-90 text-dark-900 font-semibold text-xs rounded-lg transition shadow-glow-cyan flex items-center justify-center gap-1.5"
          >
            <Zap className="w-3.5 h-3.5 fill-dark-900" />
            Launch Simulation
          </button>
        </div>
      </div>
    </aside>
  );
};
