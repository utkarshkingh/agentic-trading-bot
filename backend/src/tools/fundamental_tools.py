"""Fundamental analysis tools — Yahoo Finance via yfinance."""
import json
import logging
import math
from typing import Optional

import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _nse(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if "." in t else t + ".NS"


def _safe(val, default=None):
    try:
        return round(float(val), 4) if val is not None and not math.isnan(float(val)) else default
    except (TypeError, ValueError):
        return default


@tool
def analyze_fundamentals(ticker: str) -> str:
    """Run a comprehensive fundamental analysis of a stock.

    Evaluates the company across four dimensions with signal scoring:

    1. Profitability — ROE, net/operating/gross margins
    2. Growth       — Revenue, EPS, and book value growth (YoY)
    3. Financial Health — Liquidity, debt ratios, FCF conversion
    4. Valuation    — P/E, P/B, P/S, EV/EBITDA, PEG ratio

    Each dimension produces a bullish / neutral / bearish signal based on
    threshold comparisons. An overall score and recommendation are returned.

    Args:
        ticker: Stock ticker (e.g. 'RELIANCE', 'INFY', 'AAPL')
    """
    sym = _nse(ticker)
    try:
        tk = yf.Ticker(sym)
        info = tk.info

        # ── Profitability ────────────────────────────────────────────────────
        roe = _safe(info.get("returnOnEquity"))
        net_margin = _safe(info.get("profitMargins"))
        op_margin = _safe(info.get("operatingMargins"))
        gross_margin = _safe(info.get("grossMargins"))
        roa = _safe(info.get("returnOnAssets"))

        prof_signals = []
        if roe is not None:
            prof_signals.append("bullish" if roe > 0.15 else ("bearish" if roe < 0.05 else "neutral"))
        if net_margin is not None:
            prof_signals.append("bullish" if net_margin > 0.10 else ("bearish" if net_margin < 0.03 else "neutral"))
        if op_margin is not None:
            prof_signals.append("bullish" if op_margin > 0.12 else ("bearish" if op_margin < 0.05 else "neutral"))

        prof_bulls = prof_signals.count("bullish")
        prof_bears = prof_signals.count("bearish")
        profitability_signal = "bullish" if prof_bulls > prof_bears else ("bearish" if prof_bears > prof_bulls else "neutral")

        # ── Growth ───────────────────────────────────────────────────────────
        rev_growth = _safe(info.get("revenueGrowth"))
        eps_growth = _safe(info.get("earningsGrowth"))
        earnings_quarterly = _safe(info.get("earningsQuarterlyGrowth"))

        growth_signals = []
        if rev_growth is not None:
            growth_signals.append("bullish" if rev_growth > 0.10 else ("bearish" if rev_growth < 0 else "neutral"))
        if eps_growth is not None:
            growth_signals.append("bullish" if eps_growth > 0.10 else ("bearish" if eps_growth < 0 else "neutral"))

        growth_bulls = growth_signals.count("bullish")
        growth_bears = growth_signals.count("bearish")
        growth_signal = "bullish" if growth_bulls > growth_bears else ("bearish" if growth_bears > growth_bulls else "neutral")

        # ── Financial Health ─────────────────────────────────────────────────
        current_ratio = _safe(info.get("currentRatio"))
        debt_to_equity = _safe(info.get("debtToEquity"))
        # D/E from Yahoo is in %, normalize to ratio
        if debt_to_equity and debt_to_equity > 10:
            debt_to_equity = debt_to_equity / 100
        fcf = _safe(info.get("freeCashflow"))
        total_cash = _safe(info.get("totalCash"))
        total_debt = _safe(info.get("totalDebt"))

        health_signals = []
        if current_ratio is not None:
            health_signals.append("bullish" if current_ratio > 1.5 else ("bearish" if current_ratio < 1.0 else "neutral"))
        if debt_to_equity is not None:
            health_signals.append("bullish" if debt_to_equity < 0.5 else ("bearish" if debt_to_equity > 1.5 else "neutral"))

        health_bulls = health_signals.count("bullish")
        health_bears = health_signals.count("bearish")
        health_signal = "bullish" if health_bulls > health_bears else ("bearish" if health_bears > health_bulls else "neutral")

        # ── Valuation ────────────────────────────────────────────────────────
        pe = _safe(info.get("trailingPE"))
        forward_pe = _safe(info.get("forwardPE"))
        pb = _safe(info.get("priceToBook"))
        ps = _safe(info.get("priceToSalesTrailing12Months"))
        ev_ebitda = _safe(info.get("enterpriseToEbitda"))
        peg = _safe(info.get("pegRatio"))
        div_yield = _safe(info.get("dividendYield"))
        payout_ratio = _safe(info.get("payoutRatio"))

        val_signals = []
        if pe is not None and pe > 0:
            val_signals.append("bullish" if pe < 20 else ("bearish" if pe > 40 else "neutral"))
        if pb is not None:
            val_signals.append("bullish" if pb < 3 else ("bearish" if pb > 6 else "neutral"))
        if ps is not None:
            val_signals.append("bullish" if ps < 5 else ("bearish" if ps > 10 else "neutral"))
        if peg is not None and peg > 0:
            val_signals.append("bullish" if peg < 1.0 else ("bearish" if peg > 2.5 else "neutral"))

        val_bulls = val_signals.count("bullish")
        val_bears = val_signals.count("bearish")
        valuation_signal = "bullish" if val_bulls > val_bears else ("bearish" if val_bears > val_bulls else "neutral")

        # ── Overall score ────────────────────────────────────────────────────
        all_signals = [profitability_signal, growth_signal, health_signal, valuation_signal]
        overall_bulls = all_signals.count("bullish")
        overall_bears = all_signals.count("bearish")
        overall = "bullish" if overall_bulls > overall_bears else (
            "bearish" if overall_bears > overall_bulls else "neutral"
        )
        confidence = round(max(overall_bulls, overall_bears) / len(all_signals) * 100, 1)

        result = {
            "ticker": sym,
            "company_name": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "overall_signal": overall,
            "confidence_pct": confidence,
            "dimension_signals": {
                "profitability": profitability_signal,
                "growth": growth_signal,
                "financial_health": health_signal,
                "valuation": valuation_signal,
            },
            "profitability": {
                "roe_pct": _safe(roe * 100 if roe else None),
                "roa_pct": _safe(roa * 100 if roa else None),
                "net_margin_pct": _safe(net_margin * 100 if net_margin else None),
                "operating_margin_pct": _safe(op_margin * 100 if op_margin else None),
                "gross_margin_pct": _safe(gross_margin * 100 if gross_margin else None),
            },
            "growth": {
                "revenue_growth_yoy_pct": _safe(rev_growth * 100 if rev_growth else None),
                "eps_growth_yoy_pct": _safe(eps_growth * 100 if eps_growth else None),
                "earnings_quarterly_growth_pct": _safe(earnings_quarterly * 100 if earnings_quarterly else None),
            },
            "financial_health": {
                "current_ratio": current_ratio,
                "debt_to_equity": debt_to_equity,
                "free_cash_flow_cr": _safe(fcf / 1e7 if fcf else None),  # in crores (INR)
                "total_cash_cr": _safe(total_cash / 1e7 if total_cash else None),
                "total_debt_cr": _safe(total_debt / 1e7 if total_debt else None),
            },
            "valuation": {
                "trailing_pe": pe,
                "forward_pe": forward_pe,
                "price_to_book": pb,
                "price_to_sales": ps,
                "ev_to_ebitda": ev_ebitda,
                "peg_ratio": peg,
                "dividend_yield_pct": _safe(div_yield * 100 if div_yield else None),
                "payout_ratio_pct": _safe(payout_ratio * 100 if payout_ratio else None),
            },
            "market_data": {
                "market_cap_cr": _safe(info.get("marketCap", 0) / 1e7),
                "enterprise_value_cr": _safe(info.get("enterpriseValue", 0) / 1e7),
                "beta": _safe(info.get("beta")),
                "52w_high": _safe(info.get("fiftyTwoWeekHigh")),
                "52w_low": _safe(info.get("fiftyTwoWeekLow")),
                "avg_volume_3m": info.get("averageVolume"),
            },
        }
        return json.dumps({"success": True, "analysis": result})

    except Exception as e:
        logger.error("analyze_fundamentals %s: %s", sym, e, exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


@tool
def get_analyst_recommendations(ticker: str) -> str:
    """Get analyst price targets and buy/hold/sell recommendation distribution.

    Args:
        ticker: Stock ticker
    """
    sym = _nse(ticker)
    try:
        tk = yf.Ticker(sym)
        info = tk.info

        recs = tk.recommendations
        rec_summary = {}
        if recs is not None and not recs.empty:
            latest = recs.iloc[-1] if len(recs) > 0 else None
            if latest is not None:
                rec_summary = {
                    "strong_buy": int(latest.get("strongBuy", 0)),
                    "buy": int(latest.get("buy", 0)),
                    "hold": int(latest.get("hold", 0)),
                    "sell": int(latest.get("sell", 0)),
                    "strong_sell": int(latest.get("strongSell", 0)),
                }

        total = sum(rec_summary.values())
        bull_rec = (rec_summary.get("strong_buy", 0) + rec_summary.get("buy", 0)) / total if total > 0 else 0
        rec_signal = "bullish" if bull_rec > 0.6 else ("bearish" if bull_rec < 0.3 else "neutral")

        return json.dumps({
            "success": True,
            "ticker": sym,
            "target_high": _safe(info.get("targetHighPrice")),
            "target_low": _safe(info.get("targetLowPrice")),
            "target_mean": _safe(info.get("targetMeanPrice")),
            "target_median": _safe(info.get("targetMedianPrice")),
            "current_price": _safe(info.get("currentPrice")),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "recommendation_key": info.get("recommendationKey", ""),
            "recommendation_distribution": rec_summary,
            "recommendation_signal": rec_signal,
        })
    except Exception as e:
        logger.error("get_analyst_recommendations %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})
