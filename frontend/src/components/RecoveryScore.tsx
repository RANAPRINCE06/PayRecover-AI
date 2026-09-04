import React from 'react';

interface RecoveryScoreProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
}

export const RecoveryScore: React.FC<RecoveryScoreProps> = ({ score, size = 'md' }) => {
  const getColor = () => {
    if (score >= 80) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    if (score >= 50) return 'text-brand-cyan bg-brand-cyan/10 border-brand-cyan/30';
    if (score >= 30) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
  };

  const sizeStyles = {
    sm: 'text-xs px-1.5 py-0.5 font-semibold',
    md: 'text-sm px-2 py-0.5 font-bold',
    lg: 'text-base px-3 py-1 font-extrabold',
  };

  return (
    <span className={`inline-flex items-center gap-1 rounded font-mono border ${getColor()} ${sizeStyles[size]}`}>
      {score.toFixed(0)}%
    </span>
  );
};
