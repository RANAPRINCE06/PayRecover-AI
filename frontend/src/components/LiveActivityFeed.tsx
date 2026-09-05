import React, { useState, useEffect, useRef } from 'react';
import {
  Radio,
  Clock,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Bot,
  BrainCircuit,
  MessageSquare,
  ShieldCheck,
  Pause,
  Play,
  RotateCcw
} from 'lucide-react';
import { RealtimeEvent } from '../types';
import { api } from '../services/api';

const EVENT_CONFIG: Record<string, { icon: React.FC<any>; color: string; bg: string }> = {
  PAYMENT_FAILED: { icon: AlertTriangle, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/30' },
  CASE_CREATED: { icon: Zap, color: 'text-brand-cyan', bg: 'bg-brand-cyan/10 border-brand-cyan/30' },
  AI_ANALYSIS_STARTED: { icon: Bot, color: 'text-brand-indigo', bg: 'bg-brand-indigo/10 border-brand-indigo/30' },
  AI_ANALYSIS_COMPLETED: { icon: CheckCircle2, color: 'text-brand-cyan', bg: 'bg-brand-cyan/10 border-brand-cyan/30' },
  INTENT_DETECTED: { icon: MessageSquare, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  STRATEGY_GENERATED: { icon: BrainCircuit, color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/30' },
  RECOVERY_STARTED: { icon: Zap, color: 'text-brand-cyan', bg: 'bg-brand-cyan/10 border-brand-cyan/30' },
  RECOVERY_EXECUTED: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' },
  PAYMENT_RECOVERED: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/20 border-emerald-500/40' },
  HUMAN_APPROVAL_REQUIRED: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/20 border-amber-500/40' },
  RECOVERY_BLOCKED: { icon: AlertTriangle, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/30' },
  RECOVERY_SETTLED: { icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/20 border-emerald-500/40' }
};

interface LiveActivityFeedProps {
  maxItems?: number;
  onSelectCaseId?: (caseId: string) => void;
}

export const LiveActivityFeed: React.FC<LiveActivityFeedProps> = ({ maxItems = 20, onSelectCaseId }) => {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // 1. Initial Load of recent events
  useEffect(() => {
    let mounted = true;
    api.getRecentEvents(maxItems)
      .then((recent) => {
        if (mounted && recent && recent.length > 0) {
          setEvents(recent);
        }
      })
      .catch((err) => console.warn('Could not load recent events:', err));

    return () => {
      mounted = false;
    };
  }, [maxItems]);

  // 2. Establish SSE connection
  useEffect(() => {
    if (isPaused) return;

    const sse = new EventSource('/api/events/stream');
    eventSourceRef.current = sse;

    sse.onopen = () => {
      setIsConnected(true);
    };

    sse.addEventListener('message', (e) => {
      try {
        const newEvt: RealtimeEvent = JSON.parse(e.data);
        setEvents((prev) => [newEvt, ...prev.slice(0, maxItems - 1)]);
      } catch (err) {
        console.warn('Error parsing incoming SSE event:', err);
      }
    });

    sse.addEventListener('connected', () => {
      setIsConnected(true);
    });

    sse.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects automatically
    };

    return () => {
      sse.close();
      setIsConnected(false);
    };
  }, [isPaused, maxItems]);

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);

  return (
    <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dark-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Live Operations Telemetry
            </h3>
          </div>
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-dark-800 text-slate-400 border border-dark-700">
            SSE {isConnected ? 'STREAMING' : 'CONNECTING'}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`p-1.5 rounded-lg border text-xs transition ${
              isPaused
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                : 'bg-dark-800 border-dark-700 text-slate-400 hover:text-white'
            }`}
            title={isPaused ? 'Resume live feed' : 'Pause live feed'}
          >
            {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
          </button>
          <button
            onClick={() => setEvents([])}
            className="p-1.5 rounded-lg border border-dark-700 bg-dark-800 text-slate-400 hover:text-white transition"
            title="Clear feed"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Streaming Event Items */}
      <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500 font-mono">
            Awaiting real-time payment telemetry events...
          </div>
        ) : (
          events.map((evt) => {
            const conf = EVENT_CONFIG[evt.type] || {
              icon: Zap,
              color: 'text-brand-cyan',
              bg: 'bg-dark-800 border-dark-700'
            };
            const Icon = conf.icon;

            return (
              <div
                key={evt.id}
                onClick={() => evt.case_id && onSelectCaseId && onSelectCaseId(evt.case_id)}
                className={`p-2.5 rounded-xl border transition-all ${
                  evt.case_id ? 'cursor-pointer hover:border-brand-cyan/50' : ''
                } ${conf.bg}`}
              >
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <div className="flex items-center gap-1.5">
                    <Icon className={`w-3.5 h-3.5 ${conf.color} shrink-0`} />
                    <span className="font-bold text-white font-sans text-xs">
                      {evt.message}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-slate-400 font-mono shrink-0 ml-2">
                    <Clock className="w-3 h-3" />
                    <span>{formatTime(evt.timestamp)}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono pt-1 border-t border-dark-700/40">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.2 rounded bg-dark-900 border border-dark-700 text-slate-300">
                      {evt.type.replace(/_/g, ' ')}
                    </span>
                    {evt.case_id && (
                      <span className="text-brand-cyan hover:underline">
                        {evt.case_id}
                      </span>
                    )}
                  </div>

                  {evt.amount ? (
                    <span className="font-bold text-emerald-400">
                      {formatCurrency(evt.amount)}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
