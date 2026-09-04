import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { CommandCenter } from './pages/CommandCenter';
import { RecoveryIntelligence } from './pages/RecoveryIntelligence';
import { PaymentsPage } from './pages/PaymentsPage';
import { AgentActivityPage } from './pages/AgentActivityPage';
import { AICopilotPage } from './pages/AICopilotPage';
import { GuardrailsPage } from './pages/GuardrailsPage';
import { SettingsPage } from './pages/SettingsPage';
import { PaymentDetailModal } from './components/PaymentDetailModal';
import { SimulateModal } from './components/SimulateModal';
import { LoadingState } from './components/LoadingState';
import { api } from './services/api';
import { DashboardMetrics, Payment, RecoveryCase, AgentAction } from './types';

export function App() {
  const [activeTab, setActiveTab] = useState('command-center');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [recoveryCases, setRecoveryCases] = useState<RecoveryCase[]>([]);
  const [agentActions, setAgentActions] = useState<AgentAction[]>([]);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    setRefreshing(true);
    try {
      const [m, p, rc, acts] = await Promise.all([
        api.getMetrics(),
        api.getPayments({ limit: 100 }),
        api.getRecoveryCases(),
        api.getAgentActivity(50)
      ]);
      setMetrics(m);
      setPayments(p);
      setRecoveryCases(rc);
      setAgentActions(acts);
    } catch (err) {
      console.error('Failed loading data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-dark-900 text-slate-100 antialiased font-sans">
      {/* Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenSimulate={() => setIsSimulateOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <Topbar onRefresh={loadData} isRefreshing={refreshing} />

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto p-8">
          {loading ? (
            <LoadingState message="Connecting to PayRecover AI Engine & Razorpay Telemetry..." />
          ) : (
            <>
              {activeTab === 'command-center' && (
                <CommandCenter
                  metrics={metrics}
                  payments={payments}
                  recoveryCases={recoveryCases}
                  onSelectPayment={(p) => setSelectedPayment(p)}
                  onOpenSimulate={() => setIsSimulateOpen(true)}
                />
              )}

              {activeTab === 'intelligence' && (
                <RecoveryIntelligence metrics={metrics} />
              )}

              {activeTab === 'payments' && (
                <PaymentsPage
                  payments={payments}
                  onSelectPayment={(p) => setSelectedPayment(p)}
                />
              )}

              {activeTab === 'agent-activity' && (
                <AgentActivityPage actions={agentActions} />
              )}

              {activeTab === 'copilot' && (
                <AICopilotPage />
              )}

              {activeTab === 'guardrails' && (
                <GuardrailsPage />
              )}

              {activeTab === 'settings' && (
                <SettingsPage />
              )}
            </>
          )}
        </main>
      </div>

      {/* Payment Inspector Modal */}
      <PaymentDetailModal
        payment={selectedPayment}
        onClose={() => setSelectedPayment(null)}
        onRefresh={loadData}
      />

      {/* Interactive Simulation / Sandbox Modal */}
      <SimulateModal
        isOpen={isSimulateOpen}
        onClose={() => setIsSimulateOpen(false)}
        onSimulationSuccess={loadData}
      />
    </div>
  );
}

export default App;
