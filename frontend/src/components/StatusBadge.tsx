import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'payment' | 'recovery' | 'action' | 'intent';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getStyle = () => {
    switch (status.toUpperCase()) {
      case 'SUCCESS':
      case 'RECOVERED':
      case 'APPROVED':
      case 'EXECUTED':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'FAILED':
      case 'REJECTED':
      case 'BLOCKED_BY_GUARDRAIL':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      case 'AWAITING_HUMAN_APPROVAL':
      case 'PRICE_OBJECTION':
      case 'PAY_LATER':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'ACTION_IN_PROGRESS':
      case 'INVESTIGATING':
      case 'STRATEGY_SELECTED':
      case 'ALTERNATE_PAYMENT_METHOD':
        return 'bg-brand-cyan/15 text-brand-cyan border-brand-cyan/30';
      default:
        return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
    }
  };

  const formatted = status.replace(/_/g, ' ');

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border uppercase tracking-wider ${getStyle()}`}>
      {formatted}
    </span>
  );
};
