#!/usr/bin/env python3
"""
0DTE Trade Monitor
Real-time monitoring for active option trades.
Run via cron every 1-5 minutes during market hours.
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

from market_data.market_data import get_market_context
from parser.trade_parser import TradeParser


def load_active_trades():
    """Load active trades from JSON file."""
    trades_file = Path(__file__).parent.parent / "logs" / "active_trades.json"
    if trades_file.exists():
        with open(trades_file) as f:
            return json.load(f)
    return {}


def save_active_trades(trades):
    """Save active trades to JSON file."""
    trades_file = Path(__file__).parent.parent / "logs" / "active_trades.json"
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


def check_thresholds(trade, prices):
    """Check if any thresholds have been hit."""
    stock_price = prices.get("stock_price")
    if not stock_price:
        return []
    
    alerts = []
    ticker = trade["ticker"]
    current = prices.get("option_price", trade["entry"])
    
    # Check support levels (stock going down)
    for support in trade.get("supports", []):
        if stock_price <= support:
            alerts.append({
                "type": "SUPPORT_HIT",
                "level": support,
                "current": stock_price,
                "message": f"🚨 {ticker} hit support ${support:.2f} (now ${stock_price:.2f})",
                "action": "WATCH CLOSELY",
            })
    
    # Check resistance levels (stock going up)
    for resistance in trade.get("resistances", []):
        if stock_price >= resistance:
            alerts.append({
                "type": "RESISTANCE_HIT",
                "level": resistance,
                "current": stock_price,
                "message": f"🎯 {ticker} hit resistance ${resistance:.2f} (now ${stock_price:.2f})",
                "action": "CONSIDER TAKING PROFIT",
            })
    
    # Check stop breach
    if stock_price <= trade["stop"]:
        alerts.append({
            "type": "STOP_BREACHED",
            "level": trade["stop"],
            "current": stock_price,
            "message": f"🛑 STOP TRIGGERED: {ticker} at ${stock_price:.2f} (stop ${trade['stop']:.2f})",
            "action": "CLOSE NOW",
        })
    
    # Check target hit
    if current >= trade["target"]:
        alerts.append({
            "type": "TARGET_HIT",
            "level": trade["target"],
            "current": current,
            "message": f"🎯 TARGET HIT: {ticker} option at ${current:.2f} (target ${trade['target']:.2f})",
            "action": "TAKE PROFIT",
        })
    
    # Check within X% of stop
    if stock_price > trade["stop"]:
        dist_to_stop_pct = (stock_price - trade["stop"]) / stock_price * 100
        if dist_to_stop_pct < 1.0:  # Within 1%
            alerts.append({
                "type": "STOP_WARNING",
                "level": trade["stop"],
                "current": stock_price,
                "message": f"⚠️ {ticker} within 1% of stop (${stock_price:.2f} vs ${trade['stop']:.2f})",
                "action": "WATCH CLOSELY",
            })
    
    return alerts


def check_momentum(trade, prices, prev_prices):
    """Check for significant price movements."""
    if not prev_prices:
        return []
    
    alerts = []
    ticker = trade["ticker"]
    current = prices.get("stock_price")
    prev = prev_prices.get("stock_price")
    
    if not current or not prev:
        return []
    
    pct_change = (current - prev) / prev * 100
    
    # Significant move in last check period
    if abs(pct_change) >= 1.0:
        direction = "📈" if pct_change > 0 else "📉"
        alerts.append({
            "type": "MOMENTUM",
            "pct": round(pct_change, 1),
            "message": f"{direction} {ticker} moved {pct_change:+.1f}% in last check",
            "action": "EVALUATE" if pct_change > 0 else "WATCH STOP",
        })
    
    return alerts


def generate_summary(trade, prices):
    """Generate a brief summary of current position."""
    ticker = trade["ticker"]
    stock_price = prices.get("stock_price", 0)
    option_price = prices.get("option_price", trade["entry"])
    entry = trade["entry"]
    
    pnl = calculate_pnl(entry, option_price, trade["contracts"])
    
    time_since_entry = datetime.now() - datetime.fromisoformat(trade["opened_at"])
    hours, mins = divmod(int(time_since_entry.total_seconds()), 3600)
    mins = int((time_since_entry.total_seconds() % 3600) / 60)
    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    
    return f"""
📊 {ticker} {trade['strike']}{trade['type']} Status
━━━━━━━━━━━━━━━━━━━━━━━━
Entry: ${entry:.2f} | Current: ${option_price:.2f}
P/L: ${pnl['total']:.2f} ({pnl['pct']:+.1f}%)
Stock: ${stock_price:.2f}
Time in trade: {time_str}
Stop: ${trade['stop']:.2f} | Target: ${trade['target']:.2f}
""".strip()


def main():
    """Main monitor loop."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Trade monitor checking...")
    
    # Load active trades
    trades = load_active_trades()
    if not trades:
        print("No active trades to monitor.")
        return
    
    # Track previous prices for momentum detection
    prev_prices_file = Path(__file__).parent.parent / "logs" / "prev_prices.json"
    prev_prices = {}
    if prev_prices_file.exists():
        with open(prev_prices_file) as f:
            prev_prices = json.load(f)
    
    alerts_sent = []
    
    for trade_id, trade in trades.items():
        try:
            # Get live prices
            prices = get_live_prices(trade["ticker"])
            if not prices:
                continue
            
            prices["option_price"] = trade["entry"]  # Simplified - would fetch option price
            
            # Check thresholds
            alerts = check_thresholds(trade, prices)
            
            # Check momentum
            prev = prev_prices.get(trade_id, {})
            momentum_alerts = check_momentum(trade, prices, prev)
            alerts.extend(momentum_alerts)
            
            # Store current prices for next check
            prev_prices[trade_id] = prices
            
            if alerts:
                for alert in alerts:
                    print(f"  {alert['type']}: {alert['message']}")
                    alerts_sent.append({
                        "trade_id": trade_id,
                        "ticker": trade["ticker"],
                        **alert,
                        "timestamp": datetime.now().isoformat(),
                    })
            
        except Exception as e:
            print(f"Error monitoring {trade_id}: {e}")
    
    # Save previous prices
    with open(prev_prices_file, "w") as f:
        json.dump(prev_prices, f)
    
    # Print summary
    if alerts_sent:
        print(f"\n⚠️  {len(alerts_sent)} alerts generated")
    else:
        print("✅ All trades within normal parameters")
    
    # Generate summaries for all active trades
    print("\n" + "="*40)
    for trade_id, trade in trades.items():
        prices = get_live_prices(trade["ticker"])
        if prices:
            prices["option_price"] = trade["entry"]
            summary = generate_summary(trade, prices)
            print(summary)
            print()


if __name__ == "__main__":
    main()
