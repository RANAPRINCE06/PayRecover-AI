import React, { useState, useEffect } from 'react';
import {
  MessageSquareCode,
  Sparkles,
  TrendingUp,
  Target,
  AlertTriangle,
  HelpCircle,
  Zap,
  ArrowRight,
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import { AICopilotChat } from '../components/AICopilotChat';
import { RevenueRiskCard } from '../components/RevenueRiskCard';
import { RecoveryOpportunityCard } from '../components/RecoveryOpportunityCard';
import { DecisionExplanationModal } from '../components/DecisionExplanationModal';
import { AgentTraceViewer } from '../components/AgentTraceViewer';
import { api } from '../services/api';
import { RevenueAtRisk, OpportunityScore } from '../types';
import { useToast } from '../components/Toast';

export const AICopilotPage: React.FC = () => {
  const { success, error, info } = useToast();
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [riskData, setRiskData] = useState<RevenueAtRisk | null>(null);
  const [opportunities, setOpportunities] = useState<OpportunityScore[]>([]);
  const [loadingContext, setLoadingContext] = useState(true);

  // Modals
  const [explanationCaseId, setExplanationCaseId] = useState<string | null>(null);
  const [traceCaseId, setTraceCaseId] = useState<string | null>(null);

  const fetchContextData = async () => {
    setLoadingContext(true);
    try {
      const [riskRes, oppsRes] = await Promise.all([
        api.getRevenueAtRisk().catch(() => null),
        api.getRecoveryOpportunities(5).catch(() => ({ opportunities: [] }))
      ]);

      if (riskRes) setRiskData(riskRes);

      if (oppsRes && oppsRes.opportunities) {
        // Map to OpportunityScore structure
        const mapped: OpportunityScore[] = oppsRes.opportunities.map((o: any) => ({
          case_id: o.case_id,
          payment_id: o.payment_id,
          amount: o.amount,
          currency: o.currency || 'INR',
          customer_name: o.customer_name,
          customer_tier: o.priority || 'STANDARD',
          failure_reason: o.failure_reason,
          score: o.recovery_score || 80,
          priority: o.priority || (o.recovery_score >= 80 ? 'CRITICAL' : 'HIGH'),
          positive_factors: o.positive_factors || ['High customer engagement', 'Transient gateway drop-off'],
          negative_factors: o.negative_factors || ['Standard recovery window'],
          recommended_strategy: o.current_strategy || 'ALTERNATE_PAYMENT_METHOD',
          estimated_recovery_probability: o.recovery_probability || 0.8,
          is_heuristic: true
        }));
        setOpportunities(mapped);
      }
    } catch (err: any) {
      console.error('Failed to load copilot side context:', err);
    } finally {
      setLoadingContext(false);
    }
  };

  useEffect(() => {
    fetchContextData();
  }, []);

  const handleApplyStrategy = async (caseId: string, strategy: string) => {
    info(`Triggering ${strategy.replace(/_/g, ' ')} on Case #${caseId.slice(0, 8)}...`);
    try {
      await api.executeRecoveryAction(caseId, {
        tool_type: 'CREATE_PAYMENT_LINK',
        parameters: { strategy }
      });
      success(`Recovery strategy dispatched successfully for Case #${caseId.slice(0, 8)}!`);
      fetchContextData();
    } catch (err: any) {
      error(`Action failed: ${err.message || err}`);
    }
  };

  const promptCategories = [
    {
      category: 'Revenue & Performance',
      prompts: [
        'What is my biggest recovery opportunity?',
        'How much revenue is currently at risk?',
        'How much revenue did AI recover this week?'
      ]
    },
    {
      category: 'Diagnostics & Telemetry',
      prompts: [
        'Which payment method is failing the most?',
        'Why did recovery revenue drop today?',
        'Why are customers abandoning checkout?'
      ]
    },
    {
      category: 'Strategic Next Steps',
      prompts: [
        'Which recovery strategy performs best?',
        'What should I fix first?',
        'Show high-value cases requiring approval'
      ]
    }
  ];

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 px-2.5 py-0.5 rounded-full border border-cyan-500/20 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" /> AI Revenue Copilot
            </span>
            <span className="text-xs text-slate-400">• Grounded Telemetry & Explainability</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            Revenue Intelligence Copilot
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Conversational executive insights, revenue-at-risk prioritization, and autonomous multi-agent explainability.
          </p>
        </div>

        <button
          onClick={fetchContextData}
          disabled={loadingContext}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 text-slate-300 hover:text-white text-xs font-semibold transition-all shadow-md self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingContext ? 'animate-spin text-cyan-400' : ''}`} />
          <span>Refresh Context</span>
        </button>
      </div>

      {/* 3-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Prompt Library & Categories (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 shadow-lg">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquareCode className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                Suggested Prompts
              </h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Click any question to query real-time database analytics:
            </p>

            <div className="space-y-4">
              {promptCategories.map((group, gIdx) => (
                <div key={gIdx} className="space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block px-1">
                    {group.category}
                  </span>
                  {group.prompts.map((p, pIdx) => (
                    <button
                      key={pIdx}
                      onClick={() => setSelectedPrompt(p)}
                      className="w-full text-left p-2.5 rounded-xl bg-slate-950/40 hover:bg-cyan-500/10 border border-slate-800/80 hover:border-cyan-500/30 text-xs text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-between group"
                    >
                      <span className="line-clamp-2">{p}</span>
                      <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-cyan-400 shrink-0 ml-1.5 transition-transform group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* Quick Guidance Box */}
          <div className="p-4 bg-slate-900/40 border border-slate-800/60 rounded-2xl text-xs space-y-2 text-slate-400">
            <div className="flex items-center gap-1.5 font-semibold text-slate-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Grounded Guardrail Engine</span>
            </div>
            <p className="leading-relaxed">
              Every answer is verified against your PostgreSQL transaction ledger. The Copilot cannot execute actions without merchant approval when guardrail thresholds are crossed.
            </p>
          </div>
        </div>

        {/* Center Column: Live Chat Interface (5 cols) */}
        <div className="lg:col-span-5 h-[720px]">
          <AICopilotChat
            externalQuery={selectedPrompt}
            onExecuteAction={(action, caseId) => {
              if (caseId) {
                handleApplyStrategy(caseId, action);
              }
            }}
          />
        </div>

        {/* Right Column: Live Context & Opportunities (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Revenue at Risk Summary */}
          <RevenueRiskCard data={riskData} loading={loadingContext} />

          {/* Top Opportunities */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Top Recovery Opportunities
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Ranked by Expected ROI</span>
            </div>

            {loadingContext ? (
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-44 bg-slate-900/60 rounded-2xl border border-slate-800 animate-pulse" />
                ))}
              </div>
            ) : opportunities.length === 0 ? (
              <div className="p-6 bg-slate-900/40 border border-slate-800/60 rounded-2xl text-center text-xs text-slate-400">
                No active recovery opportunities found. Pipeline is fully resolved.
              </div>
            ) : (
              <div className="space-y-4">
                {opportunities.map((opp) => (
                  <RecoveryOpportunityCard
                    key={opp.case_id}
                    opportunity={opp}
                    onSelectAction={(caseId, strat) => handleApplyStrategy(caseId, strat)}
                    onViewExplanation={(caseId) => setExplanationCaseId(caseId)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      {explanationCaseId && (
        <DecisionExplanationModal
          caseId={explanationCaseId}
          onClose={() => setExplanationCaseId(null)}
        />
      )}

      {traceCaseId && (
        <AgentTraceViewer
          caseId={traceCaseId}
          onClose={() => setTraceCaseId(null)}
        />
      )}
    </div>
  );
};
