#!/usr/bin/env python3
"""
0DTE Trade Workflow Handler
Parses trade messages, analyzes, and sets up monitoring.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Add project root and src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from parser.trade_parser import TradeParser
from risk_engine.risk_engine import RiskEngine
from analysis.trade_analyzer import TradeAnalyzer
from market_data.market_data import get_market_context
from ai_agent.ai_agent import OptionAIAgent


def parse_trade_message(message):
    """Parse trade from text message or screenshot reference."""
    # Try to parse as text first
    parser = TradeParser()
    trade = parser.parse(message)
    
    if trade:
        return {
            "type": "text",
            "trade": trade,
            "raw": message,
        }
    
    # Check if message references a screenshot
    screenshot_match = re.search(r'screenshot[:\s]+(.+)', message, re.IGNORECASE)
    if screenshot_match:
        return {
            "type": "screenshot",
            "path": screenshot_match.group(1).strip(),
            "raw": message,
        }
    
    return None


def analyze_trade(trade, current_price=None):
    """Run full analysis on a trade."""
    from market_data.market_data import get_market_context
    
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    # Get market context
    try:
        market_context = get_market_context(trade.ticker)
        current_price = market_context.get("current_price")
    except:
        market_context = {}
    
    # Create trade plan
    engine = RiskEngine(str(config_path))
    trade_plan = engine.create_trade_plan(trade, current_price=current_price, market_context=market_context)
    
    # Run analysis
    analyzer = TradeAnalyzer(str(config_path))
    analysis = analyzer.analyze(trade, trade_plan, current_price, market_context)
    
    return {
        "trade_plan": trade_plan,
        "analysis": analysis,
        "current_price": current_price,
        "market_context": market_context,
    }


def generate_recommendation(analysis, trade_plan, trade):
    """Generate a clear recommendation."""
    score = getattr(analysis, "setup_score", 50)
    confidence = getattr(analysis, "confidence", 0.5)
    quality = getattr(analysis, "setup_quality", "UNKNOWN").upper()
    
    # Decision based on score and red flags
    red_flags = getattr(analysis, "red_flags", [])
    has_major_red_flags = any(f.get("severity") == "high" for f in red_flags)
    
    if score >= 70 and not has_major_red_flags:
        recommendation = "PLAY"
        emoji = "🟢"
    elif score >= 50 and not has_major_red_flags:
        recommendation = "WATCH"
        emoji = "🟡"
    else:
        recommendation = "DON'T PLAY"
        emoji = "🔴"
    
    entry_zone = trade_plan.entry_zone
    stop = trade_plan.stop_loss
    target = trade_plan.target_1
    target_r = trade_plan.target_1_r
    
    return {
        "recommendation": recommendation,
        "emoji": emoji,
        "score": score,
        "quality": quality,
        "confidence": confidence,
        "entry": entry_zone,
        "stop": stop,
        "target": target,
        "target_r": target_r,
        "red_flags": [f.get("message") for f in red_flags],
    }


def setup_trade_monitoring(trade, analysis, current_price):
    """Generate monitoring configuration for a trade."""
    ticker = trade.ticker
    strike = trade.strike
    option_type = trade.option_type
    
    # Generate support/resistance levels based on current price
    supports = []
    resistances = []
    
    if current_price:
        # Generate levels around current price
        for i in range(1, 4):
            supports.append(round((current_price - i * 5) / 1) * 1)
            resistances.append(round((current_price + i * 5) / 1) * 1)
    
    # Generate monitoring config
    monitoring_config = {
        "ticker": ticker,
        "strike": strike,
        "type": option_type,
        "entry": trade.premium,
        "stop": analysis.stop_loss if hasattr(analysis, "stop_loss") else trade.premium * 0.5,
        "target": analysis.target_1 if hasattr(analysis, "target_1") else trade.premium * 2,
        "contracts": trade_plan.position.contracts if hasattr(trade_plan, "position") else 3,
        "supports": sorted([s for s in supports if s < current_price], reverse=True)[:3],
        "resistances": sorted([r for r in resistances if r > current_price])[:3],
        "dte": getattr(trade, "days_to_expiration", 0),
        "is_ode": getattr(trade, "is_ode", False),
        "opened_at": datetime.now().isoformat(),
        "status": "ACTIVE",
    }
    
    return monitoring_config


def save_active_trade(trade_id, config):
    """Save trade to active trades file."""
    trades_file = Path(__file__).parent.parent / "logs" / "active_trades.json"
    trades_file.parent.mkdir(parents=True, exist_ok=True)
    
    trades = {}
    if trades_file.exists():
        with open(trades_file) as f:
            trades = json.load(f)
    
    trades[trade_id] = config
    
    with open(trades_file, "w") as f:
        json.dump(trades, f, indent=2)


def close_trade(trade_id, exit_price, reason):
    """Close a trade and log the result."""
    trades_file = Path(__file__).parent.parent / "logs" / "active_trades.json"
    journal_file = Path(__file__).parent.parent / "logs" / "trade_journal.json"
    
    if not trades_file.exists():
        return
    
    with open(trades_file) as f:
        trades = json.load(f)
    
    if trade_id not in trades:
        return
    
    trade = trades.pop(trade_id)
    
    # Calculate P&L
    entry = trade["entry"]
    contracts = trade["contracts"]
    pnl = (exit_price - entry) * contracts * 100
    
    # Log to journal
    journal_entry = {
        "trade_id": trade_id,
        "ticker": trade["ticker"],
        "strike": trade["strike"],
        "type": trade["type"],
        "entry_price": entry,
        "exit_price": exit_price,
        "contracts": contracts,
        "pnl": round(pnl, 2),
        "pnl_pct": round((exit_price - entry) / entry * 100, 1),
        "opened_at": trade["opened_at"],
        "closed_at": datetime.now().isoformat(),
        "reason": reason,
    }
    
    journal = []
    if journal_file.exists():
        with open(journal_file) as f:
            journal = json.load(f)
    
    journal.append(journal_entry)
    
    with open(journal_file, "w") as f:
        json.dump(journal, f, indent=2)
    
    # Save updated trades
    with open(trades_file, "w") as f:
        json.dump(trades, f, indent=2)
    
    return journal_entry


def generate_cron_entry(trade_id):
    """Generate a cron entry for monitoring a trade."""
    script_path = Path(__file__).parent / "trade-monitor.py"
    
    # Cron runs every 2 minutes during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
    # 9-16 * * 1-5 = every minute from 9 AM to 4 PM, Monday through Friday
    # */2 9-16 * * 1-5 = every 2 minutes
    
    cron_line = f"*/2 9-16 * * 1-5 python {script_path} --trade {trade_id}\n"
    
    return cron_line


def process_trade_decision(message, decision, exit_info=None):
    """
    Process user's decision about a trade.
    
    decision: "taken" | "skipped" | "waiting" | "closed"
    exit_info: { "price": 0.68, "reason": "stop_hit" }
    """
    # Extract trade ID or ticker from message
    # This would need more sophisticated parsing
    
    if decision == "taken":
        # Set up monitoring
        trade_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # Would save trade and generate cron entry
        return f"✅ Trade confirmed. Setting up live monitoring for trade {trade_id}..."
    
    elif decision == "closed":
        if exit_info:
            result = close_trade(None, exit_info["price"], exit_info["reason"])
            return f"🚪 Trade closed. P/L: ${result['pnl']:.2f}"
        else:
            return "Trade closed."
    
    return "Decision recorded."


def format_trade_recommendation(analysis, trade_plan, trade, current_price):
    """Format a nice recommendation message."""
    rec = generate_recommendation(analysis, trade_plan, trade)
    
    msg = f"""
{rec['emoji']} RECOMMENDATION: {rec['recommendation']}
{'='*40}

📊 Setup Quality: {rec['quality']} ({rec['score']}/100)
🎯 Confidence: {rec['confidence']:.0%}

💰 Trade Plan:
   Entry: {rec['entry']}
   Stop: ${rec['stop']:.2f}
   Target: ${rec['target']:.2f} ({rec['target_r']}R)

"""
    
    if rec['red_flags']:
        msg += "⚠️  Red Flags:\n"
        for flag in rec['red_flags']:
            msg += f"   • {flag}\n"
        msg += "\n"
    
    if current_price:
        moneyness = (current_price - trade.strike) / current_price * 100 if trade.option_type.upper() == "CALL" else (trade.strike - current_price) / current_price * 100
        direction = "OTM" if moneyness > 0 else "ITM"
        msg += f"📈 Current: {trade.ticker} ${current_price:.2f} ({abs(moneyness):.1f}% {direction})\n"
    
    msg += f"""
⏰ Time to Expiration: {getattr(trade, 'days_to_expiration', '?')} days

Reply with:
- "TOOK IT @ $X" — I'll set up monitoring
- "SKIPPED" — No action needed
- "WAITING" — Monitor for better entry
"""
    
    return msg


# Example usage
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trade-workflow.py <trade_message>")
        print("       python trade-workflow.py --take <trade_id> <price>")
        print("       python trade-workflow.py --close <trade_id> <price> <reason>")
        sys.exit(1)
    
    message = " ".join(sys.argv[1:])
    
    # Parse and analyze
    parsed = parse_trade_message(message)
    if parsed:
        trade = parsed["trade"]
        analysis = analyze_trade(trade)
        msg = format_trade_recommendation(
            analysis["analysis"],
            analysis["trade_plan"],
            trade,
            analysis["current_price"]
        )
        print(msg)
    else:
        print("Could not parse trade message")
