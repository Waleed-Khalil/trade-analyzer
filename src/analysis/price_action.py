"""
Price Action Analysis Module
Detects support/resistance zones from actual price behavior (swing highs/lows)
rather than algorithmic levels.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def find_swing_highs_lows(df: pd.DataFrame, window: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    Detect swing highs and swing lows using a rolling window approach.

    A swing high is a peak where price is higher than N bars before and after.
    A swing low is a trough where price is lower than N bars before and after.

    Args:
        df: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)
        window: Number of bars on each side to compare (default 5)

    Returns:
        Tuple of (swing_highs, swing_lows) where each is a list of dicts with:
        - price: float
        - date: datetime
        - volume: float
        - touches: int (initially 1)
    """
    swing_highs = []
    swing_lows = []

    if len(df) < window * 2 + 1:
        return swing_highs, swing_lows

    # Ensure we have datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        if 'date' in df.columns:
            df.set_index('date', inplace=True)

    # Detect swing highs
    for i in range(window, len(df) - window):
        current_high = df['high'].iloc[i]
        is_swing_high = True

        # Check if current bar is higher than all bars in window before and after
        for j in range(i - window, i):
            if df['high'].iloc[j] >= current_high:
                is_swing_high = False
                break

        if is_swing_high:
            for j in range(i + 1, i + window + 1):
                if df['high'].iloc[j] >= current_high:
                    is_swing_high = False
                    break

        if is_swing_high:
            swing_highs.append({
                'price': float(current_high),
                'date': df.index[i],
                'volume': float(df['volume'].iloc[i]) if 'volume' in df.columns else 0,
                'touches': 1,
            })

    # Detect swing lows
    for i in range(window, len(df) - window):
        current_low = df['low'].iloc[i]
        is_swing_low = True

        # Check if current bar is lower than all bars in window before and after
        for j in range(i - window, i):
            if df['low'].iloc[j] <= current_low:
                is_swing_low = False
                break

        if is_swing_low:
            for j in range(i + 1, i + window + 1):
                if df['low'].iloc[j] <= current_low:
                    is_swing_low = False
                    break

        if is_swing_low:
            swing_lows.append({
                'price': float(current_low),
                'date': df.index[i],
                'volume': float(df['volume'].iloc[i]) if 'volume' in df.columns else 0,
                'touches': 1,
            })

    return swing_highs, swing_lows


def cluster_levels(levels: List[Dict], clustering_pct: float = 0.5,
                   atr: Optional[float] = None) -> List[Dict]:
    """
    Cluster nearby price levels into zones.

    Levels within clustering_pct or 0.5*ATR are grouped together.
    The zone's price is the weighted average (by touches and volume).

    Args:
        levels: List of price level dicts with 'price', 'touches', 'volume', 'date'
        clustering_pct: Percentage threshold (e.g., 0.5 = 0.5%)
        atr: Average True Range value for distance-based clustering

    Returns:
        List of clustered zone dicts with weighted average price and metadata
    """
    if not levels:
        return []

    # Sort by price
    sorted_levels = sorted(levels, key=lambda x: x['price'])

    zones = []
    current_zone = [sorted_levels[0]]

    for i in range(1, len(sorted_levels)):
        prev_price = current_zone[-1]['price']
        curr_price = sorted_levels[i]['price']

        # Calculate distance threshold
        pct_distance = abs(curr_price - prev_price) / prev_price * 100

        # Check if within clustering threshold
        within_pct = pct_distance <= clustering_pct
        within_atr = False
        if atr and atr > 0:
            within_atr = abs(curr_price - prev_price) <= (0.5 * atr)

        if within_pct or within_atr:
            current_zone.append(sorted_levels[i])
        else:
            # Finalize current zone
            zones.append(_create_zone_from_levels(current_zone))
            current_zone = [sorted_levels[i]]

    # Add last zone
    if current_zone:
        zones.append(_create_zone_from_levels(current_zone))

    return zones


def _create_zone_from_levels(levels: List[Dict]) -> Dict:
    """
    Create a support/resistance zone from clustered levels.
    Uses weighted average by touches and volume.
    """
    total_touches = sum(l['touches'] for l in levels)
    total_volume = sum(l.get('volume', 0) for l in levels)

    # Weighted average price (by touches)
    if total_touches > 0:
        weighted_price = sum(l['price'] * l['touches'] for l in levels) / total_touches
    else:
        weighted_price = sum(l['price'] for l in levels) / len(levels)

    # Most recent interaction
    most_recent_date = max(l['date'] for l in levels)

    return {
        'price': float(weighted_price),
        'touches': int(total_touches),
        'volume': float(total_volume),
        'last_touch': most_recent_date,
        'strength': _calculate_zone_strength(levels, total_touches, total_volume, most_recent_date),
        'range_low': float(min(l['price'] for l in levels)),
        'range_high': float(max(l['price'] for l in levels)),
    }


def _calculate_zone_strength(levels: List[Dict], total_touches: int,
                             total_volume: float, last_touch: datetime) -> float:
    """
    Calculate strength score for a zone (0-100).

    Based on:
    - Number of touches (more = stronger)
    - Volume at zone (higher = stronger)
    - Recency (more recent = more relevant)
    """
    score = 0.0

    # Touches component (0-40 points)
    touches_score = min(total_touches * 10, 40)
    score += touches_score

    # Volume component (0-30 points)
    # Normalize by number of levels
    avg_volume = total_volume / len(levels) if levels else 0
    if avg_volume > 0:
        # Logarithmic scale for volume
        volume_score = min(np.log10(avg_volume + 1) * 5, 30)
        score += volume_score

    # Recency component (0-30 points)
    # Handle timezone-aware datetime
    now = pd.Timestamp.now(tz=last_touch.tzinfo if hasattr(last_touch, 'tzinfo') else None)
    days_ago = (now - last_touch).days
    if days_ago < 7:
        recency_score = 30
    elif days_ago < 30:
        recency_score = 20
    elif days_ago < 60:
        recency_score = 10
    else:
        recency_score = 5
    score += recency_score

    return min(100.0, score)


def calculate_support_resistance_zones(
    df: pd.DataFrame,
    current_price: float,
    ticker: str = "",
    lookback_days: int = 60,
    swing_window: int = 5,
    min_touches: int = 2,
    zone_clustering_pct: float = 0.5,
    atr: Optional[float] = None,
    max_levels: int = 5,
) -> Dict[str, Any]:
    """
    Build support and resistance zones from actual price action.

    Args:
        df: DataFrame with OHLC data
        current_price: Current underlying price
        ticker: Ticker symbol
        lookback_days: Days of history to analyze
        swing_window: Window for swing detection
        min_touches: Minimum touches to consider a valid zone
        zone_clustering_pct: Clustering threshold percentage
        atr: Average True Range for clustering
        max_levels: Maximum number of levels to return

    Returns:
        Dict with support_zones, resistance_zones, key_levels, method, and metadata
    """
    if df is None or len(df) < swing_window * 2 + 1:
        return {
            'support_zones': [],
            'resistance_zones': [],
            'key_levels': {},
            'method': 'price_action',
            'error': 'Insufficient data',
        }

    # Limit to lookback period
    if lookback_days > 0:
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        if isinstance(df.index, pd.DatetimeIndex):
            # Handle timezone-aware index
            if df.index.tz is not None:
                cutoff_date = pd.Timestamp(cutoff_date).tz_localize(df.index.tz)
            df = df[df.index >= cutoff_date]

    # Find swing points
    swing_highs, swing_lows = find_swing_highs_lows(df, window=swing_window)

    # Count touches (levels that were tested multiple times)
    swing_highs = _count_touches(swing_highs, zone_clustering_pct, atr)
    swing_lows = _count_touches(swing_lows, zone_clustering_pct, atr)

    # Cluster into zones
    resistance_zones = cluster_levels(swing_highs, zone_clustering_pct, atr)
    support_zones = cluster_levels(swing_lows, zone_clustering_pct, atr)

    # Filter by minimum touches
    resistance_zones = [z for z in resistance_zones if z['touches'] >= min_touches]
    support_zones = [z for z in support_zones if z['touches'] >= min_touches]

    # Separate into support (below price) and resistance (above price)
    support_zones = [z for z in support_zones if z['price'] < current_price]
    resistance_zones = [z for z in resistance_zones if z['price'] > current_price]

    # Sort by strength and limit
    support_zones = sorted(support_zones, key=lambda x: x['strength'], reverse=True)[:max_levels]
    resistance_zones = sorted(resistance_zones, key=lambda x: x['strength'], reverse=True)[:max_levels]

    # Sort by proximity to current price
    support_zones = sorted(support_zones, key=lambda x: current_price - x['price'])
    resistance_zones = sorted(resistance_zones, key=lambda x: x['price'] - current_price)

    # Identify key levels
    key_levels = {
        'nearest_support': support_zones[0]['price'] if support_zones else current_price * 0.98,
        'nearest_resistance': resistance_zones[0]['price'] if resistance_zones else current_price * 1.02,
        'strongest_support': max(support_zones, key=lambda x: x['strength'])['price'] if support_zones else None,
        'strongest_resistance': max(resistance_zones, key=lambda x: x['strength'])['price'] if resistance_zones else None,
    }

    return {
        'support_zones': support_zones,
        'resistance_zones': resistance_zones,
        'key_levels': key_levels,
        'method': 'price_action',
        'metadata': {
            'lookback_days': lookback_days,
            'swing_window': swing_window,
            'total_swing_highs': len(swing_highs),
            'total_swing_lows': len(swing_lows),
            'zones_found': len(support_zones) + len(resistance_zones),
        },
    }


def _count_touches(levels: List[Dict], clustering_pct: float, atr: Optional[float]) -> List[Dict]:
    """
    Count how many times each level was touched/tested.
    Levels within clustering threshold are considered the same level.
    """
    if not levels:
        return []

    # Sort by price
    sorted_levels = sorted(levels, key=lambda x: x['price'])

    # Group nearby levels and count touches
    result = []
    i = 0
    while i < len(sorted_levels):
        base_level = sorted_levels[i]
        touches = 1
        total_volume = base_level.get('volume', 0)
        j = i + 1

        # Find all levels within clustering threshold
        while j < len(sorted_levels):
            pct_diff = abs(sorted_levels[j]['price'] - base_level['price']) / base_level['price'] * 100
            atr_diff = abs(sorted_levels[j]['price'] - base_level['price']) if atr else float('inf')

            if pct_diff <= clustering_pct or (atr and atr_diff <= 0.5 * atr):
                touches += 1
                total_volume += sorted_levels[j].get('volume', 0)
                j += 1
            else:
                break

        # Store aggregated level
        result.append({
            'price': base_level['price'],
            'date': base_level['date'],
            'touches': touches,
            'volume': total_volume,
        })

        i = j

    return result


def identify_key_levels(
    current_price: float,
    sr_zones: Dict[str, Any],
    max_distance_pct: float = 5.0
) -> List[Dict[str, Any]]:
    """
    Filter support/resistance zones to only include nearby, relevant levels.

    Args:
        current_price: Current underlying price
        sr_zones: Output from calculate_support_resistance_zones()
        max_distance_pct: Maximum distance from price (percentage)

    Returns:
        List of relevant zones sorted by proximity
    """
    relevant_zones = []

    # Filter support zones
    for zone in sr_zones.get('support_zones', []):
        distance_pct = abs(current_price - zone['price']) / current_price * 100
        if distance_pct <= max_distance_pct:
            relevant_zones.append({
                **zone,
                'type': 'support',
                'distance_pct': distance_pct,
            })

    # Filter resistance zones
    for zone in sr_zones.get('resistance_zones', []):
        distance_pct = abs(zone['price'] - current_price) / current_price * 100
        if distance_pct <= max_distance_pct:
            relevant_zones.append({
                **zone,
                'type': 'resistance',
                'distance_pct': distance_pct,
            })

    # Sort by proximity
    relevant_zones = sorted(relevant_zones, key=lambda x: x['distance_pct'])

    return relevant_zones


def check_level_quality(
    price: float,
    level: Dict[str, Any],
    df: pd.DataFrame,
    atr: Optional[float] = None
) -> Dict[str, Any]:
    """
    Validate the quality and relevance of a support/resistance level.

    Args:
        price: Current price
        level: S/R zone dict
        df: Historical OHLC data
        atr: Average True Range

    Returns:
        Dict with quality assessment
    """
    # Handle timezone-aware datetime for recency calculation
    last_touch = level.get('last_touch', pd.Timestamp.now())
    now = pd.Timestamp.now(tz=last_touch.tzinfo if hasattr(last_touch, 'tzinfo') else None)

    quality = {
        'is_valid': True,
        'strength': level.get('strength', 0),
        'touches': level.get('touches', 0),
        'recency_days': (now - last_touch).days,
        'distance_atr': None,
        'assessment': 'unknown',
    }

    # Calculate distance in ATR terms
    if atr and atr > 0:
        distance = abs(price - level['price'])
        quality['distance_atr'] = distance / atr

    # Assess strength
    if level.get('touches', 0) >= 3 and level.get('strength', 0) >= 70:
        quality['assessment'] = 'strong'
    elif level.get('touches', 0) >= 2 and level.get('strength', 0) >= 50:
        quality['assessment'] = 'moderate'
    else:
        quality['assessment'] = 'weak'

    # Check if level is too old
    if quality['recency_days'] > 90:
        quality['is_valid'] = False
        quality['assessment'] = 'stale'

    return quality


# Example usage
if __name__ == "__main__":
    import yfinance as yf

    # Fetch sample data
    ticker = "AAPL"
    df = yf.download(ticker, period="3mo", interval="1d", progress=False)

    if not df.empty:
        current_price = df['Close'].iloc[-1]

        # Calculate ATR for clustering
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean().iloc[-1]

        # Calculate S/R zones
        sr_zones = calculate_support_resistance_zones(
            df=df,
            current_price=current_price,
            ticker=ticker,
            lookback_days=60,
            atr=atr,
        )

        print(f"\n{'='*60}")
        print(f"Price Action Analysis: {ticker} @ ${current_price:.2f}")
        print(f"ATR: ${atr:.2f}")
        print(f"{'='*60}\n")

        print(f"Support Zones ({len(sr_zones['support_zones'])}):")
        for zone in sr_zones['support_zones'][:5]:
            print(f"  ${zone['price']:.2f} | Touches: {zone['touches']} | "
                  f"Strength: {zone['strength']:.0f} | "
                  f"Range: ${zone['range_low']:.2f}-${zone['range_high']:.2f}")

        print(f"\nResistance Zones ({len(sr_zones['resistance_zones'])}):")
        for zone in sr_zones['resistance_zones'][:5]:
            print(f"  ${zone['price']:.2f} | Touches: {zone['touches']} | "
                  f"Strength: {zone['strength']:.0f} | "
                  f"Range: ${zone['range_low']:.2f}-${zone['range_high']:.2f}")

        print(f"\nKey Levels:")
        for k, v in sr_zones['key_levels'].items():
            if v:
                print(f"  {k}: ${v:.2f}")
