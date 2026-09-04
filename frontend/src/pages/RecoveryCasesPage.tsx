import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Search, Filter, ChevronDown, FolderKanban, RefreshCw,
  AlertTriangle, CheckCircle2, Clock, Loader2, ChevronUp,
  ArrowUpDown, IndianRupee, Shield
} from 'lucide-react';
import { RecoveryCase, Payment } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { RecoveryScore } from '../components/RecoveryScore';
import { api } from '../services/api';
import { useToast } from '../components/Toast';

interface RecoveryCasesPageProps {
  onSelectPayment: (p: Payment) => void;
  onNavigate?: (tab: string) => void;
}

const STATUS_OPTIONS = ['', 'IDENTIFIED', 'INVESTIGATING', 'STRATEGY_SELECTED', 'ACTION_IN_PROGRESS',
  'AWAITING_CUSTOMER', 'AWAITING_HUMAN_APPROVAL', 'RECOVERED', 'FAILED', 'EXPIRED'];
const METHOD_OPTIONS = ['', 'CARD', 'UPI', 'NETBANKING', 'WALLET', 'EMI'];
const STRATEGY_OPTIONS = ['', 'ALTERNATE_PAYMENT_METHOD', 'PAYMENT_LINK', 'RETRY_PAYMENT', 'FOLLOW_UP',
  'INCENTIVE', 'HUMAN_ESCALATION', 'STOP_RECOVERY', 'VERIFY_PAYMENT'];

function EmptyState({ label, icon: Icon }: { label: string; icon: React.FC<any> }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Icon className="w-10 h-10 text-slate-700" />
      <div className="text-sm font-semibold text-slate-500">{label}</div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-5 py-3 border-b border-dark-700 animate-pulse">
      <div className="w-8 h-8 rounded-lg bg-dark-700" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 w-32 bg-dark-700 rounded" />
        <div className="h-2.5 w-48 bg-dark-700 rounded" />
      </div>
      <div className="h-3 w-16 bg-dark-700 rounded" />
      <div className="h-3 w-20 bg-dark-700 rounded" />
    </div>
  );
}

type SortKey = 'amount' | 'score' | 'probability' | 'created' | 'updated';

export const RecoveryCasesPage: React.FC<RecoveryCasesPageProps> = ({ onSelectPayment, onNavigate }) => {
  const { error: showError } = useToast();
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [methodFilter, setMethodFilter] = useState('');
  const [strategyFilter, setStrategyFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getRecoveryCases(statusFilter || undefined);
      setCases(data);
      setPage(0);
    } catch (err: any) {
      showError(err.message || 'Failed to load recovery cases');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, showError]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let out = [...cases];
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      out = out.filter(c =>
        c.id.toLowerCase().includes(q) ||
        c.payment_id?.toLowerCase().includes(q) ||
        c.payment?.customer?.name?.toLowerCase().includes(q) ||
        c.customer_intent?.toLowerCase().includes(q)
      );
    }
    if (methodFilter) out = out.filter(c => c.payment?.payment_method === methodFilter);
    if (strategyFilter) out = out.filter(c => c.current_strategy === strategyFilter);
    // Sort
    out.sort((a, b) => {
      let va = 0, vb = 0;
      if (sortKey === 'amount') { va = a.payment?.amount ?? 0; vb = b.payment?.amount ?? 0; }
      else if (sortKey === 'score') { va = a.recovery_score ?? 0; vb = b.recovery_score ?? 0; }
      else if (sortKey === 'probability') { va = a.recovery_probability ?? 0; vb = b.recovery_probability ?? 0; }
      else if (sortKey === 'created') { va = new Date(a.started_at || '').getTime(); vb = new Date(b.started_at || '').getTime(); }
      return sortAsc ? va - vb : vb - va;
    });
    return out;
  }, [cases, search, methodFilter, strategyFilter, sortKey, sortAsc]);

  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p);
    else { setSortKey(key); setSortAsc(false); }
  };

  const SortBtn = ({ label, k }: { label: string; k: SortKey }) => (
    <button onClick={() => handleSort(k)} className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 uppercase tracking-wider font-semibold">
      {label}
      {sortKey === k ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
    </button>
  );

  // Summary stats
  const awaitingApproval = cases.filter(c => c.status === 'AWAITING_HUMAN_APPROVAL').length;
  const activeCount = cases.filter(c => !['RECOVERED','FAILED','EXPIRED'].includes(c.status)).length;
  const recoveredCount = cases.filter(c => c.status === 'RECOVERED').length;

  return (
    <div className="space-y-4 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center">
            <FolderKanban className="w-4 h-4 text-brand-cyan" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white">Recovery Cases</h1>
            <p className="text-[11px] text-slate-500">{filtered.length} cases {statusFilter ? `(${statusFilter})` : 'total'}</p>
          </div>
        </div>
        <button onClick={load} disabled={loading} className="p-2 text-slate-400 hover:text-brand-cyan rounded-lg hover:bg-dark-800 transition">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-xl bg-dark-850 border border-dark-700 flex items-center gap-2">
          <Clock className="w-4 h-4 text-amber-400" />
          <div>
            <div className="text-lg font-black text-white">{activeCount}</div>
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Active</div>
          </div>
        </div>
        <div className="p-3 rounded-xl bg-dark-850 border border-amber-500/20 flex items-center gap-2">
          <Shield className="w-4 h-4 text-amber-400" />
          <div>
            <div className="text-lg font-black text-amber-400">{awaitingApproval}</div>
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Need Approval</div>
          </div>
        </div>
        <div className="p-3 rounded-xl bg-dark-850 border border-emerald-500/20 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <div>
            <div className="text-lg font-black text-emerald-400">{recoveredCount}</div>
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Recovered</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="p-3 rounded-xl bg-dark-850 border border-dark-700 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-44">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
            placeholder="Search customer, case ID, payment ID…"
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-dark-800 border border-dark-700 rounded-lg text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-cyan/40"
          />
        </div>
        {[
          { label: 'Status', value: statusFilter, setter: setStatusFilter, options: STATUS_OPTIONS },
          { label: 'Method', value: methodFilter, setter: setMethodFilter, options: METHOD_OPTIONS },
          { label: 'Strategy', value: strategyFilter, setter: setStrategyFilter, options: STRATEGY_OPTIONS },
        ].map(f => (
          <select
            key={f.label}
            value={f.value}
            onChange={e => { f.setter(e.target.value); setPage(0); }}
            className="py-1.5 px-2.5 text-xs bg-dark-800 border border-dark-700 rounded-lg text-slate-300 focus:outline-none focus:border-brand-cyan/40"
          >
            <option value="">All {f.label}s</option>
            {f.options.filter(Boolean).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
        {(search || statusFilter || methodFilter || strategyFilter) && (
          <button onClick={() => { setSearch(''); setStatusFilter(''); setMethodFilter(''); setStrategyFilter(''); setPage(0); }}
            className="text-[10px] text-slate-500 hover:text-slate-300 px-2 py-1.5 rounded bg-dark-800 border border-dark-700">
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-xl bg-dark-850 border border-dark-700 overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-[2rem_1fr_6rem_6rem_7rem_7rem_7rem_4rem] items-center px-5 py-2.5 border-b border-dark-700 bg-dark-800/50 gap-3">
          <div />
          <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Case / Customer</div>
          <SortBtn label="Amount" k="amount" />
          <SortBtn label="Score" k="score" />
          <SortBtn label="Probability" k="probability" />
          <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Strategy</div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Status</div>
          <div />
        </div>

        {/* Rows */}
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
        ) : paginated.length === 0 ? (
          <EmptyState
            label={search || statusFilter || methodFilter ? 'No cases match your filters. Try adjusting the criteria.' : 'No recovery cases found. Run a simulation to create cases.'}
            icon={FolderKanban}
          />
        ) : (
          paginated.map(rc => {
            const payment = rc.payment || null;
            const prob = rc.recovery_probability ?? 0;
            const probColor = prob >= 0.85 ? 'text-emerald-400' : prob >= 0.65 ? 'text-amber-400' : 'text-rose-400';
            const needsApproval = rc.status === 'AWAITING_HUMAN_APPROVAL';
            return (
              <div
                key={rc.id}
                onClick={() => payment && onSelectPayment(payment)}
                className={`grid grid-cols-[2rem_1fr_6rem_6rem_7rem_7rem_7rem_4rem] items-center px-5 py-3 border-b border-dark-700/50 gap-3 cursor-pointer transition hover:bg-dark-800/50 ${needsApproval ? 'bg-amber-500/3' : ''}`}
              >
                <RecoveryScore score={rc.recovery_score} size="sm" />
                <div>
                  <div className="text-xs font-semibold text-white truncate">
                    {payment?.customer?.name || rc.id.slice(0, 12)}
                    {needsApproval && <span className="ml-2 text-[9px] font-mono px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">APPROVAL</span>}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono truncate">{rc.id.slice(0, 20)} · {payment?.payment_method || '—'} · {payment?.failure_reason || '—'}</div>
                </div>
                <div className="text-xs font-mono font-bold text-white">₹{payment?.amount?.toLocaleString() || '—'}</div>
                <div className="text-xs font-mono text-slate-300">{rc.recovery_score?.toFixed(0) ?? '—'}/100</div>
                <div className={`text-xs font-mono font-bold ${probColor}`}>{(prob * 100).toFixed(0)}%</div>
                <div className="text-[10px] text-slate-400 font-mono truncate">{rc.current_strategy || '—'}</div>
                <StatusBadge status={rc.status} />
                <button
                  onClick={e => { e.stopPropagation(); onNavigate?.('command-center'); }}
                  className="text-[10px] text-brand-cyan hover:text-white font-bold px-1.5 py-0.5 rounded bg-brand-cyan/10 hover:bg-brand-cyan/20 transition"
                >
                  VIEW
                </button>
              </div>
            );
          })
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-dark-700">
            <span className="text-[10px] text-slate-500">{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}</span>
            <div className="flex gap-1">
              <button disabled={page === 0} onClick={() => setPage(p => p - 1)}
                className="px-2.5 py-1 text-[10px] text-slate-400 disabled:opacity-40 bg-dark-800 border border-dark-700 rounded hover:border-brand-cyan/30 transition">
                Prev
              </button>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}
                className="px-2.5 py-1 text-[10px] text-slate-400 disabled:opacity-40 bg-dark-800 border border-dark-700 rounded hover:border-brand-cyan/30 transition">
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
