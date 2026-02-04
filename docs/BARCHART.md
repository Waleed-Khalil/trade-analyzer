# Barchart Integration

Integrate Barchart.com data into your trading workflow for better IV rankings, options flow, and unusual activity signals.

## What is Barchart?

Barchart.com provides:
- **IV Rank & IV Percentile** - Compare current IV to historical levels
- **Unusual Options Activity** - Large orders, high volume/OI ratios
- **Options Flow** - Call/Put ratios, sentiment indicators
- **Market Sentiment** - Overall market mood

## Quick Start

### Manual Entry Workflow

When you check Barchart manually, enter the data:

```python
from barchart_client import BarchartData, BarchartIVData, BarchartUnusualActivity

data = BarchartData()

# Add IV data you see on Barchart
data.add_iv_data(BarchartIVData(
    ticker="MSFT",
    iv_rank=25,          # From Barchart IV Rank page
    iv_percentile=28,
    implied_volatility=0.38,
    historical_iv=0.45,  # Historical average from Barchart
))

# Add unusual activity
data.add_unusual_activity([
    BarchartUnusualActivity(
        ticker="NVDA",
        option_type="CALL",
        strike=1000,
        expiration="2/21",
        volume=15000,
        open_interest=5000,
        volume_oi_ratio=3.0,  # High ratio = unusual
        sentiment="bullish",
        last_price=15.50,
    ),
])
```

### Get Trading Recommendations

```python
# Get recommendation for MSFT calls
rec = data.get_trading_recommendation("MSFT", "CALL")

print(f"Recommendation: {rec['recommendation']}")  # BUY/WATCH/SELL/AVOID
print(f"Confidence: {rec['confidence']}%")
print(f"IV Status: {rec['iv_status']}")  # low/medium/high
print(f"Sentiment: {rec['sentiment']}")  # bullish/bearish/neutral

for reason in rec['reasons']:
    print(f"  - {reason}")
```

## How to Use Barchart Data

### 1. Check IV Rank First

| IV Rank | Action |
|---------|--------|
| < 30% | ✅ Favorable for buying options |
| 30-70% | ⚠️ Neutral |
| > 70% | ❌ IV crush risk, avoid longs |

### 2. Look for Unusual Activity

| Volume/OI Ratio | Meaning |
|----------------|---------|
| < 1.0 | Normal activity |
| 1.25-2.0 | Slightly unusual |
| > 2.0 | Highly unusual |

### 3. Check Options Flow

| Call/Put Ratio | Sentiment |
|----------------|-----------|
| > 1.2 | Bullish |
| 0.8-1.2 | Neutral |
| < 0.8 | Bearish |

### 4. Combine Signals

```
LOW IV + BULLISH FLOW + UNUSUAL CALL ACTIVITY = STRONG BUY SIGNAL
HIGH IV + BEARISH FLOW + UNUSUAL PUT ACTIVITY = STRONG SELL SIGNAL
```

## Example Workflow

### Before Trading:

```python
# 1. Check IV on Barchart.com/stocks/quotes/MSFT/iv-rank
# You see: IV Rank = 25%

# 2. Check unusual activity on Barchart.com/options/unusual-activity
# You see: NVDA calls with 3.0x volume/OI ratio

# 3. Add to our system
data.add_iv_data(BarchartIVData(
    ticker="NVDA",
    iv_rank=25,
    iv_percentile=28,
    implied_volatility=0.65,
    historical_iv=0.70,
))

# 4. Get recommendation
rec = data.get_trading_recommendation("NVDA", "CALL")
# Output: BUY - confidence 60% - Low IV + unusual call activity
```

### During Trading:

```python
# Check if your trade setup aligns with Barchart signals
iv_data = data.get_iv_for_ticker("NVDA")
if iv_data and iv_data.iv_rank < 30:
    print("✅ IV is favorable for buying calls")
else:
    print("⚠️ IV might be unfavorable")
```

## Integration with Trade Analyzer

Combine Barchart data with our analyzer:

```python
from trade_analyzer import analyze_trade
from barchart_client import get_trading_recommendation

# Analyze a trade
analysis = analyze_trade("NVDA 1000 CALL @ 15.50 0DTE")

# Get Barchart context
barchart_rec = get_trading_recommendation("NVDA", "CALL")

# Combine signals
if analysis.score > 70 and barchart_rec['recommendation'] == 'BUY':
    print("✅ STRONG SETUP: Analyzer + Barchart both bullish")
elif analysis.score > 70:
    print("⚠️ Analyzer bullish but Barchart neutral")
elif barchart_rec['recommendation'] == 'BUY':
    print("⚠️ Barchart bullish but analyzer neutral")
else:
    print("❌ Both neutral/bearish - skip or small size")
```

## Data Storage

Barchart data is stored in:
```
logs/barchart_data.json
```

Export your data:
```python
data.export_json("my_barchart_data.json")
```

## Tips for Using Barchart

1. **Check IV Rank daily** - Low IV = better odds for long options
2. **Watch unusual activity** - Large orders often precede moves
3. **Follow the flow** - Call/Put ratio shows institutional sentiment
4. **Combine with our analyzer** - Use both for confirmation
5. **Trade small on neutral signals** - Only size up on strong agreement

## Barchart Premium Features

Barchart Premier offers:
- Real-time data
- More filtering options
- API access
- Custom screeners

This integration works with free Barchart data as well.

## File Location

```
src/market_data/barchart_client.py
```

Import:
```python
from market_data.barchart_client import BarchartData, get_trading_recommendation
```
