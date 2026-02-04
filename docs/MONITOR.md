# 0DTE Trade Monitor v2.1

Real-time monitoring system for 0DTE/same-day option trades with Telegram alerts.

## What's New in v2.1

- **Telegram Integration** - Alerts sent directly to your phone
- **Smart Exit Logic** - Warning vs panic thresholds
- **Momentum Detection** - Reversal alerts
- **Trailing Stops** - Auto profit protection

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
├── trade-workflow.py     # Main workflow handler
├── trade-monitor.py     # Live monitoring script v2.1
├── telegram_alerts.py    # Telegram integration & rate limiting
└── test_massastic.py    # Bulk testing
```

## Smart Exit Logic v2

### Loss Thresholds
```
-15% loss: ⚠️ "Watch closely" — Don't panic
-25% loss: 🚨 "Consider exiting" — Time running out
```

### Support Confirmation
- Old: Touch support → "EXIT NOW"
- New: Support must **break** (close below) → "CONSIDER EXITING"

### Momentum Detection
- Reversal pattern (down → up) → "Reversal detected"
- Accelerating downside → "Watch stop closely"

### Auto-Trailing Stop
- Up +20% → Activates trailing stop at -5% from peak
- Locks in profits automatically

### Time Rules
- Before 3 PM: More tolerant of drawdowns
- After 3 PM: Tighten stops, wrap up

## Telegram Integration

### Alert Types
| Type | Urgency | Rate Limit |
|------|---------|------------|
| Stop Breached | High | None |
| Support Broken | High | None |
| Loss Panic | High | None |
| Loss Warning | Medium | 5 min |
| Reversal Detected | Medium | 5 min |
| Target Hit | Low | 10 min |
| Time Warning | Low | 10 min |

### Example Alerts
```
🚨 URGENT: MSFT support $415 BROKEN (now $414.50)
📊 Action: CONSIDER EXITING
💰 Entry: $0.78 | Target: $1.55 | Stop: $0.39

🔄 Reversal detected: MSFT showing reversal signs (down → up)
📊 Action: WATCH FOR CONFIRMATION
```

## Quick Start

### Running Analysis

```bash
# Text-based trade
python scripts/trade-workflow.py "MSFT 430 CALL @ 0.78 0DTE"
```

### Manual Monitoring

```bash
# Run monitor manually
python scripts/trade-monitor.py

# Or via cron (every 2 minutes during market hours)
*/2 9-16 * * 1-5 python /home/ubuntu/clawd/trade-analyzer/scripts/trade-monitor.py
```
