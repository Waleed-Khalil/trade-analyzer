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
