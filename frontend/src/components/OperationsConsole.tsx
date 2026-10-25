import React, { useState, useEffect } from 'react';
import {
  Activity,
  Server,
  Database,
  Cpu,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RotateCcw,
  ShieldAlert,
  Layers,
  Terminal,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from './Toast';

interface WorkerStatus {
  status: string;
  is_running: boolean;
  active_processing: number;
  last_cycle_timestamp?: string;
  uptime_seconds?: number;
  consecutive_errors: number;
  queue: {
    pending_count: number;
    processing_count: number;
    retry_pending_count: number;
    dead_letter_count: number;
    oldest_pending_seconds?: number | null;
  };
}

interface DepsHealth {
  overall: string;
  dependencies: {
    database?: { status: string; mode: string };
    redis?: { status: string; mode: string };
    gemini?: { status: string; mode: string; model?: string };
    razorpay?: { status: string; mode: string };
    outbox_worker?: { status: string; queue_backlog: number; dead_letters: number };
  };
  timestamp: string;
}

export const OperationsConsole: React.FC = () => {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const canOperate = user?.role === 'ADMIN' || user?.role === 'OPERATOR';

  const [deps, setDeps] = useState<DepsHealth | null>(null);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  const [replaying, setReplaying] = useState(false);
  const [showReplayModal, setShowReplayModal] = useState(false);
  const [replayEventId, setReplayEventId] = useState('');

  const fetchOperationalData = async () => {
    setLoading(true);
    try {
      const [depsRes, workerRes] = await Promise.all([
        fetch('/health/deps'),
        fetch('/health/worker')
      ]);

      if (depsRes.ok) {
        setDeps(await depsRes.json());
      }
      if (workerRes.ok) {
        setWorker(await workerRes.json());
      }
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed fetching operational health:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperationalData();
    const interval = setInterval(fetchOperationalData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleReplaySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canOperate || !replayEventId.trim()) return;

    setReplaying(true);
    try {
      const token = localStorage.getItem('payrecover_token');
      const res = await fetch(`/api/webhooks/events/${replayEventId.trim()}/retry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Replay failed');
      }

      showSuccess('Operational Replay Queued', `Event ${replayEventId} transitioned to RETRY_PENDING.`);
      setShowReplayModal(false);
      setReplayEventId('');
      fetchOperationalData();
    } catch (err: any) {
      showError('Replay Error', err.message || 'Failed to reprocess event.');
    } finally {
      setReplaying(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    const s = (status || 'UNKNOWN').toUpperCase();
    if (s === 'HEALTHY' || s === 'CONNECTED' || s === 'READY' || s === 'ALIVE' || s === 'RUNNING') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {s}
        </span>
      );
    }
    if (s === 'DEGRADED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          DEGRADED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
        {s}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-dark-800/80 border border-dark-700">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              System Operations & Observability
              {getStatusBadge(deps?.overall || 'UNKNOWN')}
            </h4>
            <p className="text-xs text-slate-400">
              Real-time telemetry, outbox event queue health, and background worker state.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          {lastRefreshed && (
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              Refreshed: <span className="text-slate-200 font-mono">{lastRefreshed}</span>
            </span>
          )}
          <button
            onClick={fetchOperationalData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-700 hover:bg-dark-600 text-slate-200 font-semibold transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-brand-cyan' : ''}`} />
            Refresh
          </button>
          <a
            href="/metrics"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-cyan/10 hover:bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/30 font-semibold transition"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Prometheus Metrics
          </a>
        </div>
      </div>

      {/* Grid: Dependencies & Subsystems */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* PostgreSQL Database */}
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300 font-semibold text-xs">
              <Database className="w-4 h-4 text-brand-cyan" />
              Primary Database
            </div>
            {getStatusBadge(deps?.dependencies?.database?.status)}
          </div>
          <div className="text-[11px] text-slate-400">
            {deps?.dependencies?.database?.mode || 'PostgreSQL Connection Pool'}
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            pool_size: 10 | pool_recycle: 1800s
          </div>
        </div>

        {/* Redis Cache & Broker */}
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300 font-semibold text-xs">
              <Server className="w-4 h-4 text-emerald-400" />
              Redis Broker
            </div>
            {getStatusBadge(deps?.dependencies?.redis?.status)}
          </div>
          <div className="text-[11px] text-slate-400">
            {deps?.dependencies?.redis?.mode || 'Redis / In-Memory Fallback'}
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            Zero-loss local fallback active
          </div>
        </div>

        {/* AI Engine & Gemini */}
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300 font-semibold text-xs">
              <Cpu className="w-4 h-4 text-purple-400" />
              AI Reasoning Engine
            </div>
            {getStatusBadge(deps?.dependencies?.gemini?.status)}
          </div>
          <div className="text-[11px] text-slate-400">
            {deps?.dependencies?.gemini?.mode || 'Gemini 1.5 Flash'}
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            Deterministic fallback calibrated
          </div>
        </div>

        {/* Razorpay Gateway */}
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300 font-semibold text-xs">
              <ShieldAlert className="w-4 h-4 text-indigo-400" />
              Payment Gateway
            </div>
            {getStatusBadge(deps?.dependencies?.razorpay?.status)}
          </div>
          <div className="text-[11px] text-slate-400">
            Mode: {deps?.dependencies?.razorpay?.mode || 'Razorpay Test / Simulation'}
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            Authoritative verification required
          </div>
        </div>
      </div>

      {/* Background Outbox Worker Health Section */}
      <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-cyan" />
              Background Outbox Worker & Queue Telemetry
              {getStatusBadge(worker?.is_running ? 'RUNNING' : 'STOPPED')}
            </h4>
            <p className="text-xs text-slate-400">
              Continuous background job claiming with atomic database updates, exponential backoff, and crash recovery.
            </p>
          </div>

          {canOperate && (
            <button
              onClick={() => setShowReplayModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-semibold transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Replay Dead-Letter Event
            </button>
          )}
        </div>

        {/* Worker Queue Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700">
            <span className="text-[11px] text-slate-400 block mb-1">Pending Queue</span>
            <span className="text-xl font-bold font-mono text-brand-cyan">
              {worker?.queue?.pending_count ?? 0}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700">
            <span className="text-[11px] text-slate-400 block mb-1">Active Claims</span>
            <span className="text-xl font-bold font-mono text-indigo-300">
              {worker?.queue?.processing_count ?? 0}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700">
            <span className="text-[11px] text-slate-400 block mb-1">Retry Pending</span>
            <span className="text-xl font-bold font-mono text-amber-400">
              {worker?.queue?.retry_pending_count ?? 0}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-dark-800 border border-dark-700">
            <span className="text-[11px] text-slate-400 block mb-1">Dead-Letter Events</span>
            <span className="text-xl font-bold font-mono text-rose-400">
              {worker?.queue?.dead_letter_count ?? 0}
            </span>
          </div>
        </div>

        {/* Worker Diagnostics Details */}
        <div className="p-3.5 rounded-xl bg-dark-900 border border-dark-700/80 font-mono text-xs text-slate-300 space-y-1.5">
          <div className="flex justify-between">
            <span className="text-slate-500">Worker Status:</span>
            <span className="text-slate-200">{worker?.status || 'Active asyncio loop'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Consecutive Errors:</span>
            <span className={worker?.consecutive_errors ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {worker?.consecutive_errors ?? 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Oldest Pending Event Age:</span>
            <span className="text-slate-200">
              {worker?.queue?.oldest_pending_seconds
                ? `${worker.queue.oldest_pending_seconds.toFixed(1)}s`
                : '0.0s (Queue clear)'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Crash Claim Threshold:</span>
            <span className="text-slate-200">120s (Auto-recovers interrupted tasks to RETRY_PENDING)</span>
          </div>
        </div>
      </div>

      {/* Operator Replay Modal */}
      {showReplayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-md p-6 rounded-2xl bg-dark-850 border border-dark-700 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <RotateCcw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Replay Dead-Letter Event</h3>
                <p className="text-xs text-slate-400">Requires OPERATOR or ADMIN role.</p>
              </div>
            </div>

            <form onSubmit={handleReplaySubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Webhook Event ID
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. whe_dl_1234abcd"
                  value={replayEventId}
                  onChange={(e) => setReplayEventId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-700 text-slate-100 text-xs font-mono focus:border-brand-cyan focus:outline-none"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  Replays are strictly audited with operator email and timestamp.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReplayModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-dark-700 hover:bg-dark-600 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={replaying || !replayEventId.trim()}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-dark-900 text-xs font-bold transition disabled:opacity-50"
                >
                  {replaying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  Confirm Replay
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
