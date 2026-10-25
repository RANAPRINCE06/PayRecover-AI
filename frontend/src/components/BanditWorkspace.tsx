import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain,
  Shield,
  Layers,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  Loader2,
  Sliders,
  Play,
  Scale,
  ArrowRight,
  Info,
  Clock,
  ExternalLink,
  ChevronRight,
  Activity,
  Zap,
  Flame,
  Award
} from 'lucide-react';
import {
  BanditPolicyStatusResponse,
  BanditShadowDecisionItem,
  BanditRecommendationResponse,
  BanditOfflineEvaluationResponse
} from '../types';
import { api } from '../services/api';

export const BanditWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'weights' | 'decisions' | 'sandbox' | 'offline_eval'>('weights');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [status, setStatus] = useState<BanditPolicyStatusResponse | null>(null);

  // Shadow decisions state
  const [decisions, setDecisions] = useState<BanditShadowDecisionItem[]>([]);
  const [decisionsTotal, setDecisionsTotal] = useState(0);
  const [agreementRate, setAgreementRate] = useState(100.0);
  const [decisionFilterAgreement, setDecisionFilterAgreement] = useState<'ALL' | 'AGREED' | 'DIVERGENT'>('ALL');
  const [decisionsPage, setDecisionsPage] = useState(1);

  // Sandbox state
  const [sandboxMethod, setSandboxMethod] = useState('UPI');
  const [sandboxFailure, setSandboxFailure] = useState('TECHNICAL_TIMEOUT');
  const [sandboxAmount, setSandboxAmount] = useState(4500);
  const [sandboxRetries, setSandboxRetries] = useState(0);
  const [sandboxIntent, setSandboxIntent] = useState('TECH_DIFFICULTY');
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<BanditRecommendationResponse | null>(null);

  // Offline eval state
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalResult, setEvalResult] = useState<BanditOfflineEvaluationResponse | null>(null);
  const [evalSplitPct, setEvalSplitPct] = useState(0.7);
  const [evalAlpha, setEvalAlpha] = useState(1.0);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getBanditPolicyStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to load bandit policy status:', err);
    }
  }, []);

  const fetchDecisions = useCallback(async () => {
    try {
      const agreementParam =
        decisionFilterAgreement === 'ALL' ? undefined : decisionFilterAgreement === 'AGREED';
      const data = await api.getBanditShadowDecisions(decisionsPage, 15, agreementParam);
      setDecisions(data.items);
      setDecisionsTotal(data.total);
      setAgreementRate(data.agreement_rate);
    } catch (err) {
      console.error('Failed to load shadow decisions:', err);
    }
  }, [decisionsPage, decisionFilterAgreement]);

  const loadData = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchStatus(), fetchDecisions()]);
    setLoading(false);
  }, [fetchStatus, fetchDecisions]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchStatus(), fetchDecisions()]);
    setRefreshing(false);
  };

  const handleRunSandbox = async () => {
    setSandboxLoading(true);
    try {
      const res = await api.getBanditRecommendation({
        payment_method: sandboxMethod,
        failure_category: sandboxFailure,
        amount: sandboxAmount,
        retry_count: sandboxRetries,
        customer_intent: sandboxIntent
      });
      setSandboxResult(res);
    } catch (err) {
      console.error('Sandbox evaluation failed:', err);
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleRunOfflineEval = async () => {
    setEvalLoading(true);
    try {
      const res = await api.evaluateBanditOffline({
        policy_type: 'LINUCB',
        alpha_exploration: evalAlpha,
        temporal_split_pct: evalSplitPct,
        random_seed: 42
      });
      setEvalResult(res);
    } catch (err) {
      console.error('Offline evaluation failed:', err);
    } finally {
      setEvalLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="w-8 h-8 text-brand-cyan animate-spin" />
        <p className="text-xs text-slate-400 font-medium">Initializing Contextual Bandit Policy & Safe Envelopes...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* SHADOW MODE ALERT BANNER */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-violet-950/40 via-dark-850 to-dark-850 border border-violet-500/30 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/30 flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-violet-400" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white font-mono">LinUCB Contextual Bandit Engine</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30 flex items-center gap-1">
                <Shield className="w-3 h-3 text-violet-400" /> SHADOW MODE ACTIVE
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-dark-750 text-slate-300">
                Schema {status?.feature_schema_version || 'v1.0'}
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              Evaluating multi-armed contextual strategy decisions in parallel with the production orchestrator.
              <strong className="text-white"> Policy recommendations are completely isolated from live execution</strong> and strictly bounded by deterministic financial safety envelopes (high-value approval, discount ceilings, and quiet hours).
            </p>
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="p-2 bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-300 hover:text-white rounded-lg transition disabled:opacity-50 shrink-0"
          title="Refresh Bandit telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-brand-cyan' : ''}`} />
        </button>
      </div>

      {/* TOP KPI STRIP */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Shadow Decisions Logged</span>
          <div className="text-2xl font-extrabold text-brand-cyan font-mono mt-1">
            {status?.total_decisions_logged ?? decisionsTotal}
          </div>
          <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
            <Activity className="w-3 h-3 text-cyan-400" /> Continuous shadow evaluation
          </div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Production Agreement</span>
          <div className="text-2xl font-extrabold text-emerald-400 font-mono mt-1">
            {status?.agreement_rate_with_production ?? agreementRate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Alignment with expert heuristics
          </div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Exploration Parameter (α)</span>
          <div className="text-2xl font-extrabold text-amber-400 font-mono mt-1">
            {status?.alpha_exploration.toFixed(2) ?? '1.00'}
          </div>
          <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
            <Sliders className="w-3 h-3 text-amber-400" /> Upper confidence bound bonus
          </div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Ridge Regularizer (λ)</span>
          <div className="text-2xl font-extrabold text-violet-400 font-mono mt-1">
            {status?.ridge_lambda.toFixed(2) ?? '1.00'}
          </div>
          <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
            <Scale className="w-3 h-3 text-violet-400" /> Disjoint matrix conditioning
          </div>
        </div>
      </div>

      {/* NAVIGATION SUB-TABS */}
      <div className="flex items-center gap-2 border-b border-dark-700 pb-2">
        <button
          onClick={() => setActiveTab('weights')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'weights'
              ? 'bg-brand-cyan text-dark-900 shadow-glow-cyan'
              : 'text-slate-400 hover:text-white hover:bg-dark-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Learned Weights & Arm Models
        </button>

        <button
          onClick={() => setActiveTab('decisions')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'decisions'
              ? 'bg-brand-cyan text-dark-900 shadow-glow-cyan'
              : 'text-slate-400 hover:text-white hover:bg-dark-800'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Shadow Decisions Audit Stream
          <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-dark-700 text-slate-300">
            {decisionsTotal}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('sandbox')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'sandbox'
              ? 'bg-brand-cyan text-dark-900 shadow-glow-cyan'
              : 'text-slate-400 hover:text-white hover:bg-dark-800'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          Context Recommendation Sandbox
        </button>

        <button
          onClick={() => setActiveTab('offline_eval')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'offline_eval'
              ? 'bg-brand-cyan text-dark-900 shadow-glow-cyan'
              : 'text-slate-400 hover:text-white hover:bg-dark-800'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          Offline Policy Evaluation (OPE)
        </button>
      </div>

      {/* TAB 1: LEARNED WEIGHTS & DISJOINT MODELS */}
      {activeTab === 'weights' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              Disjoint Linear Ridge Regression Models θ̂ₐ = Aₐ⁻¹ bₐ for each canonical strategy envelope:
            </span>
            <span className="text-[11px] font-mono text-brand-cyan">Feature Dimension: 21 numerical features</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {status?.arms.map((arm) => (
              <div
                key={arm.arm_name}
                className="p-4 rounded-xl bg-dark-850 border border-dark-750 hover:border-brand-cyan/40 transition space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-xs font-mono">{arm.arm_name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-dark-800 text-slate-300 border border-dark-700">
                    N = {arm.sample_count} observations
                  </span>
                </div>

                <div className="space-y-1.5 text-[11px]">
                  <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider block">
                    Top Positive Coefficients:
                  </span>
                  {arm.top_positive_features.length > 0 ? (
                    <div className="space-y-1">
                      {arm.top_positive_features.map((f, i) => (
                        <div key={i} className="flex items-center justify-between text-slate-300 font-mono">
                          <span className="text-slate-400">+{f.feature}</span>
                          <span className="text-emerald-400 font-bold">+{f.weight.toFixed(3)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-slate-500 text-[10px]">Priors initialized uniformly.</span>
                  )}
                </div>

                <div className="space-y-1.5 text-[11px] pt-1 border-t border-dark-750">
                  <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider block">
                    Top Negative Coefficients:
                  </span>
                  {arm.top_negative_features.length > 0 ? (
                    <div className="space-y-1">
                      {arm.top_negative_features.map((f, i) => (
                        <div key={i} className="flex items-center justify-between text-slate-300 font-mono">
                          <span className="text-slate-400">{f.feature}</span>
                          <span className="text-rose-400 font-bold">{f.weight.toFixed(3)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-slate-500 text-[10px]">No negative penalties learned yet.</span>
                  )}
                </div>

                <div className="pt-2 border-t border-dark-750 flex items-center justify-between text-[10px] text-slate-400">
                  <span>Uncertainty Score (1/√N):</span>
                  <span className="font-mono text-amber-400 font-bold">{arm.uncertainty_score.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: SHADOW DECISIONS STREAM */}
      {activeTab === 'decisions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">Filter Agreement:</span>
              {(['ALL', 'AGREED', 'DIVERGENT'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => {
                    setDecisionFilterAgreement(mode);
                    setDecisionsPage(1);
                  }}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                    decisionFilterAgreement === mode
                      ? 'bg-dark-700 text-white border border-dark-600'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>

            <div className="text-xs text-slate-400 font-mono">
              Total Decisions: <strong className="text-white">{decisionsTotal}</strong>
            </div>
          </div>

          {decisions.length === 0 ? (
            <div className="py-16 text-center text-slate-500 text-xs">
              No shadow decisions recorded yet. Decisions are automatically logged when recovery cases run through the orchestrator.
            </div>
          ) : (
            <div className="space-y-2.5">
              {decisions.map((dec) => (
                <div
                  key={dec.id}
                  className="p-3.5 rounded-xl bg-dark-850 border border-dark-750 hover:border-dark-600 transition space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white font-bold">{dec.recovery_case_id}</span>
                      <span className="text-slate-500 font-mono">[{dec.payment_id}]</span>
                    </div>

                    <div className="flex items-center gap-2">
                      {dec.is_agreement ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Agreement with Production
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> Divergent Recommendation
                        </span>
                      )}

                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          dec.eventual_outcome === 'RECOVERED'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : dec.eventual_outcome === 'UNSUCCESSFUL'
                            ? 'bg-rose-500/10 text-rose-400'
                            : 'bg-dark-750 text-slate-400'
                        }`}
                      >
                        {dec.eventual_outcome}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] bg-dark-900 p-2.5 rounded-lg border border-dark-750 font-mono">
                    <div>
                      <span className="text-slate-500 block text-[10px]">Production Selected Strategy:</span>
                      <span className="text-slate-200 font-bold">{dec.production_strategy}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">LinUCB Recommended Arm:</span>
                      <span className="text-brand-cyan font-bold flex items-center gap-1">
                        {dec.selected_action}
                        <span className="text-[10px] text-slate-400 font-normal">
                          (Exp: {dec.predicted_reward.toFixed(2)} + Width: {dec.confidence_width.toFixed(2)})
                        </span>
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-300 font-sans leading-relaxed">
                    {dec.selection_reason}
                  </p>

                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-dark-750/50">
                    <span>Decision Time: {new Date(dec.decision_timestamp).toLocaleString()}</span>
                    {dec.actual_reward !== null && dec.actual_reward !== undefined && (
                      <span className="font-mono text-emerald-400 font-bold">
                        Authoritative Economic Reward: {dec.actual_reward.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: INTERACTIVE RECOMMENDATION SANDBOX */}
      {activeTab === 'sandbox' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 p-5 rounded-xl bg-dark-850 border border-dark-750 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-brand-cyan" />
              Context Input Simulator
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Input hypothetical payment transaction telemetry to inspect LinUCB scoring, safe policy envelope filtering, and feature attributions in real time.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Payment Method</label>
                <select
                  value={sandboxMethod}
                  onChange={(e) => setSandboxMethod(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-white font-mono"
                >
                  <option value="UPI">UPI</option>
                  <option value="CARD">Credit/Debit Card</option>
                  <option value="NETBANKING">Net Banking</option>
                  <option value="MANDATE">Recurring E-Mandate</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Failure Reason Category</label>
                <select
                  value={sandboxFailure}
                  onChange={(e) => setSandboxFailure(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-white font-mono"
                >
                  <option value="TECHNICAL_TIMEOUT">TECHNICAL_TIMEOUT (Bank/PSP Latency)</option>
                  <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS (Balance Deficit)</option>
                  <option value="CARD_DECLINED">CARD_DECLINED (Issuing Bank Decline)</option>
                  <option value="AUTHENTICATION_FAILED">AUTHENTICATION_FAILED (OTP/3DS Drop)</option>
                  <option value="USER_DROPPED">USER_DROPPED (Abandoned Checkout)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 flex items-center justify-between">
                  <span>Transaction Amount (₹)</span>
                  <span className="font-mono text-brand-cyan">₹{sandboxAmount.toLocaleString()}</span>
                </label>
                <input
                  type="range"
                  min="500"
                  max="75000"
                  step="500"
                  value={sandboxAmount}
                  onChange={(e) => setSandboxAmount(Number(e.target.value))}
                  className="w-full accent-brand-cyan"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
                  <span>₹500</span>
                  <span className="text-amber-400">₹50,000 High-Value Threshold</span>
                  <span>₹75,000</span>
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Retry Count</label>
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={sandboxRetries}
                  onChange={(e) => setSandboxRetries(Number(e.target.value))}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-white font-mono"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Customer Intent Signal</label>
                <select
                  value={sandboxIntent}
                  onChange={(e) => setSandboxIntent(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-white font-mono"
                >
                  <option value="TECH_DIFFICULTY">TECH_DIFFICULTY (Facing app error)</option>
                  <option value="WILL_PAY_LATER">WILL_PAY_LATER (Remind me tomorrow)</option>
                  <option value="PRICE_CONCERN">PRICE_CONCERN (Too expensive / seeking discount)</option>
                  <option value="ALTERNATE_METHOD">ALTERNATE_METHOD (Wants QR/UPI instead)</option>
                </select>
              </div>

              <button
                onClick={handleRunSandbox}
                disabled={sandboxLoading}
                className="w-full py-2.5 rounded-lg bg-brand-cyan text-dark-900 font-bold hover:brightness-110 transition flex items-center justify-center gap-2"
              >
                {sandboxLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-dark-900" />}
                Evaluate Contextual Recommendation
              </button>
            </div>
          </div>

          <div className="lg:col-span-7 p-5 rounded-xl bg-dark-850 border border-dark-750 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              Bandit Recommendation & Policy Envelope
            </h3>

            {sandboxResult ? (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-dark-900 border border-brand-cyan/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Recommended Strategy Arm</span>
                    <span className="text-xs font-mono text-emerald-400 font-bold">
                      UCB Score: {sandboxResult.ucb_score.toFixed(3)}
                    </span>
                  </div>
                  <div className="text-xl font-extrabold text-white font-mono">
                    {sandboxResult.selected_action}
                  </div>
                  <div className="text-xs text-slate-400 font-mono flex items-center gap-3 pt-1">
                    <span>Expected Reward: <strong className="text-brand-cyan">+{sandboxResult.predicted_reward.toFixed(3)}</strong></span>
                    <span>Exploration Width: <strong className="text-amber-400">+{sandboxResult.confidence_width.toFixed(3)}</strong></span>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-300">Decision Explanation:</span>
                  <p className="text-xs text-slate-400 bg-dark-900 p-3 rounded-lg border border-dark-750 leading-relaxed">
                    {sandboxResult.selection_reason}
                  </p>
                </div>

                <div className="space-y-2">
                  <span className="text-xs font-semibold text-slate-300">Safe Policy Envelope (Eligible Actions):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {sandboxResult.eligible_actions.map((act) => (
                      <span
                        key={act}
                        className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium ${
                          act === sandboxResult.selected_action
                            ? 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/40 font-bold'
                            : 'bg-dark-900 text-slate-300 border border-dark-750'
                        }`}
                      >
                        {act}
                      </span>
                    ))}
                  </div>
                </div>

                {sandboxResult.guardrail_overrides.length > 0 && (
                  <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 space-y-1">
                    <span className="font-bold flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> Hard Guardrails Applied:
                    </span>
                    <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                      {sandboxResult.guardrail_overrides.map((g, idx) => (
                        <li key={idx}>{g}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-24 text-center text-slate-500 text-xs">
                Configure context attributes on the left and click "Evaluate Contextual Recommendation" to inspect decision scoring.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: OFFLINE POLICY EVALUATION (OPE) */}
      {activeTab === 'offline_eval' && (
        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-dark-850 border border-dark-750 flex items-center justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <span className="text-sm font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand-cyan" />
                Offline Policy Evaluation (OPE) via Replay & Doubly Robust Estimator
              </span>
              <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
                Evaluates LinUCB against deterministic Historical Best, Epsilon-Greedy, and Oracle benchmarks over verified historical outcomes with strict temporal splitting.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-xs space-y-0.5">
                <span className="text-slate-400 block text-[10px]">Temporal Split</span>
                <span className="font-mono text-white font-bold">{Math.round(evalSplitPct * 100)}% Train / {Math.round((1 - evalSplitPct) * 100)}% Test</span>
              </div>

              <button
                onClick={handleRunOfflineEval}
                disabled={evalLoading}
                className="px-4 py-2 rounded-lg bg-brand-cyan text-dark-900 font-bold hover:brightness-110 transition flex items-center gap-2 text-xs"
              >
                {evalLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-dark-900" />}
                Run Off-Policy Evaluation
              </button>
            </div>
          </div>

          {evalResult ? (
            <div className="space-y-6">
              {/* COMPARATIVE POLICIES TABLE */}
              <div className="rounded-xl border border-dark-700 overflow-hidden bg-dark-850">
                <div className="p-3.5 bg-dark-800/80 border-b border-dark-750 flex items-center justify-between">
                  <span className="text-xs font-bold text-white">Policy Performance Matrix (Test Cohort N={evalResult.test_size})</span>
                  <span className="text-[11px] font-mono text-emerald-400 font-bold">
                    Winner: {evalResult.winner_policy} (+{evalResult.lift_over_historical_best.toFixed(1)}% Lift)
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-dark-750 text-slate-400 text-[10px] uppercase font-semibold">
                        <th className="py-2.5 px-4">Policy Algorithm</th>
                        <th className="py-2.5 px-4">Recovery Rate</th>
                        <th className="py-2.5 px-4">Mean Reward / Case</th>
                        <th className="py-2.5 px-4">Recovered Rev / Case</th>
                        <th className="py-2.5 px-4">Avg Discount Cost</th>
                        <th className="py-2.5 px-4">Human Escalation</th>
                        <th className="py-2.5 px-4">Simulated Regret</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-750/50 font-mono text-[11px]">
                      {Object.values(evalResult.policies).map((p) => {
                        const isWinner = p.policy_name === evalResult.winner_policy;
                        const isOracle = p.policy_name === 'ORACLE_BENCHMARK';
                        return (
                          <tr
                            key={p.policy_name}
                            className={`hover:bg-dark-800/50 transition ${
                              isWinner ? 'bg-emerald-500/5 font-bold text-white' : 'text-slate-300'
                            }`}
                          >
                            <td className="py-3 px-4 flex items-center gap-2">
                              {isWinner && <Award className="w-4 h-4 text-emerald-400" />}
                              {isOracle && <Sparkles className="w-4 h-4 text-amber-400" />}
                              <span>{p.policy_name}</span>
                            </td>
                            <td className="py-3 px-4">
                              <span className={isWinner ? 'text-emerald-400 text-sm font-extrabold' : 'text-slate-200'}>
                                {p.estimated_recovery_rate.toFixed(1)}%
                              </span>
                            </td>
                            <td className="py-3 px-4 font-bold text-brand-cyan">
                              +{p.mean_reward_per_case.toFixed(3)}
                            </td>
                            <td className="py-3 px-4">₹{p.mean_revenue_recovered.toLocaleString()}</td>
                            <td className="py-3 px-4 text-slate-400">{p.mean_discount_cost.toFixed(1)}%</td>
                            <td className="py-3 px-4 text-slate-400">{p.human_escalation_rate.toFixed(1)}%</td>
                            <td className="py-3 px-4 text-rose-400">{p.simulated_regret.toFixed(2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* CATEGORY BREAKDOWN */}
              <div className="p-4 rounded-xl bg-dark-850 border border-dark-750 space-y-3">
                <span className="text-xs font-bold text-white block">Recovery Rate Lift by Failure Category:</span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {Object.entries(evalResult.category_breakdown).map(([cat, stats]) => (
                    <div key={cat} className="p-3 rounded-lg bg-dark-900 border border-dark-750 space-y-1">
                      <span className="text-[10px] text-slate-400 font-mono block">{cat}</span>
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span>LinUCB: <strong className="text-emerald-400">{stats.linucb_rate}%</strong></span>
                        <span className="text-slate-500">vs</span>
                        <span>Hist Best: <strong className="text-slate-300">{stats.hist_rate}%</strong></span>
                      </div>
                      <span className="text-[9px] text-slate-500 block">N={stats.sample_size} cases</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* METHODOLOGICAL INTEGRITY DISCLAIMER */}
              <div className="p-3 rounded-lg bg-dark-800 border border-dark-700 flex items-start gap-2.5 text-[11px] text-slate-400">
                <Info className="w-4 h-4 text-brand-cyan shrink-0 mt-0.5" />
                <span>{evalResult.limitations_disclaimer}</span>
              </div>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-500 text-xs">
              Click "Run Off-Policy Evaluation" to benchmark LinUCB against historical baselines over verified historical datasets.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
