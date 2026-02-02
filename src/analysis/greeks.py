"""
Greeks and probability helpers for option analysis.
Black-Scholes Probability of Profit (PoP), option pricing, and stress-test P/L.
"""

import math
from typing import Optional, List, Tuple

try:
    from scipy.stats import norm
except ImportError:
    norm = None


def probability_of_profit(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
    option_type: str = "call",
) -> Optional[float]:
    """
    Black-Scholes risk-neutral probability that option expires ITM (PoP).
    spot: current underlying price; strike: strike price; time_years: DTE/365.
    implied_vol: annualized (e.g. 0.25 for 25%). risk_free_rate: e.g. 0.05.
    Returns probability in [0, 1] or None if inputs invalid or scipy missing.
    """
    if norm is None or time_years <= 0 or implied_vol <= 0 or spot <= 0 or strike <= 0:
        return None
    try:
        d1 = (
            (__ln(spot / strike) + (risk_free_rate + 0.5 * implied_vol ** 2) * time_years)
            / (implied_vol * (time_years ** 0.5))
        )
        d2 = d1 - implied_vol * (time_years ** 0.5)
        if (option_type or "call").lower() == "put":
            return float(norm.cdf(-d2))
        return float(norm.cdf(d2))
    except Exception:
        return None


def __ln(x: float) -> float:
    return math.log(x)


def black_scholes_call_price(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
) -> float:
    """Black-Scholes call price. Returns intrinsic at expiry (T=0)."""
    if norm is None or spot <= 0 or strike <= 0 or implied_vol <= 0:
        return 0.0
    if time_years <= 0:
        return max(spot - strike, 0.0)
    try:
        d1 = (
            math.log(spot / strike)
            + (risk_free_rate + 0.5 * implied_vol ** 2) * time_years
        ) / (implied_vol * math.sqrt(time_years))
        d2 = d1 - implied_vol * math.sqrt(time_years)
        return spot * norm.cdf(d1) - strike * math.exp(-risk_free_rate * time_years) * norm.cdf(d2)
    except Exception:
        return max(spot - strike, 0.0)


def black_scholes_put_price(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
) -> float:
    """Black-Scholes put price. Returns intrinsic at expiry (T=0)."""
    if norm is None or spot <= 0 or strike <= 0 or implied_vol <= 0:
        return 0.0
    if time_years <= 0:
        return max(strike - spot, 0.0)
    try:
        d1 = (
            math.log(spot / strike)
            + (risk_free_rate + 0.5 * implied_vol ** 2) * time_years
        ) / (implied_vol * math.sqrt(time_years))
        d2 = d1 - implied_vol * math.sqrt(time_years)
        return strike * math.exp(-risk_free_rate * time_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    except Exception:
        return max(strike - spot, 0.0)


def estimate_pl(
    spot: float,
    strike: float,
    entry_premium: float,
    new_spot: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
    option_type: str,
    contracts: int = 1,
) -> float:
    """
    Estimate P/L for an instant move to new_spot (Black-Scholes reprice).
    Returns (new_premium - entry_premium) * contracts * 100.
    """
    opt = (option_type or "call").lower()
    if opt == "put":
        new_prem = black_scholes_put_price(
            new_spot, strike, time_years, risk_free_rate, implied_vol
        )
    else:
        new_prem = black_scholes_call_price(
            new_spot, strike, time_years, risk_free_rate, implied_vol
        )
    return (new_prem - entry_premium) * contracts * 100


def stress_test_scenarios(
    spot: float,
    strike: float,
    entry_premium: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
    option_type: str,
    contracts: int,
    risk_dollars: float,
    scenario_pct_changes: List[float],
) -> Optional[List[Tuple[float, float, float]]]:
    """
    For each scenario (underlying % change), return (pct_change, pl_dollars, pct_return_on_risk).
    risk_dollars: max loss from plan. Returns None if scipy unavailable (BS pricing requires norm).
    """
    if norm is None:
        return None
    if risk_dollars <= 0:
        risk_dollars = 1.0  # avoid div by zero
    results = []
    for pct in scenario_pct_changes:
        new_spot = spot * (1 + pct)
        pl = estimate_pl(
            spot, strike, entry_premium, new_spot,
            time_years, risk_free_rate, implied_vol,
            option_type, contracts,
        )
        pct_ror = (pl / risk_dollars) * 100 if risk_dollars else 0.0
        results.append((pct, pl, pct_ror))
    return results


def _bs_price_for_iv(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    implied_vol: float,
    option_type: str,
) -> float:
    """Black-Scholes price for a given IV; used by IV solver."""
    opt = (option_type or "call").lower()
    if opt == "put":
        return black_scholes_put_price(
            spot, strike, time_years, risk_free_rate, implied_vol
        )
    return black_scholes_call_price(
        spot, strike, time_years, risk_free_rate, implied_vol
    )


def solve_iv_black_scholes(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    option_type: str,
    market_price: float,
    sigma_low: float = 0.001,
    sigma_high: float = 5.0,
) -> Optional[float]:
    """
    Solve for implied volatility (sigma) such that Black-Scholes price equals market_price.
    Uses scipy.optimize.brentq. Returns annualized IV as decimal (e.g. 0.25 for 25%) or None.
    """
    if spot <= 0 or strike <= 0 or market_price <= 0 or time_years <= 0:
        return None
    opt = (option_type or "call").lower()
    if opt == "put":
        intrinsic = max(strike - spot, 0.0)
    else:
        intrinsic = max(spot - strike, 0.0)
    if market_price <= intrinsic:
        return None
    try:
        from scipy.optimize import brentq
    except ImportError:
        return None

    def objective(sigma: float) -> float:
        return _bs_price_for_iv(
            spot, strike, time_years, risk_free_rate, sigma, option_type
        ) - market_price

    try:
        sigma = brentq(objective, sigma_low, sigma_high, xtol=1e-6, maxiter=100)
        return round(float(sigma), 6)
    except (ValueError, ZeroDivisionError):
        return None


def days_to_years(days: Optional[int]) -> Optional[float]:
    """Convert DTE to time in years for Black-Scholes."""
    if days is None or days < 0:
        return None
    return days / 365.0


def theta_high_decay_risk(theta: Optional[float], threshold: float = -0.05) -> bool:
    """
    True if theta is more negative than threshold (e.g. theta < -0.05 => fast time decay).
    For long options, very negative theta means premium erodes quickly.
    """
    if theta is None:
        return False
    return theta < threshold


def vega_high_risk(vega: Optional[float], threshold: float = 0.20) -> bool:
    """True if vega above threshold (sensitive to IV changes)."""
    if vega is None:
        return False
    return vega > threshold
