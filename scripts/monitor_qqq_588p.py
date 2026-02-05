#!/usr/bin/env python3
"""
Simple Live Monitor for QQQ 588P
Checks every 2 minutes and logs updates.
"""

import yfinance as yf
import sys
from datetime import datetime

# Trade details
TICKER = "QQQ"
STRIKE = 588
OPTION_TYPE = "PUT"
ENTRY = 1.00
CONTRACTS = 1
STOP = 0.65
TARGET = 2.74

def get_option_price(ticker, strike, exp):
    """Try to get live option price from yfinance."""
    try:
        t = yf.Ticker(ticker)
        exp_date = exp.strftime("%Y-%m-%d")
        opts = t.option_chain(exp_date)
        
        if OPTION_TYPE == "PUT":
            opts = puts = opts.puts
        else:
            opts = calls = opts.calls
        
        # Find the strike
        for _, row in opts.iterrows():
            if abs(row['strike'] - strike) < 0.5:
                return row.get('lastTradePrice') or row.get('bid') or row.get('ask') or ENTRY
    except:
        pass
    return ENTRY  # Fallback

def check_trade():
    """Check the trade and print status."""
    now = datetime.now().strftime("%H:%M")
    
    # Get stock price
    stock = yf.Ticker(TICKER)
    stock_price = stock.history(period="1d")["Close"].iloc[-1]
    
    # Get option price
    exp = stock.options[0] if stock.options else "2026-02-05"
    opt_price = get_option_price(TICKER, STRIKE, exp)
    
    # Calculate P/L
    pnl = (opt_price - ENTRY) * 100 * CONTRACTS
    pnl_pct = (opt_price - ENTRY) / ENTRY * 100
    
    # ITM/OTM status
    if OPTION_TYPE == "CALL":
        itm_amount = stock_price - STRIKE
    else:
        itm_amount = STRIKE - stock_price
    
    status = "ITM" if itm_amount > 0 else "OTM"
    
    # Alert levels
    alerts = []
    if opt_price <= STOP:
        alerts.append("🚨 STOP HIT")
    elif opt_price >= TARGET:
        alerts.append("🎯 TARGET HIT")
    elif pnl_pct <= -15:
        alerts.append("⚠️ DOWN 15%")
    elif pnl_pct >= 50:
        alerts.append("📈 UP 50%")
    
    alert_str = " | " + " ".join(alerts) if alerts else ""
    
    print(f"[{now}] {TICKER} {STRIKE}{OPTION_TYPE[0]} | {opt_price:.2f} ({pnl_pct:+.1f}%) | Stock: {stock_price:.2f} ({status} {abs(itm_amount):.2f}) | Stop: {STOP} | Target: {TARGET}{alert_str}")
    
    return opt_price

if __name__ == "__main__":
    check_trade()
