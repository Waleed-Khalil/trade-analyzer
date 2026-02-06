#!/usr/bin/env python3
"""
0DTE Trade Monitor v2.1
Enhanced with smart exit logic, momentum detection, reversal alerts, and Telegram integration.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add project root and src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import yaml

from market_data.market_data import get_market_context
from parser.trade_parser import TradeParser
from scripts.telegram_alerts import send_telegram_alert, should_send_alert


# Load target_profit_pct from config.yaml
def _load_target_profit_pct():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        targets = cfg.get("targets", {})
        enabled = targets.get("target_profit_pct_enabled", False)
        pct = targets.get("target_profit_pct", 0.20)
        return pct if enabled else None
    except Exception:
        return None


_TARGET_PROFIT_PCT = _load_target_profit_pct()


# Configuration
CONFIG = {
    "panic_loss_pct": -25,      # Exit panic threshold
    "warning_loss_pct": -15,     # Warning threshold
    "profit_protection_pct": 20, # Trail to breakeven when up 20%
    "target_profit_pct": (_TARGET_PROFIT_PCT * 100) if _TARGET_PROFIT_PCT else 20,  # From config
    "close_hour": 15,           # After 3 PM ET, tighten stops
    "support_breach_tolerance": 0.5,  # Allow X% below support before warning
    "reversal_detection_window": 3,  # Check last N checks for reversal
}


def load_active_trades():
    """Load active trades from JSON file."""
    trades_file = PROJECT_ROOT / "logs" / "active_trades.json"
    if trades_file.exists():
        with open(trades_file) as f:
            return json.load(f)
    return {}


def save_active_trades(trades):
    """Save active trades to JSON file."""
    trades_file = PROJECT_ROOT / "logs" / "active_trades.json"
    trades_file.parent.mkdir(parents=True, exist_ok=True)
    with open(trades_file, "w") as f:
        json.dump(trades, f, indent=2)


def get_live_prices(ticker):
    """Fetch live prices for ticker."""
    try:
        context = get_market_context(ticker)
        return {
            "stock_price": context.get("current_price"),
            "volume": context.get("volume"),
            "day_high": context.get("high"),
            "day_low": context.get("low"),
        }
    except Exception as e:
        print(f"Error fetching prices for {ticker}: {e}")
        return None


def calculate_pnl(entry_price, current_price, contracts):
    """Calculate P&L for the position."""
    per_contract = (current_price - entry_price) * 100
    total = per_contract * contracts
    pct = ((current_price - entry_price) / entry_price) * 100
    return {
        "per_contract": round(per_contract, 2),
        "total": round(total, 2),
        "pct": round(pct, 1),
    }


def get_market_hour():
    """Get current market hour (ET)."""
    now = datetime.now()
    # Simplified - would use proper timezone handling
    return now.hour


def check_loss_thresholds(trade, prices, option_pnl):
    """Check loss thresholds with warning vs panic levels."""
    alerts = []
    ticker = trade["ticker"]
    loss_pct = option_pnl["pct"]
    
    # Check if we're in profit protection mode
    trailing_stop = trade.get("trailing_stop")
    
    if trailing_stop:
        # Trailing stop triggered - price fell below trailing level
        if prices["stock_price"] <= trailing_stop:
            alerts.append({
                "type": "TRAILING_STOP_HIT",
                "level": trailing_stop,
                "current": prices["stock_price"],
                "message": f"🐢 Trailing stop hit at ${trailing_stop:.2f}",
                "action": "CLOSE FOR PROFIT",
                "urgency": "medium",
            })
    
    # Check warning threshold
    elif loss_pct <= CONFIG["warning_loss_pct"] and loss_pct > CONFIG["panic_loss_pct"]:
        alerts.append({
            "type": "LOSS_WARNING",
            "level": loss_pct,
            "current": prices["stock_price"],
            "message": f"⚠️ {ticker} down {abs(loss_pct):.1f}% — monitor closely",
            "action": "WATCH - DON'T PANIC",
            "urgency": "low",
        })
    
    # Check panic threshold
    elif loss_pct <= CONFIG["panic_loss_pct"]:
        market_hour = get_market_hour()
        
        if market_hour >= CONFIG["close_hour"]:
            # After 3 PM - time is running out
            alerts.append({
                "type": "LOSS_PANIC",
                "level": loss_pct,
                "current": prices["stock_price"],
                "message": f"🚨 {ticker} down {abs(loss_pct):.1f}% — consider exiting (time running out)",
                "action": "DECIDE NOW",
                "urgency": "high",
            })
        else:
            # Before 3 PM - give it more time
            alerts.append({
                "type": "LOSS_PANIC",
                "level": loss_pct,
                "current": prices["stock_price"],
                "message": f"⚠️ {ticker} down {abs(loss_pct):.1f}% — still time for reversal",
                "action": "WAIT FOR SUPPORT OR RECOVERY",
                "urgency": "medium",
            })
    
    return alerts


def check_support_confirmation(trade, prices):
    """Check if support has been CONFIRMED broken (not just touched)."""
    alerts = []
    ticker = trade["ticker"]
    stock_price = prices["stock_price"]
    entry_price = trade["entry"]
    
    for support in trade.get("supports", []):
        # Support broken only if we close below it (with tolerance)
        if stock_price < support * (1 - CONFIG["support_breach_tolerance"] / 100):
            alerts.append({
                "type": "SUPPORT_BROKEN",
                "level": support,
                "current": stock_price,
                "message": f"🛑 {ticker} support ${support:.2f} BROKEN (now ${stock_price:.2f})",
                "action": "CONSIDER EXITING",
                "urgency": "high",
            })
            break
        
        # Warning when approaching support
        elif stock_price <= support * 1.01:  # Within 1%
            alerts.append({
                "type": "SUPPORT_APPROACHING",
                "level": support,
                "current": stock_price,
                "message": f"📉 {ticker} approaching support ${support:.2f}",
                "action": "WATCH CLOSELY",
                "urgency": "low",
            })
    
    return alerts


def check_momentum_and_reversal(trade, prices, price_history):
    """Detect momentum and potential reversals."""
    alerts = []
    ticker = trade["ticker"]
    stock_price = prices["stock_price"]
    
    if not price_history or len(price_history) < 3:
        return alerts
    
    # Calculate momentum over last N checks
    prices_list = list(price_history.values())
    recent = prices_list[-3:]  # Last 3 readings
    
    if len(recent) < 3:
        return alerts
    
    # Check direction
    moves = []
    for i in range(1, len(recent)):
        if recent[i] and recent[i-1]:
            move = (recent[i] - recent[i-1]) / recent[i-1] * 100
            moves.append(move)
    
    if len(moves) < 2:
        return alerts
    
    # Detect reversal: if last 2 moves were negative but recent is positive
    if moves[-2] < 0 and moves[-1] > 0:
        alerts.append({
            "type": "REVERSAL_DETECTED",
            "level": stock_price,
            "current": stock_price,
            "message": f"🔄 {ticker} showing reversal signs (down → up)",
            "action": "WATCH FOR CONFIRMATION",
            "urgency": "low",
        })
    
    # Detect acceleration: if last 2 moves are increasingly negative
    if len(moves) >= 2 and moves[-1] < moves[-2] < 0:
        alerts.append({
            "type": "MOMENTUM_ACCELERATING",
            "level": stock_price,
            "current": stock_price,
            "message": f"📉 {ticker} momentum accelerating downward",
            "action": "WATCH STOP CLOSELY",
            "urgency": "medium",
        })
    
    return alerts


def check_profit_protection(trade, prices, current_option_price):
    """Check if we should activate trailing stop (profit protection)."""
    alerts = []
    ticker = trade["ticker"]
    entry = trade["entry"]
    current = current_option_price
    
    # Calculate profit percentage
    profit_pct = (current - entry) / entry * 100
    
    # Check if we should trail
    if profit_pct >= CONFIG["profit_protection_pct"]:
        trailing_level = current - (current * 0.05)  # Trail 5% below current
        
        if not trade.get("trailing_stop") or trade["trailing_stop"] < trailing_level:
            # Update trailing stop
            alerts.append({
                "type": "TRAILING_ACTIVATED",
                "level": trailing_level,
                "current": prices["stock_price"],
                "message": f"🐢 {ticker} up {profit_pct:.1f}% — activating trailing stop at ${trailing_level:.2f}",
                "action": "PROTECT PROFITS",
                "urgency": "low",
            })
    
    return alerts


def check_profit_target(trade, prices, current_option_price):
    """Check if premium profit target (e.g. +20%) has been hit."""
    alerts = []
    ticker = trade["ticker"]
    entry = trade["entry"]
    current = current_option_price
    target_pct = CONFIG["target_profit_pct"]

    profit_pct = (current - entry) / entry * 100

    if profit_pct >= target_pct and not trade.get("target_hit"):
        contracts = trade.get("contracts", 1)
        half = max(1, contracts // 2)
        alerts.append({
            "type": "PROFIT_TARGET_HIT",
            "level": target_pct,
            "current": current,
            "message": f"TARGET HIT: {ticker} up {profit_pct:.1f}% -- take {half} of {contracts} contracts, trail rest at breakeven",
            "action": f"SELL {half} contracts, move stop to ${entry:.2f}",
            "urgency": "medium",
        })

    return alerts


def check_thresholds(trade, prices):
    """Check if resistance or target levels are hit."""
    alerts = []
    ticker = trade["ticker"]
    stock_price = prices["stock_price"]
    current_option = prices.get("option_price", trade["entry"])
    
    # Check resistance (moving up toward target)
    for resistance in trade.get("resistances", []):
        if stock_price >= resistance:
            alerts.append({
                "type": "RESISTANCE_HIT",
                "level": resistance,
                "current": stock_price,
                "message": f"🎯 {ticker} hit resistance ${resistance:.2f}",
                "action": "CONSIDER TAKING PROFIT",
                "urgency": "low",
            })
    
    # Check target
    if current_option >= trade["target"]:
        alerts.append({
            "type": "TARGET_HIT",
            "level": trade["target"],
            "current": current_option,
            "message": f"🎯 TARGET HIT: {ticker} at ${current_option:.2f}",
            "action": "TAKE PROFIT",
            "urgency": "medium",
        })
    
    return alerts


def check_time_exit(trade, prices):
    """Check if time exit rules apply."""
    alerts = []
    ticker = trade["ticker"]
    
    # Simplified - would calculate actual time to expiration
    time_remaining = trade.get("dte", 0)
    
    if time_remaining == 0:  # 0DTE
        market_hour = get_market_hour()
        
        # After 3 PM - consider closing
        if market_hour >= CONFIG["close_hour"]:
            alerts.append({
                "type": "TIME_WARNING",
                "level": market_hour,
                "current": prices["stock_price"],
                "message": f"⏰ {ticker} approaching close — consider wrapping up",
                "action": "DECIDE",
                "urgency": "low",
            })
    
    return alerts


def generate_summary(trade, prices, option_pnl):
    """Generate a brief summary of current position."""
    ticker = trade["ticker"]
    stock_price = prices.get("stock_price", 0)
    option_price = prices.get("option_price", trade["entry"])
    entry = trade["entry"]
    trailing = trade.get("trailing_stop")
    
    pnl = calculate_pnl(entry, option_price, trade["contracts"])
    
    time_since_entry = datetime.now() - datetime.fromisoformat(trade["opened_at"])
    hours, mins = divmod(int(time_since_entry.total_seconds()), 3600)
    mins = int((time_since_entry.total_seconds() % 3600) / 60)
    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    
    trailing_info = f" | Trailing: ${trailing:.2f}" if trailing else ""
    
    return f"""
📊 {ticker} {trade['strike']}{trade['type']} Status
━━━━━━━━━━━━━━━━━━━━━━━━
Entry: ${entry:.2f} | Current: ${option_price:.2f}
P/L: ${pnl['total']:.2f} ({pnl['pct']:+.1f}%)
Stock: ${stock_price:.2f}
Time: {time_str}{trailing_info}
Stop: ${trade['stop']:.2f} | Target: ${trade['target']:.2f}
""".strip()


def main():
    """Main monitor loop."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Trade monitor checking...")
    
    trades = load_active_trades()
    if not trades:
        print("No active trades to monitor.")
        return
    
    # Load price history for momentum detection
    history_file = PROJECT_ROOT / "logs" / "price_history.json"
    price_history = {}
    if history_file.exists():
        with open(history_file) as f:
            price_history = json.load(f)
    
    # Load previous prices
    prev_file = PROJECT_ROOT / "logs" / "prev_prices.json"
    prev_prices = {}
    if prev_file.exists():
        with open(prev_file) as f:
            prev_prices = json.load(f)
    
    all_alerts = []
    
    for trade_id, trade in trades.items():
        try:
            prices = get_live_prices(trade["ticker"])
            if not prices:
                continue
            
            # Estimate option price (simplified)
            option_pnl = calculate_pnl(trade["entry"], trade["entry"], trade["contracts"])
            option_price = trade["entry"]
            prices["option_price"] = option_price
            
            alerts = []
            
            # 1. Check loss thresholds (warning vs panic)
            alerts.extend(check_loss_thresholds(trade, prices, option_pnl))
            
            # 2. Check support confirmation (don't panic on touch)
            alerts.extend(check_support_confirmation(trade, prices))
            
            # 3. Check momentum and reversals
            history = price_history.get(trade_id, {})
            alerts.extend(check_momentum_and_reversal(trade, prices, history))
            
            # 4. Check profit protection (trailing stop)
            alerts.extend(check_profit_protection(trade, prices, option_price))

            # 4b. Check percentage profit target (+20%)
            alerts.extend(check_profit_target(trade, prices, option_price))

            # 5. Check resistance/target
            alerts.extend(check_thresholds(trade, prices))
            
            # 6. Check time rules
            alerts.extend(check_time_exit(trade, prices))
            
            # Store prices for history
            prev_prices[trade_id] = prices
            
            # Update price history
            if trade_id not in price_history:
                price_history[trade_id] = {}
            price_history[trade_id][datetime.now().isoformat()] = prices["stock_price"]
            
            # Only alert on HIGH urgency or new support/resistance
            high_urgency = [a for a in alerts if a.get("urgency") in ["high", "medium"]]
            
            if high_urgency:
                for alert in high_urgency:
                    print(f"  {alert['type']}: {alert['message']}")
                    all_alerts.append({**alert, "trade_id": trade_id})
                    
                    # Send to Telegram (commented out until configured)
                    # send_alert_to_telegram(alert, trade)
            
        except Exception as e:
            print(f"Error monitoring {trade_id}: {e}")
    
    # Save updated history
    with open(history_file, "w") as f:
        json.dump(price_history, f)
    
    with open(prev_file, "w") as f:
        json.dump(prev_prices, f)
    
    # Print summaries
    print("\n" + "="*50)
    for trade_id, trade in trades.items():
        prices = get_live_prices(trade["ticker"])
        if prices:
            option_pnl = calculate_pnl(trade["entry"], trade["entry"], trade["contracts"])
            prices["option_price"] = trade["entry"]
            summary = generate_summary(trade, prices, option_pnl)
            print(summary)
            print()


def send_alert_to_telegram(alert_data, trade_data):
    """
    Send alert to Telegram via Clawdbot message tool.
    Returns True if sent, False if rate limited.
    """
    from scripts.telegram_alerts import send_telegram_alert, should_send_alert
    
    trade_id = f"{trade_data['ticker']}_{trade_data['strike']}_{trade_data['type']}"
    urgency = alert_data.get("urgency", "medium")
    
    # Check rate limiting
    if not should_send_alert(trade_id, alert_data["type"], urgency):
        return False
    
    # Format the alert
    message = send_telegram_alert(alert_data, trade_data)
    
    # Log the alert
    log_file = PROJECT_ROOT / "logs" / "telegram_alerts.log"
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {alert_data['type']}: {alert_data['message']}\n")
    
    # In a full implementation, this would use the Clawdbot message tool:
    # message.send(channel="telegram", message=message)
    
    print(f"\n📱 TELEGRAM: {message}\n")
    return True


if __name__ == "__main__":
    main()
