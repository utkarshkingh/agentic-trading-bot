"""News and sentiment tools — RSS/Google News + yfinance insider data."""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lightweight sentiment lexicon (no external API needed)
# ─────────────────────────────────────────────────────────────────────────────

_BULLISH_WORDS = {
    "surge", "jump", "rally", "gain", "profit", "beat", "upgrade", "buy",
    "bullish", "positive", "strong", "growth", "record", "high", "rise",
    "outperform", "boost", "breakout", "momentum", "win", "expand",
}
_BEARISH_WORDS = {
    "fall", "drop", "decline", "loss", "miss", "downgrade", "sell",
    "bearish", "negative", "weak", "cut", "low", "concern", "risk",
    "underperform", "slump", "crash", "caution", "warning", "fraud",
}


def _score_headline(text: str) -> tuple[str, float]:
    """Return (sentiment_label, confidence) for a headline string."""
    words = re.findall(r"\w+", text.lower())
    bull = sum(1 for w in words if w in _BULLISH_WORDS)
    bear = sum(1 for w in words if w in _BEARISH_WORDS)
    if bull == 0 and bear == 0:
        return "neutral", 0.5
    total = bull + bear
    confidence = max(bull, bear) / total
    return ("positive" if bull >= bear else "negative"), round(confidence, 2)


def _nse(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if "." in t else t + ".NS"


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_news_sentiment(ticker: str, max_articles: int = 20) -> str:
    """Fetch recent news and compute sentiment for a stock.

    Uses Google Finance RSS and Yahoo Finance to collect headlines, then runs
    lexicon-based sentiment scoring. Returns per-article sentiment and an
    aggregated weighted score.

    Args:
        ticker: Stock ticker (e.g. 'RELIANCE', 'AAPL')
        max_articles: Number of recent articles to analyse (max 30)
    """
    sym = _nse(ticker)
    company_q = sym.replace(".NS", "").replace(".BO", "")
    max_articles = min(max_articles, 30)

    articles = []

    # ── Source 1: Yahoo Finance news ────────────────────────────────────────
    try:
        tk = yf.Ticker(sym)
        yf_news = tk.news
        if yf_news:
            for item in yf_news[:15]:
                title = item.get("title", "")
                link = item.get("link", item.get("url", ""))
                published = item.get("providerPublishTime") or item.get("publish_time")
                pub_str = (
                    datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                    if published
                    else ""
                )
                label, conf = _score_headline(title)
                articles.append({
                    "source": "Yahoo Finance",
                    "title": title,
                    "url": link,
                    "published": pub_str,
                    "sentiment": label,
                    "confidence": conf,
                })
    except Exception as e:
        logger.warning("Yahoo Finance news failed for %s: %s", sym, e)

    # ── Source 2: Google Finance RSS ─────────────────────────────────────────
    try:
        rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=IN&lang=en-IN"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published_parsed = entry.get("published_parsed")
            pub_str = datetime(*published_parsed[:3]).strftime("%Y-%m-%d") if published_parsed else ""
            label, conf = _score_headline(title)
            articles.append({
                "source": "Yahoo RSS",
                "title": title,
                "url": link,
                "published": pub_str,
                "sentiment": label,
                "confidence": conf,
            })
    except Exception as e:
        logger.warning("Yahoo RSS failed for %s: %s", sym, e)

    # Deduplicate by title prefix
    seen = set()
    deduped = []
    for a in articles:
        key = a["title"][:40].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    deduped = deduped[:max_articles]

    # ── Aggregate sentiment ──────────────────────────────────────────────────
    pos = sum(1 for a in deduped if a["sentiment"] == "positive")
    neg = sum(1 for a in deduped if a["sentiment"] == "negative")
    neu = sum(1 for a in deduped if a["sentiment"] == "neutral")
    total = len(deduped)

    weighted_score = 0.0
    if total > 0:
        weighted_score = (pos - neg) / total  # range -1 to +1

    overall_sentiment = (
        "positive" if weighted_score > 0.1 else
        "negative" if weighted_score < -0.1 else
        "neutral"
    )
    overall_signal = (
        "bullish" if overall_sentiment == "positive" else
        "bearish" if overall_sentiment == "negative" else
        "neutral"
    )

    return json.dumps({
        "success": True,
        "ticker": sym,
        "articles_analysed": total,
        "overall_sentiment": overall_sentiment,
        "overall_signal": overall_signal,
        "sentiment_score": round(weighted_score, 3),  # -1 to +1
        "breakdown": {"positive": pos, "negative": neg, "neutral": neu},
        "articles": deduped[:10],  # top 10 for display
    })


@tool
def get_insider_activity(ticker: str) -> str:
    """Fetch recent insider trading activity (buys vs. sells) for a stock.

    Insider buying is a bullish signal; heavy selling can indicate distribution.

    Args:
        ticker: Stock ticker
    """
    sym = _nse(ticker)
    try:
        tk = yf.Ticker(sym)
        trades_df = tk.insider_transactions
        if trades_df is None or trades_df.empty:
            return json.dumps({"success": True, "ticker": sym, "trades": [], "signal": "neutral", "note": "No insider data"})

        trades = []
        buys = 0
        sells = 0
        for _, row in trades_df.head(20).iterrows():
            txt = str(row.get("Text", "")).lower()
            shares = row.get("Shares", 0)
            direction = "buy" if "purchase" in txt or "acquisition" in txt else (
                "sell" if "sale" in txt or "disposed" in txt else "other"
            )
            if direction == "buy":
                buys += 1
            elif direction == "sell":
                sells += 1
            trades.append({
                "date": str(row.get("Start Date", "")),
                "insider": str(row.get("Insider", "")),
                "title": str(row.get("Position", "")),
                "type": direction,
                "shares": int(shares) if shares else 0,
                "value": float(row.get("Value", 0)) if row.get("Value") else 0,
            })

        signal = (
            "bullish" if buys > sells * 1.5 else
            "bearish" if sells > buys * 1.5 else
            "neutral"
        )

        return json.dumps({
            "success": True,
            "ticker": sym,
            "total_trades": len(trades),
            "buys": buys,
            "sells": sells,
            "signal": signal,
            "recent_trades": trades[:10],
        })
    except Exception as e:
        logger.error("get_insider_activity %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})


@tool
def get_options_sentiment(ticker: str) -> str:
    """Get put/call ratio and options sentiment as a contrarian indicator.

    High put/call ratio → fearful market (contrarian bullish).
    Low put/call ratio → complacent market (contrarian bearish).

    Args:
        ticker: Stock ticker
    """
    sym = _nse(ticker)
    try:
        tk = yf.Ticker(sym)
        exp_dates = tk.options
        if not exp_dates:
            return json.dumps({"success": True, "ticker": sym, "note": "No options data", "signal": "neutral"})

        # Use nearest expiry
        opts = tk.option_chain(exp_dates[0])
        calls_oi = opts.calls["openInterest"].sum() if not opts.calls.empty else 0
        puts_oi = opts.puts["openInterest"].sum() if not opts.puts.empty else 0
        calls_vol = opts.calls["volume"].sum() if not opts.calls.empty else 0
        puts_vol = opts.puts["volume"].sum() if not opts.puts.empty else 0

        pcr_oi = puts_oi / calls_oi if calls_oi > 0 else 1.0
        pcr_vol = puts_vol / calls_vol if calls_vol > 0 else 1.0

        # Contrarian interpretation
        signal = "bullish" if pcr_oi > 1.3 else ("bearish" if pcr_oi < 0.7 else "neutral")

        return json.dumps({
            "success": True,
            "ticker": sym,
            "expiry": exp_dates[0],
            "calls_open_interest": int(calls_oi),
            "puts_open_interest": int(puts_oi),
            "calls_volume": int(calls_vol),
            "puts_volume": int(puts_vol),
            "put_call_ratio_oi": round(pcr_oi, 3),
            "put_call_ratio_volume": round(pcr_vol, 3),
            "signal": signal,
            "interpretation": (
                "High PCR → fear in market, contrarian bullish" if pcr_oi > 1.3 else
                "Low PCR → complacency, contrarian bearish" if pcr_oi < 0.7 else
                "Neutral PCR → balanced sentiment"
            ),
        })
    except Exception as e:
        logger.error("get_options_sentiment %s: %s", sym, e)
        return json.dumps({"success": False, "error": str(e)})
