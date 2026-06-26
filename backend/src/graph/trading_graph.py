"""LangGraph multi-agent trading graph.

Architecture:
  entry → chat_node ⇄ tool_node → (loop until done) → END

The chat_node is a ReAct-style LLM node that has access to all trading tools
plus any tools injected by the AG-UI frontend (render_a2ui, state snapshot).
After tool execution the tool_node parses structured results and updates
the relevant state fields (technical_signals, fundamental_data, etc.).
Whenever state is updated it dispatches a manually_emit_intermediate_state
event so the AG-UI frontend receives a live state delta.
"""
import json
import logging
import os
from typing import Any, Literal

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_litellm import ChatLiteLLM
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.graph.state import TradingState
from src.settings import settings
from src.tools.fundamental_tools import analyze_fundamentals, get_analyst_recommendations
from src.tools.market_tools import (
    get_current_quote,
    get_historical_ohlcv,
    get_market_overview,
    get_sector_performance,
    search_ticker,
)
from src.tools.news_tools import (
    get_insider_activity,
    get_news_sentiment,
    get_options_sentiment,
)
from src.tools.portfolio_tools import (
    add_to_watchlist,
    get_watchlist,
    get_zerodha_holdings,
    get_zerodha_margins,
    get_zerodha_positions,
    remove_from_watchlist,
    summarize_portfolio,
    update_activity_log,
)
from src.tools.risk_tools import (
    compute_portfolio_correlation,
    compute_risk_metrics,
    suggest_position_size,
)
from src.tools.ta_tools import (
    compute_support_resistance,
    compute_technical_analysis,
    compute_vwap_and_volume,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────────────

TRADING_TOOLS = [
    # Market data
    get_current_quote,
    get_historical_ohlcv,
    search_ticker,
    get_market_overview,
    get_sector_performance,
    # Technical analysis
    compute_technical_analysis,
    compute_support_resistance,
    compute_vwap_and_volume,
    # Fundamental analysis
    analyze_fundamentals,
    get_analyst_recommendations,
    # News & sentiment
    get_news_sentiment,
    get_insider_activity,
    get_options_sentiment,
    # Risk
    compute_risk_metrics,
    suggest_position_size,
    compute_portfolio_correlation,
    # Portfolio / watchlist
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    update_activity_log,
    get_zerodha_holdings,
    get_zerodha_positions,
    get_zerodha_margins,
    summarize_portfolio,
]

TOOL_NAMES = {t.name for t in TRADING_TOOLS}

# ─────────────────────────────────────────────────────────────────────────────
# LLM factory
# ─────────────────────────────────────────────────────────────────────────────

def _make_llm() -> ChatLiteLLM:
    """Build the LiteLLM-backed ChatLangChain model.

    Injects API keys from settings into the environment so LiteLLM picks them up.
    """
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    return ChatLiteLLM(model=settings.trading_model, temperature=0.1)


_llm: ChatLiteLLM | None = None


def get_llm() -> ChatLiteLLM:
    global _llm
    if _llm is None:
        _llm = _make_llm()
    return _llm


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert AI trading analyst and portfolio advisor.

You have access to a comprehensive suite of financial tools covering:
- **Market Data**: Real-time quotes, historical OHLCV, sector performance, indices
- **Technical Analysis**: Multi-strategy ensemble (trend, momentum, mean-reversion, volatility, statistical), support/resistance, volume analysis
- **Fundamental Analysis**: Profitability, growth, financial health, valuation ratios, analyst recommendations
- **Sentiment & News**: News sentiment scoring, insider trading activity, options put/call ratio
- **Risk Management**: VaR (historical + parametric), CVaR, Sharpe/Sortino/Calmar ratios, beta, max drawdown, position sizing
- **Portfolio**: Watchlist management, Zerodha holdings/positions, P&L summary

## Analysis Guidelines

When the user asks to analyse a stock, ALWAYS run in this sequence unless they specify otherwise:
1. get_current_quote → establish current price context
2. compute_technical_analysis → generate TA signals
3. analyze_fundamentals → generate fundamental signals
4. get_news_sentiment → sentiment context
5. compute_risk_metrics → risk profile
6. Synthesize → produce a clear BUY / HOLD / SELL recommendation with reasoning

For each analysis step, summarise findings concisely in your response.

## Rendering Rich UI (A2UI)

After completing any substantive analysis, call render_a2ui EXACTLY ONCE with the complete structured surface.
Use trading-specific components:
- **SignalCard**: For trade recommendations (signal, confidence, key reasons)
- **TechnicalPanel**: For TA indicator values (RSI, MACD, BB position, ADX)
- **PortfolioTable**: For holdings with P&L columns
- **RiskPanel**: For risk metrics (VaR, Sharpe, drawdown)
- **PriceCard**: For quick price + change display
- **WatchlistGrid**: For displaying multiple symbols at once
- **NewsItem**: For individual news articles with sentiment
- **Table/InfoTable/StatRow/BarChart/LineChart**: For other structured data

CRITICAL A2UI FORMAT:
- `components` is a FLAT array; every component has an `id` and `component` field
- Exactly ONE component must have `id: "root"` and it MUST be a layout type (Column, Card)
- Children are referenced by id, never nested

## State Updates

After completing significant analysis (TA, fundamentals, risk), call update_activity_log
with a brief summary of what was analysed and the key finding.
This updates the live sidebar the user sees.

## Watchlist

When the user asks to track/watch a symbol, call add_to_watchlist.
Always confirm what's currently in the watchlist when relevant.

## Indian Market Context

- Most queries will be about NSE/BSE listed stocks. Append '.NS' for NSE, '.BO' for BSE.
- Amounts are in Indian Rupees (INR / ₹). Market cap / crore conversions: 1 cr = 10 million.
- Risk-free rate benchmark: India 10-year G-Sec (~6.5% annualised).
- Zerodha is the broker. If the user wants live portfolio data, guide them through Kite OAuth.

## Communication Style

- Be direct and specific. Give concrete numbers, not vague generalities.
- Lead with the conclusion, support with evidence.
- Flag risks prominently — don't bury warnings in footnotes.
- This is for personal use (not a licensed advisory). Always include the disclaimer:
  "This analysis is for informational purposes only and is not financial advice."
"""


# ─────────────────────────────────────────────────────────────────────────────
# State update helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tool_result(tool_name: str, content: str, state: TradingState) -> dict[str, Any]:
    """Extract structured state updates from a tool result message."""
    updates: dict[str, Any] = {}
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return updates

    if not data.get("success", False):
        return updates

    analysis = data.get("analysis", {})

    if tool_name == "compute_technical_analysis" and analysis:
        updates["technical_signals"] = analysis
        sym = analysis.get("ticker", "")
        if sym:
            updates["ticker"] = sym.replace(".NS", "").replace(".BO", "")

    elif tool_name == "analyze_fundamentals" and analysis:
        updates["fundamental_data"] = analysis
        sym = analysis.get("ticker", "")
        if sym:
            updates["ticker"] = sym.replace(".NS", "").replace(".BO", "")

    elif tool_name == "get_news_sentiment":
        updates["news_sentiment"] = {k: v for k, v in data.items() if k != "success"}

    elif tool_name in ("compute_risk_metrics",):
        rm = data.get("risk_metrics", {})
        if rm:
            updates["risk_metrics"] = rm

    elif tool_name == "add_to_watchlist":
        new_wl = data.get("watchlist", [])
        if new_wl:
            updates["watchlist"] = new_wl

    elif tool_name == "remove_from_watchlist":
        new_wl = data.get("watchlist", [])
        updates["watchlist"] = new_wl

    return updates


async def _emit_state(state: TradingState, updates: dict[str, Any], config: RunnableConfig):
    """Push the merged state to the AG-UI frontend as an intermediate snapshot."""
    merged = {**state, **updates}
    try:
        await adispatch_custom_event("manually_emit_intermediate_state", merged, config=config)
    except Exception as e:
        logger.warning("State emit failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Graph nodes
# ─────────────────────────────────────────────────────────────────────────────

async def chat_node(state: TradingState, config: RunnableConfig):
    """Main LLM reasoning node.

    Builds the system prompt with current state context, binds all tools
    (trading tools + AG-UI injected tools), and runs one LLM turn.
    """
    injected_tools = state.get("tools", [])
    all_tools = [*TRADING_TOOLS, *injected_tools]

    # Thread-specific context injected into the system prompt
    context_lines = []
    if state.get("ticker"):
        context_lines.append(f"Current analysis subject: {state['ticker']}")
    if state.get("watchlist"):
        context_lines.append(f"User's watchlist: {', '.join(state['watchlist'])}")
    if state.get("technical_signals") and state["technical_signals"].get("overall_signal"):
        sig = state["technical_signals"]
        context_lines.append(
            f"Latest TA on {sig.get('ticker','')}: {sig['overall_signal']} "
            f"({sig.get('confidence_pct', '?')}% confidence)"
        )

    system_content = SYSTEM_PROMPT
    if context_lines:
        system_content += "\n\n## Current Session Context\n" + "\n".join(f"- {l}" for l in context_lines)

    llm_with_tools = get_llm().bind_tools(all_tools, parallel_tool_calls=False)

    response = await llm_with_tools.ainvoke(
        [SystemMessage(content=system_content), *state["messages"]],
        config,
    )

    return {"messages": [response]}


async def state_update_tool_node(state: TradingState, config: RunnableConfig):
    """Executes tool calls and updates the TradingState fields accordingly.

    Wraps LangGraph's prebuilt ToolNode but adds post-processing to keep
    structured state (technical_signals, fundamental_data, etc.) up to date
    and pushes live state events to the AG-UI frontend.
    """
    injected_tools = state.get("tools", [])
    all_tools = [*TRADING_TOOLS, *injected_tools]
    tool_node = ToolNode(all_tools)

    result = await tool_node.ainvoke(state, config)

    # Parse tool messages for state updates
    state_updates: dict[str, Any] = {}
    new_messages = result.get("messages", [])

    last_ai_msg = next(
        (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    tool_calls = getattr(last_ai_msg, "tool_calls", []) if last_ai_msg else []
    tc_map = {tc["id"]: tc["name"] for tc in tool_calls} if tool_calls else {}

    # Update activity log
    activity = list(state.get("activity", []))
    for msg in new_messages:
        if isinstance(msg, ToolMessage):
            tool_name = tc_map.get(msg.tool_call_id, "")
            partial = _parse_tool_result(tool_name, msg.content, state)
            state_updates.update(partial)

            # Append explicit entries from update_activity_log tool
            if tool_name == "update_activity_log":
                try:
                    data = json.loads(msg.content)
                    if data.get("success") and data.get("entry"):
                        activity.append(data["entry"])
                except Exception:
                    pass
            else:
                # Auto-summarise from structured tool results
                try:
                    data = json.loads(msg.content)
                    if data.get("success"):
                        analysis = data.get("analysis", data.get("risk_metrics", {}))
                        sig = analysis.get("overall_signal", "")
                        tkr = analysis.get("ticker", state.get("ticker", ""))
                        if sig and tkr:
                            entry = f"✓ {tool_name.replace('_', ' ').title()}: {tkr} → {sig}"
                            activity.append(entry)
                except Exception:
                    pass

    if activity != state.get("activity", []):
        state_updates["activity"] = activity[-10:]  # keep last 10

    all_updates = {**result, **state_updates}
    await _emit_state(state, state_updates, config)

    return all_updates


def should_continue(state: TradingState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", []):
        return "tools"
    return "__end__"


# ─────────────────────────────────────────────────────────────────────────────
# Graph construction
# ─────────────────────────────────────────────────────────────────────────────

def build_trading_graph() -> Any:
    workflow = StateGraph(TradingState)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tools", state_update_tool_node)

    workflow.set_entry_point("chat_node")
    workflow.add_conditional_edges("chat_node", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "chat_node")

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Module-level compiled graph
trading_graph = build_trading_graph()
