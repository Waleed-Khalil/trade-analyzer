"""
Market Data Module
Fetch underlying price and rich context (yfinance) and optional news (Brave Search) for option analysis.
"""

from datetime import date, datetime
from typing import Optional, Dict, Any, List


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_underlying_price(ticker: str) -> Optional[float]:
    """Fetch current underlying stock price. Returns None if unavailable."""
    ctx = get_market_context(ticker)
    return ctx.get("current_price")


def get_market_context(ticker: str) -> Dict[str, Any]:
    """
    Fetch rich market context for ticker from Yahoo Finance.
    Returns dict with: current_price, open, high, low, volume, day_range, prev_close,
    fifty_two_week_high, fifty_two_week_low, market_cap (when available).
    Empty dict on failure.
    """
    ctx: Dict[str, Any] = {}
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # 1) Try info dict (most reliable in yfinance 1.x for current price)
        try:
            info = t.info
            if isinstance(info, dict):
                price = _safe_float(
                    info.get("regularMarketPrice")
                    or info.get("currentPrice")
                    or info.get("previousClose")
                )
                if price is not None:
                    ctx["current_price"] = price
                prev = _safe_float(info.get("previousClose"))
                if prev is not None:
                    ctx["prev_close"] = prev
                hi52 = _safe_float(info.get("fiftyTwoWeekHigh"))
                if hi52 is not None:
                    ctx["fifty_two_week_high"] = hi52
                lo52 = _safe_float(info.get("fiftyTwoWeekLow"))
                if lo52 is not None:
                    ctx["fifty_two_week_low"] = lo52
                cap = info.get("marketCap")
                if cap is not None:
                    ctx["market_cap"] = _safe_int(cap)
        except Exception:
            pass

        # 2) Try fast_info for current price if not yet set
        if ctx.get("current_price") is None:
            try:
                fi = getattr(t, "fast_info", None)
                if fi is not None:
                    lp = getattr(fi, "last_price", None)
                    if lp is not None:
                        ctx["current_price"] = _safe_float(lp)
            except Exception:
                pass

        # 3) History: 1d for today's OHLCV, 5d for recent context
        for period, key_prefix in (("1d", "today"), ("5d", "recent")):
            try:
                hist = t.history(period=period)
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    last = hist.iloc[-1]
                    close = _safe_float(last.get("Close"))
                    if close is not None and ctx.get("current_price") is None:
                        ctx["current_price"] = close
                    if key_prefix == "today":
                        ctx["open"] = _safe_float(last.get("Open"))
                        ctx["high"] = _safe_float(last.get("High"))
                        ctx["low"] = _safe_float(last.get("Low"))
                        ctx["volume"] = _safe_int(last.get("Volume"))
                        if ctx.get("high") is not None and ctx.get("low") is not None:
                            ctx["day_range"] = (ctx["high"], ctx["low"])
                    break
            except Exception:
                continue

        # 4) If we still have no price, try 5d history
        if ctx.get("current_price") is None:
            try:
                hist = t.history(period="5d")
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    ctx["current_price"] = _safe_float(hist["Close"].iloc[-1])
                    last = hist.iloc[-1]
                    if ctx.get("open") is None:
                        ctx["open"] = _safe_float(last.get("Open"))
                    if ctx.get("high") is None:
                        ctx["high"] = _safe_float(last.get("High"))
                    if ctx.get("low") is None:
                        ctx["low"] = _safe_float(last.get("Low"))
                    if ctx.get("volume") is None:
                        ctx["volume"] = _safe_int(last.get("Volume"))
            except Exception:
                pass

        # 5) 5d return and 5d range (for momentum and S/R context)
        try:
            hist = t.history(period="5d")
            if hist is not None and len(hist) >= 2 and "Close" in hist.columns:
                first_close = _safe_float(hist["Close"].iloc[0])
                last_close = _safe_float(hist["Close"].iloc[-1])
                if first_close and last_close and first_close != 0:
                    ctx["five_d_return_pct"] = round((last_close - first_close) / first_close * 100, 2)
                if "High" in hist.columns and "Low" in hist.columns:
                    ctx["recent_5d_high"] = _safe_float(hist["High"].max())
                    ctx["recent_5d_low"] = _safe_float(hist["Low"].min())
        except Exception:
            pass
    except Exception:
        pass
    return ctx


def get_news_context(ticker: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Fetch recent news/headlines for the ticker via Brave Search API.
    Returns list of {"title": ..., "url": ..., "description": ...}.
    Empty list if BRAVE_API_KEY not set or request fails.
    """
    import os
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return []
    try:
        from brave import Brave
        client = Brave(api_key=api_key)
        query = f"{ticker} stock news"
        result = client.search(q=query, count=max_results)
        news = []
        for source in ("news_results", "web_results"):
            items = getattr(result, source, None) or []
            for n in items[:max_results]:
                item = {}
                if getattr(n, "title", None):
                    item["title"] = str(n.title)
                if getattr(n, "url", None):
                    item["url"] = str(n.url)
                if getattr(n, "description", None):
                    item["description"] = str(n.description)
                if item:
                    news.append(item)
            if news:
                break
        return news
    except Exception:
        return []


def get_atr(
    ticker: str,
    period: int = 14,
    days_back: int = 60,
) -> Optional[float]:
    """
    Compute 14-day (or period) ATR for the underlying using Yahoo Finance daily OHLC.
    True Range = max(H-L, |H-prev_close|, |L-prev_close|); ATR = rolling mean(TR).
    Returns ATR in same units as price (e.g. $ for QQQ). None if insufficient data or fetch fails.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{days_back}d", interval="1d")
        if hist is None or len(hist) < period:
            return None
        high = hist.get("High", hist.get("high"))
        low = hist.get("Low", hist.get("low"))
        close = hist.get("Close", hist.get("close"))
        if high is None or low is None or close is None:
            return None
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = tr1.combine(tr2, max).combine(tr3, max)
        tr = tr.fillna(tr1)  # first row: no prev_close, use H-L only
        atr_series = tr.rolling(window=period).mean()
        valid = atr_series.dropna()
        if len(valid) == 0:
            return None
        atr = _safe_float(valid.iloc[-1])
        if atr is None or (atr != atr):  # reject NaN
            return None
        return atr
    except Exception:
        return None


def get_events(ticker: str, dte: int) -> Dict[str, Any]:
    """
    Fetch upcoming earnings and ex-dividend dates within the option's DTE window.
    Uses yfinance. Returns dict of events: {'earnings': {'date': 'YYYY-MM-DD', 'days_to': n}, ...}
    or {} if none in window / fetch fails. dte is days to expiration (0 = today).
    """
    events: Dict[str, Any] = {}
    today = date.today()
    window_end = dte + 1

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # Earnings: earliest future date within [0, dte+1] days (some sources show Apr 27/28/29 variants; we take soonest in window)
        try:
            cal = t.get_earnings_dates(limit=12)
            if cal is not None and not cal.empty:
                next_earnings: Optional[Dict[str, Any]] = None
                for idx in cal.index:
                    try:
                        if hasattr(idx, "to_pydatetime"):
                            ed = idx.to_pydatetime().date()
                        elif hasattr(idx, "date"):
                            ed = idx.date()
                        else:
                            continue
                        days_to = (ed - today).days
                        if 0 <= days_to <= window_end:
                            if next_earnings is None or days_to < next_earnings["days_to"]:
                                next_earnings = {"date": ed.strftime("%Y-%m-%d"), "days_to": days_to}
                    except Exception:
                        continue
                if next_earnings:
                    events["earnings"] = next_earnings
        except Exception:
            pass

        # Dividend: exDividendDate from info (Unix timestamp)
        try:
            info = t.info
            if isinstance(info, dict):
                ex_ts = info.get("exDividendDate")
                if ex_ts is not None and isinstance(ex_ts, (int, float)):
                    ex_dt = datetime.fromtimestamp(ex_ts)
                    ex_d = ex_dt.date()
                    days_to_div = (ex_d - today).days
                    if 0 <= days_to_div <= window_end:
                        events["dividend"] = {"date": ex_d.strftime("%Y-%m-%d"), "days_to": days_to_div}
        except Exception:
            pass
    except Exception:
        pass
    return events
