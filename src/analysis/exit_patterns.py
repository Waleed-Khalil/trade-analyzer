"""
Exit Pattern Detection
Identifies reversal patterns that signal optimal exit points
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np


def detect_exit_patterns(
    df: pd.DataFrame,
    option_type: str,
    current_profit_pct: float = 0.0,
    require_volume_confirmation: bool = True
) -> List[Dict[str, Any]]:
    """
    Detect reversal patterns that suggest exiting the position.

    Args:
        df: OHLC DataFrame
        option_type: 'CALL' or 'PUT'
        current_profit_pct: Current profit percentage (0.20 = 20%)
        require_volume_confirmation: Require volume spike for confirmation

    Returns:
        List of detected exit patterns with strength and recommendations
    """
    if df is None or len(df) < 5:
        return []

    exit_patterns = []

    # Only trigger exit patterns if in profit >20%
    if current_profit_pct < 0.20:
        return exit_patterns

    # Get recent bars
    recent = df.tail(5)

    # For CALLS: Look for bearish reversal patterns
    if option_type == 'CALL':
        # Bearish engulfing
        bearish_engulfing = _detect_bearish_engulfing(recent)
        if bearish_engulfing:
            exit_patterns.append(bearish_engulfing)

        # Evening star
        evening_star = _detect_evening_star(recent)
        if evening_star:
            exit_patterns.append(evening_star)

        # Shooting star
        shooting_star = _detect_shooting_star(recent)
        if shooting_star:
            exit_patterns.append(shooting_star)

        # Bearish three black crows
        three_black_crows = _detect_three_black_crows(recent)
        if three_black_crows:
            exit_patterns.append(three_black_crows)

    # For PUTS: Look for bullish reversal patterns
    else:
        # Bullish engulfing
        bullish_engulfing = _detect_bullish_engulfing(recent)
        if bullish_engulfing:
            exit_patterns.append(bullish_engulfing)

        # Morning star
        morning_star = _detect_morning_star(recent)
        if morning_star:
            exit_patterns.append(morning_star)

        # Hammer
        hammer = _detect_hammer(recent)
        if hammer:
            exit_patterns.append(hammer)

        # Bullish three white soldiers
        three_white_soldiers = _detect_three_white_soldiers(recent)
        if three_white_soldiers:
            exit_patterns.append(three_white_soldiers)

    # Add volume confirmation check
    if require_volume_confirmation and exit_patterns:
        exit_patterns = _check_volume_confirmation(df, exit_patterns)

    return exit_patterns


def _detect_bearish_engulfing(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect bearish engulfing pattern."""
    if len(df) < 2:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_body = abs(prev['close'] - prev['open'])
    curr_body = abs(curr['close'] - curr['open'])

    # Prev bullish, current bearish
    if prev['close'] > prev['open'] and curr['close'] < curr['open']:
        # Current body engulfs previous
        if curr['open'] >= prev['close'] and curr['close'] <= prev['open']:
            if curr_body > prev_body * 1.2:
                return {
                    'pattern': 'bearish_engulfing',
                    'strength': 85,
                    'type': 'exit',
                    'recommendation': 'Take profit - strong bearish reversal',
                    'urgency': 'high',
                    'confirmed': False  # Need volume check
                }
    return None


def _detect_evening_star(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect evening star pattern (3-bar bearish reversal)."""
    if len(df) < 3:
        return None

    first = df.iloc[-3]
    second = df.iloc[-2]
    third = df.iloc[-1]

    first_body = abs(first['close'] - first['open'])
    second_body = abs(second['close'] - second['open'])
    third_body = abs(third['close'] - third['open'])

    # First: Strong bullish
    if first['close'] <= first['open']:
        return None

    # Second: Small body (indecision)
    if second_body > first_body * 0.3:
        return None

    # Third: Strong bearish
    if third['close'] >= third['open']:
        return None

    if third_body < first_body * 0.6:
        return None

    # Third closes into first's body
    if third['close'] < (first['open'] + first['close']) / 2:
        return {
            'pattern': 'evening_star',
            'strength': 90,
            'type': 'exit',
            'recommendation': 'Take profit - trend reversal signal',
            'urgency': 'high',
            'confirmed': False
        }

    return None


def _detect_shooting_star(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect shooting star (long upper shadow after uptrend)."""
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    body = abs(curr['close'] - curr['open'])
    upper_shadow = curr['high'] - max(curr['open'], curr['close'])
    lower_shadow = min(curr['open'], curr['close']) - curr['low']

    # Long upper shadow, small body, small lower shadow
    if upper_shadow > body * 2 and lower_shadow < body * 0.3:
        # After uptrend
        prev = df.iloc[-2]
        if prev['close'] > prev['open']:
            return {
                'pattern': 'shooting_star',
                'strength': 75,
                'type': 'exit',
                'recommendation': 'Consider profit taking - rejection at highs',
                'urgency': 'medium',
                'confirmed': False
            }

    return None


def _detect_three_black_crows(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect three black crows (3 consecutive bearish bars)."""
    if len(df) < 3:
        return None

    bars = df.tail(3)

    # All bearish
    if not all(bar['close'] < bar['open'] for _, bar in bars.iterrows()):
        return None

    # Each closes lower than previous
    closes = bars['close'].values
    if not all(closes[i] < closes[i-1] for i in range(1, len(closes))):
        return None

    # Each opens within previous body
    for i in range(1, 3):
        curr = bars.iloc[i]
        prev = bars.iloc[i-1]
        if curr['open'] > prev['open'] or curr['open'] < prev['close']:
            return None

    return {
        'pattern': 'three_black_crows',
        'strength': 85,
        'type': 'exit',
        'recommendation': 'Exit now - strong bearish momentum',
        'urgency': 'high',
        'confirmed': False
    }


def _detect_bullish_engulfing(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect bullish engulfing pattern."""
    if len(df) < 2:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_body = abs(prev['close'] - prev['open'])
    curr_body = abs(curr['close'] - curr['open'])

    # Prev bearish, current bullish
    if prev['close'] < prev['open'] and curr['close'] > curr['open']:
        # Current body engulfs previous
        if curr['open'] <= prev['close'] and curr['close'] >= prev['open']:
            if curr_body > prev_body * 1.2:
                return {
                    'pattern': 'bullish_engulfing',
                    'strength': 85,
                    'type': 'exit',
                    'recommendation': 'Exit PUT - strong bullish reversal',
                    'urgency': 'high',
                    'confirmed': False
                }
    return None


def _detect_morning_star(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect morning star pattern (3-bar bullish reversal)."""
    if len(df) < 3:
        return None

    first = df.iloc[-3]
    second = df.iloc[-2]
    third = df.iloc[-1]

    first_body = abs(first['close'] - first['open'])
    second_body = abs(second['close'] - second['open'])
    third_body = abs(third['close'] - third['open'])

    # First: Strong bearish
    if first['close'] >= first['open']:
        return None

    # Second: Small body (indecision)
    if second_body > first_body * 0.3:
        return None

    # Third: Strong bullish
    if third['close'] <= third['open']:
        return None

    if third_body < first_body * 0.6:
        return None

    # Third closes into first's body
    if third['close'] > (first['open'] + first['close']) / 2:
        return {
            'pattern': 'morning_star',
            'strength': 90,
            'type': 'exit',
            'recommendation': 'Exit PUT - trend reversal signal',
            'urgency': 'high',
            'confirmed': False
        }

    return None


def _detect_hammer(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect hammer (long lower shadow after downtrend)."""
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    body = abs(curr['close'] - curr['open'])
    upper_shadow = curr['high'] - max(curr['open'], curr['close'])
    lower_shadow = min(curr['open'], curr['close']) - curr['low']

    # Long lower shadow, small body, small upper shadow
    if lower_shadow > body * 2 and upper_shadow < body * 0.3:
        # After downtrend
        prev = df.iloc[-2]
        if prev['close'] < prev['open']:
            return {
                'pattern': 'hammer',
                'strength': 75,
                'type': 'exit',
                'recommendation': 'Exit PUT - support found',
                'urgency': 'medium',
                'confirmed': False
            }

    return None


def _detect_three_white_soldiers(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Detect three white soldiers (3 consecutive bullish bars)."""
    if len(df) < 3:
        return None

    bars = df.tail(3)

    # All bullish
    if not all(bar['close'] > bar['open'] for _, bar in bars.iterrows()):
        return None

    # Each closes higher than previous
    closes = bars['close'].values
    if not all(closes[i] > closes[i-1] for i in range(1, len(closes))):
        return None

    # Each opens within previous body
    for i in range(1, 3):
        curr = bars.iloc[i]
        prev = bars.iloc[i-1]
        if curr['open'] < prev['open'] or curr['open'] > prev['close']:
            return None

    return {
        'pattern': 'three_white_soldiers',
        'strength': 85,
        'type': 'exit',
        'recommendation': 'Exit PUT - strong bullish momentum',
        'urgency': 'high',
        'confirmed': False
    }


def _check_volume_confirmation(
    df: pd.DataFrame,
    patterns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Check if patterns have volume confirmation."""
    if len(df) < 20:
        return patterns

    avg_volume = df['volume'].tail(20).mean()
    current_volume = df['volume'].iloc[-1]

    # Volume spike = >1.5x average
    has_volume_spike = current_volume > avg_volume * 1.5

    for pattern in patterns:
        pattern['confirmed'] = has_volume_spike
        if has_volume_spike:
            pattern['strength'] = min(100, pattern['strength'] + 10)
            pattern['volume_confirmation'] = f"Volume spike: {current_volume/avg_volume:.1f}x average"
        else:
            pattern['strength'] = max(50, pattern['strength'] - 15)
            pattern['volume_confirmation'] = "No volume spike - lower confidence"

    return patterns


# ============================================================================
# PHASE A: BREAKOUT DETECTION - Resistance Level Breakouts
# ============================================================================

def detect_resistance_breakout(
    df: pd.DataFrame,
    current_price: float,
    resistance_level: float,
    resistance_strength: int,
    volume_threshold_multiplier: float = 1.5,
    breakout_confirmation_pct: float = 0.005
) -> Dict[str, Any]:
    """
    Detect breakout above resistance with volume confirmation.

    When price breaks resistance convincingly:
    - Hold runner for next level
    - Trail stop to broken resistance (now support)
    - Set new runner target

    Args:
        df: Recent OHLC data (min 20 bars for volume calc)
        current_price: Current underlying price
        resistance_level: Resistance price to check
        resistance_strength: Strength score (0-100) from price_action
        volume_threshold_multiplier: Volume must be >Nx average
        breakout_confirmation_pct: Price must be >X% above level (0.005 = 0.5%)

    Returns:
        Dict with action, new_stop, new_target, reasoning
    """
    if len(df) < 20:
        return {'action': 'insufficient_data', 'reason': 'Need at least 20 bars for analysis'}

    # Check if price is above resistance
    breakout_threshold = resistance_level * (1 + breakout_confirmation_pct)
    if current_price < breakout_threshold:
        return {
            'action': 'no_breakout',
            'reason': f'Price ${current_price:.2f} not above ${breakout_threshold:.2f}'
        }

    # Check volume confirmation
    avg_volume = df['volume'].tail(20).mean()
    current_volume = df['volume'].iloc[-1]
    volume_confirmed = current_volume > avg_volume * volume_threshold_multiplier

    if not volume_confirmed:
        return {
            'action': 'breakout_unconfirmed',
            'reason': f'Breakout without volume (current: {current_volume:.0f}, need: {avg_volume * volume_threshold_multiplier:.0f})',
            'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0
        }

    # Check for clean breakout (not just a spike wick)
    last_bar = df.iloc[-1]
    close_above_level = last_bar['close'] > resistance_level

    if not close_above_level:
        return {
            'action': 'false_breakout',
            'reason': f'Wick above ${resistance_level:.2f} but close below - likely rejection'
        }

    # CONFIRMED BREAKOUT
    # Set new stop slightly below broken resistance
    new_stop = resistance_level * 0.995  # 0.5% buffer below

    return {
        'action': 'breakout_confirmed',
        'new_stop': new_stop,
        'reason': f'Broke ${resistance_level:.2f} (strength: {resistance_strength}) on {current_volume/avg_volume:.1f}x volume',
        'volume_ratio': current_volume / avg_volume,
        'resistance_strength': resistance_strength,
        'recommendation': 'Hold runner - trail stop to broken level (now support)',
        'urgency': 'high' if resistance_strength >= 75 else 'medium'
    }


def get_next_resistance_level(
    resistance_zones: List[Dict[str, Any]],
    current_level: float,
    current_price: float
) -> Optional[float]:
    """
    Find next resistance level above current broken level.

    Args:
        resistance_zones: List of resistance zone dicts from price_action
        current_level: Just-broken resistance level
        current_price: Current underlying price

    Returns:
        Next resistance price or None
    """
    if not resistance_zones:
        return None

    # Filter to levels above current level and price
    higher_levels = [
        z for z in resistance_zones
        if z['price'] > max(current_level, current_price)
    ]

    if not higher_levels:
        return None

    # Return closest level above
    return min(higher_levels, key=lambda z: z['price'])['price']


# ============================================================================
# PHASE B: REJECTION DETECTION - Resistance Rejection Patterns
# ============================================================================

def detect_resistance_rejection(
    df: pd.DataFrame,
    resistance_level: float,
    option_type: str = 'CALL',
    proximity_pct: float = 0.005,
    wick_ratio_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Detect bearish rejection patterns at resistance (for CALLs).

    Common rejection patterns:
    - Shooting star: Small body, long upper wick, close near low
    - Bearish engulfing at level
    - Long upper wick (>70% of candle range)

    When detected at resistance → EXIT MORE CONTRACTS

    Args:
        df: Recent OHLC data (min 3 bars)
        resistance_level: Resistance price to check
        option_type: 'CALL' or 'PUT'
        proximity_pct: How close to level counts as "at resistance" (0.005 = 0.5%)
        wick_ratio_threshold: Upper wick must be >X% of total range (0.7 = 70%)

    Returns:
        Dict with action, exit_pct, reasoning
    """
    if len(df) < 3:
        return {'action': 'insufficient_data', 'reason': 'Need at least 3 bars'}

    last_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]

    # Check if price is near resistance
    high = last_bar['high']
    distance = abs(high - resistance_level) / resistance_level

    if distance > proximity_pct:
        return {
            'action': 'not_at_level',
            'reason': f'High ${high:.2f} not near resistance ${resistance_level:.2f}'
        }

    # Pattern detection (for CALLs - bearish rejection)
    if option_type == 'CALL':
        rejection = _detect_bearish_rejection_at_level(
            last_bar, prev_bar, resistance_level, wick_ratio_threshold
        )
    else:
        # For PUTs - look for bullish rejection at support
        rejection = _detect_bullish_rejection_at_level(
            last_bar, prev_bar, resistance_level, wick_ratio_threshold
        )

    if rejection:
        # Increase exit percentage based on rejection strength
        if rejection['pattern'] == 'bearish_engulfing':
            exit_pct = 0.75  # Strong rejection - exit 75%
        elif rejection['pattern'] == 'shooting_star':
            exit_pct = 0.60  # Medium rejection - exit 60%
        elif rejection['pattern'] == 'long_wick':
            exit_pct = 0.50  # Weak rejection - exit 50%
        else:
            exit_pct = 0.50

        return {
            'action': 'rejection_detected',
            'exit_pct': exit_pct,
            'pattern': rejection['pattern'],
            'strength': rejection['strength'],
            'reason': f"{rejection['pattern']} at ${resistance_level:.2f} - take increased profit",
            'recommendation': f'Exit {exit_pct:.0%} of position - resistance holding',
            'urgency': 'high'
        }

    return {'action': 'no_rejection', 'reason': 'No rejection pattern detected'}


def _detect_bearish_rejection_at_level(
    current_bar: pd.Series,
    previous_bar: pd.Series,
    level: float,
    wick_threshold: float
) -> Optional[Dict[str, Any]]:
    """Helper: Detect bearish rejection patterns."""
    body = abs(current_bar['close'] - current_bar['open'])
    total_range = current_bar['high'] - current_bar['low']
    upper_wick = current_bar['high'] - max(current_bar['open'], current_bar['close'])
    lower_wick = min(current_bar['open'], current_bar['close']) - current_bar['low']

    # Shooting star pattern
    if upper_wick > body * 2 and lower_wick < body * 0.3:
        if current_bar['close'] < current_bar['open']:  # Bearish close
            return {
                'pattern': 'shooting_star',
                'strength': 75,
                'description': 'Shooting star - strong rejection'
            }

    # Bearish engulfing at level
    if (previous_bar['close'] > previous_bar['open'] and  # Prev bullish
        current_bar['close'] < current_bar['open'] and    # Curr bearish
        current_bar['open'] >= previous_bar['close'] and  # Opens above prev close
        current_bar['close'] <= previous_bar['open']):    # Closes below prev open
        return {
            'pattern': 'bearish_engulfing',
            'strength': 90,
            'description': 'Bearish engulfing - very strong rejection'
        }

    # Long upper wick (rejection wick)
    if total_range > 0 and upper_wick / total_range > wick_threshold:
        if current_bar['close'] < current_bar['open']:  # Bearish close
            return {
                'pattern': 'long_wick',
                'strength': 65,
                'description': f'Long upper wick ({upper_wick/total_range:.0%}) - moderate rejection'
            }

    return None


def _detect_bullish_rejection_at_level(
    current_bar: pd.Series,
    previous_bar: pd.Series,
    level: float,
    wick_threshold: float
) -> Optional[Dict[str, Any]]:
    """Helper: Detect bullish rejection patterns (for PUTs at support)."""
    body = abs(current_bar['close'] - current_bar['open'])
    total_range = current_bar['high'] - current_bar['low']
    upper_wick = current_bar['high'] - max(current_bar['open'], current_bar['close'])
    lower_wick = min(current_bar['open'], current_bar['close']) - current_bar['low']

    # Hammer pattern
    if lower_wick > body * 2 and upper_wick < body * 0.3:
        if current_bar['close'] > current_bar['open']:  # Bullish close
            return {
                'pattern': 'hammer',
                'strength': 75,
                'description': 'Hammer - strong bullish rejection'
            }

    # Bullish engulfing at level
    if (previous_bar['close'] < previous_bar['open'] and  # Prev bearish
        current_bar['close'] > current_bar['open'] and    # Curr bullish
        current_bar['open'] <= previous_bar['close'] and  # Opens below prev close
        current_bar['close'] >= previous_bar['open']):    # Closes above prev open
        return {
            'pattern': 'bullish_engulfing',
            'strength': 90,
            'description': 'Bullish engulfing - very strong rejection'
        }

    # Long lower wick (rejection wick)
    if total_range > 0 and lower_wick / total_range > wick_threshold:
        if current_bar['close'] > current_bar['open']:  # Bullish close
            return {
                'pattern': 'long_wick',
                'strength': 65,
                'description': f'Long lower wick ({lower_wick/total_range:.0%}) - moderate rejection'
            }

    return None


# Example usage
if __name__ == "__main__":
    import yfinance as yf

    # Fetch test data
    ticker = "AAPL"
    df = yf.download(ticker, period="1mo", interval="1d", progress=False)

    # Standardize columns
    df.columns = [str(col).lower() for col in df.columns]

    # Detect exit patterns for a CALL position in 25% profit
    exit_signals = detect_exit_patterns(
        df,
        option_type='CALL',
        current_profit_pct=0.25,
        require_volume_confirmation=True
    )

    print(f"Exit patterns detected for {ticker} CALL:")
    for pattern in exit_signals:
        print(f"\nPattern: {pattern['pattern']}")
        print(f"  Strength: {pattern['strength']}/100")
        print(f"  Recommendation: {pattern['recommendation']}")
        print(f"  Urgency: {pattern['urgency']}")
        print(f"  Confirmed: {pattern['confirmed']}")
        if 'volume_confirmation' in pattern:
            print(f"  Volume: {pattern['volume_confirmation']}")
