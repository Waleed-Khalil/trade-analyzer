# Traders Cheat Sheet Integration

Store and use Barchart Traders Cheat Sheet data for technical analysis.

## What is the Traders Cheat Sheet?

Barchart's Traders Cheat Sheet provides:
- **Pivot Points** - Key S/R levels (PP, R1-R3, S1-S3)
- **Moving Averages** - 20, 50, 200-day MA
- **Technical Indicators** - RSI, MACD, ATR
- **Trading Signals** - Bullish/Bearish/Neutral
- **Price Context** - Day high/low, volume

## Quick Start

### Manual Entry

```python
from cheat_sheet import CheatSheetStore, CheatSheetData

store = CheatSheetStore()

# Add data from Barchart Traders Cheat Sheet
store.add(CheatSheetData(
    ticker="MSFT",
    current_price=415.30,
    previous_close=413.50,
    
    # Pivot Points
    pivot_point=415.00,
    r1=418.00, r2=421.00, r3=424.00,
    s1=412.00, s2=409.00, s3=406.00,
    
    # Moving Averages
    ma_20=418.50,
    ma_50=410.00,
    ma_200=395.00,
    
    # Technical Indicators
    rsi=52,
    macd_signal="bullish",
    atr=5.20,
    
    # Signals
    overall_signal="neutral",
    short_term="neutral",
    medium_term="bullish",
    long_term="bullish",
    
    # Volume
    volume=22000000,
    avg_volume=25000000,
))
```

### Get Trade Setup

```python
# Get CALL setup for MSFT
setup = store.get_trade_setup("MSFT", "CALL")

print(f"Setup: {setup['setup']}")
print(f"Confidence: {setup['confidence']}%")
print(f"Entry: {setup['entry_zone']}")
print(f"Stop: {setup['stop']}")
print(f"Target: {setup['target_1']}")
print(f"Support: {setup['support']}")
print(f"Resistance: {setup['resistance']}")
```

## Example Output

```
MSFT Traders Cheat Sheet - CALL Setup
======================================================================
ticker: MSFT
option_type: CALL
setup: bullish
confidence: 70
current_price: 415.3
entry_zone: $414.80 - $415.80
stop: $412.00
target_1: $418.00
target_2: $421.00
support: [412.0, 409.0, 406.0]
resistance: [418.0, 421.0, 424.0]
reasons:
  - Price above 50 MA ($410.00)
  - RSI neutral (52)
  - MACD bullish
pivot_point: 415.0
```

## How to Use

### 1. Check Barchart Traders Cheat Sheet

Visit: `https://www.barchart.com/stocks/quotes/MSFT/cheat-sheet`

Or search for your ticker on Barchart and find "Traders Cheat Sheet"

### 2. Enter Key Data

| Field | Where to Find | Example |
|-------|---------------|---------|
| Current Price | Top of page | 415.30 |
| Pivot Point | "Classic Pivot Points" section | 415.00 |
| R1, R2, R3 | Resistance levels | 418, 421, 424 |
| S1, S2, S3 | Support levels | 412, 409, 406 |
| MA-20, MA-50, MA-200 | Moving Averages | 418.50, 410.00, 395.00 |
| RSI | RSI indicator | 52 |
| MACD | MACD signal | bullish |
| Overall Signal | Bottom summary | neutral |

### 3. Get Trading Recommendations

```python
# Should we buy calls?
should_buy = store.should_buy_calls("MSFT")
# Returns: True (yes), False (no), or None (neutral)

# Get full setup
setup = store.get_trade_setup("MSFT", "CALL")
```

## Integration with Analyzer

Combine with our trade analyzer:

```python
from trade_analyzer import analyze_trade
from cheat_sheet import get_trade_setup

# Analyze a trade
analysis = analyze_trade("MSFT 420 CALL @ 2.50 0DTE")

# Get cheat sheet context
cheat = get_trade_setup("MSFT", "CALL")

# Combine signals
if analysis.score > 70 and cheat['setup'] == 'bullish':
    print("✅ STRONG SETUP: Analyzer + Cheat Sheet both bullish")
elif analysis.score > 70:
    print("⚠️ Analyzer bullish, Cheat Sheet neutral")
elif cheat['setup'] == 'bullish':
    print("⚠️ Cheat Sheet bullish, analyzer neutral")
else:
    print("❌ Both neutral/bearish")
```

## Pivot Points Explained

| Level | Meaning |
|-------|---------|
| R3 | Strong resistance |
| R2 | Resistance |
| R1 | First resistance |
| **PP** | Pivot Point (mid) |
| S1 | First support |
| S2 | Support |
| S3 | Strong support |

## Trading Rules

### For CALLS (Bullish)
- Buy when price > 50 MA
- Entry: Near support or 50 MA
- Stop: Below S1 or 50 MA
- Target: R1 or R2

### For PUTS (Bearish)
- Buy when price < 50 MA
- Entry: Near resistance or 50 MA
- Stop: Above R1 or 50 MA
- Target: S1 or S2

## Data Storage

Cheat sheet data stored in:
```
logs/cheat_sheets.json
```

Export:
```python
store.export_json("my_cheat_sheets.json")
```

## File Location

```
src/market_data/cheat_sheet.py
```

Import:
```python
from market_data.cheat_sheet import CheatSheetStore, CheatSheetData
```

## Tips

1. **Update daily** - Enter new data each morning
2. **Check pivot levels** - Use for stops and targets
3. **Combine with our analyzer** - Use both for confirmation
4. **Watch for reversals** - RSI < 30 or > 70 signals potential reversals
5. **Volume context** - High volume on breakouts is more reliable

## Example Workflow

```python
# Morning routine
store = CheatSheetStore()

# Check your watchlist
tickers = ["MSFT", "QQQ", "NVDA", "SPY"]

for ticker in tickers:
    # Get cheat sheet setup
    setup = store.get_trade_setup(ticker, "CALL")
    
    if setup['confidence'] >= 70:
        print(f"✅ {ticker}: {setup['setup'].upper()} setup ({setup['confidence']}% confidence)")
        print(f"   Entry: {setup['entry_zone']}")
        print(f"   Stop: {setup['stop']} | Target: {setup['target_1']}")
    else:
        print(f"⚠️ {ticker}: Neutral ({setup['confidence']}% confidence)")
```
