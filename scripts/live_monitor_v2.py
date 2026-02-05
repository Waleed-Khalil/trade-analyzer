#!/usr/bin/env python3
"""
0DTE Trade Monitor v2.1 - LIVE
Uses Massive API for live option prices + Telegram alerts.

Setup for Telegram:
1. Get your Telegram chat ID (@userinfobot on Telegram)
2. Add to .env: TELEGRAM_CHAT_ID=your_chat_id
"""

import sys
sys.path.insert(0, '/home/ubuntu/clawd/trade-analyzer/src')

from market_data.polygon_client import get_option_snapshot
from datetime import datetime
import json
import os

# Trade Configuration
TRADE = {
    "ticker": "QQQ",
    "strike": 588,
    "type": "PUT",
    "entry": 1.00,
    "stop": 0.65,
    "target": 2.74,
    "expiration": "2026-02-05",
    "contract_type": "put",
}

# Alert thresholds
ALERTS = {
    "target": 2.74,
    "stop": 0.65,
    "down_15": -15,
    "down_25": -25,
    "up_50": 50,
}

last_alerts = {}

def send_telegram(message):
    """Send alert to Telegram via Clawdbot."""
    import subprocess
    
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        print(f"         ⚠️ TELEGRAM_CHAT_ID not set")
        return False
    
    try:
        result = subprocess.run([
            "clawdbot", "message", "send",
            "--channel", "telegram",
            "--target", chat_id,
            "--message", message
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            print(f"         ⚠️ Telegram failed: {result.stderr[:100]}")
            return False
    except Exception as e:
        print(f"         ⚠️ Telegram error: {e}")
        return False

def check_alerts(pnl_pct, opt_price):
    """Check if alerts should trigger."""
    alerts = []
    
    if opt_price >= ALERTS["target"]:
        alerts.append({
            "type": "TARGET_HIT",
            "message": "🎯 TARGET HIT - TAKE PROFIT",
            "urgency": "high",
            "action": "Take profit + trail runner"
        })
    elif pnl_pct <= ALERTS["down_25"]:
        alerts.append({
            "type": "LOSS_PANIC",
            "message": "🚨 DOWN 25% - CONSIDER EXITING",
            "urgency": "high",
            "action": "Decide: cut or hold?"
        })
    elif pnl_pct <= ALERTS["down_15"]:
        alerts.append({
            "type": "LOSS_WARNING",
            "message": "⚠️ DOWN 15% - WATCH CLOSELY",
            "urgency": "medium",
            "action": "Don't panic - normal volatility"
        })
    elif pnl_pct >= ALERTS["up_50"]:
        alerts.append({
            "type": "PROFIT_RALLY",
            "message": "📈 UP 50% - NICE RUN",
            "urgency": "low",
            "action": "Consider taking partial"
        })
    elif opt_price <= ALERTS["stop"] * 1.1:
        alerts.append({
            "type": "APPROACHING_STOP",
            "message": f"📉 Approaching stop ${ALERTS['stop']:.2f}",
            "urgency": "medium",
            "action": "Watch closely"
        })
    
    return alerts

def get_live_price():
    """Get live option price from Massive API."""
    snapshot = get_option_snapshot(
        underlying_asset=TRADE["ticker"],
        strike_price=TRADE["strike"],
        expiration_date=TRADE["expiration"],
        contract_type=TRADE["contract_type"],
    )
    
    if snapshot:
        return snapshot.get("last"), snapshot
    return None, None

def run_check():
    """Run a single check."""
    global last_alerts
    
    opt_price, snapshot = get_live_price()
    
    if opt_price is None:
        print(f"[{datetime.now().strftime('%H:%M')}] Could not fetch live price")
        return
    
    pnl = (opt_price - TRADE["entry"]) * 100
    pnl_pct = (opt_price - TRADE["entry"]) / TRADE["entry"] * 100
    
    alerts = check_alerts(pnl_pct, opt_price)
    alert_str = " | " + " | ".join(a["message"] for a in alerts) if alerts else ""
    
    # Print to console
    print(f"[{datetime.now().strftime('%H:%M')}] {TRADE['ticker']} {TRADE['strike']}{TRADE['type']} | ${opt_price:.2f} ({pnl_pct:+.1f}%){alert_str}")
    print(f"         Stop: ${ALERTS['stop']} | Target: ${ALERTS['target']}")
    
    # Send Telegram alerts (rate-limited)
    trade_id = f"{TRADE['ticker']}-{TRADE['strike']}-{TRADE['expiration']}"
    
    for alert in alerts:
        key = f"{trade_id}-{alert['type']}"
        last_time = last_alerts.get(key)
        if last_time:
            last = datetime.fromisoformat(last_time)
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed < 300:
                continue
        
        message = f"""
{alert['message']}

📊 {TRADE['ticker']} {TRADE['strike']}{TRADE['type']} @ ${TRADE['entry']:.2f}
Current: ${opt_price:.2f} ({pnl_pct:+.1f}%)
Stop: ${ALERTS['stop']} | Target: ${ALERTS['target']}

Action: {alert['action']}
"""
        if os.getenv("TELEGRAM_CHAT_ID"):
            send_telegram(message)
        else:
            print(f"         → Would send: {alert['type']}")
        
        last_alerts[key] = datetime.now().isoformat()

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 0DTE TRADE MONITOR v2.1 + TELEGRAM ALERTS")
    print("=" * 50)
    print()
    print(f"Trade: {TRADE['ticker']} {TRADE['strike']}{TRADE['type']} @ ${TRADE['entry']:.2f}")
    print(f"Stop: ${ALERTS['stop']} | Target: ${ALERTS['target']}")
    print()
    print("To enable Telegram: Add TELEGRAM_CHAT_ID to .env")
    print()
    run_check()
