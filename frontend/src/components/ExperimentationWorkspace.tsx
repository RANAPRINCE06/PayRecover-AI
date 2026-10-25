import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical,
  Play,
  Pause,
  CheckCircle,
  Plus,
  RefreshCw,
  AlertTriangle,
  Download,
  Info,
  Sliders,
  TrendingUp,
  Percent,
  IndianRupee,
  Clock,
  Layers,
  ArrowRight,
  ShieldAlert,
  HelpCircle,
  X,
  Loader2,
  Check,
  Zap,
  BarChart2,
  Scale
} from 'lucide-react';
import {
  RecoveryExperimentItem,
  ExperimentMetricsResponse,
  ExperimentAssignmentItem,
  ExperimentCreateRequest,
  ExperimentArmConfig,
  OfflineSimulationRequest,
  OfflineSimulationResponse
} from '../types';
import { api } from '../services/api';

const CANONICAL_STRATEGIES = [
  'PAYMENT_LINK',
  'ALTERNATIVE_PAYMENT_METHOD',
  'PAYMENT_RETRY',
  'SCHEDULED_REMINDER',
  'MANDATE_RECOVERY',
  'HUMAN_ESCALATION'
];

export const ExperimentationWorkspace: React.FC = () => {
  const [experiments, setExperiments] = useState<RecoveryExperimentItem[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<string | null>(null);
  const [selectedExp, setSelectedExp] = useState<RecoveryExperimentItem | null>(null);
  const [metrics, setMetrics] = useState<ExperimentMetricsResponse | null>(null);
  const [assignments, setAssignments] = useState<ExperimentAssignmentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMetrics, setLoadingMetrics] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Modals
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showSimulateModal, setShowSimulateModal] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<OfflineSimulationResponse | null>(null);

  // New Experiment Form State
  const [formName, setFormName] = useState('');
  const [formObjective, setFormObjective] = useState('');
  const [formHypothesis, setFormHypothesis] = useState('');
  const [formMetric, setFormMetric] = useState('recovery_rate');
  const [formSandbox, setFormSandbox] = useState(true);
  const [formFailureCat, setFormFailureCat] = useState('UPI_TIMEOUT');
  const [formPaymentMethod, setFormPaymentMethod] = useState('UPI');
  const [formMinObs, setFormMinObs] = useState(30);
  const [formArms, setFormArms] = useState<ExperimentArmConfig[]>([
    { arm_id: 'control', strategy: 'PAYMENT_LINK', traffic_percentage: 50.0, is_control: true, description: 'Control: Standard Payment Link' },
    { arm_id: 'treatment', strategy: 'ALTERNATIVE_PAYMENT_METHOD', traffic_percentage: 50.0, is_control: false, description: 'Treatment: Alternative Payment Method' }
  ]);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Simulation Form State
  const [simCohortSize, setSimCohortSize] = useState(100);
  const [simUseBandit, setSimUseBandit] = useState(false);

  // Load Experiments
  const fetchExperiments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getExperiments(1, 50, statusFilter || undefined);
      setExperiments(res.experiments);
      if (res.experiments.length > 0 && !selectedExpId) {
        setSelectedExpId(res.experiments[0].id);
      }
    } catch (err) {
      console.error('Failed fetching experiments:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, selectedExpId]);

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  // Load Details & Metrics when selected experiment changes
  const loadExperimentDetails = useCallback(async (expId: string) => {
    try {
      setLoadingMetrics(true);
      const [expDetail, expMetrics, asgnData] = await Promise.all([
        api.getExperimentById(expId),
        api.getExperimentMetrics(expId),
        api.getExperimentAssignments(expId, 1, 20)
      ]);
      setSelectedExp(expDetail);
      setMetrics(expMetrics);
      setAssignments(asgnData.assignments);
    } catch (err) {
      console.error('Failed loading experiment metrics:', err);
    } finally {
      setLoadingMetrics(false);
    }
  }, []);

  useEffect(() => {
    if (selectedExpId) {
      loadExperimentDetails(selectedExpId);
    }
  }, [selectedExpId, loadExperimentDetails]);

  // Status transition handler
  const handleTransitionStatus = async (targetStatus: string) => {
    if (!selectedExpId) return;
    try {
      await api.transitionExperimentStatus(selectedExpId, targetStatus, `Manual transition to ${targetStatus}`);
      await fetchExperiments();
      await loadExperimentDetails(selectedExpId);
    } catch (err: any) {
      alert(`Status transition failed: ${err.message || err}`);
    }
  };

  // Create Experiment Submit
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const totalTraffic = formArms.reduce((sum, a) => sum + Number(a.traffic_percentage), 0);
    if (Math.abs(totalTraffic - 100) > 0.05) {
      setFormError(`Traffic percentages must sum to 100% (currently ${totalTraffic}%).`);
      return;
    }

    try {
      setFormSubmitting(true);
      const payload: ExperimentCreateRequest = {
        name: formName,
        objective: formObjective,
        hypothesis: formHypothesis || undefined,
        primary_metric: formMetric,
        is_sandbox_only: formSandbox,
        target_failure_categories: formFailureCat ? [formFailureCat] : undefined,
        target_payment_methods: formPaymentMethod ? [formPaymentMethod] : undefined,
        candidate_strategies: formArms,
        min_observation_count: formMinObs
      };
      const created = await api.createExperiment(payload);
      setShowCreateModal(false);
      await fetchExperiments();
      setSelectedExpId(created.id);
    } catch (err: any) {
      setFormError(err.message || 'Failed to create experiment.');
    } finally {
      setFormSubmitting(false);
    }
  };

  // Run Offline Simulation
  const handleRunSimulation = async () => {
    if (!selectedExpId) return;
    try {
      setSimulating(true);
      const simReq: OfflineSimulationRequest = {
        cohort_size: simCohortSize,
        failure_category: selectedExp?.target_failure_categories[0] || 'UPI_TIMEOUT',
        payment_method: selectedExp?.target_payment_methods[0] || 'UPI',
        random_seed: 42,
        enable_thompson_sampling: simUseBandit
      };
      const res = await api.simulateExperiment(selectedExpId, simReq);
      setSimulationResult(res);
    } catch (err: any) {
      alert(`Simulation failed: ${err.message || err}`);
    } finally {
      setSimulating(false);
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'RUNNING':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> RUNNING</span>;
      case 'READY':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">READY</span>;
      case 'PAUSED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">PAUSED</span>;
      case 'COMPLETED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30">COMPLETED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 border border-slate-600">DRAFT</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Epistemic Distinctions & Fintech Guardrails */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-dark-850 via-dark-800 to-dark-850 border border-brand-cyan/20 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 text-brand-cyan shrink-0 mt-0.5">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white">Controlled Recovery Strategy Experimentation Engine</h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-cyan/20 text-brand-cyan font-mono font-semibold">PHASE 6</span>
            </div>
            <p className="text-xs text-slate-400">
              Deterministic, reproducible random assignment with authoritative payment attribution, 95% Wilson confidence intervals, and two-proportion hypothesis tests.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-1.5 rounded-xl bg-brand-cyan hover:bg-brand-cyan/90 text-dark-900 font-bold text-xs flex items-center gap-1.5 shadow-glow-cyan transition"
          >
            <Plus className="w-3.5 h-3.5" />
            New Experiment
          </button>
          <button
            onClick={() => { if (selectedExpId) loadExperimentDetails(selectedExpId); }}
            disabled={loadingMetrics}
            className="p-2 rounded-xl bg-dark-750 hover:bg-dark-700 border border-dark-600 text-slate-300 hover:text-white transition"
            title="Refresh metrics"
          >
            <RefreshCw className={`w-4 h-4 ${loadingMetrics ? 'animate-spin text-brand-cyan' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Grid: Experiment Selector Sidebar + Experiment Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Experiments List */}
        <div className="lg:col-span-1 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Experiments ({experiments.length})</h4>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-dark-800 border border-dark-700 text-[11px] text-slate-300 rounded px-2 py-1 outline-none"
            >
              <option value="">All Statuses</option>
              <option value="RUNNING">Running</option>
              <option value="PAUSED">Paused</option>
              <option value="COMPLETED">Completed</option>
              <option value="DRAFT">Draft</option>
            </select>
          </div>

          {loading ? (
            <div className="py-12 flex justify-center">
              <Loader2 className="w-6 h-6 text-brand-cyan animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {experiments.map((exp) => (
                <div
                  key={exp.id}
                  onClick={() => setSelectedExpId(exp.id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition text-left ${
                    selectedExpId === exp.id
                      ? 'bg-dark-800 border-brand-cyan shadow-glow-cyan/20'
                      : 'bg-dark-850 hover:bg-dark-800 border-dark-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    {getStatusBadge(exp.status)}
                    <span className="text-[10px] text-slate-500 font-mono">v{exp.version}</span>
                  </div>
                  <h5 className="text-xs font-bold text-white line-clamp-1">{exp.name}</h5>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{exp.objective}</p>

                  <div className="mt-3 pt-2 border-t border-dark-750 flex items-center justify-between text-[10px] text-slate-400">
                    <span>{exp.total_assignments} assigned</span>
                    <span className="text-emerald-400 font-medium">{exp.total_terminal_outcomes} verified</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 3 Columns: Active Experiment Details & Scientific Telemetry */}
        <div className="lg:col-span-3 space-y-6">
          {selectedExp && (
            <>
              {/* Experiment Header & Controls */}
              <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      {getStatusBadge(selectedExp.status)}
                      <span className="text-xs text-slate-500 font-mono">ID: {selectedExp.id} · Version {selectedExp.version}</span>
                      {selectedExp.is_sandbox_only && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                          Sandbox Isolated
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-extrabold text-white">{selectedExp.name}</h3>
                    <p className="text-xs text-slate-300 mt-1">{selectedExp.objective}</p>
                    {selectedExp.hypothesis && (
                      <div className="text-xs text-brand-cyan/90 mt-1 flex items-center gap-1.5 font-medium">
                        <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                        <span>Hypothesis: {selectedExp.hypothesis}</span>
                      </div>
                    )}
                  </div>

                  {/* Lifecycle Controls */}
                  <div className="flex items-center gap-2 shrink-0">
                    {selectedExp.status === 'READY' && (
                      <button
                        onClick={() => handleTransitionStatus('RUNNING')}
                        className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs flex items-center gap-1.5 transition"
                      >
                        <Play className="w-3.5 h-3.5" /> Activate
                      </button>
                    )}
                    {selectedExp.status === 'RUNNING' && (
                      <>
                        <button
                          onClick={() => handleTransitionStatus('PAUSED')}
                          className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 font-bold text-xs flex items-center gap-1.5 transition"
                        >
                          <Pause className="w-3.5 h-3.5" /> Pause
                        </button>
                        <button
                          onClick={() => handleTransitionStatus('COMPLETED')}
                          className="px-3 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/30 font-bold text-xs flex items-center gap-1.5 transition"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Complete
                        </button>
                      </>
                    )}
                    {selectedExp.status === 'PAUSED' && (
                      <button
                        onClick={() => handleTransitionStatus('RUNNING')}
                        className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs flex items-center gap-1.5 transition"
                      >
                        <Play className="w-3.5 h-3.5" /> Resume
                      </button>
                    )}
                    <button
                      onClick={() => setShowSimulateModal(true)}
                      className="px-3 py-1.5 rounded-lg bg-dark-750 hover:bg-dark-700 border border-dark-600 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition"
                    >
                      <Zap className="w-3.5 h-3.5 text-amber-400" /> Offline Simulation
                    </button>
                    <a
                      href={api.exportExperimentTelemetryUrl(selectedExp.id, 'csv')}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1.5 rounded-lg bg-dark-750 hover:bg-dark-700 border border-dark-600 text-slate-300 hover:text-white transition"
                      title="Export CSV Telemetry"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                </div>

                {/* Eligibility & Target Rail Metadata */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-dark-750 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Target Rails</span>
                    <span className="text-slate-200 font-medium">
                      {selectedExp.target_payment_methods.length > 0 ? selectedExp.target_payment_methods.join(', ') : 'All Methods'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Failure Categories</span>
                    <span className="text-slate-200 font-medium">
                      {selectedExp.target_failure_categories.length > 0 ? selectedExp.target_failure_categories.join(', ') : 'All Failures'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Min Observation Cohort</span>
                    <span className="text-slate-200 font-medium">{selectedExp.min_observation_count} cases</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Primary Metric</span>
                    <span className="text-brand-cyan font-mono font-semibold">{selectedExp.primary_metric}</span>
                  </div>
                </div>
              </div>

              {/* Statistical KPI Strip */}
              {metrics && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Assigned</span>
                    <div className="text-xl font-extrabold text-white font-mono mt-1">{metrics.total_assigned}</div>
                    <div className="text-[10px] text-slate-500 mt-1">{metrics.total_eligible} eligible · {metrics.total_pending} pending</div>
                  </div>

                  <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Verified Recovery Rate</span>
                    <div className="text-xl font-extrabold text-brand-cyan font-mono mt-1">
                      {(metrics.overall_recovery_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">{metrics.total_recovered} recovered out of {metrics.total_eligible} terminal</div>
                  </div>

                  <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Recovered Revenue</span>
                    <div className="text-xl font-extrabold text-emerald-400 font-mono mt-1">
                      ₹{metrics.total_revenue_recovered.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">Directly attributed captures</div>
                  </div>

                  <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Statistical Status</span>
                    <div className="text-sm font-extrabold text-white mt-1">
                      {metrics.comparisons.length > 0 && metrics.comparisons[0].is_statistically_significant ? (
                        <span className="text-emerald-400 flex items-center gap-1"><Check className="w-4 h-4" /> Statistically Significant</span>
                      ) : (
                        <span className="text-amber-400 flex items-center gap-1"><Clock className="w-4 h-4" /> Observation in Progress</span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {metrics.comparisons.length > 0 ? `p-value: ${metrics.comparisons[0].p_value.toFixed(4)}` : 'Awaiting baseline'}
                    </div>
                  </div>
                </div>
              )}

              {/* Sample Size Warning Banner if < 30 */}
              {metrics && metrics.sample_size_warnings.length > 0 && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs flex items-start gap-3">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-amber-200 space-y-1">
                    <span className="font-bold">Statistical Sample Size Warning:</span>
                    {metrics.sample_size_warnings.map((w, idx) => (
                      <p key={idx} className="text-[11px] text-amber-300/80">{w}</p>
                    ))}
                  </div>
                </div>
              )}

              {/* Candidate Strategy Arms Comparison Table */}
              {metrics && (
                <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        <Scale className="w-4 h-4 text-brand-cyan" />
                        Candidate Strategy Arm Comparisons (Verified Attribution)
                      </h4>
                      <p className="text-xs text-slate-400">
                        Rigorous pairwise comparison using 95% Wilson Score Intervals. Pending cases excluded from rate denominator.
                      </p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-dark-700 text-slate-400 font-semibold">
                          <th className="py-2.5 px-3">Arm</th>
                          <th className="py-2.5 px-3">Strategy</th>
                          <th className="py-2.5 px-3">Traffic</th>
                          <th className="py-2.5 px-3">Assigned / Eligible</th>
                          <th className="py-2.5 px-3">Verified Recovery Rate</th>
                          <th className="py-2.5 px-3">95% Wilson CI</th>
                          <th className="py-2.5 px-3">Recovered Revenue</th>
                          <th className="py-2.5 px-3">Rev / Eligible</th>
                          <th className="py-2.5 px-3">Guardrail Deviations</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dark-800">
                        {metrics.arm_metrics.map((arm) => (
                          <tr key={arm.arm_id} className={`hover:bg-dark-800/50 transition ${arm.is_control ? 'bg-dark-900/40' : ''}`}>
                            <td className="py-3 px-3 font-semibold text-white">
                              <div className="flex items-center gap-1.5">
                                <span>{arm.arm_id}</span>
                                {arm.is_control && (
                                  <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold">
                                    CONTROL
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-3">
                              <span className="font-mono text-slate-200 text-[11px] bg-dark-800 px-2 py-0.5 rounded border border-dark-700">
                                {arm.strategy}
                              </span>
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-300">{arm.traffic_percentage}%</td>
                            <td className="py-3 px-3 font-mono text-slate-300">
                              <span className="text-white font-bold">{arm.assigned_count}</span>
                              <span className="text-slate-500"> / {arm.eligible_count}</span>
                              {arm.pending_count > 0 && (
                                <span className="ml-1 text-[10px] text-amber-400">({arm.pending_count} pend)</span>
                              )}
                            </td>
                            <td className="py-3 px-3 font-mono font-bold text-emerald-400">
                              {(arm.recovery_rate * 100).toFixed(1)}%
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-400 text-[11px]">
                              [{(arm.wilson_ci_95[0] * 100).toFixed(1)}%, {(arm.wilson_ci_95[1] * 100).toFixed(1)}%]
                            </td>
                            <td className="py-3 px-3 font-mono text-emerald-400">
                              ₹{arm.total_recovered_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-200">
                              ₹{arm.revenue_per_eligible_case.toFixed(0)}
                            </td>
                            <td className="py-3 px-3">
                              {arm.strategy_deviation_count > 0 ? (
                                <span className="text-amber-400 text-[11px] flex items-center gap-1 font-medium">
                                  <ShieldAlert className="w-3.5 h-3.5" />
                                  {arm.strategy_deviation_count} ({ (arm.strategy_deviation_rate * 100).toFixed(1) }%)
                                </span>
                              ) : (
                                <span className="text-slate-500 text-[11px]">0</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Pairwise Hypothesis Tests (Treatment vs Control) */}
              {metrics && metrics.comparisons.length > 0 && (
                <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    Hypothesis Testing & Causal Lift Analysis (Two-Proportion Z-Test)
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {metrics.comparisons.map((cmp, idx) => (
                      <div key={idx} className="p-4 rounded-xl bg-dark-900 border border-dark-750 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">
                            {cmp.treatment_arm_id} <span className="text-slate-500">vs</span> {cmp.control_arm_id}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            cmp.recommendation === 'WINNER_TREATMENT'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              : cmp.recommendation === 'WINNER_CONTROL'
                              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                              : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          }`}>
                            {cmp.recommendation.replace(/_/g, ' ')}
                          </span>
                        </div>

                        <div className="grid grid-cols-3 gap-2 text-center py-2 bg-dark-850 rounded-lg">
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase">Absolute Lift</span>
                            <div className={`text-sm font-extrabold font-mono ${cmp.absolute_lift >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {cmp.absolute_lift >= 0 ? '+' : ''}{(cmp.absolute_lift * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase">Relative Lift</span>
                            <div className="text-sm font-extrabold font-mono text-white">
                              {cmp.relative_lift !== undefined && cmp.relative_lift !== null ? `${cmp.relative_lift > 0 ? '+' : ''}${cmp.relative_lift.toFixed(1)}%` : 'N/A'}
                            </div>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 uppercase">p-value</span>
                            <div className="text-sm font-extrabold font-mono text-brand-cyan">
                              {cmp.p_value.toFixed(4)}
                            </div>
                          </div>
                        </div>

                        <p className="text-[11px] text-slate-300 leading-relaxed">
                          {cmp.statistical_rationale}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Assigned Cases Telemetry */}
              <div className="p-5 rounded-2xl bg-dark-850 border border-dark-700 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-brand-cyan" />
                    Recent Assignment & Attribution Stream ({assignments.length})
                  </h4>
                  <span className="text-[10px] text-slate-400 font-mono">Deterministic Hash Bucketing</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-dark-700 text-slate-400">
                        <th className="py-2 px-3">Case ID</th>
                        <th className="py-2 px-3">Assigned Arm</th>
                        <th className="py-2 px-3">Assigned Strategy</th>
                        <th className="py-2 px-3">Executed Strategy</th>
                        <th className="py-2 px-3">Outcome</th>
                        <th className="py-2 px-3">Recovered Amount</th>
                        <th className="py-2 px-3">Bucket</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-800 font-mono">
                      {assignments.map((asgn) => (
                        <tr key={asgn.assignment_id} className="hover:bg-dark-800/40">
                          <td className="py-2 px-3 text-slate-300">{asgn.recovery_case_id}</td>
                          <td className="py-2 px-3 text-white font-medium">{asgn.arm_id}</td>
                          <td className="py-2 px-3 text-brand-cyan">{asgn.assigned_strategy}</td>
                          <td className="py-2 px-3 text-slate-300">
                            {asgn.is_strategy_deviated ? (
                              <span className="text-amber-400 font-bold flex items-center gap-1">
                                {asgn.actual_executed_strategy}*
                              </span>
                            ) : (
                              asgn.actual_executed_strategy || asgn.assigned_strategy
                            )}
                          </td>
                          <td className="py-2 px-3">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              asgn.outcome_status === 'RECOVERED'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : asgn.outcome_status === 'UNSUCCESSFUL'
                                ? 'bg-rose-500/20 text-rose-400'
                                : 'bg-slate-700 text-slate-300'
                            }`}>
                              {asgn.outcome_status || 'PENDING'}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-emerald-400 font-bold">
                            ₹{asgn.recovered_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </td>
                          <td className="py-2 px-3 text-slate-500 text-[11px]">{asgn.hash_bucket}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* CREATE EXPERIMENT MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-2xl bg-dark-900 border border-dark-700 rounded-2xl p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-dark-750 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FlaskConical className="w-5 h-5 text-brand-cyan" />
                Configure Controlled Recovery Experiment
              </h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Experiment Name</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. UPI Technical Timeout: Alt Rail vs Instant Link"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-white outline-none focus:border-brand-cyan"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Measurable Objective</label>
                <textarea
                  required
                  rows={2}
                  value={formObjective}
                  onChange={(e) => setFormObjective(e.target.value)}
                  placeholder="State the primary operational goal and measurable hypothesis..."
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-white outline-none focus:border-brand-cyan"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Target Payment Method</label>
                  <select
                    value={formPaymentMethod}
                    onChange={(e) => setFormPaymentMethod(e.target.value)}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-white outline-none focus:border-brand-cyan"
                  >
                    <option value="UPI">UPI</option>
                    <option value="CARD">CARD</option>
                    <option value="NETBANKING">NETBANKING</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Target Failure Category</label>
                  <select
                    value={formFailureCat}
                    onChange={(e) => setFormFailureCat(e.target.value)}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-white outline-none focus:border-brand-cyan"
                  >
                    <option value="UPI_TIMEOUT">UPI_TIMEOUT</option>
                    <option value="CARD_DECLINED">CARD_DECLINED</option>
                    <option value="BANK_SERVER_DOWN">BANK_SERVER_DOWN</option>
                    <option value="AUTHENTICATION_FAILED">AUTHENTICATION_FAILED</option>
                  </select>
                </div>
              </div>

              {/* Arms Setup */}
              <div className="space-y-2 pt-2 border-t border-dark-750">
                <span className="block text-slate-300 font-semibold">Candidate Strategy Arms (Must Sum to 100%)</span>
                {formArms.map((arm, idx) => (
                  <div key={idx} className="p-3 bg-dark-850 rounded-xl border border-dark-750 grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-3">
                      <input
                        type="text"
                        value={arm.arm_id}
                        onChange={(e) => {
                          const updated = [...formArms];
                          updated[idx].arm_id = e.target.value;
                          setFormArms(updated);
                        }}
                        className="w-full bg-dark-800 border border-dark-700 rounded px-2 py-1 text-white text-xs"
                      />
                    </div>
                    <div className="col-span-4">
                      <select
                        value={arm.strategy}
                        onChange={(e) => {
                          const updated = [...formArms];
                          updated[idx].strategy = e.target.value;
                          setFormArms(updated);
                        }}
                        className="w-full bg-dark-800 border border-dark-700 rounded px-2 py-1 text-white text-xs"
                      >
                        {CANONICAL_STRATEGIES.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={arm.traffic_percentage}
                        onChange={(e) => {
                          const updated = [...formArms];
                          updated[idx].traffic_percentage = Number(e.target.value);
                          setFormArms(updated);
                        }}
                        className="w-full bg-dark-800 border border-dark-700 rounded px-2 py-1 text-white text-xs"
                      />
                    </div>
                    <div className="col-span-3 flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={arm.is_control}
                        onChange={(e) => {
                          const updated = formArms.map((a, i) => ({ ...a, is_control: i === idx }));
                          setFormArms(updated);
                        }}
                        id={`control_${idx}`}
                      />
                      <label htmlFor={`control_${idx}`} className="text-slate-300 text-[10px]">Control Arm</label>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="sandbox_toggle"
                  checked={formSandbox}
                  onChange={(e) => setFormSandbox(e.target.checked)}
                />
                <label htmlFor="sandbox_toggle" className="text-slate-300">
                  Enable Sandbox Isolation (Fintech safety: Live real customers excluded by default)
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-dark-750">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-dark-750 text-slate-300 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 rounded-lg bg-brand-cyan text-dark-900 font-bold hover:bg-brand-cyan/90 transition disabled:opacity-50"
                >
                  {formSubmitting ? 'Validating...' : 'Create Experiment (Draft)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OFFLINE SIMULATION MODAL */}
      {showSimulateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-xl bg-dark-900 border border-dark-700 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-dark-750 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-400" />
                Offline Multi-Armed Bandit & Policy Simulation
              </h3>
              <button onClick={() => setShowSimulateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-dark-850 border border-dark-700 text-xs text-slate-300 space-y-1">
              <span className="font-semibold text-white">Scientific Sandbox Isolation:</span>
              <p>Simulates deterministic traffic allocation or adaptive Thompson Sampling over synthetic evaluation fixtures without affecting live recovery cases.</p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Simulated Cohort Size</label>
                <input
                  type="number"
                  min="20"
                  max="500"
                  value={simCohortSize}
                  onChange={(e) => setSimCohortSize(Number(e.target.value))}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Bandit Algorithm</label>
                <div className="flex items-center gap-2 mt-2">
                  <input
                    type="checkbox"
                    id="bandit_toggle"
                    checked={simUseBandit}
                    onChange={(e) => setSimUseBandit(e.target.checked)}
                  />
                  <label htmlFor="bandit_toggle" className="text-slate-300">
                    Thompson Sampling
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={handleRunSimulation}
                disabled={simulating}
                className="px-4 py-2 rounded-lg bg-amber-500 text-dark-900 font-bold hover:bg-amber-400 transition flex items-center gap-2 text-xs disabled:opacity-50"
              >
                {simulating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Run Offline Simulation
              </button>
            </div>

            {/* Simulation Results Display */}
            {simulationResult && (
              <div className="mt-4 p-4 rounded-xl bg-dark-850 border border-amber-500/30 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white uppercase tracking-wider">Simulation Output ({simulationResult.allocation_method})</span>
                  <span className="text-amber-400 font-mono">ID: {simulationResult.simulation_id}</span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-center py-2 bg-dark-900 rounded-lg">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">Simulated Lift</span>
                    <div className="text-sm font-extrabold text-emerald-400 font-mono">
                      +{(simulationResult.simulated_absolute_lift * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">Simulated Revenue Gain</span>
                    <div className="text-sm font-extrabold text-brand-cyan font-mono">
                      ₹{simulationResult.simulated_revenue_gain.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                  </div>
                </div>

                <div className="space-y-1">
                  {simulationResult.arm_results.map((r, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px] py-1 border-b border-dark-800">
                      <span className="text-slate-300 font-mono">{r.arm_id} ({r.strategy})</span>
                      <span className="text-emerald-400 font-bold">{(r.recovery_rate * 100).toFixed(1)}% ({r.recovered}/{r.assigned})</span>
                    </div>
                  ))}
                </div>

                <p className="text-[10px] text-slate-500 italic mt-1">
                  {simulationResult.methodology_disclaimer}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
