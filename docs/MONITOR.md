# 0DTE Trade Monitor

Real-time monitoring system for 0DTE/same-day option trades.

## How It Works

1. **Send a trade** (screenshot or text)
2. **I analyze** and recommend PLAY/WATCH/DON'T PLAY
3. **You decide** to take it or skip
4. **I set up** live monitoring with alerts
5. **You get Telegram alerts** when thresholds hit

## Quick Start

### Running Analysis

```bash
# Text-based trade
python scripts/trade-workflow.py "MSFT 430 CALL @ 0.78 0DTE"

# Or let Clawdbot parse your screenshot automatically
```

### Manual Monitoring

```bash
# Run monitor manually
python scripts/trade-monitor.py

# Or via cron (every 2 minutes during market hours)
*/2 9-16 * * 1-5 python /path/to/trade-analyzer/scripts/trade-monitor.py
```

## Files

```
scripts/
├── trade-workflow.py    # Main workflow handler
├── trade-monitor.py     # Live monitoring script
└── test_massive.py     # Bulk testing
```

## Workflow

### 1. Send a Trade
```
You: [Screenshot or "BTO MSFT 430c @ 0.78 0DTE"]
```

### 2. I Analyze
```
🟢 RECOMMENDATION: PLAY
========================================

📊 Setup Quality: HIGH (86/100)
🎯 Confidence: 95%

💰 Trade Plan:
   Entry: $0.73 - $0.83
   Stop: $0.39
   Target: $1.55 (2R)

⚠️ Red Flags:
   • Live option price 22% lower than pasted
   • MACD bearish

...

Reply with:
- "TOOK IT @ $0.78" — I'll set up monitoring
- "SKIPPED" — No action needed
- "WAITING" — Monitor for better entry
```

### 3. You Execute
```
You: "TOOK IT @ 0.78"
```

### 4. I Set Up Monitoring
```
✅ Trade confirmed: MSFT 430c @ $0.78

🚀 Setting up live monitor...
📊 Checking every 2 minutes during market hours
🔔 Alerts enabled for:
   - Support: $415, $408
   - Resistance: $420, $423
   - Stop breach warning
   - Target hit
```

### 5. You Get Alerts
```
[URGENT] MSFT hit $415 support
⚠️ Stock breaking through support level

[URGENT] MSFT stopped out @ $410
🛑 STOP TRIGGERED - Close your position
```

## Configuration

### Cron Setup

Add to crontab (`crontab -e`):

```bash
# Every 1 minute during market hours (0DTE)
* 9-16 * * 1-5 python /home/ubuntu/clawd/trade-analyzer/scripts/trade-monitor.py

# Every 2 minutes (less aggressive)
*/2 9-16 * * 1-5 python /home/ubuntu/clawd/trade-analyzer/scripts/trade-monitor.py

# Every 5 minutes (conservative)
*/5 9-16 * * 1-5 python /home/ubuntu/clawd/trade-analyzer/scripts/trade-monitor.py
```

### Alerts

The monitor tracks:
- **Support levels** — Stock falling toward stop
- **Resistance levels** — Stock rising toward target
- **Stop breach** — Immediate "CLOSE NOW" alert
- **Target hit** — "TAKE PROFIT" alert
- **Momentum** — Significant price moves
- **Theta decay** — Time value erosion

## Example Output

```
[14:32:01] Trade monitor checking...
  SUPPORT_HIT: 🚨 MSFT hit support $415 (now $414.50)
  ⚠️  2 alerts generated

========================================
📊 MSFT 430c Status
━━━━━━━━━━━━━━━━━━━━━━━━
Entry: $0.78 | Current: $0.72
P/L: -$18.00 (-7.7%)
Stock: $414.50
Time in trade: 1h 32m
Stop: $0.39 | Target: $1.55
```

## Telegram Integration

To receive push alerts:

1. Use Clawdbot's message tool
2. Configure Telegram channel in Clawdbot
3. Alerts sent directly to your phone

## Active Trades

Active trades stored in: `logs/active_trades.json`
Trade history stored in: `logs/trade_journal.json`

## Tips for 0DTE

- Set tighter stops (35-40% vs 50%)
- Take profits faster (1.5R vs 2R)
- Monitor every 1-2 minutes
- Have exit plan before entry
- Don't avg down on 0DTE
