import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  change?: string;
  isPositive?: boolean;
  icon: LucideIcon;
  variant?: 'cyan' | 'emerald' | 'indigo' | 'amber' | 'rose' | 'default';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subValue,
  change,
  isPositive,
  icon: Icon,
  variant = 'default'
}) => {
  const variantStyles = {
    cyan: 'border-brand-cyan/20 from-dark-800 to-dark-850 hover:border-brand-cyan/40 shadow-glow-cyan/10',
    emerald: 'border-brand-emerald/20 from-dark-800 to-dark-850 hover:border-brand-emerald/40 shadow-glow-emerald/10',
    indigo: 'border-brand-indigo/20 from-dark-800 to-dark-850 hover:border-brand-indigo/40 shadow-glow-indigo/10',
    amber: 'border-brand-amber/20 from-dark-800 to-dark-850 hover:border-brand-amber/40',
    rose: 'border-brand-rose/20 from-dark-800 to-dark-850 hover:border-brand-rose/40',
    default: 'border-dark-700 from-dark-800 to-dark-850 hover:border-dark-600',
  };

  const iconColors = {
    cyan: 'text-brand-cyan bg-brand-cyan/10',
    emerald: 'text-brand-emerald bg-brand-emerald/10',
    indigo: 'text-brand-indigo bg-brand-indigo/10',
    amber: 'text-brand-amber bg-brand-amber/10',
    rose: 'text-brand-rose bg-brand-rose/10',
    default: 'text-slate-400 bg-dark-700',
  };

  return (
    <div className={`p-5 rounded-xl bg-gradient-to-b border transition-all duration-200 glass-card-hover ${variantStyles[variant]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-400 tracking-wide uppercase">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconColors[variant]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="flex items-baseline justify-between">
        <div className="text-2xl font-black tracking-tight text-white font-mono">{value}</div>
        {change && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            isPositive ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
          }`}>
            {change}
          </span>
        )}
      </div>

      {subValue && (
        <div className="mt-2 text-xs text-slate-400 flex items-center gap-1">
          {subValue}
        </div>
      )}
    </div>
  );
};
