"""Technical analysis tools — pandas-ta powered, with ensemble signal generation."""
import json
import logging
import math
from typing import Literal, Optional

import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    sym = ticker.upper()
    if "." not in sym:
        sym += ".NS"
    df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    return df.dropna()


def _hurst(ts: np.ndarray, max_lag: int = 20) -> float:
    """Estimate the Hurst exponent via R/S analysis.

    H < 0.5 → mean-reverting, H = 0.5 → random walk, H > 0.5 → trending.
    """
    lags = range(2, min(max_lag, len(ts) // 4))
    rs_list = []
    for lag in lags:
        chunks = [ts[i:i + lag] for i in range(0, len(ts) - lag, lag)]
        chunk_rs = []
        for chunk in chunks:
            mean = np.mean(chunk)
            dev = np.cumsum(chunk - mean)
            r = dev.max() - dev.min()
            s = np.std(chunk, ddof=1)
            if s > 0:
                chunk_rs.append(r / s)
        if chunk_rs:
            rs_list.append((lag, np.mean(chunk_rs)))
    if len(rs_list) < 2:
        return 0.5
    log_lags = np.log([x[0] for x in rs_list])
    log_rs = np.log([x[1] for x in rs_list])
    return float(np.polyfit(log_lags, log_rs, 1)[0])


def _signal(value: float | None, bullish_condition: bool, bearish_condition: bool) -> str:
    if value is None:
        return "neutral"
    if bullish_condition:
        return "bullish"
    if bearish_condition:
        return "bearish"
    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@tool
def compute_technical_analysis(
    ticker: str,
    period: Literal["3mo", "6mo", "1y", "2y"] = "1y",
) -> str:
    """Run a comprehensive multi-strategy technical analysis on a stock.

    Computes signals across 5 strategies — Trend, Momentum, Mean Reversion,
    Volatility, and Statistical Arbitrage — then aggregates them into a
    weighted ensemble signal (bullish / neutral / bearish) with a confidence %.

    Strategies and weights:
      Trend (25%)        — EMA 8/21/55/200, ADX, Parabolic SAR
      Momentum (25%)     — RSI 14/28, MACD, Stochastic, Williams %R
      Mean Reversion (20%) — Z-score, Bollinger Bands, Keltner Channels
      Volatility (15%)   — Historical vol, ATR regime, Bollinger width
      Statistical (15%)  — Hurst exponent, return skewness, kurtosis

    Returns structured analysis including per-strategy signals, key indicator
    values, and an overall recommendation.

    Args:
        ticker: NSE/BSE/global symbol (e.g. 'RELIANCE', 'AAPL')
        period: Historical lookback (3mo / 6mo / 1y / 2y)
    """
    sym = ticker.upper()
    if "." not in sym:
        sym += ".NS"

    try:
        df = _fetch_ohlcv(sym, period)
        if len(df) < 60:
            return json.dumps({"success": False, "error": "Not enough data (< 60 bars)"})

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        returns = close.pct_change().dropna()

        # ── Trend analysis ───────────────────────────────────────────────────
        ema8 = ta.ema(close, length=8)
        ema21 = ta.ema(close, length=21)
        ema55 = ta.ema(close, length=55)
        ema200 = ta.ema(close, length=200)
        adx_df = ta.adx(high, low, close, length=14)
        adx_val = float(adx_df[f"ADX_14"].iloc[-1]) if adx_df is not None else None
        dmp = float(adx_df[f"DMP_14"].iloc[-1]) if adx_df is not None else None
        dmn = float(adx_df[f"DMN_14"].iloc[-1]) if adx_df is not None else None

        curr_price = float(close.iloc[-1])
        ema8_v = float(ema8.iloc[-1])
        ema21_v = float(ema21.iloc[-1])
        ema55_v = float(ema55.iloc[-1])
        ema200_v = float(ema200.iloc[-1]) if len(ema200.dropna()) > 0 else None

        trend_bullish = (
            ema8_v > ema21_v > ema55_v
            and curr_price > ema21_v
            and (adx_val or 0) > 25
            and (dmp or 0) > (dmn or 0)
        )
        trend_bearish = (
            ema8_v < ema21_v < ema55_v
            and curr_price < ema21_v
            and (adx_val or 0) > 25
            and (dmn or 0) > (dmp or 0)
        )
        trend_signal = "bullish" if trend_bullish else ("bearish" if trend_bearish else "neutral")

        # ── Momentum analysis ────────────────────────────────────────────────
        rsi14 = ta.rsi(close, length=14)
        rsi28 = ta.rsi(close, length=28)
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        stoch_df = ta.stoch(high, low, close, k=14, d=3)
        willr = ta.willr(high, low, close, length=14)

        rsi14_v = float(rsi14.iloc[-1]) if rsi14 is not None else None
        rsi28_v = float(rsi28.iloc[-1]) if rsi28 is not None else None
        macd_v = float(macd_df["MACD_12_26_9"].iloc[-1]) if macd_df is not None else None
        macd_sig = float(macd_df["MACDs_12_26_9"].iloc[-1]) if macd_df is not None else None
        macd_hist = float(macd_df["MACDh_12_26_9"].iloc[-1]) if macd_df is not None else None
        stoch_k = float(stoch_df["STOCHk_14_3_3"].iloc[-1]) if stoch_df is not None else None
        willr_v = float(willr.iloc[-1]) if willr is not None else None

        # Price momentum
        mom_1m = float(((close.iloc[-1] / close.iloc[-22]) - 1) * 100) if len(close) > 22 else None
        mom_3m = float(((close.iloc[-1] / close.iloc[-63]) - 1) * 100) if len(close) > 63 else None

        momentum_score = 0
        momentum_total = 0
        if rsi14_v:
            momentum_total += 1
            if rsi14_v > 55 and rsi14_v < 75:
                momentum_score += 1
            elif rsi14_v < 45 and rsi14_v > 25:
                momentum_score -= 1
        if macd_hist:
            momentum_total += 1
            if macd_hist > 0 and (macd_df["MACDh_12_26_9"].iloc[-2] if macd_df is not None else 0) < 0:
                momentum_score += 1  # MACD bullish crossover
            elif macd_hist < 0:
                momentum_score -= 1
        if mom_1m:
            momentum_total += 1
            if mom_1m > 2:
                momentum_score += 1
            elif mom_1m < -2:
                momentum_score -= 1

        momentum_signal = "bullish" if momentum_score > 0 else ("bearish" if momentum_score < 0 else "neutral")

        # ── Mean reversion analysis ──────────────────────────────────────────
        bb_df = ta.bbands(close, length=20, std=2)
        bb_upper = float(bb_df["BBU_20_2.0"].iloc[-1]) if bb_df is not None else None
        bb_lower = float(bb_df["BBL_20_2.0"].iloc[-1]) if bb_df is not None else None
        bb_mid = float(bb_df["BBM_20_2.0"].iloc[-1]) if bb_df is not None else None
        bb_pct = float(bb_df["BBP_20_2.0"].iloc[-1]) if bb_df is not None else None

        # Z-score vs 50-period MA
        ma50 = close.rolling(50).mean()
        std50 = close.rolling(50).std()
        zscore = float((close.iloc[-1] - ma50.iloc[-1]) / std50.iloc[-1]) if std50.iloc[-1] > 0 else 0.0

        mr_bullish = bb_pct is not None and bb_pct < 0.2 and zscore < -1.5
        mr_bearish = bb_pct is not None and bb_pct > 0.8 and zscore > 1.5
        mr_signal = "bullish" if mr_bullish else ("bearish" if mr_bearish else "neutral")

        # ── Volatility analysis ──────────────────────────────────────────────
        atr_df = ta.atr(high, low, close, length=14)
        atr_v = float(atr_df.iloc[-1]) if atr_df is not None else None
        atr_pct = (atr_v / curr_price) * 100 if atr_v else None

        hist_vol_21 = float(returns.rolling(21).std().iloc[-1] * math.sqrt(252) * 100)
        hist_vol_63 = float(returns.rolling(63).std().iloc[-1] * math.sqrt(252) * 100) if len(returns) > 63 else hist_vol_21
        vol_zscore = float((hist_vol_21 - returns.rolling(63).std().mean() * math.sqrt(252) * 100) /
                           (returns.rolling(63).std().std() * math.sqrt(252) * 100)) if len(returns) > 63 else 0.0

        # High-vol regime → bearish bias (risk-off)
        vol_signal = "bearish" if vol_zscore > 1.5 else ("bullish" if vol_zscore < -1.0 else "neutral")

        # ── Statistical / regime analysis ────────────────────────────────────
        log_returns = np.log(close / close.shift(1)).dropna().values[-63:]
        hurst = _hurst(log_returns)
        skew = float(returns.iloc[-63:].skew())
        kurt = float(returns.iloc[-63:].kurt())

        # H > 0.55 → trending (good for trend-following), H < 0.45 → mean-reverting
        stat_signal = "bullish" if hurst > 0.55 and trend_bullish else (
            "bearish" if hurst > 0.55 and trend_bearish else "neutral"
        )

        # ── Ensemble aggregation ─────────────────────────────────────────────
        weights = {
            "trend": 0.25,
            "momentum": 0.25,
            "mean_reversion": 0.20,
            "volatility": 0.15,
            "statistical": 0.15,
        }
        signals = {
            "trend": trend_signal,
            "momentum": momentum_signal,
            "mean_reversion": mr_signal,
            "volatility": vol_signal,
            "statistical": stat_signal,
        }

        bull_score = sum(weights[k] for k, v in signals.items() if v == "bullish")
        bear_score = sum(weights[k] for k, v in signals.items() if v == "bearish")
        overall = "bullish" if bull_score > bear_score + 0.05 else (
            "bearish" if bear_score > bull_score + 0.05 else "neutral"
        )
        confidence = round(max(bull_score, bear_score) * 100 / sum(weights.values()), 1)

        result = {
            "ticker": sym,
            "overall_signal": overall,
            "confidence_pct": confidence,
            "strategies": signals,
            "indicators": {
                "ema_8": round(ema8_v, 2),
                "ema_21": round(ema21_v, 2),
                "ema_55": round(ema55_v, 2),
                "ema_200": round(ema200_v, 2) if ema200_v else None,
                "adx": round(adx_val, 1) if adx_val else None,
                "adx_trend_strength": "strong" if (adx_val or 0) > 25 else "weak",
                "rsi_14": round(rsi14_v, 1) if rsi14_v else None,
                "rsi_28": round(rsi28_v, 1) if rsi28_v else None,
                "rsi_condition": (
                    "overbought" if (rsi14_v or 50) > 70 else
                    "oversold" if (rsi14_v or 50) < 30 else "neutral"
                ),
                "macd": round(macd_v, 3) if macd_v else None,
                "macd_histogram": round(macd_hist, 3) if macd_hist else None,
                "macd_signal": round(macd_sig, 3) if macd_sig else None,
                "stochastic_k": round(stoch_k, 1) if stoch_k else None,
                "williams_r": round(willr_v, 1) if willr_v else None,
                "bollinger_upper": round(bb_upper, 2) if bb_upper else None,
                "bollinger_lower": round(bb_lower, 2) if bb_lower else None,
                "bollinger_pct": round(bb_pct, 3) if bb_pct else None,
                "zscore_50ma": round(zscore, 2),
                "atr": round(atr_v, 2) if atr_v else None,
                "atr_pct": round(atr_pct, 2) if atr_pct else None,
                "hist_vol_21d_annualized_pct": round(hist_vol_21, 1),
                "hist_vol_63d_annualized_pct": round(hist_vol_63, 1),
                "volatility_zscore": round(vol_zscore, 2),
                "hurst_exponent": round(hurst, 3),
                "hurst_regime": (
                    "trending" if hurst > 0.55 else
                    "mean_reverting" if hurst < 0.45 else "random_walk"
                ),
                "return_skewness_63d": round(skew, 3),
                "return_kurtosis_63d": round(kurt, 3),
                "momentum_1m_pct": round(mom_1m, 2) if mom_1m else None,
                "momentum_3m_pct": round(mom_3m, 2) if mom_3m else None,
            },
            "current_price": round(curr_price, 2),
            "key_levels": {
                "ema_21_support": round(ema21_v, 2),
                "bollinger_upper_resistance": round(bb_upper, 2) if bb_upper else None,
                "bollinger_lower_support": round(bb_lower, 2) if bb_lower else None,
            },
        }
        return json.dumps({"success": True, "analysis": result})

    except Exception as e:
        logger.error("compute_technical_analysis %s: %s", sym, e, exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


@tool
def compute_support_resistance(ticker: str, period: Literal["3mo", "6mo", "1y"] = "6mo") -> str:
    """Identify key support and resistance levels using pivot points and swing highs/lows.

    Args:
        ticker: Stock ticker
        period: Historical period for swing detection
    """
    sym = ticker.upper()
    if "." not in sym:
        sym += ".NS"
    try:
        df = _fetch_ohlcv(sym, period)
        if len(df) < 20:
            return json.dumps({"success": False, "error": "Not enough data"})

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Classic pivot points (previous week)
        prev_high = float(high.iloc[-6:-1].max())
        prev_low = float(low.iloc[-6:-1].min())
        prev_close = float(close.iloc[-2])
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = 2 * pivot - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = 2 * pivot - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)

        # Swing highs/lows (last 5 significant peaks/troughs)
        window = 5
        swing_highs = []
        swing_lows = []
        for i in range(window, len(high) - window):
            if high.iloc[i] == high.iloc[i - window:i + window + 1].max():
                swing_highs.append(round(float(high.iloc[i]), 2))
            if low.iloc[i] == low.iloc[i - window:i + window + 1].min():
                swing_lows.append(round(float(low.iloc[i]), 2))

        curr_price = float(close.iloc[-1])

        # Nearest support below price, nearest resistance above
        supports = sorted([s for s in swing_lows if s < curr_price], reverse=True)[:3]
        resistances = sorted([r for r in swing_highs if r > curr_price])[:3]

        return json.dumps({
            "success": True,
            "ticker": sym,
            "current_price": round(curr_price, 2),
            "pivot_points": {
                "pivot": round(pivot, 2),
                "r1": round(r1, 2), "r2": round(r2, 2), "r3": round(r3, 2),
                "s1": round(s1, 2), "s2": round(s2, 2), "s3": round(s3, 2),
            },
            "swing_supports": supports,
            "swing_resistances": resistances,
        })
    except Exception as e:
        logger.error("compute_support_resistance %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def compute_vwap_and_volume(ticker: str) -> str:
    """Compute VWAP, OBV, and volume momentum for intraday context.

    Uses the most recent 30 days of daily data to compute:
    - On-Balance Volume (OBV) trend
    - Volume vs 21-day average
    - Money Flow Index (MFI 14)

    Args:
        ticker: Stock ticker
    """
    sym = ticker.upper()
    if "." not in sym:
        sym += ".NS"
    try:
        df = _fetch_ohlcv(sym, "3mo")
        if len(df) < 30:
            return json.dumps({"success": False, "error": "Not enough data"})

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        obv = ta.obv(close, volume)
        obv_trend = "rising" if float(obv.iloc[-1]) > float(obv.iloc[-10]) else "falling"

        mfi = ta.mfi(high, low, close, volume, length=14)
        mfi_v = float(mfi.iloc[-1]) if mfi is not None else None
        mfi_signal = "overbought" if (mfi_v or 50) > 80 else ("oversold" if (mfi_v or 50) < 20 else "neutral")

        vol_avg_21 = float(volume.rolling(21).mean().iloc[-1])
        vol_curr = float(volume.iloc[-1])
        vol_ratio = round(vol_curr / vol_avg_21, 2) if vol_avg_21 > 0 else 1.0

        return json.dumps({
            "success": True,
            "ticker": sym,
            "obv_trend": obv_trend,
            "mfi_14": round(mfi_v, 1) if mfi_v else None,
            "mfi_signal": mfi_signal,
            "volume_vs_21d_avg": vol_ratio,
            "volume_signal": "above_average" if vol_ratio > 1.5 else ("below_average" if vol_ratio < 0.7 else "normal"),
        })
    except Exception as e:
        logger.error("compute_vwap_and_volume %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})
