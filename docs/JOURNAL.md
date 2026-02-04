# Trade Journal

Local database for tracking all option trades with full analytics.

## Features

- **Trade Logging** - Add trades from text or screenshots
- **P&L Tracking** - Calculate wins/losses automatically
- **Monthly Stats** - See how you're doing each month
- **Win Rate** - Track win percentage over time
- **Performance Reports** - Generate detailed reports
- **Export** - Export to CSV for Excel

## Quick Start

### Add a Trade from Text

```bash
python scripts/trade_journal.py add MSFT 430 CALL 0.78 3
python scripts/trade_journal.py add SPY 580 PUT 1.20 2 --stop 0.80 --target 2.00
```

### Close a Trade

```bash
python scripts/trade_journal.py close TRD_20260204_190000_abc123 0.85
```

### View Statistics

```bash
# All-time stats
python scripts/trade_journal.py stats

# Monthly breakdown
python scripts/trade_journal.py monthly

# Performance report (last 30 days)
python scripts/trade_journal.py report

# List recent trades
python scripts/trade_journal.py list
```

## Adding Trades from Screenshots

Send me screenshots of your trades and I'll:
1. Extract the data (ticker, strike, premium, etc.)
2. Add to the journal
3. Track until you close it

## Analytics

### Monthly Stats

```
2026-02: +$120.50 (12 trades, 58% win rate)
2026-01: -$45.20 (8 trades, 45% win rate)
2025-12: +$280.00 (15 trades, 62% win rate)
```

### Performance Report

```
╔══════════════════════════════════════════════════════════════╗
║           TRADE JOURNAL PERFORMANCE REPORT                  ║
║                    Last 30 Days                            ║
╚══════════════════════════════════════════════════════════════╝

📊 SUMMARY
─────────────────────────────────────────────────────────────
Total Trades: 24
Closed: 20
Open: 4
Win Rate: 55.0%

💰 P/L
─────────────────────────────────────────────────────────────
Total P/L: +$145.50
Wins: +$320.00 (11 trades)
Losses: -$174.50 (9 trades)

📈 BEST TRADES
─────────────────────────────────────────────────────────────
1. NVDA 1500C @ $25.00 → $32.50
   +$2,250.00 (+90.0%) | 2 contracts

2. MSFT 430C @ $0.78 → $1.25
   +$141.00 (+60.2%) | 3 contracts
```

## Data Storage

Trades stored in: `logs/trade_journal.json`
Export CSV: `logs/trade_journal.csv`

## Example Workflow

```
You: [Screenshot of MSFT 430c]

I: Extracting trade data...
✅ Trade added: TRD_20260204_150000_abc123
   MSFT 430C @ $0.78 x 3 contracts

[Later...]

You: Closed MSFT @ 0.85

I: ✅ Trade closed
   P/L: +$21.00 (+8.5%)
   Monthly total: +$85.50 (5 trades, 60% win rate)
```

## API Usage

```python
from trade_journal import TradeJournal, create_trade_from_text

journal = TradeJournal()

# Add trade
trade = create_trade_from_text("MSFT", 430, "CALL", 0.78, 3)
journal.add_trade(trade)

# Close trade
journal.close_trade(trade.id, 0.85)

# Get stats
stats = journal.get_monthly_stats(2026, 2)
print(f"Monthly P/L: ${stats['total_pnl']:+.2f}")
print(f"Win Rate: {stats['win_rate']}%")
```

## Trade Fields

| Field | Description |
|-------|-------------|
| id | Unique trade ID |
| ticker | Stock ticker (MSFT, SPY, etc.) |
| strike | Strike price |
| option_type | CALL or PUT |
| entry_price | Premium paid |
| exit_price | Premium received (on close) |
| contracts | Number of contracts |
| pnl | Profit/loss in dollars |
| pnl_pct | Profit/loss percentage |
| stop_loss | Planned stop loss |
| target | Target price |
| notes | Any additional notes |

## Export

Export all trades to CSV for analysis in Excel:

```bash
python scripts/trade_journal.py export
```

This creates `logs/trade_journal.csv` with all trade data.
