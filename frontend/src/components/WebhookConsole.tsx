import React, { useState, useEffect } from 'react';
import {
  Radio,
  CheckCircle2,
  AlertCircle,
  Clock,
  RotateCw,
  RefreshCw,
  Eye,
  ShieldAlert,
  Search,
  Filter,
  X,
  Copy,
  ExternalLink,
  Layers,
  ArrowRight,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { WebhookEventItem, WebhookHealth } from '../types';

export const WebhookConsole: React.FC = () => {
  const { user } = useAuth();
  const canOperate = user?.role === 'ADMIN' || user?.role === 'OPERATOR';

  const [health, setHealth] = useState<WebhookHealth | null>(null);
  const [events, setEvents] = useState<WebhookEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [limit] = useState(15);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<WebhookEventItem | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const data = await api.getWebhookHealth();
      setHealth(data);
    } catch (err) {
      console.warn('Could not load webhook health:', err);
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchEvents = async (pageNumber = 1) => {
    setLoading(true);
    try {
      const res = await api.getWebhookEvents(pageNumber, limit, statusFilter || undefined, eventTypeFilter || undefined);
      setEvents(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      setPage(res.page);
    } catch (err: any) {
      console.error('Failed to load webhook events:', err);
      setActionMessage({ type: 'error', text: err?.message || 'Failed to fetch webhook events.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  useEffect(() => {
    fetchEvents(page);
  }, [page, statusFilter, eventTypeFilter]);

  const handleRetry = async (eventId: string) => {
    if (!canOperate) return;
    setRetryingId(eventId);
    setActionMessage(null);
    try {
      const res = await api.retryWebhookEvent(eventId);
      setActionMessage({ type: 'success', text: res.message || `Event ${eventId} reprocessed successfully.` });
      await fetchEvents(page);
      await fetchHealth();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err?.message || `Failed to reprocess event ${eventId}.` });
    } finally {
      setRetryingId(null);
    }
  };

  const handleSweep = async () => {
    if (!canOperate) return;
    setSweeping(true);
    setActionMessage(null);
    try {
      const res = await api.sweepWebhooks(120, 20);
      setActionMessage({
        type: 'success',
        text: `Sweep complete: ${res.stale_events_recovered} stale event(s) recovered, ${res.retries_processed} retry job(s) processed.`
      });
      await fetchEvents(1);
      await fetchHealth();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err?.message || 'Failed to trigger worker sweep.' });
    } finally {
      setSweeping(false);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PROCESSED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> PROCESSED
          </span>
        );
      case 'PROCESSING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse">
            <RotateCw className="w-3 h-3 animate-spin" /> PROCESSING
          </span>
        );
      case 'RETRY_PENDING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3 h-3" /> RETRY_PENDING
          </span>
        );
      case 'DEAD_LETTER':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <ShieldAlert className="w-3 h-3" /> DEAD_LETTER
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3 h-3" /> FAILED
          </span>
        );
      case 'RECEIVED':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-300 border border-slate-500/20">
            <Radio className="w-3 h-3" /> RECEIVED
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Notification */}
      {actionMessage && (
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between text-xs animate-fadeIn ${
            actionMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-slate-400 hover:text-slate-200 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-[11px]">
            <span>Total Ingested</span>
            <Radio className="w-3.5 h-3.5 text-brand-cyan" />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-white">
            {healthLoading ? '...' : health?.total_received ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Durable Outbox</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-[11px]">
            <span>Processed</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-emerald-400">
            {healthLoading ? '...' : health?.total_processed ?? 0}
          </div>
          <div className="text-[10px] text-emerald-500/70 mt-1">Settled & Completed</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-[11px]">
            <span>In Processing</span>
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-cyan-400">
            {healthLoading ? '...' : health?.total_pending ?? 0}
          </div>
          <div className="text-[10px] text-cyan-500/70 mt-1">Queue & Retry Buffer</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-[11px]">
            <span>Failed Retries</span>
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-amber-400">
            {healthLoading ? '...' : health?.total_failed ?? 0}
          </div>
          <div className="text-[10px] text-amber-500/70 mt-1">Bounded Exponential</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-[11px]">
            <span>Dead Letter</span>
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-rose-400">
            {healthLoading ? '...' : health?.total_dead_letter ?? 0}
          </div>
          <div className="text-[10px] text-rose-500/70 mt-1">Exhausted Max Retries</div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-dark-850 border border-dark-700">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs text-slate-300">
            <Filter className="w-3.5 h-3.5 text-brand-cyan" />
            <span className="font-semibold">Filter Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter events by processing status"
            className="px-3 py-1.5 rounded-lg bg-dark-800 border border-dark-700 text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-cyan"
          >
            <option value="">All Statuses</option>
            <option value="RECEIVED">RECEIVED</option>
            <option value="PROCESSING">PROCESSING</option>
            <option value="PROCESSED">PROCESSED</option>
            <option value="RETRY_PENDING">RETRY_PENDING</option>
            <option value="FAILED">FAILED</option>
            <option value="DEAD_LETTER">DEAD_LETTER</option>
          </select>

          <select
            value={eventTypeFilter}
            onChange={(e) => {
              setEventTypeFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter events by Razorpay lifecycle event type"
            className="px-3 py-1.5 rounded-lg bg-dark-800 border border-dark-700 text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-cyan"
          >
            <option value="">All Event Types</option>
            <option value="payment.failed">payment.failed</option>
            <option value="payment.authorized">payment.authorized</option>
            <option value="payment.captured">payment.captured</option>
            <option value="payment_link.paid">payment_link.paid</option>
            <option value="payment_link.expired">payment_link.expired</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          {canOperate && (
            <button
              onClick={handleSweep}
              disabled={sweeping}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 hover:border-slate-500 transition disabled:opacity-50"
              title="Recover crashed workers and execute due retry backlog"
            >
              <RotateCw className={`w-3.5 h-3.5 text-cyan-400 ${sweeping ? 'animate-spin' : ''}`} />
              <span>{sweeping ? 'Sweeping...' : 'Sweep Backlog'}</span>
            </button>
          )}

          <button
            onClick={() => {
              fetchEvents(page);
              fetchHealth();
            }}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-cyan text-dark-900 shadow-glow-cyan font-bold hover:brightness-110 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Events Table */}
      <div className="rounded-xl bg-dark-850 border border-dark-700 overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-dark-800 text-slate-400 border-b border-dark-700 font-mono text-[11px]">
              <tr>
                <th className="py-3 px-4">Event ID / Type</th>
                <th className="py-3 px-3">Provider Event ID</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3 text-center">Attempts</th>
                <th className="py-3 px-3">Received At</th>
                <th className="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-750 font-mono text-[11px]">
              {loading && events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    <RotateCw className="w-5 h-5 mx-auto animate-spin text-brand-cyan mb-2" />
                    Loading webhook event stream...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No webhook events matched the current filter criteria.
                  </td>
                </tr>
              ) : (
                events.map((evt) => (
                  <tr key={evt.id} className="hover:bg-dark-800/50 transition">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-200">{evt.event_type}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{evt.id}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-300">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate max-w-[150px]" title={evt.provider_event_id}>
                          {evt.provider_event_id}
                        </span>
                        <button
                          onClick={() => handleCopy(evt.provider_event_id, evt.id)}
                          className="text-slate-400 hover:text-slate-200 transition"
                          title="Copy Event ID"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                        {copiedId === evt.id && (
                          <span className="text-[9px] text-emerald-400">Copied!</span>
                        )}
                      </div>
                      {evt.internal_payment_id && (
                        <div className="text-[10px] text-slate-400">
                          Payment: <span className="text-brand-cyan">{evt.internal_payment_id}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {getStatusBadge(evt.status)}
                      {evt.last_error && (
                        <div className="text-[10px] text-rose-400/90 truncate max-w-[180px] mt-0.5" title={evt.last_error}>
                          Err: {evt.last_error}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className="font-semibold text-slate-300">
                        {evt.attempt_count} / {evt.max_attempts}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400">
                      <div>{new Date(evt.received_at).toLocaleTimeString()}</div>
                      <div className="text-[10px] text-slate-400">
                        {new Date(evt.received_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setSelectedEvent(evt)}
                          className="px-2.5 py-1 rounded bg-dark-750 hover:bg-dark-700 text-slate-300 border border-dark-650 transition flex items-center gap-1"
                          title="Inspect Payload"
                        >
                          <Eye className="w-3 h-3 text-brand-cyan" />
                          <span>Inspect</span>
                        </button>

                        {(evt.status === 'FAILED' || evt.status === 'DEAD_LETTER' || evt.status === 'RETRY_PENDING') && (
                          <button
                            onClick={() => handleRetry(evt.id)}
                            disabled={!canOperate || retryingId === evt.id}
                            className="px-2.5 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 transition flex items-center gap-1 disabled:opacity-40"
                            title={canOperate ? 'Reprocess Event' : 'Requires OPERATOR/ADMIN'}
                          >
                            <RefreshCw className={`w-3 h-3 ${retryingId === evt.id ? 'animate-spin' : ''}`} />
                            <span>Retry</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-dark-800 border-t border-dark-700 text-xs text-slate-400 font-mono">
          <div>
            Showing {events.length > 0 ? (page - 1) * limit + 1 : 0} to{' '}
            {Math.min(page * limit, total)} of {total} events
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-2.5 py-1 rounded bg-dark-750 border border-dark-700 hover:bg-dark-700 disabled:opacity-30 transition"
            >
              Prev
            </button>
            <span className="px-2 font-bold text-slate-200">
              {page} / {totalPages || 1}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-2.5 py-1 rounded bg-dark-750 border border-dark-700 hover:bg-dark-700 disabled:opacity-30 transition"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Payload Inspection Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-2xl rounded-2xl bg-dark-850 border border-dark-700 shadow-2xl overflow-hidden max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-dark-700 bg-dark-800">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-brand-cyan" />
                <h3 className="text-sm font-bold text-white">
                  Webhook Event: <span className="text-brand-cyan font-mono">{selectedEvent.id}</span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-dark-800 border border-dark-700">
                  <div className="text-slate-400 text-[10px]">Event Type</div>
                  <div className="font-bold text-white mt-0.5">{selectedEvent.event_type}</div>
                </div>
                <div className="p-3 rounded-lg bg-dark-800 border border-dark-700">
                  <div className="text-slate-400 text-[10px]">Status</div>
                  <div className="mt-0.5">{getStatusBadge(selectedEvent.status)}</div>
                </div>
                <div className="p-3 rounded-lg bg-dark-800 border border-dark-700">
                  <div className="text-slate-400 text-[10px]">Provider Event ID</div>
                  <div className="font-mono text-slate-200 truncate mt-0.5" title={selectedEvent.provider_event_id}>
                    {selectedEvent.provider_event_id}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-dark-800 border border-dark-700">
                  <div className="text-slate-400 text-[10px]">Correlation ID</div>
                  <div className="font-mono text-slate-200 truncate mt-0.5">
                    {selectedEvent.correlation_id || 'None'}
                  </div>
                </div>
              </div>

              {selectedEvent.last_error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs">
                  <div className="font-bold text-rose-300">Sanitized Error Log:</div>
                  <div className="font-mono text-[11px] text-rose-200 mt-1 whitespace-pre-wrap">
                    {selectedEvent.last_error}
                  </div>
                </div>
              )}

              <div>
                <div className="text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                  <span>Durable Event Record & Sanitized Payload</span>
                  <span className="text-[10px] text-emerald-400">PII & Credentials Redacted</span>
                </div>
                <pre className="p-3 rounded-xl bg-dark-900 border border-dark-750 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-60 leading-relaxed">
                  {JSON.stringify(selectedEvent, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 border-t border-dark-700 bg-dark-800">
              <div className="text-[11px] text-slate-400">
                Next Retry:{' '}
                {selectedEvent.next_retry_at
                  ? new Date(selectedEvent.next_retry_at).toLocaleString()
                  : 'N/A'}
              </div>
              <div className="flex items-center gap-2">
                {(selectedEvent.status === 'FAILED' ||
                  selectedEvent.status === 'DEAD_LETTER' ||
                  selectedEvent.status === 'RETRY_PENDING') && (
                  <button
                    onClick={() => {
                      handleRetry(selectedEvent.id);
                      setSelectedEvent(null);
                    }}
                    disabled={!canOperate}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 transition disabled:opacity-40"
                  >
                    Reprocess Now
                  </button>
                )}
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-dark-700 hover:bg-dark-650 text-slate-200 transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
