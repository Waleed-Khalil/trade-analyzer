# Trade Journal v2

Local database for tracking all option trades with bankroll and risk management.

## What's New in v2

- **Bankroll Tracking** - Track your balance over time
- **Risk % Per Trade** - See how much you're risking
- **Improvement Report** - Get actionable tips to improve
- **Loss Analysis** - Understand why you lose

## Quick Start

### Set Your Bankroll

```bash
python scripts/trade_journal.py set-bankroll 10000
```

### Add a Trade

```bash
python scripts/trade_journal.py add MSFT 430 CALL 0.78 3
```

### Close a Trade

```bash
python scripts/trade_journal.py close TRD_xxx 0.85
```

### View Report

```bash
python scripts/trade_journal.py report
```

## Commands

```
set-bankroll 10000    # Set your starting bankroll
add TICKER STRIKE TYPE PREMIUM CONTRACTS
close TRADE_ID EXIT_PRICE
report               # Full improvement report
stats                # Quick stats
monthly               # Monthly breakdown
list                  # List recent trades
```

## Example: Your Current Stats

```
╔══════════════════════════════════════════════════════════════════════╗
║                    TRADING IMPROVEMENT REPORT                  ║
╚══════════════════════════════════════════════════════════════════════╝

💰 BANKROLL
──────────────────────────────────────────────────────────────────
Starting: $10,000.00
Current:  $9,925.00
Change:   -$75.00 (-0.75%)

📊 PERFORMANCE
──────────────────────────────────────────────────────────────────
Total Trades: 2
Win Rate: 0.0%
Total P/L: -$75.00

⚠️ RISK ANALYSIS
──────────────────────────────────────────────────────────────────
Avg Risk/Trade: 0.95%
Max Risk/Trade: 0.96%
Trades >2% Risk: 0

✅ Your risk per trade looks appropriate (1-2%)

📈 IMPROVEMENT TIPS
──────────────────────────────────────────────────────────────────

❌ LOSS ANALYSIS (2 losing trades):
• Avg loss: -$37.50


🎯 TOP 5 IMPROVEMENTS
──────────────────────────────────────────────────────────────────
1. Check trend before entering (RSI, MACD, 5-day direction)
2. Use the monitor - don't panic sell
3. Risk max 1-2% per trade
4. Only trade with catalysts (earnings, news)
5. Set stops BEFORE entering, don't move them
```

## Risk Management Rules

| Bankroll | Max Risk/Trade (1%) | Max Risk/Trade (2%) |
|----------|---------------------|---------------------|
| $5,000 | $50 | $100 |
| $10,000 | $100 | $200 |
| $25,000 | $250 | $500 |
| $50,000 | $500 | $1,000 |

## How to Improve

### 1. Check Trend First

```bash
# Before buying CALLS, check:
# - RSI above 50 = bullish
# - MACD bullish = bullish
# - 5-day return positive = bullish

# Before buying PUTS, check opposite
```

### 2. Use the Monitor

Every 0DTE trade should have monitoring:
```bash
python scripts/trade-monitor.py
```

### 3. Position Sizing

Example with $10,000 bankroll:
- Max risk: $100 (1%) per trade
- If entry = $1.00, stop = $0.50
- Risk = $0.50 × 100 = $50 per contract
- You can buy: 2 contracts ($100 risk)

### 4. Only Trade with Catalysts

- Earnings dates
- CPI/Fed announcements
- Major news events
- Avoid: Trading on quiet days without news

### 5. Risk:Reward Ratio

Only take trades with 2:1 or better:
```
Stop: 30% of premium
Target: 60%+ of premium
Ratio: 2:1 ✓
```

## Files

```
logs/
├── trade_journal.json   # All trades
└── bankroll.json        # Bankroll balance
```

## API Usage

```python
from trade_journal import TradeJournal

journal = TradeJournal()

# Set bankroll
journal.set_bankroll(starting=10000, current=10000)

# Add trade
trade = create_trade_from_text("MSFT", 430, "CALL", 0.78, 3)
journal.add_trade(trade)

# Close trade
journal.close_trade(trade.id, 0.85, "Took profit")

# Get report
print(journal.get_improvement_report())

# Get stats
stats = journal.get_bankroll_stats()
print(f"Bankroll: ${stats['current_balance']:,.2f}")
```

## Adding Screenshots

Send me screenshots of your trades and I'll:
1. Extract the data
2. Add to the journal
3. Track until you close
4. Generate reports

## Monthly Goals

Set monthly targets:
```bash
# Example goals for February
- Win rate: 55%+
- Max drawdown: <5%
- Profit: +$500
```

Track progress with:
```bash
python scripts/trade_journal.py monthly
```
