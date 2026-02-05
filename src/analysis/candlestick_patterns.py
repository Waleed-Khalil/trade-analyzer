"""
Candlestick Pattern Recognition Module
Detects high-reliability reversal and continuation patterns
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


def detect_patterns(
    df: pd.DataFrame,
    patterns: List[str] = None,
    require_volume_confirmation: bool = True
) -> List[Dict[str, Any]]:
    """
    Scan for candlestick patterns in recent price data.

    Args:
        df: DataFrame with OHLC data
        patterns: List of pattern names to detect (None = all)
        require_volume_confirmation: Require above-average volume for patterns

    Returns:
        List of detected pattern dicts
    """
    if df is None or len(df) < 10:
        return []

    if patterns is None:
        patterns = ['engulfing', 'pinbar', 'doji', 'morning_star', 'evening_star',
                   'hammer', 'shooting_star', 'three_soldiers', 'three_crows']

    detected = []

    # Calculate average volume for confirmation
    avg_volume = df['volume'].rolling(20).mean()

    # Detect each pattern type
    for idx in range(len(df)):
        if 'engulfing' in patterns:
            pattern = _detect_engulfing(df, idx)
            if pattern:
                pattern['volume_confirmed'] = _check_volume_confirmation(
                    df, idx, avg_volume, require_volume_confirmation
                )
                detected.append(pattern)

        if 'pinbar' in patterns or 'hammer' in patterns or 'shooting_star' in patterns:
            pattern = _detect_pinbar(df, idx)
            if pattern:
                pattern['volume_confirmed'] = _check_volume_confirmation(
                    df, idx, avg_volume, require_volume_confirmation
                )
                detected.append(pattern)

        if 'doji' in patterns:
            pattern = _detect_doji(df, idx)
            if pattern:
                pattern['volume_confirmed'] = _check_volume_confirmation(
                    df, idx, avg_volume, require_volume_confirmation
                )
                detected.append(pattern)

        if 'morning_star' in patterns or 'evening_star' in patterns:
            pattern = _detect_star_patterns(df, idx)
            if pattern:
                pattern['volume_confirmed'] = _check_volume_confirmation(
                    df, idx, avg_volume, require_volume_confirmation
                )
                detected.append(pattern)

        if 'three_soldiers' in patterns or 'three_crows' in patterns:
            pattern = _detect_three_pattern(df, idx)
            if pattern:
                pattern['volume_confirmed'] = _check_volume_confirmation(
                    df, idx, avg_volume, require_volume_confirmation
                )
                detected.append(pattern)

    return detected


def _detect_engulfing(df: pd.DataFrame, idx: int) -> Optional[Dict[str, Any]]:
    """
    Detect bullish/bearish engulfing patterns.

    Bullish engulfing: Down candle followed by larger up candle that engulfs it
    Bearish engulfing: Up candle followed by larger down candle that engulfs it
    """
    if idx < 1 or idx >= len(df):
        return None

    curr = df.iloc[idx]
    prev = df.iloc[idx - 1]

    curr_body = abs(curr['close'] - curr['open'])
    prev_body = abs(prev['close'] - prev['open'])

    # Bullish engulfing
    if prev['close'] < prev['open'] and curr['close'] > curr['open']:
        # Current candle engulfs previous
        if curr['open'] <= prev['close'] and curr['close'] >= prev['open']:
            if curr_body > prev_body * 1.1:  # At least 10% larger body
                return {
                    'date': df.index[idx],
                    'pattern': 'bullish_engulfing',
                    'type': 'reversal',
                    'direction': 'bullish',
                    'price': curr['close'],
                    'strength': _calculate_engulfing_strength(curr, prev),
                }

    # Bearish engulfing
    if prev['close'] > prev['open'] and curr['close'] < curr['open']:
        if curr['open'] >= prev['close'] and curr['close'] <= prev['open']:
            if curr_body > prev_body * 1.1:
                return {
                    'date': df.index[idx],
                    'pattern': 'bearish_engulfing',
                    'type': 'reversal',
                    'direction': 'bearish',
                    'price': curr['close'],
                    'strength': _calculate_engulfing_strength(curr, prev),
                }

    return None


def _calculate_engulfing_strength(curr: pd.Series, prev: pd.Series) -> float:
    """Calculate engulfing pattern strength (0-100)."""
    curr_body = abs(curr['close'] - curr['open'])
    prev_body = abs(prev['close'] - prev['open'])

    # Base score on body size ratio
    ratio = curr_body / prev_body if prev_body > 0 else 1
    strength = min(ratio * 40, 60)  # Max 60 from ratio

    # Bonus for large body relative to range
    curr_range = curr['high'] - curr['low']
    if curr_range > 0:
        body_pct = curr_body / curr_range
        strength += body_pct * 20  # Max 20 bonus

    # Bonus for closing near extreme
    if curr['close'] > curr['open']:  # Bullish
        close_position = (curr['close'] - curr['low']) / curr_range if curr_range > 0 else 0
    else:  # Bearish
        close_position = (curr['high'] - curr['close']) / curr_range if curr_range > 0 else 0

    strength += close_position * 20  # Max 20 bonus

    return min(100, strength)


def _detect_pinbar(df: pd.DataFrame, idx: int) -> Optional[Dict[str, Any]]:
    """
    Detect pin bar / hammer / shooting star patterns.

    Pin bar: Small body with long wick (rejection of price level)
    Hammer: Pin bar at bottom (bullish reversal)
    Shooting star: Pin bar at top (bearish reversal)
    """
    if idx < 1 or idx >= len(df):
        return None

    candle = df.iloc[idx]
    body = abs(candle['close'] - candle['open'])
    full_range = candle['high'] - candle['low']

    if full_range == 0:
        return None

    # Calculate wick lengths
    if candle['close'] > candle['open']:  # Bullish candle
        upper_wick = candle['high'] - candle['close']
        lower_wick = candle['open'] - candle['low']
    else:  # Bearish candle
        upper_wick = candle['high'] - candle['open']
        lower_wick = candle['close'] - candle['low']

    body_pct = body / full_range
    upper_wick_pct = upper_wick / full_range
    lower_wick_pct = lower_wick / full_range

    # Pin bar requirements: small body (< 30%) and long wick (> 60%)
    if body_pct > 0.3:
        return None

    # Bullish pin bar (hammer) - long lower wick
    if lower_wick_pct > 0.6 and upper_wick_pct < 0.2:
        # Check if at potential bottom (price below recent average)
        if idx >= 10:
            recent_avg = df['close'].iloc[idx-10:idx].mean()
            at_bottom = candle['low'] <= recent_avg * 0.98
        else:
            at_bottom = False

        pattern_name = 'hammer' if at_bottom else 'bullish_pinbar'

        return {
            'date': df.index[idx],
            'pattern': pattern_name,
            'type': 'reversal',
            'direction': 'bullish',
            'price': candle['close'],
            'strength': _calculate_pinbar_strength(body_pct, lower_wick_pct, upper_wick_pct),
        }

    # Bearish pin bar (shooting star) - long upper wick
    if upper_wick_pct > 0.6 and lower_wick_pct < 0.2:
        # Check if at potential top
        if idx >= 10:
            recent_avg = df['close'].iloc[idx-10:idx].mean()
            at_top = candle['high'] >= recent_avg * 1.02
        else:
            at_top = False

        pattern_name = 'shooting_star' if at_top else 'bearish_pinbar'

        return {
            'date': df.index[idx],
            'pattern': pattern_name,
            'type': 'reversal',
            'direction': 'bearish',
            'price': candle['close'],
            'strength': _calculate_pinbar_strength(body_pct, upper_wick_pct, lower_wick_pct),
        }

    return None


def _calculate_pinbar_strength(body_pct: float, long_wick_pct: float, short_wick_pct: float) -> float:
    """Calculate pin bar strength (0-100)."""
    # Smaller body = stronger
    body_score = (1 - body_pct) * 30  # Max 30

    # Longer rejection wick = stronger
    wick_score = long_wick_pct * 50  # Max 50

    # Shorter opposite wick = stronger
    opposite_score = (1 - short_wick_pct) * 20  # Max 20

    return min(100, body_score + wick_score + opposite_score)


def _detect_doji(df: pd.DataFrame, idx: int) -> Optional[Dict[str, Any]]:
    """
    Detect doji patterns (indecision candles).

    Doji: Open and close are very close (small body), representing indecision.
    Most significant at support/resistance levels.
    """
    if idx >= len(df):
        return None

    candle = df.iloc[idx]
    body = abs(candle['close'] - candle['open'])
    full_range = candle['high'] - candle['low']

    if full_range == 0:
        return None

    body_pct = body / full_range

    # Doji: body < 10% of range
    if body_pct < 0.1:
        return {
            'date': df.index[idx],
            'pattern': 'doji',
            'type': 'indecision',
            'direction': 'neutral',
            'price': candle['close'],
            'strength': (1 - body_pct) * 100,  # Smaller body = stronger doji
        }

    return None


def _detect_star_patterns(df: pd.DataFrame, idx: int) -> Optional[Dict[str, Any]]:
    """
    Detect morning star (bullish) and evening star (bearish) patterns.

    Morning star: Down candle, small body (star), strong up candle
    Evening star: Up candle, small body (star), strong down candle
    """
    if idx < 2 or idx >= len(df):
        return None

    candle1 = df.iloc[idx - 2]  # First candle
    candle2 = df.iloc[idx - 1]  # Star (middle)
    candle3 = df.iloc[idx]      # Third candle

    body1 = abs(candle1['close'] - candle1['open'])
    body2 = abs(candle2['close'] - candle2['open'])
    body3 = abs(candle3['close'] - candle3['open'])

    range2 = candle2['high'] - candle2['low']
    if range2 == 0:
        return None

    # Star must have small body
    star_body_pct = body2 / range2
    if star_body_pct > 0.3:
        return None

    # Morning star (bullish reversal)
    if (candle1['close'] < candle1['open'] and  # First candle bearish
        candle3['close'] > candle3['open'] and  # Third candle bullish
        body1 > body2 * 2 and body3 > body2 * 2):  # Star is small

        # Third candle should close well into first candle's body
        if candle3['close'] > (candle1['open'] + candle1['close']) / 2:
            return {
                'date': df.index[idx],
                'pattern': 'morning_star',
                'type': 'reversal',
                'direction': 'bullish',
                'price': candle3['close'],
                'strength': _calculate_star_strength(body1, body2, body3, candle3['close'], candle1),
            }

    # Evening star (bearish reversal)
    if (candle1['close'] > candle1['open'] and  # First candle bullish
        candle3['close'] < candle3['open'] and  # Third candle bearish
        body1 > body2 * 2 and body3 > body2 * 2):

        # Third candle should close well into first candle's body
        if candle3['close'] < (candle1['open'] + candle1['close']) / 2:
            return {
                'date': df.index[idx],
                'pattern': 'evening_star',
                'type': 'reversal',
                'direction': 'bearish',
                'price': candle3['close'],
                'strength': _calculate_star_strength(body1, body2, body3, candle3['close'], candle1),
            }

    return None


def _calculate_star_strength(body1: float, body2: float, body3: float,
                             close3: float, candle1: pd.Series) -> float:
    """Calculate morning/evening star strength."""
    # Large outer candles
    size_score = min((body1 + body3) / body2, 10) * 5  # Max 50

    # Small star
    star_score = (1 - min(body2 / body1, 1)) * 30  # Max 30

    # Penetration into first candle
    first_range = abs(candle1['open'] - candle1['close'])
    if first_range > 0:
        penetration = abs(close3 - candle1['close']) / first_range
        penetration_score = min(penetration, 1) * 20  # Max 20
    else:
        penetration_score = 0

    return min(100, size_score + star_score + penetration_score)


def _detect_three_pattern(df: pd.DataFrame, idx: int) -> Optional[Dict[str, Any]]:
    """
    Detect three white soldiers (bullish) and three black crows (bearish).

    Three soldiers: Three consecutive strong bullish candles
    Three crows: Three consecutive strong bearish candles
    """
    if idx < 2 or idx >= len(df):
        return None

    candle1 = df.iloc[idx - 2]
    candle2 = df.iloc[idx - 1]
    candle3 = df.iloc[idx]

    # Three white soldiers (bullish continuation)
    if (candle1['close'] > candle1['open'] and
        candle2['close'] > candle2['open'] and
        candle3['close'] > candle3['open']):

        # Each candle should open within previous body and close higher
        if (candle2['open'] > candle1['open'] and candle2['open'] < candle1['close'] and
            candle2['close'] > candle1['close'] and
            candle3['open'] > candle2['open'] and candle3['open'] < candle2['close'] and
            candle3['close'] > candle2['close']):

            return {
                'date': df.index[idx],
                'pattern': 'three_white_soldiers',
                'type': 'continuation',
                'direction': 'bullish',
                'price': candle3['close'],
                'strength': 75,  # Strong pattern
            }

    # Three black crows (bearish continuation)
    if (candle1['close'] < candle1['open'] and
        candle2['close'] < candle2['open'] and
        candle3['close'] < candle3['open']):

        if (candle2['open'] < candle1['open'] and candle2['open'] > candle1['close'] and
            candle2['close'] < candle1['close'] and
            candle3['open'] < candle2['open'] and candle3['open'] > candle2['close'] and
            candle3['close'] < candle2['close']):

            return {
                'date': df.index[idx],
                'pattern': 'three_black_crows',
                'type': 'continuation',
                'direction': 'bearish',
                'price': candle3['close'],
                'strength': 75,
            }

    return None


def _check_volume_confirmation(
    df: pd.DataFrame,
    idx: int,
    avg_volume: pd.Series,
    require: bool
) -> bool:
    """Check if pattern has volume confirmation."""
    if not require or avg_volume is None or idx >= len(df):
        return True

    current_vol = df['volume'].iloc[idx]
    avg_vol = avg_volume.iloc[idx] if idx < len(avg_volume) else df['volume'].mean()

    return current_vol > avg_vol * 1.2  # At least 20% above average


def pattern_strength_score(
    pattern_data: Dict[str, Any],
    context: Dict[str, Any] = None
) -> int:
    """
    Calculate overall pattern strength score (0-100) based on pattern and context.

    Args:
        pattern_data: Pattern dict from detect_patterns
        context: Additional context (at_support, at_resistance, trend, etc.)

    Returns:
        Score from 0-100
    """
    if not pattern_data:
        return 0

    base_strength = pattern_data.get('strength', 50)
    score = base_strength

    # Bonus for volume confirmation
    if pattern_data.get('volume_confirmed'):
        score += 10

    if context:
        # Bonus for pattern at support/resistance
        if context.get('at_support') and pattern_data.get('direction') == 'bullish':
            score += 15
        if context.get('at_resistance') and pattern_data.get('direction') == 'bearish':
            score += 15

        # Bonus for pattern aligned with trend
        trend = context.get('trend')
        if trend == 'uptrend' and pattern_data.get('direction') == 'bullish':
            score += 10
        elif trend == 'downtrend' and pattern_data.get('direction') == 'bearish':
            score += 10

    return min(100, int(score))


def get_pattern_signals(
    df: pd.DataFrame,
    lookback: int = 10,
    patterns: List[str] = None,
    require_volume_confirmation: bool = True
) -> List[Dict[str, Any]]:
    """
    Main entry point for pattern detection.

    Args:
        df: OHLC DataFrame
        lookback: Number of recent bars to scan
        patterns: Pattern names to detect
        require_volume_confirmation: Require volume confirmation

    Returns:
        List of detected patterns with metadata
    """
    if df is None or len(df) < 3:
        return []

    # Limit to lookback period
    start_idx = max(0, len(df) - lookback)
    recent_df = df.iloc[start_idx:]

    # Detect patterns
    detected = detect_patterns(recent_df, patterns, require_volume_confirmation)

    return detected


# Example usage
if __name__ == "__main__":
    import yfinance as yf

    ticker = "AAPL"
    df = yf.download(ticker, period="1mo", interval="1d", progress=False)

    if not df.empty:
        print(f"\n{'='*60}")
        print(f"Candlestick Pattern Analysis: {ticker}")
        print(f"{'='*60}\n")

        patterns = get_pattern_signals(df, lookback=10)

        if patterns:
            print(f"Detected {len(patterns)} patterns in last 10 days:\n")
            for p in patterns:
                vol_conf = "✓" if p.get('volume_confirmed') else "✗"
                print(f"{p['date'].date()} - {p['pattern'].upper()}")
                print(f"  Direction: {p['direction']}")
                print(f"  Strength: {p['strength']:.0f}/100")
                print(f"  Volume confirmed: {vol_conf}")
                print(f"  Price: ${p['price']:.2f}\n")
        else:
            print("No significant patterns detected in recent bars")
