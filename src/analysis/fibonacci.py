"""
Fibonacci Retracement and Extension Levels
"""

from typing import Dict, Any, Optional, List, Tuple
import pandas as pd


def calculate_fibonacci_retracements(
    swing_high: float,
    swing_low: float,
    levels: Optional[List[float]] = None
) -> Dict[float, float]:
    """
    Calculate Fibonacci retracement levels.

    Args:
        swing_high: High point of the swing
        swing_low: Low point of the swing
        levels: Fibonacci ratios (default: [0.236, 0.382, 0.5, 0.618, 0.786])

    Returns:
        Dict mapping ratio to price level
    """
    if levels is None:
        levels = [0.236, 0.382, 0.5, 0.618, 0.786]

    swing_range = swing_high - swing_low
    retracements = {}

    for level in levels:
        # Retracement from high
        retracements[level] = swing_high - (swing_range * level)

    return retracements


def calculate_fibonacci_extensions(
    swing_high: float,
    swing_low: float,
    levels: Optional[List[float]] = None
) -> Dict[float, float]:
    """
    Calculate Fibonacci extension levels for targets.

    Args:
        swing_high: High point of the swing
        swing_low: Low point of the swing
        levels: Fibonacci extension ratios (default: [1.272, 1.414, 1.618, 2.618])

    Returns:
        Dict mapping ratio to price level
    """
    if levels is None:
        levels = [1.272, 1.414, 1.618, 2.618]

    swing_range = swing_high - swing_low
    extensions = {}

    for level in levels:
        # Extension from low
        extensions[level] = swing_low + (swing_range * level)

    return extensions


def find_swing_points(
    df: pd.DataFrame,
    lookback: int = 60
) -> Tuple[Optional[float], Optional[float]]:
    """
    Find recent swing high and swing low.

    Args:
        df: OHLC DataFrame
        lookback: Number of bars to look back

    Returns:
        Tuple of (swing_high, swing_low) or (None, None)
    """
    if df is None or len(df) < lookback:
        return None, None

    recent = df.tail(lookback)
    swing_high = recent['high'].max()
    swing_low = recent['low'].min()

    return swing_high, swing_low


def get_fib_analysis(
    ticker: str,
    current_price: float,
    df: Optional[pd.DataFrame] = None,
    lookback: int = 60
) -> Optional[Dict[str, Any]]:
    """
    Get complete Fibonacci analysis for a ticker.

    Args:
        ticker: Stock symbol
        current_price: Current price
        df: OHLC DataFrame (will fetch if not provided)
        lookback: Days to look back for swing points

    Returns:
        Dict with retracements, extensions, and current position analysis
    """
    if df is None:
        try:
            import yfinance as yf
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(col).lower() for col in df.columns]
        except Exception:
            return None

    swing_high, swing_low = find_swing_points(df, lookback)

    if swing_high is None or swing_low is None:
        return None

    retracements = calculate_fibonacci_retracements(swing_high, swing_low)
    extensions = calculate_fibonacci_extensions(swing_high, swing_low)

    # Determine current position
    position = "unknown"
    if current_price >= swing_high:
        position = "above_swing_high"
    elif current_price <= swing_low:
        position = "below_swing_low"
    else:
        # Find nearest fib level
        for level, price in sorted(retracements.items()):
            if abs(current_price - price) / current_price < 0.01:  # Within 1%
                position = f"at_fib_{level}"
                break

    return {
        'swing_high': round(swing_high, 2),
        'swing_low': round(swing_low, 2),
        'swing_range': round(swing_high - swing_low, 2),
        'current_price': round(current_price, 2),
        'position': position,
        'retracements': {k: round(v, 2) for k, v in retracements.items()},
        'extensions': {k: round(v, 2) for k, v in extensions.items()}
    }


# Example usage
if __name__ == "__main__":
    # Test Fibonacci calculations
    swing_high = 280
    swing_low = 260

    retracements = calculate_fibonacci_retracements(swing_high, swing_low)
    print("Fibonacci Retracements:")
    for level, price in sorted(retracements.items()):
        print(f"  {level:.3f}: ${price:.2f}")

    extensions = calculate_fibonacci_extensions(swing_high, swing_low)
    print("\nFibonacci Extensions:")
    for level, price in sorted(extensions.items()):
        print(f"  {level:.3f}: ${price:.2f}")

    # Test with real data
    print("\n" + "="*50)
    analysis = get_fib_analysis("AAPL", 270)
    if analysis:
        print(f"AAPL Fibonacci Analysis:")
        print(f"  Swing: ${analysis['swing_low']} - ${analysis['swing_high']}")
        print(f"  Current: ${analysis['current_price']} ({analysis['position']})")
        print("\n  Key Retracement Levels:")
        for level, price in analysis['retracements'].items():
            print(f"    {level}: ${price}")
