"use client";

import { createCatalog } from "@copilotkit/a2ui-renderer";
import ReactMarkdown from "react-markdown";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

// ─────────────────────────────────────────────────────────────────────────────
// Shared styles
// ─────────────────────────────────────────────────────────────────────────────

const card = "rounded-xl border border-slate-700/60 bg-slate-800/60 p-4 shadow-lg";
const labelMuted = "text-xs font-medium uppercase tracking-wider text-slate-400";
const green = "text-emerald-400";
const red = "text-red-400";
const yellow = "text-amber-400";
const blue = "text-blue-400";

function signalColor(s: string) {
  const l = s.toLowerCase();
  if (l === "bullish" || l === "buy" || l === "positive") return green;
  if (l === "bearish" || l === "sell" || l === "negative") return red;
  return yellow;
}

function signalBg(s: string) {
  const l = s.toLowerCase();
  if (l === "bullish" || l === "buy" || l === "positive") return "bg-emerald-500/15 border-emerald-500/40";
  if (l === "bearish" || l === "sell" || l === "negative") return "bg-red-500/15 border-red-500/40";
  return "bg-amber-500/15 border-amber-500/40";
}

function changePct(v: number) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Component definitions (schema + renderer)
// ─────────────────────────────────────────────────────────────────────────────

const definitions = {
  // ── Existing base components (kept for compatibility) ────────────────────

  Markdown: {
    description: "Render Markdown-formatted prose with code blocks, lists, etc.",
    props: z.object({ content: z.string() }),
  },
  Callout: {
    description: "Highlighted note box — info / warning / success tones.",
    props: z.object({
      tone: z.enum(["info", "warning", "success"]),
      title: z.string().optional(),
      text: z.string(),
    }),
  },
  Table: {
    description: "Multi-column data table with header row.",
    props: z.object({
      title: z.string().optional(),
      columns: z.array(z.string()),
      rows: z.array(z.array(z.string())),
    }),
  },
  InfoTable: {
    description: "Two-column label/value table for key facts.",
    props: z.object({
      title: z.string().optional(),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    }),
  },
  StatRow: {
    description: "Row of KPI tiles — big value + label + optional caption.",
    props: z.object({
      stats: z.array(z.object({
        value: z.string(),
        label: z.string(),
        caption: z.string().optional(),
        trend: z.enum(["up", "down", "neutral"]).optional(),
      })),
    }),
  },
  LineChart: {
    description: "Line chart for price/metric trends over time (up to 4 series).",
    props: z.object({
      title: z.string().optional(),
      xAxis: z.array(z.string()),
      series: z.array(z.object({ name: z.string(), data: z.array(z.number()) })),
    }),
  },
  BarChart: {
    description: "Horizontal bar chart for comparing numeric values.",
    props: z.object({
      title: z.string().optional(),
      bars: z.array(z.object({
        label: z.string(),
        value: z.number(),
        display: z.string().optional(),
      })),
    }),
  },

  // ── Trading-specific components ──────────────────────────────────────────

  SignalCard: {
    description: `Trade signal card showing BUY / HOLD / SELL recommendation with confidence %,
      key supporting reasons (bullish), risk factors (bearish), and a disclaimer.
      Use this as the primary output after completing a full analysis.`,
    props: z.object({
      ticker: z.string().describe("Stock symbol e.g. RELIANCE.NS"),
      company_name: z.string().optional(),
      signal: z.enum(["BUY", "HOLD", "SELL"]),
      confidence_pct: z.number().describe("0-100"),
      current_price: z.number().optional(),
      target_price: z.number().optional().describe("12-month price target if available"),
      stop_loss: z.number().optional(),
      bullish_reasons: z.array(z.string()).describe("Up to 5 supporting points"),
      bearish_risks: z.array(z.string()).describe("Up to 3 risk factors"),
      time_horizon: z.enum(["short", "medium", "long"]).optional(),
    }),
  },

  TechnicalPanel: {
    description: `Technical indicator summary panel. Shows RSI gauge, MACD histogram,
      Bollinger Band position, EMA alignment, ADX trend strength, and Hurst regime.
      Use after compute_technical_analysis returns results.`,
    props: z.object({
      ticker: z.string(),
      overall_signal: z.enum(["bullish", "neutral", "bearish"]),
      confidence_pct: z.number(),
      indicators: z.object({
        rsi_14: z.number().optional(),
        macd_histogram: z.number().optional(),
        bollinger_pct: z.number().optional().describe("0=lower band, 1=upper band"),
        adx: z.number().optional(),
        adx_trend_strength: z.enum(["strong", "weak"]).optional(),
        hurst_exponent: z.number().optional(),
        hurst_regime: z.string().optional(),
        hist_vol_21d_annualized_pct: z.number().optional(),
        ema_8: z.number().optional(),
        ema_21: z.number().optional(),
        ema_55: z.number().optional(),
        ema_200: z.number().optional().nullable(),
        momentum_1m_pct: z.number().optional().nullable(),
        momentum_3m_pct: z.number().optional().nullable(),
      }),
      strategy_signals: z.object({
        trend: z.string().optional(),
        momentum: z.string().optional(),
        mean_reversion: z.string().optional(),
        volatility: z.string().optional(),
        statistical: z.string().optional(),
      }).optional(),
    }),
  },

  RiskPanel: {
    description: `Risk metrics dashboard showing VaR, Sharpe ratio, max drawdown, beta,
      and position sizing suggestion. Use after compute_risk_metrics returns results.`,
    props: z.object({
      ticker: z.string(),
      risk_level: z.enum(["low", "medium", "high"]),
      var_95_1d_pct: z.number(),
      var_99_1d_pct: z.number(),
      max_drawdown_pct: z.number(),
      sharpe_ratio: z.number(),
      sortino_ratio: z.number().optional(),
      calmar_ratio: z.number().optional(),
      annualised_vol_pct: z.number(),
      beta_vs_nifty50: z.number().optional().nullable(),
      recovery_days: z.number().optional().nullable(),
    }),
  },

  PriceCard: {
    description: "Compact price card for a single symbol with price, change, and key stats.",
    props: z.object({
      ticker: z.string(),
      company_name: z.string().optional(),
      price: z.number(),
      change: z.number(),
      change_pct: z.number(),
      week_52_high: z.number().optional().nullable(),
      week_52_low: z.number().optional().nullable(),
      market_cap_cr: z.number().optional().nullable(),
    }),
  },

  WatchlistGrid: {
    description: "Grid of price cards for multiple watchlist symbols.",
    props: z.object({
      items: z.array(z.object({
        ticker: z.string(),
        company_name: z.string().optional(),
        price: z.number(),
        change_pct: z.number(),
        signal: z.enum(["bullish", "neutral", "bearish"]).optional(),
      })),
    }),
  },

  NewsItem: {
    description: "Single news article card with sentiment badge. Use inside a Column.",
    props: z.object({
      title: z.string(),
      source: z.string().optional(),
      published: z.string().optional(),
      url: z.string().optional(),
      sentiment: z.enum(["positive", "negative", "neutral"]),
      confidence: z.number().optional(),
    }),
  },

  PortfolioTable: {
    description: `Holdings table showing position, quantity, avg cost, current price,
      current value, and P&L (coloured green/red). Add a summary StatRow above.`,
    props: z.object({
      title: z.string().optional(),
      positions: z.array(z.object({
        symbol: z.string(),
        qty: z.number(),
        avg_price: z.number(),
        current_price: z.number(),
        pnl_pct: z.number(),
        pnl_inr: z.number(),
        weight_pct: z.number().optional(),
      })),
      total_invested_inr: z.number().optional(),
      total_pnl_inr: z.number().optional(),
      total_pnl_pct: z.number().optional(),
    }),
  },

  FundamentalSummary: {
    description: `Compact fundamental analysis summary card showing dimension signals
      (profitability, growth, health, valuation) with colour-coded badges and key ratios.`,
    props: z.object({
      ticker: z.string(),
      company_name: z.string().optional(),
      sector: z.string().optional(),
      overall_signal: z.enum(["bullish", "neutral", "bearish"]),
      confidence_pct: z.number(),
      dimensions: z.object({
        profitability: z.string(),
        growth: z.string(),
        financial_health: z.string(),
        valuation: z.string(),
      }),
      key_ratios: z.object({
        trailing_pe: z.number().optional().nullable(),
        forward_pe: z.number().optional().nullable(),
        price_to_book: z.number().optional().nullable(),
        roe_pct: z.number().optional().nullable(),
        net_margin_pct: z.number().optional().nullable(),
        revenue_growth_pct: z.number().optional().nullable(),
        debt_to_equity: z.number().optional().nullable(),
      }),
    }),
  },

  CandlestickChart: {
    description: `Candlestick/OHLCV price chart with optional volume bars.
      Pass the most recent 60 daily bars (date, open, high, low, close).
      Each bar shows as a green (close>open) or red (close<open) candle.`,
    props: z.object({
      ticker: z.string(),
      title: z.string().optional(),
      bars: z.array(z.object({
        date: z.string(),
        open: z.number(),
        high: z.number(),
        low: z.number(),
        close: z.number(),
        volume: z.number().optional(),
      })).describe("Up to 60 OHLCV bars, chronological order"),
    }),
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Renderers
// ─────────────────────────────────────────────────────────────────────────────

const CHART_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"];

const markdownComponents = {
  h1: (p: React.ComponentProps<"h1">) => <h1 className="mb-2 mt-3 text-lg font-bold text-slate-100" {...p} />,
  h2: (p: React.ComponentProps<"h2">) => <h2 className="mb-2 mt-3 text-base font-bold text-slate-100" {...p} />,
  h3: (p: React.ComponentProps<"h3">) => <h3 className="mb-1 mt-2 text-sm font-bold text-slate-200" {...p} />,
  p: (p: React.ComponentProps<"p">) => <p className="mb-2 text-sm text-slate-300" {...p} />,
  ul: (p: React.ComponentProps<"ul">) => <ul className="mb-2 list-disc space-y-1 pl-5 text-sm text-slate-300" {...p} />,
  ol: (p: React.ComponentProps<"ol">) => <ol className="mb-2 list-decimal space-y-1 pl-5 text-sm text-slate-300" {...p} />,
  code: (p: React.ComponentProps<"code">) => <code className="rounded bg-slate-700 px-1 py-0.5 font-mono text-xs text-blue-300" {...p} />,
  pre: (p: React.ComponentProps<"pre">) => <pre className="mb-2 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-200" {...p} />,
};

export const tradingCatalog = createCatalog(
  definitions,
  {
    // ── Base components ─────────────────────────────────────────────────────

    Markdown: ({ props }) => (
      <div className={`${card} my-1`}>
        <ReactMarkdown components={markdownComponents}>{props.content}</ReactMarkdown>
      </div>
    ),

    Callout: ({ props }) => {
      const styles = {
        info: "border-blue-500/40 bg-blue-500/10 text-blue-200",
        warning: "border-amber-500/40 bg-amber-500/10 text-amber-200",
        success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
      };
      return (
        <div className={`my-1 rounded-xl border px-4 py-3 text-sm ${styles[props.tone]}`}>
          {props.title && <p className="mb-1 font-semibold">{props.title}</p>}
          <p>{props.text}</p>
        </div>
      );
    },

    Table: ({ props }) => (
      <div className={`${card} my-1 overflow-hidden p-0`}>
        {props.title && <p className="border-b border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200">{props.title}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                {props.columns.map((c, i) => <th key={i} className="px-4 py-2 text-left font-medium text-slate-400">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {props.rows.map((row, ri) => (
                <tr key={ri} className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/20">
                  {row.map((cell, ci) => <td key={ci} className="px-4 py-2 text-slate-300">{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),

    InfoTable: ({ props }) => (
      <div className={`${card} my-1 overflow-hidden p-0`}>
        {props.title && <p className="border-b border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200">{props.title}</p>}
        <table className="w-full text-sm">
          <tbody>
            {props.rows.map((row, i) => (
              <tr key={i} className={`border-b border-slate-700/40 last:border-0 ${i % 2 ? "bg-slate-900/30" : ""}`}>
                <td className="px-4 py-2 font-medium text-slate-400">{row.label}</td>
                <td className="px-4 py-2 text-slate-200">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ),

    StatRow: ({ props }) => (
      <div className="my-1 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {props.stats.map((s, i) => {
          const trendColor = s.trend === "up" ? green : s.trend === "down" ? red : "text-slate-300";
          return (
            <div key={i} className={`${card} text-center`}>
              <p className={`text-2xl font-bold ${trendColor}`}>{s.value}</p>
              <p className="mt-0.5 text-xs font-medium text-slate-400">{s.label}</p>
              {s.caption && <p className="mt-0.5 text-[10px] text-slate-500">{s.caption}</p>}
            </div>
          );
        })}
      </div>
    ),

    LineChart: ({ props }) => {
      const data = props.xAxis.map((label, i) => {
        const point: Record<string, string | number> = { name: label };
        props.series.slice(0, 4).forEach((s) => { point[s.name] = s.data[i] ?? 0; });
        return point;
      });
      return (
        <div className={`${card} my-1`}>
          {props.title && <p className="mb-3 text-sm font-semibold text-slate-200">{props.title}</p>}
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#64748b" }} />
              <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
              <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", color: "#e2e8f0" }} />
              {props.series.slice(0, 4).map((s, i) => (
                <Line key={i} type="monotone" dataKey={s.name} stroke={CHART_COLORS[i]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    },

    BarChart: ({ props }) => {
      const max = Math.max(...props.bars.map((b) => b.value), 1);
      return (
        <div className={`${card} my-1`}>
          {props.title && <p className="mb-3 text-sm font-semibold text-slate-200">{props.title}</p>}
          <div className="space-y-2">
            {props.bars.map((b, i) => (
              <div key={i}>
                <div className="mb-0.5 flex justify-between text-sm">
                  <span className="text-slate-300">{b.label}</span>
                  <span className="text-slate-400">{b.display ?? b.value.toLocaleString()}</span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.max((b.value / max) * 100, 2)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    },

    // ── Trading-specific components ──────────────────────────────────────────

    SignalCard: ({ props }) => {
      const signalStyles = {
        BUY: "bg-emerald-500/15 border-emerald-500/50 text-emerald-400",
        HOLD: "bg-amber-500/15 border-amber-500/50 text-amber-400",
        SELL: "bg-red-500/15 border-red-500/50 text-red-400",
      };
      return (
        <div className={`${card} my-1`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-slate-100">{props.ticker}</span>
                {props.company_name && <span className="text-sm text-slate-400">{props.company_name}</span>}
              </div>
              {props.current_price && (
                <p className="mt-1 text-2xl font-bold text-slate-100">
                  ₹{props.current_price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                </p>
              )}
            </div>
            <div className={`rounded-xl border px-5 py-3 text-center ${signalStyles[props.signal]}`}>
              <p className="text-2xl font-black">{props.signal}</p>
              <p className="text-xs font-semibold">{props.confidence_pct.toFixed(0)}% confidence</p>
            </div>
          </div>

          {(props.target_price || props.stop_loss) && (
            <div className="mt-3 flex gap-4 text-sm">
              {props.target_price && (
                <span className="rounded-lg bg-emerald-500/10 px-3 py-1 text-emerald-400">
                  Target: ₹{props.target_price.toLocaleString("en-IN")}
                </span>
              )}
              {props.stop_loss && (
                <span className="rounded-lg bg-red-500/10 px-3 py-1 text-red-400">
                  Stop: ₹{props.stop_loss.toLocaleString("en-IN")}
                </span>
              )}
              {props.time_horizon && (
                <span className="rounded-lg bg-slate-700 px-3 py-1 text-slate-300 capitalize">
                  {props.time_horizon}-term
                </span>
              )}
            </div>
          )}

          {props.bullish_reasons.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-500">Supporting Factors</p>
              <ul className="space-y-1">
                {props.bullish_reasons.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="mt-0.5 text-emerald-500">+</span>{r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {props.bearish_risks.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-red-500">Key Risks</p>
              <ul className="space-y-1">
                {props.bearish_risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="mt-0.5 text-red-500">−</span>{r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-3 text-[10px] text-slate-500">
            ⚠ For informational purposes only. Not financial advice. Do your own research.
          </p>
        </div>
      );
    },

    TechnicalPanel: ({ props }) => {
      const { indicators: ind, strategy_signals: strategies } = props;
      const rsi = ind?.rsi_14;
      const rsiColor = rsi ? (rsi > 70 ? red : rsi < 30 ? green : "text-slate-300") : "text-slate-300";
      const rsiLabel = rsi ? (rsi > 70 ? "Overbought" : rsi < 30 ? "Oversold" : "Neutral") : "—";

      return (
        <div className={`${card} my-1`}>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-200">Technical Analysis · {props.ticker}</p>
            <div className={`rounded-lg border px-3 py-1 text-xs font-bold capitalize ${signalBg(props.overall_signal)} ${signalColor(props.overall_signal)}`}>
              {props.overall_signal} · {props.confidence_pct.toFixed(0)}%
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {rsi != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>RSI 14</p>
                <p className={`text-xl font-bold ${rsiColor}`}>{rsi.toFixed(1)}</p>
                <p className="text-xs text-slate-400">{rsiLabel}</p>
              </div>
            )}
            {ind?.adx != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>ADX</p>
                <p className="text-xl font-bold text-slate-100">{ind.adx.toFixed(1)}</p>
                <p className="text-xs text-slate-400">{ind.adx_trend_strength === "strong" ? "Strong trend" : "Weak trend"}</p>
              </div>
            )}
            {ind?.macd_histogram != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>MACD Hist</p>
                <p className={`text-xl font-bold ${ind.macd_histogram >= 0 ? green : red}`}>
                  {ind.macd_histogram >= 0 ? "+" : ""}{ind.macd_histogram.toFixed(3)}
                </p>
                <p className="text-xs text-slate-400">{ind.macd_histogram >= 0 ? "Positive" : "Negative"}</p>
              </div>
            )}
            {ind?.bollinger_pct != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>BB Position</p>
                <div className="mt-1 h-2 w-full rounded-full bg-slate-600">
                  <div className="h-2 rounded-full bg-blue-400 transition-all" style={{ width: `${(ind.bollinger_pct * 100).toFixed(0)}%` }} />
                </div>
                <p className="mt-1 text-xs text-slate-400">{(ind.bollinger_pct * 100).toFixed(0)}% — {ind.bollinger_pct < 0.2 ? "Near lower" : ind.bollinger_pct > 0.8 ? "Near upper" : "Middle"}</p>
              </div>
            )}
            {ind?.hist_vol_21d_annualized_pct != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>Vol 21d Ann.</p>
                <p className="text-xl font-bold text-slate-100">{ind.hist_vol_21d_annualized_pct.toFixed(1)}%</p>
                <p className="text-xs text-slate-400">Annualised</p>
              </div>
            )}
            {ind?.hurst_exponent != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>Hurst</p>
                <p className="text-xl font-bold text-slate-100">{ind.hurst_exponent.toFixed(3)}</p>
                <p className="text-xs text-slate-400">{ind.hurst_regime ?? (ind.hurst_exponent > 0.55 ? "Trending" : ind.hurst_exponent < 0.45 ? "Mean-rev" : "Random")}</p>
              </div>
            )}
          </div>

          {strategies && (
            <div className="mt-3">
              <p className={`mb-2 ${labelMuted}`}>Strategy Signals</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(strategies).map(([name, sig]) => (
                  <span key={name} className={`rounded-full border px-3 py-0.5 text-xs font-medium capitalize ${signalBg(sig as string)} ${signalColor(sig as string)}`}>
                    {name.replace("_", " ")} · {String(sig)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    },

    RiskPanel: ({ props }) => {
      const levelColor = props.risk_level === "high" ? red : props.risk_level === "medium" ? yellow : green;
      return (
        <div className={`${card} my-1`}>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-200">Risk Profile · {props.ticker}</p>
            <span className={`rounded-full border px-3 py-0.5 text-xs font-bold uppercase ${signalBg(props.risk_level === "low" ? "bullish" : props.risk_level === "high" ? "bearish" : "neutral")} ${levelColor}`}>
              {props.risk_level} risk
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-slate-700/40 p-3">
              <p className={labelMuted}>VaR 95% 1D</p>
              <p className={`text-xl font-bold ${red}`}>{props.var_95_1d_pct.toFixed(2)}%</p>
              <p className="text-xs text-slate-400">Hist. 95%</p>
            </div>
            <div className="rounded-lg bg-slate-700/40 p-3">
              <p className={labelMuted}>Max Drawdown</p>
              <p className={`text-xl font-bold ${red}`}>{props.max_drawdown_pct.toFixed(1)}%</p>
              {props.recovery_days != null && <p className="text-xs text-slate-400">{props.recovery_days}d recovery</p>}
            </div>
            <div className="rounded-lg bg-slate-700/40 p-3">
              <p className={labelMuted}>Sharpe Ratio</p>
              <p className={`text-xl font-bold ${props.sharpe_ratio >= 1 ? green : props.sharpe_ratio >= 0.5 ? yellow : red}`}>
                {props.sharpe_ratio.toFixed(2)}
              </p>
              <p className="text-xs text-slate-400">{props.sharpe_ratio >= 1 ? "Good" : props.sharpe_ratio >= 0.5 ? "Moderate" : "Poor"}</p>
            </div>
            <div className="rounded-lg bg-slate-700/40 p-3">
              <p className={labelMuted}>Ann. Volatility</p>
              <p className="text-xl font-bold text-slate-100">{props.annualised_vol_pct.toFixed(1)}%</p>
            </div>
            {props.beta_vs_nifty50 != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>Beta vs Nifty</p>
                <p className="text-xl font-bold text-slate-100">{props.beta_vs_nifty50.toFixed(2)}</p>
                <p className="text-xs text-slate-400">{props.beta_vs_nifty50 > 1.2 ? "High-beta" : props.beta_vs_nifty50 < 0.8 ? "Defensive" : "Market"}</p>
              </div>
            )}
            {props.sortino_ratio != null && (
              <div className="rounded-lg bg-slate-700/40 p-3">
                <p className={labelMuted}>Sortino</p>
                <p className={`text-xl font-bold ${props.sortino_ratio >= 1 ? green : yellow}`}>{props.sortino_ratio.toFixed(2)}</p>
              </div>
            )}
          </div>
        </div>
      );
    },

    PriceCard: ({ props }) => {
      const isPos = props.change_pct >= 0;
      return (
        <div className={`${card} my-1`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="font-bold text-slate-100">{props.ticker.replace(".NS", "").replace(".BO", "")}</p>
              {props.company_name && <p className="text-xs text-slate-400">{props.company_name}</p>}
            </div>
            <span className={`rounded-lg px-2 py-0.5 text-xs font-semibold ${isPos ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"}`}>
              {changePct(props.change_pct)}
            </span>
          </div>
          <p className="mt-2 text-2xl font-black text-slate-100">
            ₹{props.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </p>
          {(props.week_52_high || props.week_52_low) && (
            <div className="mt-2 flex gap-3 text-xs text-slate-400">
              {props.week_52_low && <span>52W L: ₹{props.week_52_low.toLocaleString()}</span>}
              {props.week_52_high && <span>52W H: ₹{props.week_52_high.toLocaleString()}</span>}
            </div>
          )}
          {props.market_cap_cr && (
            <p className="mt-1 text-xs text-slate-500">Mkt Cap: ₹{props.market_cap_cr.toLocaleString("en-IN")} Cr</p>
          )}
        </div>
      );
    },

    WatchlistGrid: ({ props }) => (
      <div className="my-1 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {props.items.map((item, i) => {
          const isPos = item.change_pct >= 0;
          return (
            <div key={i} className={`${card}`}>
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-100">{item.ticker.replace(".NS", "").replace(".BO", "")}</span>
                {item.signal && (
                  <span className={`text-xs font-medium capitalize ${signalColor(item.signal)}`}>{item.signal}</span>
                )}
              </div>
              <p className="mt-1 text-xl font-bold text-slate-100">
                ₹{item.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </p>
              <span className={`text-sm font-medium ${isPos ? green : red}`}>{changePct(item.change_pct)}</span>
            </div>
          );
        })}
      </div>
    ),

    NewsItem: ({ props }) => {
      const sentColor = props.sentiment === "positive" ? green : props.sentiment === "negative" ? red : "text-slate-400";
      const sentBg = props.sentiment === "positive" ? "bg-emerald-500/10 text-emerald-400" : props.sentiment === "negative" ? "bg-red-500/10 text-red-400" : "bg-slate-600 text-slate-300";
      return (
        <div className={`${card} my-1`}>
          <div className="flex items-start gap-3">
            <div className="flex-1">
              {props.url ? (
                <a href={props.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-200 hover:text-blue-400">
                  {props.title}
                </a>
              ) : (
                <p className="text-sm font-medium text-slate-200">{props.title}</p>
              )}
              <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                {props.source && <span>{props.source}</span>}
                {props.published && <span>· {props.published}</span>}
              </div>
            </div>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${sentBg}`}>
              {props.sentiment}
            </span>
          </div>
        </div>
      );
    },

    PortfolioTable: ({ props }) => (
      <div className={`${card} my-1 overflow-hidden p-0`}>
        {props.title && <p className="border-b border-slate-700 px-4 py-2.5 text-sm font-semibold text-slate-200">{props.title}</p>}
        {(props.total_invested_inr || props.total_pnl_inr) && (
          <div className="flex gap-6 border-b border-slate-700 bg-slate-900/30 px-4 py-2 text-sm">
            {props.total_invested_inr && (
              <span className="text-slate-400">Invested: <span className="font-semibold text-slate-200">₹{props.total_invested_inr.toLocaleString("en-IN")}</span></span>
            )}
            {props.total_pnl_inr != null && (
              <span className="text-slate-400">P&L: <span className={`font-semibold ${props.total_pnl_inr >= 0 ? green : red}`}>
                ₹{props.total_pnl_inr.toLocaleString("en-IN")} ({props.total_pnl_pct?.toFixed(2)}%)
              </span></span>
            )}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                {["Symbol", "Qty", "Avg Price", "Current", "P&L %", "P&L ₹", "Weight"].map((h, i) => (
                  <th key={i} className="px-3 py-2 text-left text-xs font-medium text-slate-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {props.positions.map((p, i) => (
                <tr key={i} className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/20">
                  <td className="px-3 py-2 font-medium text-slate-200">{p.symbol.replace(".NS", "")}</td>
                  <td className="px-3 py-2 text-slate-300">{p.qty}</td>
                  <td className="px-3 py-2 text-slate-300">₹{p.avg_price.toLocaleString()}</td>
                  <td className="px-3 py-2 text-slate-300">₹{p.current_price.toLocaleString()}</td>
                  <td className={`px-3 py-2 font-semibold ${p.pnl_pct >= 0 ? green : red}`}>{changePct(p.pnl_pct)}</td>
                  <td className={`px-3 py-2 font-semibold ${p.pnl_inr >= 0 ? green : red}`}>₹{p.pnl_inr.toLocaleString("en-IN")}</td>
                  <td className="px-3 py-2 text-slate-400">{p.weight_pct?.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),

    FundamentalSummary: ({ props }) => (
      <div className={`${card} my-1`}>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="font-bold text-slate-100">{props.ticker.replace(".NS", "")}</p>
            {props.company_name && <p className="text-xs text-slate-400">{props.company_name} · {props.sector}</p>}
          </div>
          <div className={`rounded-lg border px-3 py-1.5 text-center ${signalBg(props.overall_signal)}`}>
            <p className={`text-sm font-bold capitalize ${signalColor(props.overall_signal)}`}>{props.overall_signal}</p>
            <p className="text-xs text-slate-400">{props.confidence_pct.toFixed(0)}%</p>
          </div>
        </div>
        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Object.entries(props.dimensions).map(([dim, sig]) => (
            <div key={dim} className={`rounded-lg border p-2 text-center ${signalBg(sig as string)}`}>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{dim.replace("_", " ")}</p>
              <p className={`text-xs font-bold capitalize ${signalColor(sig as string)}`}>{String(sig)}</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {[
            ["P/E", props.key_ratios.trailing_pe],
            ["Fwd P/E", props.key_ratios.forward_pe],
            ["P/B", props.key_ratios.price_to_book],
            ["ROE %", props.key_ratios.roe_pct],
            ["Net Margin %", props.key_ratios.net_margin_pct],
            ["Rev Growth %", props.key_ratios.revenue_growth_pct],
            ["D/E", props.key_ratios.debt_to_equity],
          ].filter(([, v]) => v != null).map(([label, val], i) => (
            <div key={i} className="rounded-lg bg-slate-700/30 px-2 py-1.5 text-center">
              <p className="text-[10px] text-slate-400">{label}</p>
              <p className="text-sm font-semibold text-slate-200">{Number(val).toFixed(2)}</p>
            </div>
          ))}
        </div>
      </div>
    ),

    CandlestickChart: ({ props }) => {
      const recent = props.bars.slice(-60);
      const chartData = recent.map((b) => ({
        date: b.date.slice(5),  // MM-DD
        open: b.open,
        close: b.close,
        high: b.high,
        low: b.low,
        volume: b.volume ?? 0,
        // For the bar: bottom of candle body, height of candle body
        bottom: Math.min(b.open, b.close),
        body: Math.abs(b.close - b.open),
        isGreen: b.close >= b.open,
        // Wick range
        wickTop: b.high,
        wickBottom: b.low,
        fill: b.close >= b.open ? "#22c55e" : "#ef4444",
      }));

      return (
        <div className={`${card} my-1`}>
          <p className="mb-2 text-sm font-semibold text-slate-200">
            {props.title || `${props.ticker.replace(".NS", "")} Price Chart`}
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData} margin={{ left: -10, right: 10 }}>
              <CartesianGrid strokeDasharray="2 2" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#64748b" }} interval={Math.floor(chartData.length / 8)} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 9, fill: "#64748b" }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", fontSize: 11 }}
                formatter={(val: number, name: string) => [val.toFixed(2), name]}
              />
              <Bar dataKey="body" stackId="candle" fill="transparent" radius={0}>
                {chartData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
          <p className="mt-1 text-xs text-slate-500">
            Last {recent.length} trading days · Green = bullish candle, Red = bearish candle
          </p>
        </div>
      );
    },
  },
  { includeBasicCatalog: true, catalogId: "default" }
);
