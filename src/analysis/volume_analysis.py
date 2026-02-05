"""
Volume Analysis Module
VWAP, volume profile, anomaly detection, and volume confirmation
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime


def calculate_vwap(df: pd.DataFrame, period: str = 'daily') -> pd.Series:
    """
    Calculate Volume-Weighted Average Price (VWAP).

    VWAP = Sum(Price * Volume) / Sum(Volume)
    Acts as dynamic support/resistance based on institutional average price.

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
        period: 'daily' (reset each day) or 'rolling' (cumulative)

    Returns:
        Series with VWAP values
    """
    if df is None or len(df) == 0:
        return pd.Series()

    # Typical price = (High + Low + Close) / 3
    typical_price = (df['high'] + df['low'] + df['close']) / 3

    # VWAP calculation
    if period == 'daily':
        # Reset VWAP each day
        if isinstance(df.index, pd.DatetimeIndex):
            # Group by date and calculate VWAP
            df_copy = df.copy()
            df_copy['typical_price'] = typical_price
            df_copy['pv'] = typical_price * df['volume']

            # Cumulative sum within each day
            df_copy['date'] = df_copy.index.date
            df_copy['cum_pv'] = df_copy.groupby('date')['pv'].cumsum()
            df_copy['cum_volume'] = df_copy.groupby('date')['volume'].cumsum()

            vwap = df_copy['cum_pv'] / df_copy['cum_volume']
        else:
            # If no datetime index, use simple cumulative
            pv = typical_price * df['volume']
            vwap = pv.cumsum() / df['volume'].cumsum()
    else:
        # Rolling/cumulative VWAP
        pv = typical_price * df['volume']
        vwap = pv.cumsum() / df['volume'].cumsum()

    return vwap


def build_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 50,
    value_area_pct: float = 0.70
) -> Dict[str, Any]:
    """
    Create volume profile (histogram of volume at price levels).

    Identifies:
    - POC (Point of Control): Price level with highest volume
    - Value Area: Price range containing 70% of volume
    - High/Low volume nodes (support/resistance)

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume'
        price_bins: Number of price bins for histogram
        value_area_pct: Percentage of volume for value area (default 0.70)

    Returns:
        Dict with POC, value_area_high, value_area_low, profile data
    """
    if df is None or len(df) == 0:
        return {'poc': None, 'value_area_high': None, 'value_area_low': None}

    # Get price range
    price_min = df['low'].min()
    price_max = df['high'].max()

    # Create price bins
    bin_edges = np.linspace(price_min, price_max, price_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Distribute volume across price bins
    volume_profile = np.zeros(price_bins)

    for idx, row in df.iterrows():
        # For each bar, distribute its volume across bins it touched
        bar_low = row['low']
        bar_high = row['high']
        bar_volume = row['volume']

        # Find bins within this bar's range
        relevant_bins = (bin_centers >= bar_low) & (bin_centers <= bar_high)
        num_bins = relevant_bins.sum()

        if num_bins > 0:
            # Distribute volume evenly across touched bins
            volume_profile[relevant_bins] += bar_volume / num_bins

    # Find POC (Point of Control) - highest volume bin
    poc_idx = np.argmax(volume_profile)
    poc_price = bin_centers[poc_idx]

    # Calculate Value Area (70% of volume)
    total_volume = volume_profile.sum()
    target_volume = total_volume * value_area_pct

    # Start from POC and expand outward
    value_area_indices = {poc_idx}
    current_volume = volume_profile[poc_idx]

    # Expand to adjacent bins until we reach target volume
    lower_idx = poc_idx - 1
    upper_idx = poc_idx + 1

    while current_volume < target_volume and (lower_idx >= 0 or upper_idx < price_bins):
        # Check which side has more volume
        lower_vol = volume_profile[lower_idx] if lower_idx >= 0 else 0
        upper_vol = volume_profile[upper_idx] if upper_idx < price_bins else 0

        if lower_vol >= upper_vol and lower_idx >= 0:
            value_area_indices.add(lower_idx)
            current_volume += lower_vol
            lower_idx -= 1
        elif upper_idx < price_bins:
            value_area_indices.add(upper_idx)
            current_volume += upper_vol
            upper_idx += 1
        else:
            break

    # Value area bounds
    va_indices = sorted(list(value_area_indices))
    value_area_low = bin_centers[va_indices[0]]
    value_area_high = bin_centers[va_indices[-1]]

    # Find high and low volume nodes (potential S/R)
    # High volume nodes: bins with > 1.5x average volume
    avg_volume = total_volume / price_bins
    high_volume_nodes = []
    low_volume_nodes = []

    for i, vol in enumerate(volume_profile):
        if vol > avg_volume * 1.5:
            high_volume_nodes.append({
                'price': bin_centers[i],
                'volume': vol,
                'type': 'high_volume_node'
            })
        elif vol < avg_volume * 0.5 and vol > 0:
            low_volume_nodes.append({
                'price': bin_centers[i],
                'volume': vol,
                'type': 'low_volume_node'
            })

    return {
        'poc': poc_price,
        'value_area_high': value_area_high,
        'value_area_low': value_area_low,
        'value_area_pct': value_area_pct,
        'total_volume': total_volume,
        'high_volume_nodes': high_volume_nodes,
        'low_volume_nodes': low_volume_nodes,
        'profile_data': {
            'bin_centers': bin_centers.tolist(),
            'volume_profile': volume_profile.tolist(),
        }
    }


def detect_volume_anomalies(
    df: pd.DataFrame,
    lookback: int = 20,
    threshold_multiplier: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Detect unusual volume spikes or drops.

    Args:
        df: DataFrame with 'volume' column
        lookback: Period for average volume calculation
        threshold_multiplier: Volume multiplier for anomaly detection

    Returns:
        List of anomaly dicts with date, volume, avg_volume, type
    """
    if df is None or len(df) < lookback:
        return []

    anomalies = []

    # Calculate rolling average volume
    avg_volume = df['volume'].rolling(window=lookback).mean()

    for idx in range(lookback, len(df)):
        current_vol = df['volume'].iloc[idx]
        avg_vol = avg_volume.iloc[idx]

        if avg_vol == 0:
            continue

        vol_ratio = current_vol / avg_vol

        # Volume spike (high volume = institutional interest)
        if vol_ratio >= threshold_multiplier:
            anomalies.append({
                'date': df.index[idx],
                'volume': current_vol,
                'avg_volume': avg_vol,
                'ratio': vol_ratio,
                'type': 'spike',
                'price': df['close'].iloc[idx],
            })

        # Volume dry-up (low volume = caution, potential reversal)
        elif vol_ratio <= (1 / threshold_multiplier):
            anomalies.append({
                'date': df.index[idx],
                'volume': current_vol,
                'avg_volume': avg_vol,
                'ratio': vol_ratio,
                'type': 'dryup',
                'price': df['close'].iloc[idx],
            })

    return anomalies


def volume_confirmation(
    price_move_pct: float,
    volume_change_pct: float,
    threshold: float = 50.0
) -> Dict[str, Any]:
    """
    Check if price move is confirmed by volume.

    Strong moves should be accompanied by above-average volume.
    Moves without volume are more likely false breakouts.

    Args:
        price_move_pct: Percentage price change
        volume_change_pct: Percentage volume change vs average
        threshold: Minimum volume increase required for confirmation

    Returns:
        Dict with confirmed (bool), strength, reasoning
    """
    confirmed = False
    strength = "weak"
    reasoning = ""

    abs_price_move = abs(price_move_pct)

    if abs_price_move < 1.0:
        # Small move - volume less relevant
        confirmed = True
        strength = "neutral"
        reasoning = "Small price move - volume confirmation not critical"
    elif abs_price_move >= 2.0 and volume_change_pct >= threshold:
        # Strong move with volume = confirmed
        confirmed = True
        strength = "strong"
        reasoning = f"Strong {abs_price_move:.1f}% move with {volume_change_pct:.0f}% volume increase"
    elif abs_price_move >= 2.0 and volume_change_pct < threshold:
        # Strong move without volume = suspicious
        confirmed = False
        strength = "weak"
        reasoning = f"Strong {abs_price_move:.1f}% move without volume support - potential false breakout"
    elif abs_price_move >= 1.0 and volume_change_pct >= threshold * 0.5:
        # Moderate move with moderate volume
        confirmed = True
        strength = "moderate"
        reasoning = f"Moderate {abs_price_move:.1f}% move with {volume_change_pct:.0f}% volume increase"
    else:
        confirmed = False
        strength = "weak"
        reasoning = f"Price move {abs_price_move:.1f}% not confirmed by volume"

    return {
        'confirmed': confirmed,
        'strength': strength,
        'reasoning': reasoning,
        'price_move_pct': price_move_pct,
        'volume_change_pct': volume_change_pct,
    }


def analyze_volume_trend(df: pd.DataFrame, period: int = 10) -> Dict[str, Any]:
    """
    Analyze volume trend over recent period.

    Args:
        df: DataFrame with 'volume' column
        period: Number of periods to analyze

    Returns:
        Dict with trend direction, strength, and analysis
    """
    if df is None or len(df) < period:
        return {'trend': 'unknown', 'strength': 0}

    recent_volume = df['volume'].iloc[-period:]
    avg_recent = recent_volume.mean()

    # Compare to longer period
    if len(df) >= period * 2:
        older_volume = df['volume'].iloc[-period*2:-period]
        avg_older = older_volume.mean()
    else:
        avg_older = df['volume'].mean()

    if avg_older == 0:
        return {'trend': 'unknown', 'strength': 0}

    change_pct = ((avg_recent - avg_older) / avg_older) * 100

    # Determine trend
    if change_pct > 20:
        trend = 'increasing'
        strength = 'strong' if change_pct > 50 else 'moderate'
    elif change_pct < -20:
        trend = 'decreasing'
        strength = 'strong' if change_pct < -50 else 'moderate'
    else:
        trend = 'stable'
        strength = 'neutral'

    return {
        'trend': trend,
        'strength': strength,
        'change_pct': change_pct,
        'avg_recent': avg_recent,
        'avg_older': avg_older,
        'interpretation': _interpret_volume_trend(trend, strength),
    }


def _interpret_volume_trend(trend: str, strength: str) -> str:
    """Interpret what volume trend means for trading."""
    if trend == 'increasing' and strength == 'strong':
        return "Strong institutional interest - increased conviction in direction"
    elif trend == 'increasing':
        return "Moderate interest increase - trend gaining participation"
    elif trend == 'decreasing' and strength == 'strong':
        return "Sharp volume decline - trend losing momentum, caution"
    elif trend == 'decreasing':
        return "Declining interest - potential exhaustion or consolidation"
    else:
        return "Stable volume - consistent participation"


def check_price_vs_vwap(current_price: float, vwap: float) -> Dict[str, Any]:
    """
    Check current price position relative to VWAP.

    Args:
        current_price: Current underlying price
        vwap: Current VWAP value

    Returns:
        Dict with position, deviation, signal
    """
    if vwap is None or vwap == 0:
        return {'position': 'unknown', 'deviation_pct': 0}

    deviation_pct = ((current_price - vwap) / vwap) * 100

    if abs(deviation_pct) < 0.5:
        position = 'at_vwap'
        signal = 'neutral'
        interpretation = "Price near institutional average - neutral"
    elif deviation_pct > 2.0:
        position = 'above_vwap'
        signal = 'mean_reversion_risk'
        interpretation = f"Price {deviation_pct:.1f}% above VWAP - overextended, mean reversion risk"
    elif deviation_pct > 0:
        position = 'above_vwap'
        signal = 'bullish'
        interpretation = f"Price {deviation_pct:.1f}% above VWAP - bullish positioning"
    elif deviation_pct < -2.0:
        position = 'below_vwap'
        signal = 'mean_reversion_opportunity'
        interpretation = f"Price {deviation_pct:.1f}% below VWAP - oversold, bounce opportunity"
    else:
        position = 'below_vwap'
        signal = 'bearish'
        interpretation = f"Price {deviation_pct:.1f}% below VWAP - bearish positioning"

    return {
        'position': position,
        'deviation_pct': deviation_pct,
        'signal': signal,
        'interpretation': interpretation,
        'vwap': vwap,
        'current_price': current_price,
    }


# Example usage
if __name__ == "__main__":
    import yfinance as yf

    ticker = "AAPL"
    df = yf.download(ticker, period="1mo", interval="1d", progress=False)

    if not df.empty:
        print(f"\n{'='*60}")
        print(f"Volume Analysis: {ticker}")
        print(f"{'='*60}\n")

        # VWAP
        vwap = calculate_vwap(df)
        current_price = df['close'].iloc[-1]
        current_vwap = vwap.iloc[-1]

        print(f"Current Price: ${current_price:.2f}")
        print(f"Current VWAP: ${current_vwap:.2f}")

        vwap_check = check_price_vs_vwap(current_price, current_vwap)
        print(f"Position: {vwap_check['position']} ({vwap_check['deviation_pct']:.2f}%)")
        print(f"Signal: {vwap_check['signal']}")
        print(f"  {vwap_check['interpretation']}\n")

        # Volume Profile
        profile = build_volume_profile(df)
        print(f"Volume Profile:")
        print(f"  POC (Point of Control): ${profile['poc']:.2f}")
        print(f"  Value Area: ${profile['value_area_low']:.2f} - ${profile['value_area_high']:.2f}")
        print(f"  High Volume Nodes: {len(profile['high_volume_nodes'])}")
        print(f"  Low Volume Nodes: {len(profile['low_volume_nodes'])}\n")

        # Volume anomalies
        anomalies = detect_volume_anomalies(df)
        recent_anomalies = [a for a in anomalies if (datetime.now() - a['date']).days <= 5]
        print(f"Recent Volume Anomalies (last 5 days): {len(recent_anomalies)}")
        for anom in recent_anomalies[-3:]:
            print(f"  {anom['date'].date()}: {anom['type'].upper()} - "
                  f"{anom['ratio']:.1f}x average volume at ${anom['price']:.2f}")

        # Volume trend
        vol_trend = analyze_volume_trend(df)
        print(f"\nVolume Trend: {vol_trend['trend']} ({vol_trend['strength']})")
        print(f"  Change: {vol_trend['change_pct']:.1f}%")
        print(f"  {vol_trend['interpretation']}")
