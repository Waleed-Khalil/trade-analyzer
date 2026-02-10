"""
Quick Trade Check - Pre-Trade Go/No-Go Filter
Fast analysis: Should I take this trade right now?
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from src.analysis.price_action import calculate_support_resistance_zones
from src.analysis.trend_analysis import identify_trend, calculate_adx
from src.analysis.volume_analysis import calculate_vwap


def quick_check(
    ticker: str,
    strike: float,
    option_type: str,  # CALL or PUT
    premium: float,
    underlying_price: Optional[float] = None,
    dte: int = 7,
    iv: Optional[float] = None
) -> Dict[str, Any]:
    """
    Quick pre-trade analysis - Should you take this trade?

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        strike: Option strike price
        option_type: "CALL" or "PUT"
        premium: Option premium (entry cost)
        underlying_price: Current stock price (fetched if None)
        dte: Days to expiration (default: 7)
        iv: Implied volatility (optional)

    Returns:
        Dict with recommendation, confidence, reasons, watch levels
    """

    print(f"\n{'='*80}")
    print(f"  QUICK TRADE CHECK: {ticker} {strike} {option_type} @ ${premium:.2f}")
    print(f"{'='*80}\n")

    # Fetch current data
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        # Flatten columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [str(col).lower() for col in df.columns]

        if df.empty:
            return {
                'recommendation': 'ERROR',
                'confidence': 0,
                'reasons': ['Could not fetch market data'],
                'watch_levels': {}
            }

        # Get current price
        if underlying_price is None:
            underlying_price = df['close'].iloc[-1]

        print(f"Underlying: ${underlying_price:.2f}")
        print(f"DTE: {dte} days")
        print(f"Premium: ${premium:.2f}\n")

    except Exception as e:
        return {
            'recommendation': 'ERROR',
            'confidence': 0,
            'reasons': [f'Data fetch error: {e}'],
            'watch_levels': {}
        }

    # Calculate key metrics
    try:
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean().iloc[-1]

        # Support/Resistance zones
        sr_zones = calculate_support_resistance_zones(
            df=df,
            current_price=underlying_price,
            ticker=ticker,
            lookback_days=60,
            atr=atr,
            max_levels=5
        )

        # Trend analysis
        trend_result = identify_trend(df, underlying_price)
        trend_analysis = {
            'trend': trend_result.get('trend', 'sideways'),
            'counter_trend': False
        }

        # Check if counter-trend
        if option_type == 'CALL' and trend_result.get('trend') == 'downtrend':
            trend_analysis['counter_trend'] = True
        elif option_type == 'PUT' and trend_result.get('trend') == 'uptrend':
            trend_analysis['counter_trend'] = True

        # Recent price action
        recent_5d = df['close'].iloc[-5:]
        price_change_5d = (underlying_price - recent_5d.iloc[0]) / recent_5d.iloc[0] * 100

        # Volume analysis
        avg_volume = df['volume'].tail(20).mean()
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

    except Exception as e:
        return {
            'recommendation': 'ERROR',
            'confidence': 0,
            'reasons': [f'Analysis error: {e}'],
            'watch_levels': {}
        }

    # DECISION LOGIC
    reasons = []
    red_flags = []
    green_flags = []
    confidence = 50  # Start neutral

    # 1. Check strike vs current price
    if option_type == 'CALL':
        distance_pct = (strike - underlying_price) / underlying_price * 100
        direction = 'up' if distance_pct > 0 else 'down'

        if distance_pct > 5:
            red_flags.append(f"Strike ${strike:.0f} is {distance_pct:.1f}% OTM - needs big move")
            confidence -= 15
        elif distance_pct > 2:
            red_flags.append(f"Strike {distance_pct:.1f}% OTM - moderate barrier")
            confidence -= 5
        elif distance_pct < 0:
            green_flags.append(f"Strike ${strike:.0f} ITM by {abs(distance_pct):.1f}%")
            confidence += 10
        else:
            green_flags.append(f"Strike near current price (ATM)")
            confidence += 5

    else:  # PUT
        distance_pct = (underlying_price - strike) / underlying_price * 100
        direction = 'down' if distance_pct > 0 else 'up'

        if distance_pct > 5:
            red_flags.append(f"Strike ${strike:.0f} is {distance_pct:.1f}% OTM - needs big drop")
            confidence -= 15
        elif distance_pct > 2:
            red_flags.append(f"Strike {distance_pct:.1f}% OTM")
            confidence -= 5

    # 2. Check resistance/support zones
    if option_type == 'CALL':
        resistance_zones = sr_zones.get('resistance_zones', [])
        support_zones = sr_zones.get('support_zones', [])

        # Check nearest resistance
        if resistance_zones:
            nearest_r = resistance_zones[0]
            r_distance = (nearest_r['price'] - underlying_price) / underlying_price * 100

            if r_distance < 1:
                red_flags.append(f"At resistance ${nearest_r['price']:.0f} (strength: {nearest_r['strength']:.0f}) - likely rejection")
                confidence -= 20
            elif r_distance < 2:
                red_flags.append(f"Near resistance ${nearest_r['price']:.0f} - overhead supply")
                confidence -= 10
            elif nearest_r['strength'] >= 75:
                reasons.append(f"Strong resistance at ${nearest_r['price']:.0f} - watch for breakout or rejection")

        # Check support below
        if support_zones:
            nearest_s = support_zones[0]
            s_distance = (underlying_price - nearest_s['price']) / underlying_price * 100

            if s_distance < 2:
                green_flags.append(f"Good support at ${nearest_s['price']:.0f} (strength: {nearest_s['strength']:.0f})")
                confidence += 10

    else:  # PUT
        support_zones = sr_zones.get('support_zones', [])

        if support_zones:
            nearest_s = support_zones[0]
            s_distance = (underlying_price - nearest_s['price']) / underlying_price * 100

            if s_distance < 1:
                red_flags.append(f"At support ${nearest_s['price']:.0f} - may bounce")
                confidence -= 15

    # 3. Trend analysis
    if option_type == 'CALL':
        if trend_analysis.get('counter_trend'):
            red_flags.append("Counter-trend trade (downtrend, taking calls)")
            confidence -= 15
        elif trend_analysis.get('trend') == 'uptrend':
            green_flags.append("With the trend (uptrend)")
            confidence += 15
    else:
        if trend_analysis.get('counter_trend'):
            red_flags.append("Counter-trend trade (uptrend, taking puts)")
            confidence -= 15
        elif trend_analysis.get('trend') == 'downtrend':
            green_flags.append("With the trend (downtrend)")
            confidence += 15

    # 4. Recent momentum
    if option_type == 'CALL':
        if price_change_5d > 3:
            green_flags.append(f"Strong 5-day momentum: +{price_change_5d:.1f}%")
            confidence += 10
        elif price_change_5d < -3:
            red_flags.append(f"Negative momentum: {price_change_5d:.1f}% (5d)")
            confidence -= 10
    else:
        if price_change_5d < -3:
            green_flags.append(f"Bearish momentum: {price_change_5d:.1f}% (5d)")
            confidence += 10
        elif price_change_5d > 3:
            red_flags.append(f"Against momentum: +{price_change_5d:.1f}% (5d)")
            confidence -= 10

    # 5. Volume
    if volume_ratio > 1.5:
        green_flags.append(f"High volume: {volume_ratio:.1f}x average")
        confidence += 5
    elif volume_ratio < 0.7:
        red_flags.append(f"Low volume: {volume_ratio:.1f}x average")
        confidence -= 5

    # 6. Time decay risk (DTE)
    if dte <= 3:
        red_flags.append(f"Short DTE ({dte}d) - high theta decay risk")
        confidence -= 10
    elif dte >= 7:
        green_flags.append(f"Good time buffer ({dte}d)")
        confidence += 5

    # 7. Premium/Risk ratio
    if premium < 0.50:
        red_flags.append("Low premium - poor R/R for stops")
        confidence -= 10
    elif premium > 2.00:
        green_flags.append("Adequate premium for risk management")
        confidence += 5

    # Clamp confidence
    confidence = max(0, min(100, confidence))

    # FINAL RECOMMENDATION
    if confidence >= 70:
        recommendation = "YES"
        rec_label = "TAKE THE TRADE"
        rec_color = "GREEN"
    elif confidence >= 50:
        recommendation = "MARGINAL"
        rec_label = "CAUTIOUS / SMALL SIZE"
        rec_color = "YELLOW"
    elif confidence >= 30:
        recommendation = "LEAN NO"
        rec_label = "LIKELY PASS"
        rec_color = "YELLOW"
    else:
        recommendation = "NO"
        rec_label = "PASS"
        rec_color = "RED"

    # Build watch levels
    watch_levels = {}

    if option_type == 'CALL':
        resistance_zones = sr_zones.get('resistance_zones', [])
        support_zones = sr_zones.get('support_zones', [])

        if resistance_zones:
            watch_levels['breakout_level'] = resistance_zones[0]['price']
            watch_levels['breakout_strength'] = resistance_zones[0]['strength']
            if len(resistance_zones) > 1:
                watch_levels['next_target'] = resistance_zones[1]['price']

        if support_zones:
            watch_levels['stop_level'] = support_zones[0]['price']
        else:
            watch_levels['stop_level'] = underlying_price * 0.97

    else:  # PUT
        support_zones = sr_zones.get('support_zones', [])
        resistance_zones = sr_zones.get('resistance_zones', [])

        if support_zones:
            watch_levels['breakdown_level'] = support_zones[0]['price']
            watch_levels['breakdown_strength'] = support_zones[0]['strength']

        if resistance_zones:
            watch_levels['stop_level'] = resistance_zones[0]['price']
        else:
            watch_levels['stop_level'] = underlying_price * 1.03

    # Print results
    print(f"{'='*80}")
    print(f"  RECOMMENDATION: {rec_label}")
    print(f"  Confidence: {confidence}%")
    print(f"{'='*80}\n")

    if green_flags:
        print("GREEN FLAGS:")
        for flag in green_flags:
            print(f"  [+] {flag}")
        print()

    if red_flags:
        print("RED FLAGS:")
        for flag in red_flags:
            print(f"  [-] {flag}")
        print()

    if recommendation in ["YES", "MARGINAL"]:
        print("IF YOU TAKE IT - KEY WATCH LEVELS:")
        print("-" * 40)

        if option_type == 'CALL':
            if 'breakout_level' in watch_levels:
                print(f"  BREAKOUT ALERT: ${watch_levels['breakout_level']:.2f}")
                print(f"    → If breaks above with volume >1.5x avg:")
                print(f"       - HOLD RUNNER (don't exit early)")
                print(f"       - Trail stop to ${watch_levels['breakout_level'] * 0.995:.2f}")
                if 'next_target' in watch_levels:
                    print(f"       - New target: ${watch_levels['next_target']:.2f}")
                print()

            print(f"  REJECTION ALERT: Watch for bearish candles near resistance")
            print(f"    → Shooting star, bearish engulfing, long upper wick:")
            print(f"       - EXIT 60-80% immediately")
            print(f"       - Lock partial profit before reversal")
            print()

            if 'stop_level' in watch_levels:
                print(f"  STOP LOSS: Below ${watch_levels['stop_level']:.2f}")
                print(f"    → Or -1R on premium (~${premium * 0.5:.2f})")

        else:  # PUT
            if 'breakdown_level' in watch_levels:
                print(f"  BREAKDOWN ALERT: ${watch_levels['breakdown_level']:.2f}")
                print(f"    → If breaks below with volume >1.5x avg:")
                print(f"       - HOLD RUNNER")
                print(f"       - Trail stop to ${watch_levels['breakdown_level'] * 1.005:.2f}")

            print(f"  REJECTION ALERT: Watch for bullish candles near support")
            print(f"    → Hammer, bullish engulfing:")
            print(f"       - EXIT 60-80% immediately")

        print()
        print(f"  TIME RISK: If no move in {max(2, dte//3)} days → theta decay accelerates")
        print()

    elif recommendation == "LEAN NO":
        print("WHY PASSING:")
        print("-" * 40)
        print(f"  Too many red flags. Wait for:")
        if option_type == 'CALL':
            print(f"  - Clear break above resistance")
            print(f"  - Strong volume confirmation")
            print(f"  - Better trend alignment")
        else:
            print(f"  - Clear break below support")
            print(f"  - Better risk/reward setup")
        print()

    else:  # NO
        print("STRONG PASS:")
        print("-" * 40)
        print("  Setup quality too low. Look for better opportunities.")
        print()

    print(f"{'='*80}\n")

    return {
        'recommendation': recommendation,
        'confidence': confidence,
        'green_flags': green_flags,
        'red_flags': red_flags,
        'watch_levels': watch_levels,
        'underlying_price': underlying_price,
        'atr': atr,
        'volume_ratio': volume_ratio,
        'sr_zones': sr_zones
    }


# CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quick trade check - Should I take this trade?")
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL)")
    parser.add_argument("strike", type=float, help="Option strike price")
    parser.add_argument("type", choices=['CALL', 'PUT', 'call', 'put'], help="Option type")
    parser.add_argument("premium", type=float, help="Option premium")
    parser.add_argument("--price", type=float, help="Current underlying price (fetched if omitted)")
    parser.add_argument("--dte", type=int, default=7, help="Days to expiration (default: 7)")
    parser.add_argument("--iv", type=float, help="Implied volatility (optional)")

    args = parser.parse_args()

    result = quick_check(
        ticker=args.ticker.upper(),
        strike=args.strike,
        option_type=args.type.upper(),
        premium=args.premium,
        underlying_price=args.price,
        dte=args.dte,
        iv=args.iv
    )
