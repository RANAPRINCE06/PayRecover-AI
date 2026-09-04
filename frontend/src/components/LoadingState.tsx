import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading live telemetry...' }) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <Loader2 className="w-8 h-8 text-brand-cyan animate-spin mb-3" />
      <p className="text-sm font-medium text-slate-400 font-mono">{message}</p>
    </div>
  );
};

export const EmptyState: React.FC<{ title: string; description: string; actionLabel?: string; onAction?: () => void }> = ({
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl bg-dark-850 border border-dark-700">
      <div className="w-12 h-12 rounded-full bg-dark-750 border border-dark-600 flex items-center justify-center text-slate-400 mb-3">
        🔍
      </div>
      <h3 className="text-sm font-bold text-slate-200">{title}</h3>
      <p className="text-xs text-slate-400 mt-1 max-w-sm">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-4 py-2 bg-dark-700 hover:bg-dark-600 text-brand-cyan text-xs font-semibold rounded-lg transition"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
