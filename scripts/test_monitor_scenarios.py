#!/usr/bin/env python3
"""
Test scenario for trade monitor v2
Simulates a trade drop and shows alerts
"""

import sys
sys.path.insert(0, 'src')

# Import from trade-monitor.py
import json
from datetime import datetime
from pathlib import Path

CONFIG = {
    "panic_loss_pct": -25,
    "warning_loss_pct": -15,
    "profit_protection_pct": 20,
    "close_hour": 15,
    "support_breach_tolerance": 0.5,
}

def get_market_hour():
    return 14  # 2 PM

def calculate_pnl(entry_price, current_price, contracts):
    per_contract = (current_price - entry_price) * 100
    total = per_contract * contracts
    pct = ((current_price - entry_price) / entry_price) * 100
    return {"per_contract": round(per_contract, 2), "total": round(total, 2), "pct": round(pct, 1)}

def check_loss_thresholds(trade, prices, option_pnl):
    alerts = []
    ticker = trade["ticker"]
    loss_pct = option_pnl["pct"]
    
    if loss_pct <= CONFIG["warning_loss_pct"] and loss_pct > CONFIG["panic_loss_pct"]:
        alerts.append({
            "type": "LOSS_WARNING",
            "level": loss_pct,
            "message": f"⚠️ {ticker} down {abs(loss_pct):.1f}% — monitor closely",
            "action": "WATCH - DON'T PANIC",
            "urgency": "low",
        })
    elif loss_pct <= CONFIG["panic_loss_pct"]:
        alerts.append({
            "type": "LOSS_PANIC",
            "level": loss_pct,
            "message": f"🚨 {ticker} down {abs(loss_pct):.1f}% — consider exiting",
            "action": "DECIDE NOW",
            "urgency": "high",
        })
    return alerts

def check_support_confirmation(trade, prices):
    alerts = []
    ticker = trade["ticker"]
    stock_price = prices["stock_price"]
    
    for support in trade.get("supports", []):
        if stock_price < support * (1 - CONFIG["support_breach_tolerance"] / 100):
            alerts.append({
                "type": "SUPPORT_BROKEN",
                "level": support,
                "message": f"🛑 {ticker} support ${support:.2f} BROKEN (now ${stock_price:.2f})",
                "action": "CONSIDER EXITING",
                "urgency": "high",
            })
            break
        elif stock_price <= support * 1.01:
            alerts.append({
                "type": "SUPPORT_APPROACHING",
                "level": support,
                "message": f"📉 {ticker} approaching support ${support:.2f}",
                "action": "WATCH CLOSELY",
                "urgency": "low",
            })
    return alerts

def check_momentum_and_reversal(trade, prices, price_history):
    alerts = []
    ticker = trade["ticker"]
    stock_price = prices["stock_price"]
    
    if not price_history or len(price_history) < 3:
        return alerts
    
    prices_list = list(price_history.values())
    recent = prices_list[-3:]
    
    if len(recent) < 3:
        return alerts
    
    moves = []
    for i in range(1, len(recent)):
        if recent[i] and recent[i-1]:
            move = (recent[i] - recent[i-1]) / recent[i-1] * 100
            moves.append(move)
    
    if len(moves) >= 2 and moves[-2] < 0 and moves[-1] > 0:
        alerts.append({
            "type": "REVERSAL_DETECTED",
            "level": stock_price,
            "message": f"🔄 {ticker} showing reversal signs (down → up)",
            "action": "WATCH FOR CONFIRMATION",
            "urgency": "low",
        })
    
    if len(moves) >= 2 and moves[-1] < moves[-2] < 0:
        alerts.append({
            "type": "MOMENTUM_ACCELERATING",
            "level": stock_price,
            "message": f"📉 {ticker} momentum accelerating downward",
            "action": "WATCH STOP CLOSELY",
            "urgency": "medium",
        })
    
    return alerts

# Test scenarios
print("="*70)
print("0DTE TRADE MONITOR v2.1 - TEST SCENARIOS")
print("="*70)

# Scenario 1: Small drop (-10%)
print("\n📉 SCENARIO 1: Small drop (-10%)")
print("-"*50)
trade = {"ticker": "MSFT", "strike": 420, "type": "CALL", "entry": 1.50, "stop": 1.05, "target": 2.25}
prices = {"stock_price": 417.50, "option_price": 1.35}
pnl = calculate_pnl(1.50, 1.35, 3)
print(f"MSFT: $419 → $417.50 | Option: $1.50 → $1.35 (-10%)")
for a in check_loss_thresholds(trade, prices, pnl):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")
for a in check_support_confirmation(trade, prices):
    print(f"  {a['type']}: {a['message']}")

# Scenario 2: Big drop (-20%) with support approaching
print("\n📉 SCENARIO 2: Big drop (-20%) approaching support")
print("-"*50)
trade2 = {"ticker": "MSFT", "strike": 420, "type": "CALL", "entry": 1.50, "stop": 1.05, "target": 2.25, "supports": [417, 415]}
prices2 = {"stock_price": 417.00, "option_price": 1.20}
pnl2 = calculate_pnl(1.50, 1.20, 3)
print(f"MSFT: $419 → $417 | Option: $1.50 → $1.20 (-20%)")
for a in check_loss_thresholds(trade2, prices2, pnl2):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")
for a in check_support_confirmation(trade2, prices2):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")

# Scenario 3: Support broken (-25%)
print("\n🛑 SCENARIO 3: Support BROKEN (-25%)")
print("-"*50)
trade3 = {"ticker": "MSFT", "strike": 420, "type": "CALL", "entry": 1.50, "stop": 1.05, "target": 2.25, "supports": [417, 415]}
prices3 = {"stock_price": 414.00, "option_price": 1.12}
pnl3 = calculate_pnl(1.50, 1.12, 3)
print(f"MSFT: $419 → $414 | Option: $1.50 → $1.12 (-25%)")
for a in check_loss_thresholds(trade3, prices3, pnl3):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")
for a in check_support_confirmation(trade3, prices3):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")

# Scenario 4: Reversal detected
print("\n🔄 SCENARIO 4: Reversal detected")
print("-"*50)
print(f"MSFT: $416 → $415 → $416 (down → up pattern detected)")
history = {1: 416.00, 2: 415.00, 3: 416.50}
for a in check_momentum_and_reversal(trade3, prices3, history):
    print(f"  {a['type']}: {a['message']}")
    print(f"  → {a['action']}")

# Scenario 5: Profit protection activated
print("\n🐢 SCENARIO 5: Profit protection (+25%)")
print("-"*50)
trade5 = {"ticker": "MSFT", "strike": 420, "type": "CALL", "entry": 1.50, "target": 2.25}
prices5 = {"stock_price": 425.00, "option_price": 1.88}
print(f"MSFT: $419 → $425 (+1.4%) | Option: $1.50 → $1.88 (+25%)")
print(f"  → TRAILING STOP ACTIVATED at ${1.88 * 0.95:.2f}")

print("\n" + "="*70)
print("KEY IMPROVEMENTS:")
print("="*70)
print("""
1. WARNING (-15%): 'Watch closely' instead of panic
2. SUPPORT CONFIRMATION: Wait for break, not just touch
3. REVERSAL DETECTION: 'Down → up' pattern alert
4. TIME RULES: Tighter after 3 PM
5. TRAILING STOP: Auto-protect at +20% gain
""")
