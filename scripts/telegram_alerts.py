#!/usr/bin/env python3
"""
0DTE Trade Monitor - Telegram Alert Sender
Sends alerts to Telegram channel for active trades.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def send_telegram_alert(alert_data, trade_data):
    """Send alert to Telegram using Clawdbot message tool."""
    ticker = trade_data["ticker"]
    message = alert_data["message"]
    action = alert_data.get("action", "")
    urgency = alert_data.get("urgency", "medium")
    
    # Build emoji based on type and urgency
    emoji_map = {
        "SUPPORT_BROKEN": "🛑",
        "STOP_BREACHED": "🛑",
        "LOSS_PANIC": "🚨",
        "LOSS_WARNING": "⚠️",
        "REVERSAL_DETECTED": "🔄",
        "TARGET_HIT": "🎯",
        "TRAILING_ACTIVATED": "🐢",
        "TRAILING_STOP_HIT": "🐢",
    }
    
    emoji = emoji_map.get(alert_data["type"], "⚡")
    
    # Format urgency indicator
    urgency_indicator = ""
    if urgency == "high":
        urgency_indicator = "🚨 URGENT: "
    elif urgency == "medium":
        urgency_indicator = "⚠️ "
    
    # Build the message
    formatted_message = f"""
{emoji} {urgency_indicator}{message}

📊 Action: {action}
💰 Entry: ${trade_data['entry']:.2f} | Target: ${trade_data['target']:.2f} | Stop: ${trade_data['stop']:.2f}
"""
    
    # Log to file (for debugging)
    log_file = PROJECT_ROOT / "logs" / "telegram_alerts.log"
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {alert_data['type']}: {message}\n")
    
    return formatted_message


def get_active_trades():
    """Load active trades."""
    trades_file = PROJECT_ROOT / "logs" / "active_trades.json"
    if trades_file.exists():
        with open(trades_file) as f:
            return json.load(f)
    return {}


def get_last_alert_time(trade_id):
    """Get timestamp of last alert sent for this trade."""
    alert_file = PROJECT_ROOT / "logs" / "last_alerts.json"
    if alert_file.exists():
        with open(alert_file) as f:
            alerts = json.load(f)
            return alerts.get(trade_id)
    return None


def save_alert_time(trade_id):
    """Save timestamp of last alert."""
    alert_file = PROJECT_ROOT / "logs" / "last_alerts.json"
    alerts = {}
    if alert_file.exists():
        with open(alert_file) as f:
            alerts = json.load(f)
    alerts[trade_id] = datetime.now().isoformat()
    with open(alert_file, "w") as f:
        json.dump(alerts, f)


def should_send_alert(trade_id, alert_type, urgency):
    """Check if we should send an alert (rate limiting)."""
    last_time = get_last_alert_time(trade_id)
    
    # High urgency: no rate limit
    if urgency == "high":
        return True
    
    # Medium urgency: wait 5 minutes
    if urgency == "medium":
        if not last_time:
            return True
        last = datetime.fromisoformat(last_time)
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed > 300  # 5 minutes
    
    # Low urgency: wait 10 minutes
    if not last_time:
        return True
    last = datetime.fromisoformat(last_time)
    elapsed = (datetime.now() - last).total_seconds()
    return elapsed > 600  # 10 minutes


def process_alerts_for_trading():
    """
    Called by the main monitor to process and format alerts.
    Returns list of formatted alerts ready to send.
    """
    trades = get_active_trades()
    alerts_to_send = []
    
    # This would be called from trade-monitor.py
    # Returns formatted messages
    
    return alerts_to_send


if __name__ == "__main__":
    # Test the alert formatter
    test_alert = {
        "type": "SUPPORT_BROKEN",
        "message": "MSFT support $415 broken (now $414.50)",
        "action": "CONSIDER EXITING",
        "urgency": "high",
    }
    
    test_trade = {
        "ticker": "MSFT",
        "strike": 430,
        "type": "CALL",
        "entry": 0.78,
        "stop": 0.39,
        "target": 1.55,
        "contracts": 3,
    }
    
    formatted = send_telegram_alert(test_alert, test_trade)
    print("Formatted Alert:")
    print(formatted)
