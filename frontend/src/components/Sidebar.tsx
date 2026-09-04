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
  Zap,
  FolderKanban,
  FlaskConical,
  Activity
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onOpenSimulate: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.FC<any>;
  badge?: string;
}

interface NavGroup {
  groupLabel: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    groupLabel: '',
    items: [
      { id: 'command-center', label: 'Command Center', icon: LayoutDashboard },
    ]
  },
  {
    groupLabel: 'RECOVERY',
    items: [
      { id: 'recovery-cases', label: 'Recovery Cases', icon: FolderKanban },
      { id: 'payments', label: 'Payments', icon: CreditCard },
      { id: 'intelligence', label: 'Recovery Intelligence', icon: LineChart },
    ]
  },
  {
    groupLabel: 'AI',
    items: [
      { id: 'agent-activity', label: 'Agent Activity', icon: Bot, badge: 'LIVE' },
      { id: 'copilot', label: 'AI Copilot', icon: MessageSquareCode, badge: 'AI' },
    ]
  },
  {
    groupLabel: 'OPERATIONS',
    items: [
      { id: 'guardrails', label: 'Guardrails', icon: ShieldCheck },
      { id: 'demo-center', label: 'Demo Center', icon: FlaskConical },
    ]
  },
  {
    groupLabel: 'SYSTEM',
    items: [
      { id: 'settings', label: 'Settings', icon: Settings },
    ]
  }
];

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, onOpenSimulate }) => {
  return (
    <aside className="w-60 bg-dark-850 border-r border-dark-700 flex flex-col justify-between shrink-0 select-none">
      {/* Brand Header */}
      <div className="flex-1 overflow-y-auto">
        <div className="h-14 px-5 flex items-center gap-3 border-b border-dark-700">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-cyan to-brand-indigo flex items-center justify-center shadow-glow-cyan">
            <Zap className="w-4 h-4 fill-dark-900 text-dark-900" />
          </div>
          <div>
            <div className="font-extrabold tracking-tight text-white flex items-center gap-1.5 text-sm">
              PAYRECOVER
              <span className="text-brand-cyan font-mono text-[10px] px-1 py-0.5 rounded bg-brand-cyan/10 border border-brand-cyan/30">
                AI
              </span>
            </div>
            <p className="text-[9px] text-slate-500 font-medium uppercase tracking-wider">
              Revenue Recovery
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-2.5 space-y-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.groupLabel || 'root'}>
              {group.groupLabel && (
                <div className="px-2 mb-1.5">
                  <span className="text-[9px] font-bold text-slate-600 uppercase tracking-widest">
                    {group.groupLabel}
                  </span>
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                        isActive
                          ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-brand-cyan' : 'text-slate-500'}`} />
                        <span>{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          item.badge === 'LIVE'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 animate-pulse'
                            : 'bg-brand-indigo/20 text-indigo-300 border border-brand-indigo/20'
                        }`}>
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Bottom CTA */}
      <div className="p-3 border-t border-dark-700">
        <div className="bg-dark-800 p-3 rounded-xl border border-dark-700">
          <div className="flex items-center gap-2 mb-1.5">
            <Activity className="w-3.5 h-3.5 text-brand-cyan" />
            <span className="text-[11px] font-semibold text-white">Demo Center</span>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed mb-2.5">
            5 live recovery scenarios with full pipeline execution.
          </p>
          <button
            onClick={() => setActiveTab('demo-center')}
            className="w-full py-1.5 px-2 bg-gradient-to-r from-brand-cyan/20 to-brand-indigo/20 border border-brand-cyan/25 hover:border-brand-cyan/50 text-brand-cyan font-semibold text-[11px] rounded-lg transition flex items-center justify-center gap-1.5"
          >
            <FlaskConical className="w-3 h-3" />
            Open Demo Center
          </button>
        </div>
      </div>
    </aside>
  );
};
