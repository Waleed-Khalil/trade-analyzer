#!/usr/bin/env python3
"""
Technical Analysis CLI
Usage: python technical_analysis_cli.py QQQ --strike 590 --type PUT --premium 0.70 --dte 0
"""

import sys
sys.path.insert(0, '/home/ubuntu/clawd/trade-analyzer/src')

from analysis.technical_analysis import run_full_analysis
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive Technical Analysis for Options Trading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python technical_analysis_cli.py QQQ
  
  # With option details
  python technical_analysis_cli.py QQQ --strike 590 --type PUT --premium 0.70 --dte 0
  
  # AAPL call analysis
  python technical_analysis_cli.py AAPL --strike 280 --type CALL --premium 0.49 --dte 1

Technical indicators explained:
  - RSI: Overbought (>70) / Oversold (<30)
  - MACD: Bullish (MACD > Signal) / Bearish (MACD < Signal)
  - IV Rank: Low (<30) = cheap options / High (>70) = expensive
  - Probability of Profit: Higher = better odds
        """
    )
    
    parser.add_argument('ticker', help='Stock ticker symbol (e.g., QQQ, AAPL, SPY)')
    parser.add_argument('--strike', type=float, help='Option strike price')
    parser.add_argument('--type', default='CALL', help='Option type: CALL or PUT')
    parser.add_argument('--premium', type=float, help='Option premium per share')
    parser.add_argument('--dte', type=int, default=0, help='Days to expiration (0=0DTE)')
    parser.add_argument('--short', action='store_true', help='Show short summary only')
    
    args = parser.parse_args()
    
    run_full_analysis(
        ticker=args.ticker,
        strike=args.strike,
        option_type=args.type,
        premium=args.premium,
        dte=args.dte
    )


if __name__ == "__main__":
    main()
