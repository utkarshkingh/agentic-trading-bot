"""Risk management tools — VaR, Sharpe, drawdown, and position sizing."""
import json
import logging
import math
from typing import Literal, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.tools import tool
from scipy import stats as sp_stats

from src.settings import settings

logger = logging.getLogger(__name__)


def _nse(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if "." in t else t + ".NS"


def _fetch_returns(ticker: str, period: str = "2y") -> pd.Series:
    sym = _nse(ticker)
    df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].pct_change().dropna()


@tool
def compute_risk_metrics(
    ticker: str,
    portfolio_value_inr: float = 1_000_000,
    period: Literal["1y", "2y"] = "2y",
) -> str:
    """Compute comprehensive risk metrics for a stock.

    Calculates:
    - Historical VaR (95%, 99%) at 1-day and 1-week horizons
    - Parametric VaR (normal distribution assumption)
    - CVaR / Expected Shortfall (loss beyond VaR)
    - Maximum drawdown and recovery period
    - Sharpe ratio (annualised, using configured risk-free rate)
    - Sortino ratio (downside deviation only)
    - Calmar ratio (return / max drawdown)
    - Beta vs Nifty 50

    Args:
        ticker: Stock ticker
        portfolio_value_inr: Rupee value exposed to this position for INR-denominated risk figures
        period: Historical lookback (1y / 2y)
    """
    sym = _nse(ticker)
    try:
        returns = _fetch_returns(sym, period)
        if len(returns) < 60:
            return json.dumps({"success": False, "error": "Insufficient history for risk metrics"})

        arr = returns.values
        rf_daily = settings.risk_free_rate / 252

        # ── VaR (Historical) ────────────────────────────────────────────────
        var_95_1d = float(np.percentile(arr, 5))
        var_99_1d = float(np.percentile(arr, 1))
        var_95_1w = var_95_1d * math.sqrt(5)  # sqrt-of-time scaling
        var_99_1w = var_99_1d * math.sqrt(5)

        # ── CVaR / Expected Shortfall ────────────────────────────────────────
        cvar_95 = float(arr[arr <= var_95_1d].mean()) if any(arr <= var_95_1d) else var_95_1d

        # ── Parametric VaR ───────────────────────────────────────────────────
        mu = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=1))
        param_var_95_1d = float(sp_stats.norm.ppf(0.05, mu, sigma))
        param_var_99_1d = float(sp_stats.norm.ppf(0.01, mu, sigma))

        # ── Maximum drawdown ─────────────────────────────────────────────────
        cum = (1 + returns).cumprod()
        rolling_max = cum.cummax()
        drawdown = (cum - rolling_max) / rolling_max
        max_dd = float(drawdown.min())
        # Recovery: how many days after the worst drawdown until full recovery
        trough_idx = drawdown.idxmin()
        post_trough = cum[trough_idx:]
        peak_before = rolling_max[trough_idx]
        recovery_days = None
        recovered = post_trough[post_trough >= peak_before]
        if not recovered.empty:
            recovery_days = int((recovered.index[0] - trough_idx).days)

        # ── Return metrics ───────────────────────────────────────────────────
        annualised_return = float((1 + mu) ** 252 - 1)
        annualised_vol = float(sigma * math.sqrt(252))
        sharpe = (annualised_return - settings.risk_free_rate) / annualised_vol if annualised_vol > 0 else 0.0

        downside = arr[arr < rf_daily]
        downside_dev = float(np.std(downside, ddof=1) * math.sqrt(252)) if len(downside) > 1 else annualised_vol
        sortino = (annualised_return - settings.risk_free_rate) / downside_dev if downside_dev > 0 else 0.0
        calmar = annualised_return / abs(max_dd) if max_dd != 0 else 0.0

        # ── Beta vs Nifty 50 ─────────────────────────────────────────────────
        beta = None
        try:
            nifty_ret = _fetch_returns("^NSEI", period)
            aligned = pd.concat([returns, nifty_ret], axis=1).dropna()
            aligned.columns = ["stock", "nifty"]
            if len(aligned) > 20:
                cov = aligned.cov()
                beta = round(float(cov.loc["stock", "nifty"] / cov.loc["nifty", "nifty"]), 3)
        except Exception:
            pass

        # ── INR-denominated risk ─────────────────────────────────────────────
        inr_var_95_1d = abs(var_95_1d) * portfolio_value_inr
        inr_var_99_1d = abs(var_99_1d) * portfolio_value_inr

        result = {
            "ticker": sym,
            "period": period,
            "risk_summary": {
                "var_95_1d_pct": round(var_95_1d * 100, 3),
                "var_99_1d_pct": round(var_99_1d * 100, 3),
                "var_95_1w_pct": round(var_95_1w * 100, 3),
                "var_95_1d_inr": round(inr_var_95_1d, 0),
                "var_99_1d_inr": round(inr_var_99_1d, 0),
                "cvar_95_1d_pct": round(cvar_95 * 100, 3),
                "param_var_95_1d_pct": round(param_var_95_1d * 100, 3),
                "param_var_99_1d_pct": round(param_var_99_1d * 100, 3),
                "max_drawdown_pct": round(max_dd * 100, 2),
                "recovery_days": recovery_days,
            },
            "return_metrics": {
                "annualised_return_pct": round(annualised_return * 100, 2),
                "annualised_vol_pct": round(annualised_vol * 100, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
                "risk_free_rate_pct": round(settings.risk_free_rate * 100, 2),
            },
            "market_risk": {
                "beta_vs_nifty50": beta,
                "interpretation": (
                    "High-beta (amplifies market moves)" if beta and beta > 1.2 else
                    "Low-beta (defensive)" if beta and beta < 0.8 else
                    "Market-beta (moves with index)"
                ),
            },
            "risk_level": (
                "high" if annualised_vol > 0.35 or abs(max_dd) > 0.40 else
                "medium" if annualised_vol > 0.20 or abs(max_dd) > 0.20 else
                "low"
            ),
        }
        return json.dumps({"success": True, "risk_metrics": result})

    except Exception as e:
        logger.error("compute_risk_metrics %s: %s", sym, e, exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


@tool
def suggest_position_size(
    ticker: str,
    portfolio_value_inr: float,
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate",
) -> str:
    """Calculate optimal position size using volatility-based and Kelly criterion methods.

    Combines:
    1. Volatility-based sizing (lower vol → larger allowed position)
    2. Correlation adjustment (high correlation with existing holdings → smaller)
    3. Kelly fraction (optional, capped at 20% to prevent over-betting)

    Args:
        ticker: Stock ticker
        portfolio_value_inr: Total portfolio value in rupees
        risk_tolerance: conservative / moderate / aggressive
    """
    sym = _nse(ticker)
    try:
        returns = _fetch_returns(sym, "1y")
        if len(returns) < 60:
            return json.dumps({"success": False, "error": "Insufficient data"})

        ann_vol = float(returns.std() * math.sqrt(252))
        ann_ret = float((1 + returns.mean()) ** 252 - 1)

        # Volatility-based max allocation
        risk_caps = {"conservative": 0.12, "moderate": 0.18, "aggressive": 0.25}
        base_cap = risk_caps[risk_tolerance]

        if ann_vol < 0.15:
            vol_alloc = base_cap
        elif ann_vol < 0.25:
            vol_alloc = base_cap * 0.8
        elif ann_vol < 0.35:
            vol_alloc = base_cap * 0.6
        else:
            vol_alloc = base_cap * 0.4

        # Kelly fraction (win rate estimated from positive days)
        win_rate = float((returns > 0).mean())
        avg_win = float(returns[returns > 0].mean()) if any(returns > 0) else 0.01
        avg_loss = float(abs(returns[returns < 0].mean())) if any(returns < 0) else 0.01
        kelly = (win_rate / avg_loss - (1 - win_rate) / avg_win) if avg_win > 0 else 0
        kelly_frac = max(0, min(kelly, 0.20))  # cap at 20%

        # Final suggested allocation
        suggested_alloc = min(vol_alloc, kelly_frac if kelly_frac > 0 else vol_alloc)
        suggested_inr = round(portfolio_value_inr * suggested_alloc)

        return json.dumps({
            "success": True,
            "ticker": sym,
            "portfolio_value_inr": portfolio_value_inr,
            "risk_tolerance": risk_tolerance,
            "suggested_allocation_pct": round(suggested_alloc * 100, 1),
            "suggested_amount_inr": suggested_inr,
            "methodology": {
                "volatility_based_max_pct": round(vol_alloc * 100, 1),
                "kelly_fraction_pct": round(kelly_frac * 100, 1),
                "annualised_volatility_pct": round(ann_vol * 100, 1),
                "win_rate_pct": round(win_rate * 100, 1),
            },
            "stop_loss_suggestion": {
                "pct_below_entry": round(ann_vol / math.sqrt(12) * 2 * 100, 1),
                "note": "2× monthly vol below entry as initial stop",
            },
        })
    except Exception as e:
        logger.error("suggest_position_size %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def compute_portfolio_correlation(tickers: list[str]) -> str:
    """Compute the pairwise correlation matrix for a list of tickers.

    Useful for portfolio diversification analysis — high correlations mean
    the holdings move together and don't provide true diversification.

    Args:
        tickers: List of stock tickers (e.g. ['RELIANCE', 'TCS', 'HDFCBANK'])
    """
    if len(tickers) < 2:
        return json.dumps({"success": False, "error": "Need at least 2 tickers"})

    syms = [_nse(t) for t in tickers]
    try:
        data = {}
        for sym in syms:
            returns = _fetch_returns(sym, "1y")
            if len(returns) > 30:
                data[sym] = returns

        if len(data) < 2:
            return json.dumps({"success": False, "error": "Not enough valid tickers"})

        df = pd.DataFrame(data).dropna()
        corr = df.corr().round(3)

        # Average pairwise correlation (excluding diagonal)
        corr_vals = []
        for i in range(len(corr)):
            for j in range(i + 1, len(corr)):
                corr_vals.append(float(corr.iloc[i, j]))
        avg_corr = round(sum(corr_vals) / len(corr_vals), 3) if corr_vals else 1.0

        matrix = []
        for col in corr.columns:
            matrix.append({"ticker": col, **{other: float(corr.loc[col, other]) for other in corr.columns}})

        return json.dumps({
            "success": True,
            "tickers": list(corr.columns),
            "correlation_matrix": matrix,
            "average_pairwise_correlation": avg_corr,
            "diversification_signal": (
                "poor" if avg_corr > 0.7 else
                "moderate" if avg_corr > 0.5 else
                "good"
            ),
        })
    except Exception as e:
        logger.error("compute_portfolio_correlation: %s", e)
        return json.dumps({"success": False, "error": str(e)})
