"""
Technical Analysis Module
Add support/resistance levels, ATR-based targets, and technical confluence to trade analysis.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


def get_support_resistance_levels(
    ticker: str,
    current_price: float,
    period: int = 20,
) -> Dict[str, Any]:
    """
    Calculate support and resistance levels using:
    - Recent highs/lows
    - Moving averages (20, 50, 200)
    - Round numbers (psychological levels)
    - Volume profile (if available)
    
    Returns dict with support_levels, resistance_levels, key_levels.
    """
    # Placeholder - would integrate with market_data/technical.py
    # For now, return basic psychological levels and percentage-based S/R
    
    supports = []
    resistances = []
    key_levels = []
    
    if current_price is None:
        return {"support_levels": [], "resistance_levels": [], "key_levels": []}
    
    # Psychological levels (round numbers)
    round_level = round(current_price / 5) * 5
    for i in range(1, 4):
        supports.append(round_level - i * 5)
        resistances.append(round_level + i * 5)
    
    # Percentage-based S/R (1%, 2%, 3%, 5%)
    for pct in [0.01, 0.02, 0.03, 0.05]:
        supports.append(round(current_price * (1 - pct) / 1) * 1)
        resistances.append(round(current_price * (1 + pct) / 1) * 1)
    
    # Sort and deduplicate
    supports = sorted(list(set([round(s, 2) for s in supports if s < current_price])), reverse=True)
    resistances = sorted(list(set([round(r, 2) for r in resistances if r > current_price])))
    
    # Key levels (closest S and R)
    key_levels = {
        "nearest_support": supports[0] if supports else current_price * 0.95,
        "nearest_resistance": resistances[0] if resistances else current_price * 1.05,
    }
    
    return {
        "support_levels": supports[:5],
        "resistance_levels": resistances[:5],
        "key_levels": key_levels,
        "method": "psychological_pct",
    }


def calculate_target_from_resistance(
    trade: Any,
    current_price: float,
    resistance_levels: List[float],
    option_type: str = "CALL",
) -> Optional[float]:
    """
    Calculate a realistic target price based on resistance levels.
    For calls: target at first resistance above strike
    For puts: target at first support below strike
    """
    if not resistance_levels:
        return None
    
    strike = getattr(trade, "strike", current_price)
    
    if option_type.upper() == "CALL":
        # For calls, find first resistance above current price
        for level in resistance_levels:
            if level > current_price:
                return level
        return resistance_levels[0] if resistance_levels else None
    else:
        # For puts, this function is for upside targets on puts (which is unusual)
        return None


def calculate_put_target_from_support(
    trade: Any,
    current_price: float,
    support_levels: List[float],
) -> Optional[float]:
    """
    Calculate a realistic target for put options based on support levels.
    Target = support level that would make the option profitable.
    """
    if not support_levels:
        return None
    
    strike = getattr(trade, "strike", current_price)
    
    # For puts, find support below strike (targets when underlying drops)
    for level in support_levels:
        if level < strike:
            return level
    return support_levels[-1] if support_levels else None


def estimate_option_price_at_underlying(
    spot_now: float,
    strike: float,
    time_to_expiry_years: float,
    iv_decimal: float,
    option_type: str = "CALL",
    spot_at_target: float = None,
) -> Optional[float]:
    """
    Estimate option price if underlying moves to spot_at_target.
    Uses Black-Scholes approximation for more realistic pricing.
    """
    import math
    
    if spot_at_target is None:
        return None
    
    # Black-Scholes components
    # d1 = [ln(S/K) + (r + sigma^2/2)*t] / (sigma * sqrt(t))
    # d2 = d1 - sigma * sqrt(t)
    # Call = S * N(d1) - K * e^(-rt) * N(d2)
    # Put = K * e^(-rt) * N(-d2) - S * N(-d1)
    
    r = 0.05  # risk-free rate
    sigma = iv_decimal
    t = max(time_to_expiry_years, 0.001)  # avoid division by zero
    
    S = spot_at_target
    K = strike
    
    # Calculate d1 and d2
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
    except (ValueError, ZeroDivisionError):
        # Fallback to intrinsic value
        return max(0, S - K) if option_type.upper() == "CALL" else max(0, K - S)
    
    # Standard normal CDF approximation
    def ncdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    # Calculate option price
    if option_type.upper() == "CALL":
        price = S * ncdf(d1) - K * math.exp(-r * t) * ncdf(d2)
    else:
        price = K * math.exp(-r * t) * ncdf(-d2) - S * ncdf(-d1)
    
    return round(max(0.001, price), 2)


def get_technical_target_recommendation(
    trade: Any,
    current_price: float,
    entry_premium: float,
    stop_premium: float,
    support_levels: List[float],
    resistance_levels: List[float],
    option_type: str = "CALL",
    days_to_expiration: int = 0,
    iv_percent: float = 0.30,
) -> Dict[str, Any]:
    """
    Generate technically-grounded target recommendations.
    
    Returns dict with:
    - conservative_target (price, premium, r_multiple)
    - moderate_target (price, premium, r_multiple)  
    - aggressive_target (price, premium, r_multiple)
    - reasoning (str)
    """
    
    risk = entry_premium - stop_premium
    
    # Calculate underlying price at each resistance/support
    strike = getattr(trade, "strike", current_price)
    
    if option_type.upper() == "CALL":
        # For calls: targets when underlying goes UP
        targets = []
        for res in resistance_levels:
            if res > current_price:
                # Estimate option price at this level
                time_years = days_to_expiration / 365 if days_to_expiration > 0 else 1/365
                est_premium = estimate_option_price_at_underlying(
                    current_price, strike, time_years, iv_percent, "CALL", res
                )
                if est_premium and est_premium > entry_premium:
                    r_mult = (est_premium - entry_premium) / risk if risk > 0 else 0
                    targets.append({
                        "level": res,
                        "premium": est_premium,
                        "r_multiple": round(r_mult, 1) if r_mult > 0 else 0,
                        "type": "resistance",
                    })
        
        # Also consider strike itself as a target
        if strike > current_price:
            time_years = days_to_expiration / 365 if days_to_expiration > 0 else 1/365
            est_premium = estimate_option_price_at_underlying(
                current_price, strike, time_years, iv_percent, "CALL", strike
            )
            if est_premium and est_premium > entry_premium:
                r_mult = (est_premium - entry_premium) / risk if risk > 0 else 0
                targets.append({
                    "level": strike,
                    "premium": est_premium,
                    "r_multiple": round(r_mult, 1) if r_mult > 0 else 0,
                    "type": "strike",
                })
    
    else:
        # For puts: targets when underlying goes DOWN
        targets = []
        for sup in support_levels:
            if sup < current_price:
                time_years = days_to_expiration / 365 if days_to_expiration > 0 else 1/365
                est_premium = estimate_option_price_at_underlying(
                    current_price, strike, time_years, iv_percent, "PUT", sup
                )
                if est_premium and est_premium > entry_premium:
                    r_mult = (est_premium - entry_premium) / risk if risk > 0 else 0
                    targets.append({
                        "level": sup,
                        "premium": est_premium,
                        "r_multiple": round(r_mult, 1) if r_mult > 0 else 0,
                        "type": "support",
                    })
    
    # Sort by R multiple (ascending for conservative first)
    targets = sorted(targets, key=lambda x: x["r_multiple"])
    
    # Default R-based targets as fallback
    default_t1_r = 1.5 if days_to_expiration == 0 else 2.0
    default_risk_reward = entry_premium * default_t1_r
    
    result = {
        "conservative_target": None,
        "moderate_target": None,
        "aggressive_target": None,
        "reasoning": "",
    }
    
    if targets:
        # Use technically-grounded targets
        if len(targets) >= 1:
            result["conservative_target"] = targets[0]
        if len(targets) >= 2:
            result["moderate_target"] = targets[1]
        if len(targets) >= 3:
            result["aggressive_target"] = targets[2]
        
        # Generate reasoning
        levels_text = ", ".join([f"${t['level']:.0f}" for t in targets[:3]])
        result["reasoning"] = (
            f"Technical targets based on {levels_text}. "
            f"Conservative: {targets[0]['r_multiple']}R ({'$' if 'premium' in targets[0] else ''}{targets[0].get('premium', 'N/A')})"
        )
    else:
        # Fallback to R-based
        result["conservative_target"] = {
            "level": current_price * 1.02,
            "premium": round(entry_premium * default_t1_r, 2),
            "r_multiple": default_t1_r,
            "type": "r_multiple",
        }
        result["moderate_target"] = {
            "level": current_price * 1.03,
            "premium": round(entry_premium * 2.0, 2),
            "r_multiple": 2.0,
            "type": "r_multiple",
        }
        result["reasoning"] = f"Fallback to R-based targets (1.5R-2.0R)"
    
    return result


def calculate_achievable_r_multiple(
    current_price: float,
    strike: float,
    resistance_levels: List[float],
    option_type: str = "CALL",
    iv_percent: float = 0.30,
    days_to_expiration: int = 5,
) -> Dict[str, Any]:
    """
    Calculate achievable R multiples based on technical levels.
    
    Returns analysis of what's realistic vs aspirational.
    """
    
    distance_to_strike = abs(strike - current_price) / current_price
    distance_to_first_res = 0
    
    if option_type.upper() == "CALL":
        for res in resistance_levels:
            if res > current_price:
                distance_to_first_res = (res - current_price) / current_price
                break
    else:
        for res in resistance_levels:
            if res < current_price:
                distance_to_first_res = (current_price - res) / current_price
                break
    
    # Achievability assessment
    achievable_r = 1.0 if distance_to_first_res < 0.02 else 1.5
    moderate_r = 2.0 if distance_to_first_res < 0.03 else 2.5
    
    return {
        "distance_to_strike_pct": round(distance_to_strike * 100, 1),
        "distance_to_first_level_pct": round(distance_to_first_res * 100, 1),
        "achievable_r": achievable_r,
        "moderate_r": moderate_r,
        "recommendation": (
            f"{distance_to_first_res*100:.1f}% move to first level. "
            f"Achievable R: {achievable_r}x. Moderate R: {moderate_r}x."
        ),
    }
