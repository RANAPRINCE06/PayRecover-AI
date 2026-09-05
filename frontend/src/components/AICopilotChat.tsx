import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  ArrowRight,
  Loader2,
  CheckCircle2,
  Database,
  ShieldCheck,
  CornerDownLeft
} from 'lucide-react';
import { api } from '../services/api';
import { CopilotResponse } from '../types';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  data?: CopilotResponse;
  timestamp: string;
}

interface AICopilotChatProps {
  onExecuteAction?: (actionKey: string, caseId?: string) => void;
  externalQuery?: string | null;
}

export const AICopilotChat: React.FC<AICopilotChatProps> = ({ onExecuteAction, externalQuery }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'bot',
      text: 'Hello! I am your PayRecover AI Copilot. I analyze real-time payment telemetry, failure patterns, and customer intent to optimize your revenue recovery. Ask me anything about your payments, revenue at risk, or recovery strategy.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      data: {
        reply: 'Hello! I am your PayRecover AI Copilot.',
        insights: [
          'All answers are strictly grounded in your active PostgreSQL database context.',
          'Opportunity scoring factors in failure transience, customer history, and intent.'
        ],
        recommended_actions: [
          { label: 'What is my biggest recovery opportunity?', action: 'QUERY_BIGGEST_OPPORTUNITY' },
          { label: 'How much revenue is currently at risk?', action: 'QUERY_REVENUE_RISK' },
          { label: 'Which payment method is failing the most?', action: 'QUERY_METHOD_FAILURES' }
        ],
        confidence: 0.95,
        confidence_level: 'HIGH',
        data_sources: ['PostgreSQL: recovery_cases', 'PostgreSQL: payments']
      }
    }
  ]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    if (externalQuery) {
      handleSend(externalQuery);
    }
  }, [externalQuery]);

  const handleSend = async (queryText?: string) => {
    const promptToSend = queryText || input;
    if (!promptToSend.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: promptToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.askCopilot(promptToSend);
      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: res.answer || res.reply,
        data: res,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'bot',
        text: `Error reaching AI Copilot: ${err.message || err}. Please ensure database connection is healthy.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl overflow-hidden backdrop-blur-sm">
      {/* Chat Messages Viewport */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div
              key={m.id}
              className={`flex gap-3.5 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
                  isUser
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                    : 'bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`rounded-2xl p-4 text-sm leading-relaxed space-y-3 ${
                  isUser
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-slate-950/70 border border-slate-800/80 text-slate-100 shadow-md'
                }`}
              >
                <div className="flex items-center justify-between gap-4 text-[10px] text-slate-400 font-mono">
                  <span>{isUser ? 'You' : 'PayRecover AI Copilot'}</span>
                  <span>{m.timestamp}</span>
                </div>

                <p className="whitespace-pre-wrap">{m.text}</p>

                {/* Structured Insights if present */}
                {!isUser && m.data && m.data.insights && m.data.insights.length > 0 && (
                  <div className="pt-3 border-t border-slate-800/80 space-y-2">
                    <span className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider block">
                      Key Grounded Telemetry Insights
                    </span>
                    <div className="space-y-1.5">
                      {m.data.insights.map((insight, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                          <span>{insight}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended Actions Pills */}
                {!isUser && m.data && m.data.recommended_actions && m.data.recommended_actions.length > 0 && (
                  <div className="pt-3 border-t border-slate-800/80">
                    <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-2">
                      Suggested Actions & Queries
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {m.data.recommended_actions.map((act, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            if (act.action.startsWith('QUERY_')) {
                              handleSend(act.label);
                            } else if (onExecuteAction) {
                              onExecuteAction(act.action, act.case_id);
                            } else {
                              handleSend(act.label);
                            }
                          }}
                          className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs font-medium flex items-center gap-1.5 transition-all"
                        >
                          <Sparkles className="w-3 h-3 text-cyan-400" />
                          <span>{act.label}</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Confidence & Grounding Footer */}
                {!isUser && m.data && (
                  <div className="pt-2 border-t border-slate-850 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span className="flex items-center gap-1 text-emerald-400">
                      <ShieldCheck className="w-3 h-3" />
                      Confidence: {Math.round((m.data.confidence || 0.9) * 100)}% ({m.data.confidence_level || 'HIGH'})
                    </span>
                    {m.data.data_sources && m.data.data_sources.length > 0 && (
                      <span className="flex items-center gap-1 text-slate-400">
                        <Database className="w-3 h-3 text-slate-400" />
                        Grounded in DB
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3.5 max-w-xl mr-auto">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-950/70 border border-slate-800 rounded-2xl p-4 flex items-center gap-3 text-slate-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              <span>Querying recovery telemetry & synthesizing grounded response...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/80">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="relative flex items-center"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about revenue drop, biggest recovery opportunity, failed payment trends, or strategies..."
            rows={2}
            className="w-full bg-slate-900 border border-slate-800 focus:border-cyan-500/60 rounded-xl px-4 py-3 pr-14 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 resize-none transition-all"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="absolute right-2.5 bottom-2.5 p-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-cyan-500/20"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
        <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
          <span>Press <strong>Enter</strong> to send, <strong>Shift + Enter</strong> for new line</span>
          <span className="font-mono text-cyan-400/80">Gemini Pro Grounded • Deterministic Safety</span>
        </div>
      </div>
    </div>
  );
};
