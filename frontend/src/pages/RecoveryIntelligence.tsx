import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { DashboardMetrics } from '../types';
import { LineChart, PieChart as PieIcon, Layers, Shield } from 'lucide-react';

interface RecoveryIntelligenceProps {
  metrics: DashboardMetrics | null;
}

export const RecoveryIntelligence: React.FC<RecoveryIntelligenceProps> = ({ metrics }) => {
  if (!metrics) return null;

  const segmentData = [
    { name: 'VIP Customers', value: 45, recoveryRate: 94.2, color: '#10B981' },
    { name: 'High Value', value: 30, recoveryRate: 86.5, color: '#00F0FF' },
    { name: 'Standard', value: 20, recoveryRate: 72.1, color: '#6366F1' },
    { name: 'First Time', value: 5, recoveryRate: 58.0, color: '#F59E0B' },
  ];

  const channelData = [
    { channel: 'WhatsApp (Deep-Link)', sent: 48, converted: 43, rate: 89.5 },
    { channel: 'SMS (Instant Pay)', sent: 32, converted: 24, rate: 75.0 },
    { channel: 'Email (Omni)', sent: 18, converted: 9, rate: 50.0 },
    { channel: 'Voice Concierge', sent: 6, converted: 5, rate: 83.3 },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <LineChart className="w-5 h-5 text-brand-cyan" />
          Recovery Intelligence & Analytics
        </h2>
        <p className="text-xs text-slate-400">
          In-depth breakdown of payment failure telemetry, customer intent correlation, and recovery efficiency.
        </p>
      </div>

      {/* Primary Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Method Breakdown */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
          <h3 className="text-sm font-bold text-white mb-1">Recovery Rate by Payment Method</h3>
          <p className="text-xs text-slate-400 mb-4">UPI leads in fastest autonomous conversion</p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.recovery_by_method} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" horizontal={false} />
                <XAxis type="number" stroke="#64748B" fontSize={11} domain={[0, 100]} unit="%" />
                <YAxis dataKey="method" type="category" stroke="#64748B" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                  formatter={(val: any) => [`${val}% Recovery Rate`, '']}
                />
                <Bar dataKey="recovery_rate" fill="#00F0FF" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Reason Breakdown */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
          <h3 className="text-sm font-bold text-white mb-1">Recovery by Failure Reason</h3>
          <p className="text-xs text-slate-400 mb-4">Volume of failures vs recovered percentage</p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.recovery_by_reason}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1C2538" vertical={false} />
                <XAxis dataKey="reason" stroke="#64748B" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748B" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                />
                <Bar dataKey="count" fill="#F43F5E" name="Failed Orders" radius={[4, 4, 0, 0]} />
                <Bar dataKey="recovered" fill="#10B981" name="Recovered" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Customer Segment & Channel Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Customer Segment Distribution */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700">
          <h3 className="text-sm font-bold text-white mb-1">Recovery by Customer Segment</h3>
          <p className="text-xs text-slate-400 mb-4">VIP & high-frequency buyers show 94% recovery loyalty</p>

          <div className="h-64 w-full flex items-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={segmentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {segmentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#111622', borderColor: '#2A364F', borderRadius: '8px', fontSize: '12px' }}
                  formatter={(val: any, name: any) => [`${val}% Share`, name]}
                />
                <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recovery Dispatch Channel Matrix */}
        <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-white mb-1">Channel Conversion Matrix</h3>
            <p className="text-xs text-slate-400 mb-4">Performance across WhatsApp, SMS, Email, Voice</p>

            <div className="space-y-3">
              {channelData.map((ch) => (
                <div key={ch.channel} className="p-3 rounded-xl bg-dark-800 border border-dark-700">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-bold text-slate-200">{ch.channel}</span>
                    <span className="font-mono text-emerald-400 font-bold">{ch.rate}% Conversion</span>
                  </div>
                  <div className="w-full h-1.5 bg-dark-900 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-cyan to-brand-emerald rounded-full"
                      style={{ width: `${ch.rate}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    {ch.converted} recovered out of {ch.sent} dispatches
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
