import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { CommandCenter } from './pages/CommandCenter';
import { RecoveryCasesPage } from './pages/RecoveryCasesPage';
import { RecoveryIntelligence } from './pages/RecoveryIntelligence';
import { PaymentsPage } from './pages/PaymentsPage';
import { AgentActivityPage } from './pages/AgentActivityPage';
import { AICopilotPage } from './pages/AICopilotPage';
import { GuardrailsPage } from './pages/GuardrailsPage';
import { DemoCenter } from './pages/DemoCenter';
import { SettingsPage } from './pages/SettingsPage';
import { LoginPage } from './pages/LoginPage';
import { PaymentDetailModal } from './components/PaymentDetailModal';
import { SimulateModal } from './components/SimulateModal';
import { LoadingState } from './components/LoadingState';
import { ToastProvider, useToast } from './components/Toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ErrorBoundary } from './components/ErrorBoundary';
import { api } from './services/api';
import { DashboardMetrics, Payment, RecoveryCase, AgentAction } from './types';

function MainDashboard() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('command-center');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [recoveryCases, setRecoveryCases] = useState<RecoveryCase[]>([]);
  const [agentActions, setAgentActions] = useState<AgentAction[]>([]);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSelectPaymentById = useCallback(async (paymentId: string) => {
    const found = payments.find((p) => p.id === paymentId || p.razorpay_payment_id === paymentId);
    if (found) {
      setSelectedPayment(found);
    } else {
      try {
        const p = await api.getPayment(paymentId);
        setSelectedPayment(p);
      } catch (err) {
        console.error('Failed fetching payment by id:', err);
      }
    }
  }, [payments]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-dark-900 text-slate-100 antialiased font-sans">
      {/* Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenSimulate={() => setIsSimulateOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-0 overflow-hidden">
        {/* Top Navbar */}
        <Topbar onRefresh={loadData} isRefreshing={refreshing} />

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          {loading ? (
            <LoadingState message="Connecting to PayRecover AI Engine & Telemetry Stream..." />
          ) : (
            <>
              {activeTab === 'command-center' && (
                <CommandCenter
                  metrics={metrics}
                  payments={payments}
                  recoveryCases={recoveryCases}
                  onSelectPayment={(p) => setSelectedPayment(p)}
                  onOpenSimulate={() => setIsSimulateOpen(true)}
                  onRefresh={loadData}
                  onNavigate={(tab) => setActiveTab(tab)}
                />
              )}

              {activeTab === 'recovery-cases' && (
                <RecoveryCasesPage
                  onSelectPayment={(p) => setSelectedPayment(p)}
                  onNavigate={(tab) => setActiveTab(tab)}
                />
              )}

              {activeTab === 'payments' && (
                <PaymentsPage
                  payments={payments}
                  onSelectPayment={(p) => setSelectedPayment(p)}
                />
              )}

              {activeTab === 'intelligence' && (
                <RecoveryIntelligence
                  metrics={metrics}
                  onSelectPaymentId={handleSelectPaymentById}
                />
              )}

              {activeTab === 'agent-activity' && (
                <AgentActivityPage
                  actions={agentActions}
                  onRefresh={loadData}
                />
              )}

              {activeTab === 'copilot' && (
                <AICopilotPage />
              )}

              {activeTab === 'guardrails' && (
                <GuardrailsPage />
              )}

              {activeTab === 'demo-center' && (
                <DemoCenter
                  onSelectPaymentId={handleSelectPaymentById}
                  onRefreshAll={loadData}
                />
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

function AppContent() {
  const { user, token, isLoading } = useAuth();
  const { showWarning } = useToast();

  useEffect(() => {
    const handleUnauthorized = () => {
      showWarning('Session Expired', 'Please sign in to continue.');
    };
    window.addEventListener('payrecover:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('payrecover:unauthorized', handleUnauthorized);
  }, [showWarning]);

  if (isLoading) {
    return <LoadingState message="Verifying secure PayRecover session..." />;
  }

  if (!token || !user) {
    return <LoginPage />;
  }

  return <MainDashboard />;
}

export function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
