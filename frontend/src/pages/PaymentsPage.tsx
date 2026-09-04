import React, { useState } from 'react';
import { Search, Filter, CreditCard, ArrowRight, ExternalLink } from 'lucide-react';
import { Payment } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { RecoveryScore } from '../components/RecoveryScore';

interface PaymentsPageProps {
  payments: Payment[];
  onSelectPayment: (p: Payment) => void;
}

export const PaymentsPage: React.FC<PaymentsPageProps> = ({ payments, onSelectPayment }) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [methodFilter, setMethodFilter] = useState('ALL');

  const filtered = payments.filter((p) => {
    const matchSearch =
      search === '' ||
      p.razorpay_payment_id.toLowerCase().includes(search.toLowerCase()) ||
      p.customer?.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.failure_reason && p.failure_reason.toLowerCase().includes(search.toLowerCase()));

    const matchStatus = statusFilter === 'ALL' || p.status === statusFilter;
    const matchMethod = methodFilter === 'ALL' || p.payment_method === methodFilter;

    return matchSearch && matchStatus && matchMethod;
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-brand-cyan" />
            Payment Telemetry & Recovery Cases
          </h2>
          <p className="text-xs text-slate-400">
            Real-time feed of all merchant transactions, failure reasons, and recovery states.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search bar */}
          <div className="relative w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search ID, customer, reason..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan"
            />
          </div>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-cyan"
          >
            <option value="ALL">All Statuses</option>
            <option value="FAILED">Failed</option>
            <option value="RECOVERED">Recovered</option>
            <option value="SUCCESS">Success</option>
          </select>

          {/* Method filter */}
          <select
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
            className="px-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-cyan"
          >
            <option value="ALL">All Methods</option>
            <option value="UPI">UPI</option>
            <option value="CARD">Card</option>
            <option value="NETBANKING">NetBanking</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-2xl bg-dark-850 border border-dark-700 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-dark-800/80 text-slate-400 uppercase font-semibold text-[10px] tracking-wider border-b border-dark-700">
              <tr>
                <th className="py-3.5 px-4">Payment ID</th>
                <th className="py-3.5 px-4">Customer</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Method</th>
                <th className="py-3.5 px-4">Failure Reason</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Recovery Score</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/60">
              {filtered.map((p) => {
                const score = p.status === 'RECOVERED' ? 100 : (p.amount >= 50000 ? 75 : 88);
                return (
                  <tr
                    key={p.id}
                    onClick={() => onSelectPayment(p)}
                    className="hover:bg-dark-800/80 cursor-pointer transition"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-white flex items-center gap-1.5">
                      {p.razorpay_payment_id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-200">{p.customer?.name || 'Customer'}</div>
                      <div className="text-[10px] text-slate-500">{p.customer?.customer_value || 'STANDARD'}</div>
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-white">
                      ₹{p.amount.toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-dark-750 text-slate-300 border border-dark-700 font-mono text-[10px]">
                        {p.payment_method}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-rose-400">
                      {p.failure_reason || '—'}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="py-3 px-4">
                      <RecoveryScore score={score} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[10px]">
                      {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button className="p-1 rounded bg-dark-750 hover:bg-dark-700 text-slate-400 hover:text-brand-cyan transition">
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
