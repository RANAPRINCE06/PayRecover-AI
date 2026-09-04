import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, duration?: number, title?: string) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  warning: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
  showSuccess: (title: string, message?: string) => void;
  showError: (title: string, message?: string) => void;
  showWarning: (title: string, message?: string) => void;
  showInfo: (title: string, message?: string) => void;
}

// ─── Context ─────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}

// ─── Single Toast Item ────────────────────────────────────────────────────────

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration ?? 4000);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  const styles: Record<ToastType, { icon: React.FC<any>; bg: string; border: string; text: string; iconColor: string }> = {
    success: { icon: CheckCircle2, bg: 'bg-dark-850', border: 'border-emerald-500/40', text: 'text-emerald-300', iconColor: 'text-emerald-400' },
    error:   { icon: XCircle,      bg: 'bg-dark-850', border: 'border-rose-500/40',    text: 'text-rose-300',    iconColor: 'text-rose-400' },
    warning: { icon: AlertTriangle, bg: 'bg-dark-850', border: 'border-amber-500/40',  text: 'text-amber-300',   iconColor: 'text-amber-400' },
    info:    { icon: Info,          bg: 'bg-dark-850', border: 'border-brand-cyan/40', text: 'text-brand-cyan',  iconColor: 'text-brand-cyan' },
  };

  const s = styles[toast.type];
  const Icon = s.icon;

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl border ${s.bg} ${s.border} shadow-2xl min-w-[300px] max-w-sm animate-slideInRight`}
    >
      <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${s.iconColor}`} />
      <div className="flex-1 min-w-0">
        {toast.title && (
          <div className="text-xs font-bold text-white mb-0.5">{toast.title}</div>
        )}
        <div className={`text-xs ${toast.title ? 'text-slate-300' : s.text} leading-relaxed`}>
          {toast.message}
        </div>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-slate-500 hover:text-slate-300 transition flex-shrink-0 mt-0.5"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'info', duration = 4000, title?: string) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts(prev => [...prev.slice(-4), { id, type, message, duration, title }]);
  }, []);

  const success = useCallback((msg: string, title?: string) => toast(msg, 'success', 4000, title), [toast]);
  const error   = useCallback((msg: string, title?: string) => toast(msg, 'error', 4000, title),   [toast]);
  const warning = useCallback((msg: string, title?: string) => toast(msg, 'warning', 4000, title), [toast]);
  const info    = useCallback((msg: string, title?: string) => toast(msg, 'info', 4000, title),    [toast]);

  const showSuccess = useCallback((title: string, msg = '') => toast(msg || title, 'success', 4000, msg ? title : undefined), [toast]);
  const showError   = useCallback((title: string, msg = '') => toast(msg || title, 'error', 4000, msg ? title : undefined),   [toast]);
  const showWarning = useCallback((title: string, msg = '') => toast(msg || title, 'warning', 4000, msg ? title : undefined), [toast]);
  const showInfo    = useCallback((title: string, msg = '') => toast(msg || title, 'info', 4000, msg ? title : undefined),    [toast]);

  return (
    <ToastContext.Provider value={{ toast, success, error, warning, info, showSuccess, showError, showWarning, showInfo }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
