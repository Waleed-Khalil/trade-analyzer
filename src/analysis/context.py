"""
Context helpers: strike moneyness (ITM/OTM %), time to market close (0DTE), etc.
"""

from typing import Any, Dict, Optional
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


def get_strike_context(trade: Any, current_price: Optional[float]) -> Dict[str, Any]:
    """
    Compute strike context: moneyness, % ITM/OTM.
    Returns dict with: itm_otm_pct, moneyness_label (e.g. "22.9% ITM call").
    """
    ctx: Dict[str, Any] = {}
    if current_price is None or not getattr(trade, "strike", None):
        return ctx
    strike = float(trade.strike)
    opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
    if opt_type == "CALL":
        # Call: strike < spot = ITM (positive intrinsic)
        pct = (current_price - strike) / current_price * 100 if current_price else 0
        if pct >= 0:
            ctx["moneyness_label"] = f"{abs(pct):.1f}% ITM call"
        else:
            ctx["moneyness_label"] = f"{abs(pct):.1f}% OTM call"
        ctx["itm_otm_pct"] = round(pct, 1)
    else:
        # Put: strike > spot = ITM
        pct = (strike - current_price) / current_price * 100 if current_price else 0
        if pct >= 0:
            ctx["moneyness_label"] = f"{abs(pct):.1f}% ITM put"
        else:
            ctx["moneyness_label"] = f"{abs(pct):.1f}% OTM put"
        ctx["itm_otm_pct"] = round(pct, 1)
    return ctx


def get_time_to_close_et_minutes() -> Optional[int]:
    """
    Minutes until US regular market close (4:00 PM ET).
    Returns None if zoneinfo unavailable.
    """
    if ZoneInfo is None:
        return None
    try:
        et = ZoneInfo("America/New_York")
        now = datetime.now(et).time()
        from datetime import time
        close = time(16, 0)
        now_minutes = now.hour * 60 + now.minute
        close_minutes = close.hour * 60 + close.minute
        if now_minutes <= close_minutes:
            return close_minutes - now_minutes
        return 0  # after close
    except Exception:
        return None


def pasted_vs_live_premium_diff_pct(pasted: float, live: Optional[float]) -> Optional[float]:
    """Return % difference (live - pasted) / pasted * 100. None if no live or pasted is 0."""
    if live is None or pasted is None or pasted == 0:
        return None
    return round((live - pasted) / pasted * 100, 1)
