"""LangGraph state for the trading agent."""
from typing import Any, Annotated
from langgraph.graph import MessagesState


class TradingState(MessagesState):
    """Full agent state persisted across turns within a thread."""

    # Symbol currently under analysis (user can change it mid-conversation)
    ticker: str = ""

    # Symbols the user wants to track
    watchlist: list[str] = []

    # Last portfolio snapshot from Zerodha (holdings + positions)
    portfolio: dict[str, Any] = {}

    # Technical analysis results for the active ticker
    technical_signals: dict[str, Any] = {}

    # Fundamental metrics for the active ticker
    fundamental_data: dict[str, Any] = {}

    # News + sentiment for the active ticker
    news_sentiment: dict[str, Any] = {}

    # Risk metrics for the active ticker
    risk_metrics: dict[str, Any] = {}

    # Final trade signal aggregation
    trade_signal: dict[str, Any] = {}

    # Activity log — shown in the frontend sidebar (last 10 entries)
    activity: list[str] = []

    # A2UI/CopilotKit injected tools forwarded from the frontend
    # (render_a2ui, AGUISendStateSnapshot, etc.)
    tools: list[Any] = []
