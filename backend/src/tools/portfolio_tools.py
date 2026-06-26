"""Portfolio management tools — watchlist management and P&L from Zerodha MCP."""
import json
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Watchlist management (in-memory; persisted via LangGraph state)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_watchlist(current_watchlist: list[str]) -> str:
    """Return the user's current watchlist.

    The watchlist is stored in agent state and persisted across conversation turns.

    Args:
        current_watchlist: Pass the current 'watchlist' field from state.
    """
    return json.dumps({
        "success": True,
        "watchlist": current_watchlist,
        "count": len(current_watchlist),
    })


@tool
def add_to_watchlist(ticker: str, current_watchlist: list[str]) -> str:
    """Add a stock symbol to the user's watchlist.

    Returns the updated watchlist that should be written back to agent state.

    Args:
        ticker: Symbol to add (e.g. 'RELIANCE', 'AAPL')
        current_watchlist: Current watchlist from state
    """
    sym = ticker.upper().strip()
    if "." not in sym:
        sym += ".NS"
    if sym in current_watchlist:
        return json.dumps({"success": True, "watchlist": current_watchlist, "note": f"{sym} already in watchlist"})
    updated = current_watchlist + [sym]
    return json.dumps({"success": True, "watchlist": updated, "added": sym})


@tool
def remove_from_watchlist(ticker: str, current_watchlist: list[str]) -> str:
    """Remove a stock symbol from the user's watchlist.

    Args:
        ticker: Symbol to remove
        current_watchlist: Current watchlist from state
    """
    sym = ticker.upper().strip()
    if "." not in sym:
        sym += ".NS"
    updated = [t for t in current_watchlist if t != sym]
    return json.dumps({"success": True, "watchlist": updated, "removed": sym})


# ─────────────────────────────────────────────────────────────────────────────
# Zerodha portfolio (requires active MCP session)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_zerodha_holdings() -> str:
    """Fetch current equity holdings from your Zerodha account via the Kite MCP.

    Requires authentication. If not authenticated, returns instructions to log in first.
    Shows each holding with quantity, average price, current value, and P&L.
    """
    # The actual call is routed through the Zerodha MCP session in the graph.
    # This stub is replaced by the MCP-backed version when the session is active.
    return json.dumps({
        "success": False,
        "error": "Zerodha MCP session not active. Ask the user to authenticate via the login tool first.",
        "action_required": "Call zerodha_login to start the Zerodha OAuth flow.",
    })


@tool
def get_zerodha_positions() -> str:
    """Fetch current intraday and overnight positions from Zerodha.

    Requires active Zerodha session. Returns net, day, and overnight positions.
    """
    return json.dumps({
        "success": False,
        "error": "Zerodha MCP session not active.",
        "action_required": "Call zerodha_login first.",
    })


@tool
def get_zerodha_margins() -> str:
    """Get available cash and margin in your Zerodha account.

    Returns equity, commodity, and total available balance.
    """
    return json.dumps({
        "success": False,
        "error": "Zerodha MCP session not active.",
        "action_required": "Call zerodha_login first.",
    })


@tool
def update_activity_log(entry: str) -> str:
    """Append a short summary entry to the live activity log shown on the dashboard.

    Call this after completing any substantive analysis step so the user sees
    real-time progress even before you finish typing your full response.

    Args:
        entry: One-line summary, e.g. "Analysed RELIANCE: Bullish signal, 73% confidence"
    """
    return json.dumps({"success": True, "entry": entry.strip()})


@tool
def summarize_portfolio(holdings_json: str, current_prices_json: str) -> str:
    """Calculate portfolio summary statistics from holdings and current prices.

    Use after calling get_zerodha_holdings + get_current_quote for each holding.

    Args:
        holdings_json: JSON string with holdings (list of {symbol, qty, avg_price})
        current_prices_json: JSON string with current prices {symbol: price}
    """
    try:
        holdings = json.loads(holdings_json)
        prices = json.loads(current_prices_json)

        total_invested = 0.0
        total_current = 0.0
        positions = []

        for h in holdings:
            sym = h.get("symbol", "")
            qty = float(h.get("qty", h.get("quantity", 0)))
            avg = float(h.get("avg_price", h.get("average_price", 0)))
            curr = float(prices.get(sym, avg))

            invested = qty * avg
            current_val = qty * curr
            pnl = current_val - invested
            pnl_pct = (pnl / invested) * 100 if invested > 0 else 0

            total_invested += invested
            total_current += current_val
            positions.append({
                "symbol": sym,
                "qty": qty,
                "avg_price": round(avg, 2),
                "current_price": round(curr, 2),
                "invested_inr": round(invested, 2),
                "current_value_inr": round(current_val, 2),
                "pnl_inr": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "weight_pct": 0,  # filled below
            })

        for p in positions:
            p["weight_pct"] = round(p["current_value_inr"] / total_current * 100, 2) if total_current > 0 else 0

        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested > 0 else 0

        return json.dumps({
            "success": True,
            "total_invested_inr": round(total_invested, 2),
            "total_current_value_inr": round(total_current, 2),
            "total_pnl_inr": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "positions": positions,
        })
    except Exception as e:
        logger.error("summarize_portfolio: %s", e)
        return json.dumps({"success": False, "error": str(e)})
