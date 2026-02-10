"""
Trend Analysis Module
Identifies trend structure, strength (ADX), and multi-timeframe alignment
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def identify_trend(
    df: pd.DataFrame,
    method: str = 'swing_points',
    adx_threshold: int = 25
) -> Dict[str, Any]:
    """
    Identify current trend using swing points or ADX.

    Args:
        df: DataFrame with OHLC data
        method: 'swing_points' or 'adx'
        adx_threshold: ADX value above which trend is considered strong

    Returns:
        Dict with trend direction, strength, and confidence
    """
    if df is None or len(df) < 20:
        return {'direction': 'unknown', 'strength': 0, 'confidence': 0}

    if method == 'swing_points':
        return _identify_trend_from_structure(df)
    elif method == 'adx':
        return _identify_trend_from_adx(df, adx_threshold)
    else:
        # Hybrid: use both methods
        structure = _identify_trend_from_structure(df)
        adx_trend = _identify_trend_from_adx(df, adx_threshold)

        # Combine signals
        return _combine_trend_signals(structure, adx_trend)


def _identify_trend_from_structure(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Identify trend from price structure (higher highs/lows or lower highs/lows).
    """
    if len(df) < 20:
        return {'direction': 'unknown', 'strength': 0, 'confidence': 0}

    # Find recent swing highs and lows
    highs = []
    lows = []
    window = 5

    for i in range(window, len(df) - window):
        # Check for swing high
        if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
            highs.append({'index': i, 'price': df['high'].iloc[i]})

        # Check for swing low
        if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
            lows.append({'index': i, 'price': df['low'].iloc[i]})

    if len(highs) < 2 or len(lows) < 2:
        return {'direction': 'sideways', 'strength': 30, 'confidence': 50}

    # Analyze last few swings
    recent_highs = highs[-3:] if len(highs) >= 3 else highs
    recent_lows = lows[-3:] if len(lows) >= 3 else lows

    # Check for higher highs
    higher_highs = all(
        recent_highs[i]['price'] > recent_highs[i-1]['price']
        for i in range(1, len(recent_highs))
    )

    # Check for higher lows
    higher_lows = all(
        recent_lows[i]['price'] > recent_lows[i-1]['price']
        for i in range(1, len(recent_lows))
    )

    # Check for lower highs
    lower_highs = all(
        recent_highs[i]['price'] < recent_highs[i-1]['price']
        for i in range(1, len(recent_highs))
    )

    # Check for lower lows
    lower_lows = all(
        recent_lows[i]['price'] < recent_lows[i-1]['price']
        for i in range(1, len(recent_lows))
    )

    # Determine trend
    if higher_highs and higher_lows:
        direction = 'uptrend'
        strength = 80
        confidence = 90
    elif lower_highs and lower_lows:
        direction = 'downtrend'
        strength = 80
        confidence = 90
    elif higher_highs or higher_lows:
        direction = 'uptrend'
        strength = 60
        confidence = 60
    elif lower_highs or lower_lows:
        direction = 'downtrend'
        strength = 60
        confidence = 60
    else:
        direction = 'sideways'
        strength = 40
        confidence = 70

    return {
        'direction': direction,
        'strength': strength,
        'confidence': confidence,
        'method': 'swing_points',
        'swing_highs': len(highs),
        'swing_lows': len(lows),
    }


def detect_trend_structure(df: pd.DataFrame, lookback: int = 50) -> Dict[str, Any]:
    """
    Detailed trend structure analysis.

    Returns:
        Dict with higher_highs, higher_lows, lower_highs, lower_lows counts
    """
    if df is None or len(df) < lookback:
        lookback = len(df) if df is not None else 0

    if lookback < 10:
        return {'structure': 'unknown'}

    recent_df = df.iloc[-lookback:]

    # Find all swing points
    highs = []
    lows = []
    window = 3

    for i in range(window, len(recent_df) - window):
        if recent_df['high'].iloc[i] == recent_df['high'].iloc[i-window:i+window+1].max():
            highs.append(recent_df['high'].iloc[i])

        if recent_df['low'].iloc[i] == recent_df['low'].iloc[i-window:i+window+1].min():
            lows.append(recent_df['low'].iloc[i])

    # Count higher/lower patterns
    higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
    lower_highs = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
    higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
    lower_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

    return {
        'higher_highs': higher_highs,
        'lower_highs': lower_highs,
        'higher_lows': higher_lows,
        'lower_lows': lower_lows,
        'total_swing_highs': len(highs),
        'total_swing_lows': len(lows),
    }


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX) for trend strength.

    ADX > 25: Strong trend
    ADX < 20: Weak/no trend

    Args:
        df: DataFrame with high, low, close
        period: ADX period (default 14)

    Returns:
        Series with ADX values
    """
    if df is None or len(df) < period + 1:
        return pd.Series()

    # Calculate True Range
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # Calculate Directional Movement
    up_move = df['high'] - df['high'].shift()
    down_move = df['low'].shift() - df['low']

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Smooth the values
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr

    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()

    return adx


def _identify_trend_from_adx(df: pd.DataFrame, threshold: int = 25) -> Dict[str, Any]:
    """Identify trend using ADX."""
    adx = calculate_adx(df)

    if adx.empty or len(adx) == 0:
        return {'direction': 'unknown', 'strength': 0, 'confidence': 0}

    current_adx = adx.iloc[-1]

    # Handle NaN ADX (insufficient data)
    if pd.isna(current_adx):
        return {'direction': 'unknown', 'strength': 0, 'confidence': 0, 'adx': 0, 'method': 'adx'}

    # Determine direction from price action
    sma_20 = df['close'].rolling(20).mean()
    current_price = df['close'].iloc[-1]
    sma_value = sma_20.iloc[-1]

    if current_price > sma_value:
        direction = 'uptrend'
    elif current_price < sma_value:
        direction = 'downtrend'
    else:
        direction = 'sideways'

    # ADX determines strength, not direction
    if current_adx > threshold:
        strength = min(int(current_adx), 100)
        confidence = 80
    elif current_adx > 20:
        strength = int(current_adx)
        confidence = 60
    else:
        direction = 'sideways'
        strength = int(current_adx)
        confidence = 50

    return {
        'direction': direction,
        'strength': strength,
        'confidence': confidence,
        'adx': current_adx,
        'method': 'adx',
    }


def _combine_trend_signals(signal1: Dict, signal2: Dict) -> Dict[str, Any]:
    """Combine two trend signals for higher confidence."""
    if signal1['direction'] == signal2['direction']:
        # Agreement = high confidence
        return {
            'direction': signal1['direction'],
            'strength': int((signal1['strength'] + signal2['strength']) / 2),
            'confidence': 95,
            'method': 'hybrid',
        }
    else:
        # Disagreement = lower confidence, favor ADX
        return {
            'direction': signal2['direction'],  # ADX has final say
            'strength': signal2['strength'],
            'confidence': 40,
            'method': 'hybrid',
            'conflict': True,
        }


def multi_timeframe_trend_alignment(
    ticker: str,
    timeframes: List[str] = None,
    fetch_data_func: Any = None
) -> Dict[str, Any]:
    """
    Check trend alignment across multiple timeframes.

    Args:
        ticker: Ticker symbol
        timeframes: List of timeframes (e.g., ['daily', '4h', '1h'])
        fetch_data_func: Function to fetch data (ticker, timeframe) -> DataFrame

    Returns:
        Dict with alignment analysis
    """
    if timeframes is None:
        timeframes = ['daily', '4h', '1h']

    if fetch_data_func is None:
        # Can't check alignment without data
        return {'aligned': False, 'direction': 'unknown'}

    trends = {}

    for tf in timeframes:
        try:
            df = fetch_data_func(ticker, tf)
            trend = identify_trend(df, method='swing_points')
            trends[tf] = trend
        except Exception as e:
            print(f"Failed to get {tf} data: {e}")
            trends[tf] = {'direction': 'unknown'}

    # Check alignment
    directions = [t['direction'] for t in trends.values() if t.get('direction') != 'unknown']

    if not directions:
        return {'aligned': False, 'direction': 'unknown', 'trends': trends}

    # Check if all agree
    if all(d == directions[0] for d in directions):
        aligned = True
        direction = directions[0]
        confidence = 95
    elif directions.count(directions[0]) >= len(directions) * 0.66:
        # Majority alignment (2 out of 3)
        aligned = True
        direction = directions[0]
        confidence = 75
    else:
        aligned = False
        direction = 'mixed'
        confidence = 40

    return {
        'aligned': aligned,
        'direction': direction,
        'confidence': confidence,
        'trends': trends,
        'timeframes_checked': len(directions),
    }


def find_trendlines(
    df: pd.DataFrame,
    min_touches: int = 2,
    lookback: int = 60
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect ascending and descending trendlines.

    Args:
        df: DataFrame with OHLC data
        min_touches: Minimum number of touches to validate trendline
        lookback: Number of bars to analyze

    Returns:
        Dict with 'support_trendlines' and 'resistance_trendlines'
    """
    if df is None or len(df) < lookback:
        return {'support_trendlines': [], 'resistance_trendlines': []}

    recent_df = df.iloc[-lookback:].copy()

    support_lines = []
    resistance_lines = []

    # Find swing lows for support trendlines
    swing_lows = []
    window = 5

    for i in range(window, len(recent_df) - window):
        if recent_df['low'].iloc[i] == recent_df['low'].iloc[i-window:i+window+1].min():
            swing_lows.append({
                'index': i,
                'price': recent_df['low'].iloc[i],
                'date': recent_df.index[i]
            })

    # Try to draw trendlines through swing lows
    for i in range(len(swing_lows) - 1):
        for j in range(i + 1, len(swing_lows)):
            point1 = swing_lows[i]
            point2 = swing_lows[j]

            # Calculate slope
            x_diff = point2['index'] - point1['index']
            y_diff = point2['price'] - point1['price']

            if x_diff == 0:
                continue

            slope = y_diff / x_diff

            # Only consider ascending trendlines for support
            if slope <= 0:
                continue

            # Count touches
            touches = _count_trendline_touches(
                recent_df, point1, slope, 'support', tolerance_pct=0.5
            )

            if touches >= min_touches:
                # Project to current
                current_idx = len(recent_df) - 1
                current_value = point1['price'] + slope * (current_idx - point1['index'])

                support_lines.append({
                    'start': point1,
                    'end': point2,
                    'slope': slope,
                    'touches': touches,
                    'current_value': current_value,
                    'type': 'ascending_support',
                })

    # Find swing highs for resistance trendlines
    swing_highs = []

    for i in range(window, len(recent_df) - window):
        if recent_df['high'].iloc[i] == recent_df['high'].iloc[i-window:i+window+1].max():
            swing_highs.append({
                'index': i,
                'price': recent_df['high'].iloc[i],
                'date': recent_df.index[i]
            })

    # Try to draw trendlines through swing highs
    for i in range(len(swing_highs) - 1):
        for j in range(i + 1, len(swing_highs)):
            point1 = swing_highs[i]
            point2 = swing_highs[j]

            x_diff = point2['index'] - point1['index']
            y_diff = point2['price'] - point1['price']

            if x_diff == 0:
                continue

            slope = y_diff / x_diff

            # Only consider descending trendlines for resistance
            if slope >= 0:
                continue

            touches = _count_trendline_touches(
                recent_df, point1, slope, 'resistance', tolerance_pct=0.5
            )

            if touches >= min_touches:
                current_idx = len(recent_df) - 1
                current_value = point1['price'] + slope * (current_idx - point1['index'])

                resistance_lines.append({
                    'start': point1,
                    'end': point2,
                    'slope': slope,
                    'touches': touches,
                    'current_value': current_value,
                    'type': 'descending_resistance',
                })

    return {
        'support_trendlines': sorted(support_lines, key=lambda x: x['touches'], reverse=True),
        'resistance_trendlines': sorted(resistance_lines, key=lambda x: x['touches'], reverse=True),
    }


def _count_trendline_touches(
    df: pd.DataFrame,
    start_point: Dict,
    slope: float,
    line_type: str,
    tolerance_pct: float = 0.5
) -> int:
    """Count how many times price touched a trendline."""
    touches = 0

    for i in range(start_point['index'], len(df)):
        expected_value = start_point['price'] + slope * (i - start_point['index'])
        actual_low = df['low'].iloc[i]
        actual_high = df['high'].iloc[i]

        tolerance = expected_value * (tolerance_pct / 100)

        if line_type == 'support':
            # Check if low touched the line
            if abs(actual_low - expected_value) <= tolerance:
                touches += 1
        else:  # resistance
            # Check if high touched the line
            if abs(actual_high - expected_value) <= tolerance:
                touches += 1

    return touches


# Example usage
if __name__ == "__main__":
    import yfinance as yf

    ticker = "AAPL"
    df = yf.download(ticker, period="3mo", interval="1d", progress=False)

    if not df.empty:
        print(f"\n{'='*60}")
        print(f"Trend Analysis: {ticker}")
        print(f"{'='*60}\n")

        # Identify trend
        trend = identify_trend(df, method='swing_points')
        print(f"Trend: {trend['direction'].upper()}")
        print(f"Strength: {trend['strength']}/100")
        print(f"Confidence: {trend['confidence']}%")
        print(f"Method: {trend['method']}\n")

        # ADX
        adx = calculate_adx(df)
        if not adx.empty:
            current_adx = adx.iloc[-1]
            print(f"ADX: {current_adx:.1f}")
            if current_adx > 25:
                print("  Strong trend detected")
            elif current_adx > 20:
                print("  Moderate trend")
            else:
                print("  Weak/no trend\n")

        # Trend structure
        structure = detect_trend_structure(df)
        print(f"\nTrend Structure (last 50 bars):")
        print(f"  Higher Highs: {structure['higher_highs']}")
        print(f"  Lower Highs: {structure['lower_highs']}")
        print(f"  Higher Lows: {structure['higher_lows']}")
        print(f"  Lower Lows: {structure['lower_lows']}\n")

        # Trendlines
        trendlines = find_trendlines(df)
        print(f"Support Trendlines: {len(trendlines['support_trendlines'])}")
        for line in trendlines['support_trendlines'][:2]:
            print(f"  Current: ${line['current_value']:.2f} | Touches: {line['touches']}")

        print(f"\nResistance Trendlines: {len(trendlines['resistance_trendlines'])}")
        for line in trendlines['resistance_trendlines'][:2]:
            print(f"  Current: ${line['current_value']:.2f} | Touches: {line['touches']}")
