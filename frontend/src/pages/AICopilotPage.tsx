import React, { useState } from 'react';
import { MessageSquareCode, Send, Bot, User, Sparkles, ArrowRight, CornerDownLeft, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { CopilotResponse } from '../types';

export const AICopilotPage: React.FC = () => {
  const [messages, setMessages] = useState<Array<{ sender: 'user' | 'bot'; text: string; data?: CopilotResponse }>>([
    {
      sender: 'bot',
      text: 'Hello! I am your PayRecover AI Copilot. I analyze real-time Razorpay telemetry, failure patterns, and customer intent to optimize your revenue recovery. Ask me anything about your payments or strategy.',
      data: {
        reply: '',
        insights: [
          '84.6% of card failures can be autonomously recovered via WhatsApp UPI deep-links',
          'Current recoverable revenue pipeline stands at ₹1,48,500'
        ],
        recommended_actions: [
          { label: 'Why did recovery fall yesterday?', action: 'ASK_YESTERDAY' },
          { label: 'How much revenue is currently at risk?', action: 'ASK_RISK' },
          { label: 'Which payment method is causing the most failures?', action: 'ASK_METHOD' },
          { label: 'Show high-value payments requiring approval', action: 'ASK_HIGH_VAL' }
        ]
      }
    }
  ]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const samplePrompts = [
    "How much revenue is currently at risk?",
    "Why did recovery fall yesterday?",
    "Which payment method is causing the most failures?",
    "Recommend a recovery strategy for Card 3DS drop-offs"
  ];

  const handleSend = async (textToSend?: string) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { sender: 'user', text: query }]);
    setLoading(true);

    try {
      const res = await api.askCopilot(query);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: res.reply,
          data: res
        }
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: `Could not retrieve response from AI engine: ${err.message || err}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-[calc(100vh-8.5rem)] flex flex-col rounded-2xl bg-dark-850 border border-dark-700 overflow-hidden animate-fadeIn">
      {/* Copilot Header */}
      <div className="p-4 bg-dark-800 border-b border-dark-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-indigo to-brand-cyan flex items-center justify-center text-white">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Merchant AI Recovery Copilot
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
                Gemini Model Active
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Context grounded on live merchant database and telemetry</p>
          </div>
        </div>
      </div>

      {/* Messages Thread */}
      <div className="flex-1 p-6 overflow-y-auto space-y-5">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex gap-3 max-w-2xl ${m.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
          >
            <div
              className={`w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-xs font-bold ${
                m.sender === 'user'
                  ? 'bg-brand-cyan text-dark-900'
                  : 'bg-dark-800 border border-dark-700 text-brand-cyan'
              }`}
            >
              {m.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            <div className="space-y-3">
              <div
                className={`p-4 rounded-2xl text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-gradient-to-r from-brand-cyan to-brand-blue text-dark-900 font-semibold'
                    : 'bg-dark-800 border border-dark-700 text-slate-200'
                }`}
              >
                {m.text}
              </div>

              {/* Insights and Action Recommendations */}
              {m.data?.insights && m.data.insights.length > 0 && (
                <div className="p-3.5 rounded-xl bg-dark-900/90 border border-brand-cyan/20 space-y-2">
                  <div className="text-[11px] font-bold text-brand-cyan flex items-center gap-1.5 uppercase tracking-wide">
                    <Sparkles className="w-3.5 h-3.5" /> Key Telemetry Insights
                  </div>
                  <ul className="text-xs space-y-1.5 text-slate-300">
                    {m.data.insights.map((ins, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-brand-cyan font-bold">•</span>
                        <span>{ins}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Quick Prompt Suggestions */}
              {m.data?.recommended_actions && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {m.data.recommended_actions.map((act, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(act.label)}
                      className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-[11px] text-brand-cyan hover:border-brand-cyan/40 transition flex items-center gap-1.5"
                    >
                      <span>{act.label}</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-brand-cyan font-mono p-3 bg-dark-800 rounded-xl w-fit">
            <Loader2 className="w-4 h-4 animate-spin" />
            Analyzing payment telemetry & executing inference...
          </div>
        )}
      </div>

      {/* Suggested Quick Prompts */}
      <div className="px-6 py-2 bg-dark-900/50 border-t border-dark-750 flex items-center gap-2 overflow-x-auto">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider shrink-0">Prompts:</span>
        {samplePrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p)}
            className="text-[11px] px-2.5 py-1 rounded-full bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-400 hover:text-slate-200 transition shrink-0"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input box */}
      <div className="p-4 bg-dark-800 border-t border-dark-700 flex items-center gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask AI Copilot about payment failures, recovery strategies, or customer intent..."
          className="flex-1 px-4 py-2.5 bg-dark-900 border border-dark-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className="px-4 py-2.5 bg-gradient-to-r from-brand-cyan to-brand-blue text-dark-900 font-bold text-xs rounded-xl shadow-glow-cyan hover:opacity-90 transition disabled:opacity-50 flex items-center gap-1.5"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Send</span>
        </button>
      </div>
    </div>
  );
};
