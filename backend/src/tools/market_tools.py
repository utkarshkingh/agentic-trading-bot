"""Market data tools — yfinance primary source, Zerodha MCP for live Indian data."""
import json
import logging
from datetime import datetime, timedelta
from typing import Literal, Optional

import pandas as pd
import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _nse(ticker: str) -> str:
    """Append '.NS' suffix for NSE symbols if not already qualified."""
    t = ticker.upper().strip()
    if "." not in t:
        return t + ".NS"
    return t


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_current_quote(ticker: str) -> str:
    """Get the real-time price quote for a stock.

    Returns current price, change, % change, volume, 52-week high/low,
    market cap, and P/E ratio.

    Args:
        ticker: Stock ticker (e.g. 'RELIANCE', 'RELIANCE.NS', 'AAPL')
    """
    sym = _nse(ticker)
    try:
        tk = yf.Ticker(sym)
        info = tk.fast_info
        hist = tk.history(period="2d", interval="1d")

        prev_close = None
        curr_price = _safe_float(getattr(info, "last_price", None))

        if hist is not None and len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
        elif hist is not None and len(hist) == 1:
            prev_close = float(hist["Close"].iloc[0])

        change = None
        change_pct = None
        if curr_price and prev_close:
            change = curr_price - prev_close
            change_pct = (change / prev_close) * 100

        result = {
            "ticker": sym,
            "price": curr_price,
            "prev_close": prev_close,
            "change": round(change, 2) if change else None,
            "change_pct": round(change_pct, 2) if change_pct else None,
            "volume": _safe_float(getattr(info, "three_month_average_volume", None)),
            "market_cap": _safe_float(getattr(info, "market_cap", None)),
            "week_52_high": _safe_float(getattr(info, "fifty_two_week_high", None)),
            "week_52_low": _safe_float(getattr(info, "fifty_two_week_low", None)),
            "currency": getattr(info, "currency", "INR"),
        }
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        logger.error("get_current_quote %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def get_historical_ohlcv(
    ticker: str,
    period: Literal["1mo", "3mo", "6mo", "1y", "2y", "5y"] = "1y",
    interval: Literal["1d", "1wk", "1mo"] = "1d",
) -> str:
    """Fetch historical OHLCV (Open/High/Low/Close/Volume) data for a symbol.

    Args:
        ticker: Stock ticker (e.g. 'RELIANCE', 'NIFTY50.NS', 'AAPL')
        period: Lookback window — 1mo / 3mo / 6mo / 1y / 2y / 5y
        interval: Bar interval — 1d (daily) / 1wk (weekly) / 1mo (monthly)
    """
    sym = _nse(ticker)
    try:
        df = yf.download(sym, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return json.dumps({"success": False, "error": f"No data for {sym}"})

        # Flatten MultiIndex columns if present (yfinance ≥ 0.2.37)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        records = []
        for _, row in df.iterrows():
            records.append({
                "date": row["Date"],
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return json.dumps({
            "success": True,
            "ticker": sym,
            "period": period,
            "interval": interval,
            "rows": len(records),
            "data": records,
        })
    except Exception as e:
        logger.error("get_historical_ohlcv %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def search_ticker(query: str) -> str:
    """Search for a stock ticker by company name or partial symbol.

    Useful when the user says 'Reliance Industries' or 'HDFC bank' instead of
    the exact NSE symbol. Returns up to 5 matching results.

    Args:
        query: Company name or partial ticker (e.g. 'tata motors', 'HDFC')
    """
    try:
        results = yf.Search(query, max_results=5)
        quotes = results.quotes if hasattr(results, "quotes") else []
        hits = [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname", q.get("longname", "")),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            }
            for q in quotes
        ]
        return json.dumps({"success": True, "query": query, "results": hits})
    except Exception as e:
        logger.error("search_ticker %s: %s", query, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def get_market_overview() -> str:
    """Get a snapshot of key Indian and global market indices.

    Returns Nifty 50, Bank Nifty, Sensex, Gold (MCX), USD/INR.
    """
    INDICES = {
        "Nifty 50": "^NSEI",
        "Bank Nifty": "^NSEBANK",
        "Sensex": "^BSESN",
        "Nifty IT": "^CNXIT",
        "S&P 500": "^GSPC",
        "Gold (MCX approx)": "GC=F",
        "USD/INR": "USDINR=X",
        "Crude Oil": "CL=F",
    }
    results = {}
    for name, sym in INDICES.items():
        try:
            tk = yf.Ticker(sym)
            hist = tk.history(period="2d", interval="1d")
            if hist is not None and len(hist) >= 1:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
                chg = round(close - prev, 2)
                chg_pct = round((chg / prev) * 100, 2)
                results[name] = {
                    "price": round(close, 2),
                    "change": chg,
                    "change_pct": chg_pct,
                    "symbol": sym,
                }
        except Exception:
            pass

    return json.dumps({"success": True, "indices": results, "as_of": datetime.now().strftime("%Y-%m-%d %H:%M")})


@tool
def get_sector_performance() -> str:
    """Get performance of major Indian NSE sector indices.

    Useful for understanding sector rotation and macro context.
    """
    SECTORS = {
        "Auto": "^CNXAUTO",
        "FMCG": "^CNXFMCG",
        "Pharma": "^CNXPHARMA",
        "Realty": "^CNXREALTY",
        "Metal": "^CNXMETAL",
        "Energy": "^CNXENERGY",
        "Media": "^CNXMEDIA",
        "PSU Bank": "^CNXPSUBANK",
    }
    results = {}
    for name, sym in SECTORS.items():
        try:
            hist = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=True)
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if hist is not None and len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                chg_pct = round(((close - prev) / prev) * 100, 2)
                # 1-week change
                week_close = float(hist["Close"].iloc[0]) if len(hist) >= 5 else prev
                week_chg = round(((close - week_close) / week_close) * 100, 2)
                results[name] = {
                    "price": round(close, 2),
                    "day_change_pct": chg_pct,
                    "week_change_pct": week_chg,
                    "symbol": sym,
                }
        except Exception:
            pass

    return json.dumps({"success": True, "sectors": results})
