"use client";

import {
  CopilotSidebar,
  UseAgentUpdate,
  useAgent,
  useConfigureSuggestions,
  useDefaultRenderTool,
} from "@copilotkit/react-core/v2";
import { useEffect, useState } from "react";

import { BackendSettings } from "@/components/BackendSettings";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type AgentState = {
  ticker?: string;
  watchlist?: string[];
  technical_signals?: { overall_signal?: string; confidence_pct?: number; indicators?: Record<string, unknown> };
  fundamental_data?: { overall_signal?: string; company_name?: string };
  risk_metrics?: { risk_level?: string; return_metrics?: { sharpe_ratio?: number } };
  trade_signal?: { signal?: string; confidence?: number };
  activity?: string[];
};

type ChatThread = { id: string; title: string };

function loadThreads(): ChatThread[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem("trading.threads");
    const parsed = raw ? (JSON.parse(raw) as ChatThread[]) : [];
    return Array.isArray(parsed) ? parsed.filter((t) => typeof t.id === "string") : [];
  } catch { return []; }
}

function saveThreads(threads: ChatThread[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem("trading.threads", JSON.stringify(threads));
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function SignalBadge({ signal }: { signal?: string }) {
  if (!signal) return null;
  const s = signal.toLowerCase();
  const cls =
    s === "bullish" || s === "buy" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40" :
    s === "bearish" || s === "sell" ? "bg-red-500/20 text-red-400 border-red-500/40" :
    "bg-amber-500/20 text-amber-400 border-amber-500/40";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${cls}`}>
      {signal}
    </span>
  );
}

function WatchlistItem({ ticker }: { ticker: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-700/30 px-3 py-2 text-sm">
      <span className="font-medium text-slate-200">{ticker.replace(".NS", "").replace(".BO", "")}</span>
      <span className="text-xs text-slate-500">.NS</span>
    </div>
  );
}

function ActivityLog({ entries }: { entries: string[] }) {
  if (entries.length === 0) {
    return <p className="italic text-slate-500">No activity yet. Start chatting to analyse stocks.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {entries.map((e, i) => (
        <li key={i} className="rounded-lg bg-slate-700/30 px-3 py-2 text-sm text-slate-300">
          {e}
        </li>
      ))}
    </ul>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-3 text-center">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-slate-100">{value}</p>
      {sub && <p className="text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function Home() {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const stored = loadThreads();
    if (stored.length > 0) {
      setThreads(stored);
      setActiveId(stored[0].id);
    } else {
      const first = { id: crypto.randomUUID(), title: "Analysis 1" };
      setThreads([first]);
      setActiveId(first.id);
    }
  }, []);

  useEffect(() => {
    if (threads.length > 0) saveThreads(threads);
  }, [threads]);

  const handleNewChat = () => {
    const t = { id: crypto.randomUUID(), title: `Analysis ${threads.length + 1}` };
    setThreads((p) => [t, ...p]);
    setActiveId(t.id);
  };

  const handleDelete = (id: string) => {
    const remaining = threads.filter((t) => t.id !== id);
    if (remaining.length === 0) {
      const fresh = { id: crypto.randomUUID(), title: "Analysis 1" };
      setThreads([fresh]);
      setActiveId(fresh.id);
      return;
    }
    setThreads(remaining);
    if (activeId === id) setActiveId(remaining[0].id);
  };

  const { agent } = useAgent({
    agentId: "trading_agent",
    updates: [UseAgentUpdate.OnStateChanged, UseAgentUpdate.OnRunStatusChanged],
  });

  useEffect(() => {
    if (!agent) return;
    const s = agent.state as AgentState | undefined;
    if (!s || Object.keys(s).length === 0) {
      agent.setState({ activity: [], watchlist: [] });
    }
  }, [agent, activeId]);

  useConfigureSuggestions({
    instructions:
      "Suggest short, relevant follow-up questions for a stock trader. Examples: 'Analyse RELIANCE technicals', 'What's my Nifty 50 exposure?', 'Show market overview', 'Add TCS to watchlist', 'Compute VaR for HDFC Bank'. Keep each under 8 words.",
    minSuggestions: 2,
    maxSuggestions: 4,
    available: "always",
    providerAgentId: "trading_agent",
  });

  useDefaultRenderTool();

  const state = (agent?.state ?? {}) as AgentState;
  const activity = Array.isArray(state.activity) ? state.activity : [];
  const watchlist = Array.isArray(state.watchlist) ? state.watchlist : [];
  const ticker = state.ticker || "";
  const ta = state.technical_signals;
  const fund = state.fundamental_data;
  const risk = state.risk_metrics;

  return (
    <main className="flex min-h-screen bg-slate-900 text-slate-200">
      {/* ── Left panel: threads + watchlist ──────────────────────────────────── */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-700/60 bg-slate-800/40 p-4 lg:flex">
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Sessions</p>
            <button
              onClick={handleNewChat}
              className="rounded-lg bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-500"
            >
              + New
            </button>
          </div>
          <ul className="space-y-1">
            {threads.map((t) => (
              <li key={t.id} className="flex items-center gap-1">
                <button
                  onClick={() => setActiveId(t.id)}
                  className={`flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm transition ${
                    t.id === activeId ? "bg-blue-600/20 font-semibold text-blue-300" : "text-slate-300 hover:bg-slate-700/40"
                  }`}
                >
                  {t.title}
                </button>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="rounded px-1 py-0.5 text-slate-500 hover:text-red-400"
                  title="Delete"
                >×</button>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Watchlist</p>
          {watchlist.length === 0 ? (
            <p className="text-xs italic text-slate-500">Empty — ask the agent to add symbols</p>
          ) : (
            <div className="space-y-1">
              {watchlist.map((sym) => <WatchlistItem key={sym} ticker={sym} />)}
            </div>
          )}
        </div>

        <BackendSettings />
      </aside>

      {/* ── Main content area ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-auto">
        {/* Header */}
        <header className="border-b border-slate-700/60 bg-slate-800/60 px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-black text-white">T</div>
              <div>
                <h1 className="text-sm font-bold text-slate-100">Agentic Trading Bot</h1>
                <p className="text-xs text-slate-400">LangGraph · LangChain · AG-UI</p>
              </div>
            </div>
            {ticker && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-300">Analysing:</span>
                <span className="rounded-lg bg-blue-600/20 px-3 py-1 text-sm font-bold text-blue-300">{ticker}</span>
                {ta?.overall_signal && <SignalBadge signal={ta.overall_signal} />}
              </div>
            )}
          </div>
        </header>

        {/* Dashboard body */}
        <div className="flex-1 overflow-auto p-6">
          {/* Live metrics row (shown when analysis is in state) */}
          {(ta || fund || risk) && (
            <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {ta?.overall_signal && (
                <MetricCard label="TA Signal" value={ta.overall_signal} sub={`${ta.confidence_pct?.toFixed(0) ?? "?"}% confidence`} />
              )}
              {(ta?.indicators as { rsi_14?: number } | undefined)?.rsi_14 != null && (
                <MetricCard label="RSI 14" value={((ta?.indicators as { rsi_14?: number })?.rsi_14 ?? 0).toFixed(1)} sub="14-period" />
              )}
              {fund?.overall_signal && (
                <MetricCard label="Fundamentals" value={fund.overall_signal} sub={fund.company_name} />
              )}
              {risk?.return_metrics?.sharpe_ratio != null && (
                <MetricCard label="Sharpe" value={risk.return_metrics.sharpe_ratio.toFixed(2)} sub="annualised" />
              )}
              {risk?.risk_level && (
                <MetricCard label="Risk Level" value={risk.risk_level.toUpperCase()} />
              )}
            </div>
          )}

          {/* Activity log + watchlist (mobile) */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Agent Activity</p>
                <ActivityLog entries={activity} />
              </div>
            </div>

            <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Quick Start</p>
              <div className="space-y-2 text-xs text-slate-400">
                {[
                  "Analyse RELIANCE technically and fundamentally",
                  "Show me today's market overview",
                  "Compute risk metrics for TCS",
                  "Add HDFCBANK to my watchlist",
                  "What is the sector performance today?",
                  "Suggest position size for INFY with ₹10L portfolio",
                ].map((q, i) => (
                  <div key={i} className="rounded-lg bg-slate-700/30 px-3 py-2 text-slate-300">{q}</div>
                ))}
                <p className="pt-1 text-slate-500">→ Type these (or anything) in the chat →</p>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <p className="mt-6 text-center text-xs text-slate-600">
            ⚠ All analysis is for informational purposes only and does not constitute financial advice.
            Past performance is not indicative of future results.
          </p>
        </div>
      </div>

      {/* ── CopilotKit chat sidebar ───────────────────────────────────────────── */}
      {activeId && (
        <CopilotSidebar
          agentId="trading_agent"
          defaultOpen={true}
          key={activeId}
          threadId={activeId}
          labels={{
            modalHeaderTitle: "Trading Agent",
            welcomeMessageText:
              "Hello! I can analyse stocks with technical & fundamental analysis, compute risk metrics, manage your watchlist, and stream real-time data. What would you like to analyse?",
          }}
          width="min(55vw, 780px)"
        />
      )}
    </main>
  );
}
