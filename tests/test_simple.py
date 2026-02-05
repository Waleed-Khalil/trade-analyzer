"""
Simple test of enhanced analysis - Windows compatible
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import yfinance as yf
import pandas as pd
from datetime import datetime

# Import new modules
from analysis.price_action import calculate_support_resistance_zones
from analysis.volume_analysis import (
    calculate_vwap,
    build_volume_profile,
    check_price_vs_vwap,
    analyze_volume_trend
)
from analysis.candlestick_patterns import get_pattern_signals
from analysis.trend_analysis import identify_trend, calculate_adx

# Import existing
from parser.trade_parser import TradeParser
from risk_engine.risk_engine import RiskEngine
from analysis.trade_analyzer import TradeAnalyzer


def calculate_atr(df, period=14):
    """Calculate ATR."""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return float(true_range.rolling(period).mean().iloc[-1])


print("=" * 80)
print("ENHANCED ANALYSIS TEST - AAPL CALL")
print("=" * 80)

# Fetch data
print("\n[1/5] Fetching market data...")
ticker = "AAPL"
df = yf.download(ticker, period="3mo", interval="1d", progress=False)

# Handle multi-level columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df.columns = [str(col).lower() for col in df.columns]

current_price = float(df['close'].iloc[-1])
atr = calculate_atr(df)

print(f"OK - {len(df)} bars loaded")
print(f"Current Price: ${current_price:.2f}")
print(f"ATR: ${atr:.2f}")

# Test 1: Price Action
print("\n[2/5] Testing price action analysis...")
sr_zones = calculate_support_resistance_zones(
    df=df,
    current_price=current_price,
    ticker=ticker,
    lookback_days=60,
    min_touches=2,
    atr=atr
)

support_zones = sr_zones.get('support_zones', [])
resistance_zones = sr_zones.get('resistance_zones', [])

print(f"OK - Found {len(support_zones)} support zones, {len(resistance_zones)} resistance zones")

if support_zones:
    nearest_sup = support_zones[0]
    print(f"Nearest Support: ${nearest_sup['price']:.2f} (touches: {nearest_sup['touches']}, strength: {nearest_sup['strength']:.0f})")

if resistance_zones:
    nearest_res = resistance_zones[0]
    print(f"Nearest Resistance: ${nearest_res['price']:.2f} (touches: {nearest_res['touches']}, strength: {nearest_res['strength']:.0f})")

# Test 2: Volume
print("\n[3/5] Testing volume analysis...")
vwap = calculate_vwap(df)
current_vwap = float(vwap.iloc[-1])
vwap_check = check_price_vs_vwap(current_price, current_vwap)

print(f"OK - VWAP: ${current_vwap:.2f}")
print(f"Position: {vwap_check['position']}, Signal: {vwap_check['signal']}")

profile = build_volume_profile(df)
print(f"POC: ${profile['poc']:.2f}")

vol_trend = analyze_volume_trend(df)
print(f"Volume Trend: {vol_trend['trend']} ({vol_trend['change_pct']:.1f}%)")

# Test 3: Patterns
print("\n[4/5] Testing candlestick patterns...")
patterns = get_pattern_signals(df, lookback=10)
print(f"OK - Found {len(patterns)} patterns")

if patterns:
    for p in patterns[-3:]:
        print(f"  {p['pattern']}: {p['direction']} (strength: {p['strength']:.0f})")

# Test 4: Trend
print("\n[5/5] Testing trend analysis...")
trend = identify_trend(df, method='swing_points')
adx = calculate_adx(df)
current_adx = float(adx.iloc[-1])

print(f"OK - Trend: {trend['direction']} (strength: {trend['strength']}/100)")
print(f"ADX: {current_adx:.1f}")

# Build context and test integrated analysis
print("\n" + "=" * 80)
print("INTEGRATED ANALYSIS - OLD VS NEW")
print("=" * 80)

market_context = {
    'current_price': current_price,
    'sr_analysis': sr_zones,
    'volume_analysis': {
        'vwap': current_vwap,
        'vwap_check': vwap_check,
        'profile': profile,
        'vol_trend': vol_trend
    },
    'candlestick_patterns': patterns,
    'trend_analysis': trend
}

# Parse trade
parser = TradeParser()
strike = int(current_price * 1.02)  # 2% OTM call
premium = 2.50
trade_str = f"{ticker} CALL {strike} @ {premium}"
trade = parser.parse(trade_str)

print(f"\nTrade: {ticker} CALL ${strike} @ ${premium}")

# OLD approach (no context)
print("\n--- OLD APPROACH (no enhanced analysis) ---")
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
risk_engine = RiskEngine(config_path)
old_plan = risk_engine.create_trade_plan(trade, current_price, None)

analyzer = TradeAnalyzer(config_path)
old_analysis = analyzer.analyze(trade, old_plan, current_price, {})

print(f"Setup Score: {old_analysis.setup_score}/100")
print(f"Red Flags: {len(old_analysis.red_flags)}")
print(f"Green Flags: {len(old_analysis.green_flags)}")

# NEW approach (with context)
print("\n--- NEW APPROACH (with enhanced analysis) ---")
new_plan = risk_engine.create_trade_plan(trade, current_price, market_context)
new_analysis = analyzer.analyze(trade, new_plan, current_price, market_context)

print(f"Setup Score: {new_analysis.setup_score}/100")
print(f"Red Flags: {len(new_analysis.red_flags)}")
for flag in new_analysis.red_flags[:5]:
    print(f"  [{flag['severity']}] {flag['message']}")

print(f"Green Flags: {len(new_analysis.green_flags)}")
for flag in new_analysis.green_flags[:5]:
    print(f"  [OK] {flag['message']}")

# Score breakdown
if new_analysis.score_breakdown:
    print("\nScore Breakdown:")
    for k, v in new_analysis.score_breakdown.items():
        if v != 0:
            print(f"  {k}: {v:+d}")

# Comparison
print("\n" + "=" * 80)
print("RESULTS COMPARISON")
print("=" * 80)

improvement = new_analysis.setup_score - old_analysis.setup_score
print(f"\nSetup Score: {old_analysis.setup_score} -> {new_analysis.setup_score} ({improvement:+d} points)")
print(f"Red Flags: {len(old_analysis.red_flags)} -> {len(new_analysis.red_flags)}")
print(f"Green Flags: {len(old_analysis.green_flags)} -> {len(new_analysis.green_flags)}")

# Recommendation
print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

if new_analysis.setup_score >= 90:
    print("\nSTRONG PLAY (1.5x position size)")
elif new_analysis.setup_score >= 75:
    print("\nPLAY (1.0x position size)")
elif new_analysis.setup_score >= 60:
    print("\nCAUTIOUS (0.75x position size)")
else:
    print("\nAVOID - Score too low")

print(f"\nFinal Score: {new_analysis.setup_score}/100")
print(f"Quality: {new_analysis.setup_quality}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
