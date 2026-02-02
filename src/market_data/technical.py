"""
Multi-timeframe technical indicators: RSI, MACD, SMA from yfinance OHLC.
Used for confluence (bullish/bearish) and setup score / red flags.
"""

from typing import Any, Dict, List, Optional


def _rsi(close: Any, period: int = 14) -> Optional[float]:
    """RSI = 100 - 100/(1 + RS), RS = avg gain / avg loss (simple rolling mean)."""
    if close is None or len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    try:
        val = float(rsi.iloc[-1])
        return round(val, 1) if not (val != val) else None  # NaN check
    except (IndexError, TypeError, ValueError):
        return None


def _sma(close: Any, period: int) -> Optional[float]:
    if close is None or len(close) < period:
        return None
    s = close.rolling(period).mean()
    try:
        val = float(s.iloc[-1])
        return round(val, 2) if not (val != val) else None
    except (IndexError, TypeError, ValueError):
        return None


def _macd(close: Any, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
    """MACD line, signal line, histogram. Bullish = histogram > 0."""
    out: Dict[str, Optional[float]] = {"macd_line": None, "macd_signal": None, "macd_histogram": None, "macd_bullish": None}
    if close is None or len(close) < slow + signal:
        return out
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - macd_signal
    try:
        out["macd_line"] = round(float(macd_line.iloc[-1]), 4)
        out["macd_signal"] = round(float(macd_signal.iloc[-1]), 4)
        out["macd_histogram"] = round(float(hist.iloc[-1]), 4)
        out["macd_bullish"] = float(hist.iloc[-1]) > 0
    except (IndexError, TypeError, ValueError):
        pass
    return out


def _technical_for_series(
    close: Any,
    price_now: Optional[float],
    rsi_period: int,
    sma_periods: List[int],
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    rsi = _rsi(close, rsi_period)
    if rsi is not None:
        ctx["rsi"] = rsi
    for p in sma_periods:
        sma = _sma(close, p)
        if sma is not None:
            ctx[f"sma_{p}"] = sma
            if price_now is not None:
                ctx[f"price_above_sma_{p}"] = price_now > sma
    macd = _macd(close, macd_fast, macd_slow, macd_signal)
    for k, v in macd.items():
        if v is not None:
            ctx[k] = v
    return ctx


def get_technical_context(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch daily and optional 1h OHLC from yfinance; compute RSI, SMA(20,50), MACD.
    Returns dict with keys: daily: {...}, 1h: {...} (if requested and available), technical_enabled: True.
    Empty dict if disabled or fetch fails.
    """
    tech = config.get("analysis", {}).get("technical", {})
    if not tech.get("enabled", True):
        return {}

    rsi_period = tech.get("rsi_period", 14)
    sma_periods = tech.get("sma_periods", [20, 50])
    macd_fast = tech.get("macd_fast", 12)
    macd_slow = tech.get("macd_slow", 26)
    macd_signal = tech.get("macd_signal", 9)
    timeframes = tech.get("timeframes", ["daily", "1h"])

    result: Dict[str, Any] = {"technical_enabled": True}

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # Daily
        hist_d = t.history(period="3mo", interval="1d")
        if hist_d is not None and len(hist_d) >= 50 and "Close" in hist_d.columns:
            close_d = hist_d["Close"].astype(float)
            price_now = float(close_d.iloc[-1]) if len(close_d) else None
            result["daily"] = _technical_for_series(
                close_d, price_now, rsi_period, sma_periods,
                macd_fast, macd_slow, macd_signal,
            )

        # 1h (yfinance often gives 1h for ~7d or less)
        if "1h" in timeframes:
            hist_1h = t.history(period="5d", interval="1h")
            if hist_1h is not None and len(hist_1h) >= 30 and "Close" in hist_1h.columns:
                close_1h = hist_1h["Close"].astype(float)
                price_now_1h = float(close_1h.iloc[-1]) if len(close_1h) else None
                result["1h"] = _technical_for_series(
                    close_1h, price_now_1h, rsi_period, [20],  # 1h: only SMA20
                    macd_fast, macd_slow, macd_signal,
                )
    except Exception:
        pass

    return result if result.get("daily") or result.get("1h") else {}
