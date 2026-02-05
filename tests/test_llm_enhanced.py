"""
Test LLM-Enhanced Analysis Output
Demonstrates the natural language explanations and recommendations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import yfinance as yf
import pandas as pd
from datetime import datetime

# Import modules
from analysis.price_action import calculate_support_resistance_zones
from analysis.volume_analysis import (
    calculate_vwap,
    build_volume_profile,
    check_price_vs_vwap,
    analyze_volume_trend
)
from analysis.candlestick_patterns import get_pattern_signals
from analysis.trend_analysis import identify_trend, calculate_adx

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


def test_llm_enhanced_analysis(ticker="AAPL", option_type="CALL"):
    """Test with LLM-enhanced output."""

    print("=" * 80)
    print(f"LLM-ENHANCED ANALYSIS TEST: {ticker} {option_type}")
    print("=" * 80)

    # Fetch data
    print("\n[1/6] Fetching market data...")
    df = yf.download(ticker, period="3mo", interval="1d", progress=False)

    # Handle columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(col).lower() for col in df.columns]

    current_price = float(df['close'].iloc[-1])
    atr = calculate_atr(df)

    print(f"OK - Current Price: ${current_price:.2f}, ATR: ${atr:.2f}")

    # Run all analysis
    print("\n[2/6] Running technical analysis...")

    # Price action
    sr_zones = calculate_support_resistance_zones(
        df=df, current_price=current_price, ticker=ticker,
        lookback_days=60, min_touches=2, atr=atr
    )

    # Volume
    vwap = calculate_vwap(df)
    current_vwap = float(vwap.iloc[-1])
    vwap_check = check_price_vs_vwap(current_price, current_vwap)
    profile = build_volume_profile(df)
    vol_trend = analyze_volume_trend(df)

    # Patterns
    patterns = get_pattern_signals(df, lookback=10)

    # Trend
    trend = identify_trend(df, method='swing_points')
    adx = calculate_adx(df)

    print("OK - All technical modules complete")

    # Build market context
    print("\n[3/6] Building market context...")
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
    print("\n[4/6] Creating trade scenario...")
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    parser = TradeParser()
    strike = int(current_price * 1.02)
    premium = 2.50
    trade_str = f"{ticker} {option_type} {strike} @ {premium}"
    trade = parser.parse(trade_str)

    print(f"Trade: {ticker} {option_type} ${strike} @ ${premium}")

    # Run analysis with LLM
    print("\n[5/6] Running LLM-enhanced analysis...")
    print("(This may take a few seconds...)")

    risk_engine = RiskEngine(config_path)
    trade_plan = risk_engine.create_trade_plan(trade, current_price, market_context)

    analyzer = TradeAnalyzer(config_path)
    analysis = analyzer.analyze(trade, trade_plan, current_price, market_context)

    # Display results
    print("\n[6/6] Analysis Complete!")
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)

    print(f"\n{'SETUP SCORE':.<50} {analysis.setup_score}/100")
    print(f"{'Quality':.<50} {analysis.setup_quality}")
    print(f"{'Confidence':.<50} {analysis.confidence:.0%}")

    # Score breakdown
    if analysis.score_breakdown:
        print(f"\nScore Breakdown:")
        for component, value in analysis.score_breakdown.items():
            if value != 0:
                print(f"  {component:.<40} {value:>+4d}")

    # Red flags
    print(f"\n{'RED FLAGS'} ({len(analysis.red_flags)})")
    print("-" * 80)
    for flag in analysis.red_flags:
        print(f"[{flag['severity'].upper()}] {flag['message']}")

    # Green flags
    print(f"\n{'GREEN FLAGS'} ({len(analysis.green_flags)})")
    print("-" * 80)
    for flag in analysis.green_flags:
        print(f"[OK] {flag['message']}")

    # LLM-Enhanced Output
    print("\n" + "=" * 80)
    print("LLM-ENHANCED ANALYSIS")
    print("=" * 80)

    if analysis.enhanced_summary:
        print(f"\n{'ENHANCED SUMMARY':^80}")
        print("-" * 80)
        print(analysis.enhanced_summary)

    if analysis.market_narrative:
        print(f"\n{'MARKET CONTEXT':^80}")
        print("-" * 80)
        print(analysis.market_narrative)

    if analysis.trade_reasoning:
        print(f"\n{'TRADE REASONING':^80}")
        print("-" * 80)
        print(analysis.trade_reasoning)

    if analysis.recommendations:
        print(f"\n{'RECOMMENDATIONS':^80}")
        print("-" * 80)
        print(analysis.recommendations)

    # Final recommendation
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATION")
    print("=" * 80)

    if analysis.setup_score >= 90:
        rec = "STRONG PLAY (1.5x position size)"
    elif analysis.setup_score >= 75:
        rec = "PLAY (1.0x position size)"
    elif analysis.setup_score >= 60:
        rec = "CAUTIOUS (0.75x position size)"
    else:
        rec = "AVOID - Score too low"

    print(f"\n{rec}")
    print(f"Score: {analysis.setup_score}/100")
    print(f"High Severity Red Flags: {sum(1 for f in analysis.red_flags if f.get('severity') == 'high')}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("WARNING: ANTHROPIC_API_KEY not set!")
        print("LLM features will be disabled.")
        print("\nTo enable LLM analysis:")
        print("  Windows: set ANTHROPIC_API_KEY=your_key_here")
        print("  Linux/Mac: export ANTHROPIC_API_KEY=your_key_here")
        print("\nContinuing with rule-based analysis only...\n")

    # Run test
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    option_type = sys.argv[2] if len(sys.argv) > 2 else "CALL"

    test_llm_enhanced_analysis(ticker, option_type)
