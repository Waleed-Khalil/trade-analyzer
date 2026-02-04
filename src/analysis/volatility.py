"""
Volatility helpers: IV Rank (when historical IV available), realized vol from underlying.
Historical IV: recomputed from Massive option aggs + Yahoo underlying via Black-Scholes inverse.
Realized vol from Yahoo daily closes as context (IV vs realized).
"""

from datetime import datetime, timedelta
from typing import Optional, List, Any


def get_iv_rank(
    current_iv: float,
    historical_ivs: List[float],
) -> Optional[float]:
    """
    IV Rank = (current_IV - min_IV) / (max_IV - min_IV) * 100.
    Returns 0-100 or None if historical_ivs empty or max_IV == min_IV.
    """
    if not historical_ivs:
        return None
    min_iv = min(historical_ivs)
    max_iv = max(historical_ivs)
    if max_iv <= min_iv:
        return 50.0  # flat history
    rank = (current_iv - min_iv) / (max_iv - min_iv) * 100.0
    return max(0.0, min(100.0, rank))


def get_historical_ivs_polygon(
    trade: Any,
    option_ticker: str,
    lookback_days: int = 252,
    risk_free_rate: float = 0.05,
    max_days: Optional[int] = 126,
    min_historical_samples: int = 30,
    sigma_low: float = 0.001,
    sigma_high: float = 5.0,
) -> List[float]:
    """
    Recompute historical IV from Massive option daily bars + Yahoo underlying closes.
    For each date with option close and underlying close, solve Black-Scholes for sigma.
    Returns list of annualized IVs (decimals). Empty list on failure or if valid IVs < min_historical_samples.
    max_days: cap lookback to limit API/compute (e.g. 126 for ~6 months).
    sigma_low/sigma_high: brentq solver bounds for IV (tune if extreme contracts fail).
    """
    expiration = getattr(trade, "expiration", None)
    if not expiration or not isinstance(expiration, str):
        return []
    try:
        exp_dt = datetime.strptime(expiration, "%Y-%m-%d").date()
    except ValueError:
        return []
    today = datetime.utcnow().date()
    to_date = min(today, exp_dt - timedelta(days=1))
    days_back = min(lookback_days, max_days or lookback_days)
    from_dt = to_date - timedelta(days=days_back)
    from_date = from_dt.strftime("%Y-%m-%d")
    to_date_str = to_date.strftime("%Y-%m-%d")

    try:
        from market_data.polygon_client import get_option_historical_aggs
    except ImportError:
        return []

    option_bars = get_option_historical_aggs(option_ticker, from_date, to_date_str)
    if not option_bars:
        return []

    ticker = getattr(trade, "ticker", "")
    if not ticker:
        return []
    try:
        import yfinance as yf
        yf_t = yf.Ticker(ticker)
        hist = yf_t.history(period=f"{days_back + 30}d", interval="1d")
        if hist is None or len(hist) < 2 or "Close" not in hist.columns:
            return []
        # Date string from index (handles timezone-aware indices)
        hist = hist.copy()
        if hasattr(hist.index, "date"):
            hist["date_str"] = [d.isoformat() for d in hist.index.date]
        else:
            hist["date_str"] = hist.index.strftime("%Y-%m-%d")
        spot_by_date = hist.set_index("date_str")["Close"].astype(float).to_dict()
    except Exception:
        return []

    from analysis.greeks import solve_iv_black_scholes

    strike = float(getattr(trade, "strike", 0))
    option_type = (getattr(trade, "option_type", "CALL") or "CALL").strip().lower()
    if option_type not in ("call", "put"):
        option_type = "call"

    ivs = []
    for bar in option_bars:
        date_str = bar.get("date")
        option_close = bar.get("close")
        if not date_str or option_close is None or option_close <= 0:
            continue
        spot = spot_by_date.get(date_str)
        if spot is None or spot <= 0:
            continue
        try:
            bar_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            t_days = (exp_dt - bar_dt).days
        except (ValueError, TypeError):
            continue
        if t_days <= 0:
            continue
        time_years = t_days / 365.0
        iv = solve_iv_black_scholes(
            spot=float(spot),
            strike=strike,
            time_years=time_years,
            risk_free_rate=risk_free_rate,
            option_type=option_type,
            market_price=float(option_close),
            sigma_low=sigma_low,
            sigma_high=sigma_high,
        )
        if iv is not None and iv > 0:
            ivs.append(iv)
    if len(ivs) < min_historical_samples:
        return []
    return ivs


def compute_hv_rank(
    ticker: str,
    current_hv_decimal: float,
    period: int = 252,
    rolling_window: int = 21,
) -> Optional[float]:
    """
    52-week realized-volatility rank as a proxy for IV rank when historical option IV is unavailable.
    Uses rolling_window-day annualized realized vol over the last period trading days; rank is
    (current - min) / (max - min) * 100. current_hv_decimal should be in same units as your 30d
    realized vol (e.g. 0.14 for 14%). Returns 0-100 or None on failure.
    """
    try:
        import yfinance as yf
        import numpy as np
        hist = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
        if hist is None or len(hist) < rolling_window or "Close" not in hist.columns:
            return None
        close = hist["Close"].dropna()
        if len(close) < period:
            return None
        log_ret = np.log(close / close.shift(1)).dropna()
        if len(log_ret) < period:
            return None
        # Rolling annualized vol (decimal)
        rolling_std = log_ret.rolling(rolling_window).std()
        rolling_hv = (rolling_std * np.sqrt(252)).dropna().tail(period)
        if len(rolling_hv) < 2:
            return None
        low_hv = float(rolling_hv.min().item() if hasattr(rolling_hv.min(), "item") else rolling_hv.min())
        high_hv = float(rolling_hv.max().item() if hasattr(rolling_hv.max(), "item") else rolling_hv.max())
        if high_hv <= low_hv:
            return 50.0
        current = float(current_hv_decimal) if current_hv_decimal <= 2 else current_hv_decimal / 100.0
        rank = (current - low_hv) / (high_hv - low_hv) * 100.0
        return round(max(0.0, min(100.0, rank)), 1)
    except Exception:
        return None


def get_realized_volatility(
    ticker: str,
    window_days: int = 30,
    days_back: int = 252,
) -> Optional[float]:
    """
    Annualized realized volatility from Yahoo daily closes (log returns, then std * sqrt(252)).
    Returns decimal (e.g. 0.20 for 20%) or None if insufficient data.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{days_back}d", interval="1d")
        if hist is None or len(hist) < window_days or "Close" not in hist.columns:
            return None
        close = hist["Close"].dropna()
        if len(close) < window_days:
            return None
        log_ret = close.pct_change().dropna()
        if len(log_ret) < window_days:
            return None
        # Use last window_days for realized vol
        recent = log_ret.iloc[-window_days:]
        import math
        std_daily = recent.std()
        if std_daily is None or std_daily <= 0 or math.isnan(std_daily):
            return None
        annual = float(std_daily * (252 ** 0.5))
        return round(annual, 4)
    except Exception:
        return None
