# Enhanced Analysis Features Guide

## Overview

This guide explains the new advanced technical analysis features implemented to improve win rates and profitability.

---

## Phase 1: Price Action-Based Support/Resistance

### What It Does
Identifies real support and resistance zones from actual price behavior (swing highs/lows) instead of algorithmic psychological levels.

### Key Features
- **Swing Point Detection**: Finds actual turning points in price where sellers overwhelmed buyers (resistance) or buyers overwhelmed sellers (support)
- **Zone Clustering**: Groups nearby levels within 0.5% or 0.5×ATR into zones
- **Strength Scoring**: Rates zones 0-100 based on:
  - Touches (40 pts): More tests = stronger level
  - Volume (30 pts): Higher volume = institutional level
  - Recency (30 pts): Recent = more relevant

### How to Use

```python
from analysis.price_action import calculate_support_resistance_zones
import yfinance as yf

# Fetch data
df = yf.download("AAPL", period="3mo")
current_price = df['Close'].iloc[-1]

# Calculate zones
zones = calculate_support_resistance_zones(
    df=df,
    current_price=current_price,
    lookback_days=60,
    min_touches=2,
    atr=atr_value  # Optional: from ATR calculation
)

# Access results
support_zones = zones['support_zones']
resistance_zones = zones['resistance_zones']
key_levels = zones['key_levels']

# Example: Nearest support
nearest_support = key_levels['nearest_support']
print(f"Strong support at ${nearest_support:.2f}")
```

### Configuration

```yaml
# config/config.yaml
analysis:
  support_resistance:
    enabled: true
    method: "price_action"  # or "psychological" or "hybrid"
    lookback_days: 60
    min_touches: 2
    zone_clustering_pct: 0.5
    max_levels: 5
```

### Trading Impact
- **Better stops**: Place stops just below support (calls) or above resistance (puts) instead of arbitrary % levels
- **Better targets**: Target actual resistance levels (calls) or support levels (puts)
- **Higher win rate**: Real levels are respected more often than psychological levels

---

## Phase 2: Volume Analysis

### What It Does
Analyzes volume to confirm price moves, identify institutional levels, and detect anomalies.

### Key Features
- **VWAP**: Volume-Weighted Average Price = institutional average cost
- **Volume Profile**: Shows price levels with highest volume (POC = Point of Control)
- **Volume Confirmation**: Validates price moves with volume
- **Anomaly Detection**: Flags unusual volume spikes or dry-ups

### How to Use

```python
from analysis.volume_analysis import (
    calculate_vwap,
    build_volume_profile,
    volume_confirmation,
    detect_volume_anomalies
)

# VWAP
vwap = calculate_vwap(df, period='daily')
current_vwap = vwap.iloc[-1]

# Check price vs VWAP
if current_price > current_vwap * 1.02:
    print("Price overextended above VWAP - mean reversion risk")

# Volume Profile
profile = build_volume_profile(df, price_bins=50)
poc = profile['poc']  # Point of Control - highest volume price
value_area_high = profile['value_area_high']
value_area_low = profile['value_area_low']

print(f"POC (institutional price): ${poc:.2f}")
print(f"Value Area: ${value_area_low:.2f} - ${value_area_high:.2f}")

# Volume Confirmation
price_move = 2.5  # 2.5% move
volume_change = 75  # 75% above average

conf = volume_confirmation(price_move, volume_change)
if conf['confirmed']:
    print(f"Move confirmed: {conf['reasoning']}")
```

### Configuration

```yaml
analysis:
  volume:
    enabled: true
    vwap_enabled: true
    volume_profile_enabled: true
    volume_spike_threshold: 2.0
    vwap_deviation_warning_pct: 2.0
```

### Trading Impact
- **Filter fake breakouts**: Strong moves without volume = likely reversal
- **Confirm entries**: Only enter when volume supports the move
- **Use VWAP as dynamic S/R**: Price tends to revert to VWAP
- **Identify institutional levels**: POC and value area = where big money traded

---

## Phase 3: Candlestick Pattern Recognition

### What It Does
Detects high-reliability reversal and continuation patterns with strength scoring.

### Patterns Detected
1. **Bullish/Bearish Engulfing**: Strong reversal pattern
2. **Hammer/Shooting Star**: Rejection patterns (pin bars)
3. **Doji**: Indecision candle (powerful at S/R)
4. **Morning/Evening Star**: 3-bar reversal pattern
5. **Three White Soldiers/Black Crows**: Strong continuation

### How to Use

```python
from analysis.candlestick_patterns import get_pattern_signals, pattern_strength_score

# Detect patterns in recent bars
patterns = get_pattern_signals(
    df=df,
    lookback=10,
    patterns=['engulfing', 'pinbar', 'morning_star'],
    require_volume_confirmation=True
)

# Check for bullish patterns (for call entries)
for pattern in patterns:
    if pattern['direction'] == 'bullish':
        print(f"{pattern['pattern']}: Strength {pattern['strength']}/100")
        if pattern['volume_confirmed']:
            print("  ✓ Volume confirmed")

        # Score with context
        context = {
            'at_support': True,  # Pattern at support level
            'trend': 'uptrend'   # Pattern aligned with trend
        }
        score = pattern_strength_score(pattern, context)
        print(f"  Overall score: {score}/100")
```

### Configuration

```yaml
analysis:
  patterns:
    enabled: true
    lookback_bars: 10
    detect_patterns: ["engulfing", "pinbar", "doji", "morning_star", "evening_star"]
    require_volume_confirmation: true
    bonus_at_sr: 10  # Bonus points when pattern at S/R
```

### Trading Impact
- **Better entry timing**: Wait for pattern confirmation before entering
- **Higher win rate**: Patterns at S/R have 70-80% success rate
- **Context matters**: Bullish engulfing at support in uptrend = highest probability
- **Avoid premature entries**: No pattern = wait for confirmation

---

## Phase 4: Trend Analysis

### What It Does
Identifies trend direction and strength using price structure and ADX.

### Key Features
- **Swing Structure**: Higher highs + higher lows = uptrend
- **ADX (Average Directional Index)**: Measures trend strength
  - ADX > 25 = strong trend
  - ADX < 20 = weak/no trend
- **Multi-Timeframe Alignment**: Checks if daily, 4h, 1h all agree
- **Trendline Detection**: Finds ascending/descending trendlines

### How to Use

```python
from analysis.trend_analysis import (
    identify_trend,
    calculate_adx,
    detect_trend_structure,
    multi_timeframe_trend_alignment
)

# Identify trend
trend = identify_trend(df, method='swing_points')
print(f"Trend: {trend['direction']}")
print(f"Strength: {trend['strength']}/100")

# Check ADX
adx = calculate_adx(df, period=14)
current_adx = adx.iloc[-1]
if current_adx > 25:
    print(f"Strong trend (ADX: {current_adx:.1f})")
else:
    print(f"Weak trend (ADX: {current_adx:.1f})")

# Trend structure
structure = detect_trend_structure(df, lookback=50)
if structure['higher_highs'] > structure['lower_highs']:
    print("Higher highs dominating - uptrend intact")

# Multi-timeframe alignment (requires data fetching function)
def fetch_data(ticker, timeframe):
    # Implement data fetching for different timeframes
    pass

alignment = multi_timeframe_trend_alignment(
    ticker="AAPL",
    timeframes=['daily', '4h', '1h'],
    fetch_data_func=fetch_data
)

if alignment['aligned']:
    print(f"All timeframes aligned: {alignment['direction']}")
```

### Configuration

```yaml
analysis:
  trend:
    enabled: true
    adx_period: 14
    adx_trending_threshold: 25
    adx_weak_threshold: 20
    multi_timeframe: [daily, 4h, 1h]
    alignment_bonus: 15  # Setup score bonus
    counter_trend_severity: "high"  # Red flag severity
```

### Trading Impact
- **Avoid counter-trend trades**: Call in downtrend = massive failure rate
- **Trade with momentum**: Uptrend + call = much higher win rate
- **Multi-timeframe confirmation**: All timeframes aligned = highest probability
- **ADX for conviction**: Strong trend (ADX > 25) = stay with it

---

## Integration with Setup Scoring

### Setup Score Calculation (0-100)

The enhanced setup score now includes:

**Base Components** (existing):
- Rules compliance: +10
- Green flags: +3 each (max +15)
- Red flags: -6 (medium) or -12 (high)
- PoP adjustment: ±5
- Liquidity: ±3
- Technical confluence: +15
- Events: -5 to -10
- Theta risk: -6

**NEW Components**:
- **Price action bonus**: +10 (at strong S/R zone)
- **Pattern bonus**: +10 (bullish pattern for calls, bearish for puts)
- **Multi-timeframe alignment**: +15 (all TFs aligned with trade)
- **Volume bonus**: +5 (strong volume confirmation)
- **Counter-trend penalty**: -10 (call in downtrend, put in uptrend)

### Score Interpretation

- **90-100**: Exceptional setup (1.5x position size recommended)
- **80-89**: High quality (1.25x size)
- **70-79**: Good baseline (1.0x size)
- **60-69**: Medium quality (0.75x size)
- **<60**: Reject trade

### Example Score Breakdown

```
Base: 70
+ Rules compliance: +10
+ Green flags (3×3): +9
- Red flags (1 medium): -6
+ PoP > 60%: +5
+ Liquidity: +3
+ Technical confluence: +15
+ Price at support: +10
+ Bullish engulfing: +10
+ Multi-TF alignment: +15
+ Volume confirmed: +5
= 146 → Capped at 100

Final Score: 100/100 (EXCEPTIONAL SETUP)
```

---

## Red Flags (Enhanced)

### New Red Flags Added

1. **Counter-Trend** (HIGH severity)
   - "Counter-trend trade: call entry in downtrend (strength: 80)"
   - Avoid unless reversal setup with multiple confirmations

2. **VWAP Deviation** (MEDIUM severity)
   - "Price 3.2% above VWAP - mean reversion risk"
   - Caution on entries when price extended from VWAP

3. **Volume Divergence** (MEDIUM severity)
   - "Strong price move not confirmed by volume"
   - Potential false breakout

4. **Conflicting Pattern** (MEDIUM severity)
   - "Bearish engulfing pattern conflicts with call entry"
   - Wait for pattern resolution

---

## Green Flags (Enhanced)

### New Green Flags Added

1. **Price Action**
   - "Price at strong support $215.50 - bounce opportunity"
   - Entry at validated S/R zone

2. **Candlestick Pattern**
   - "Bullish engulfing pattern detected (strength: 85/100)"
   - High-probability reversal confirmation

3. **Volume Confirmation**
   - "Volume increasing (75%) - strong institutional interest"
   - Move backed by volume

4. **Trend Alignment**
   - "Aligned with uptrend (strength: 80/100)"
   - Trading with momentum

5. **Multi-Timeframe Alignment**
   - "Multi-timeframe alignment: uptrend across all timeframes"
   - Highest conviction setup

---

## Practical Trading Examples

### Example 1: High-Probability Call Entry

```
Ticker: AAPL @ $218.50
Setup: Call entry

Analysis Results:
✓ Price at support zone $217.80-$218.20 (3 touches, strength 85)
✓ Bullish hammer pattern (strength 78/100, volume confirmed)
✓ Daily uptrend (ADX 32) + 4h uptrend + 1h uptrend
✓ Volume spike (2.3x average)
✓ Price near VWAP $218.00 (not overextended)

Setup Score: 95/100 (EXCEPTIONAL)
Recommendation: PLAY with 1.5x position size
```

### Example 2: Avoid Counter-Trend

```
Ticker: TSLA @ $235.00
Setup: Call entry

Analysis Results:
✗ Strong downtrend (ADX 45, lower lows confirmed)
✗ Bearish three black crows pattern
✗ Volume declining (breakdown not over)
✗ Price 4% below VWAP (momentum bearish)
✓ At potential support $235

Setup Score: 55/100 (REJECT)
Recommendation: AVOID - counter-trend, wait for reversal confirmation
```

### Example 3: Wait for Confirmation

```
Ticker: SPY @ $480.50
Setup: Call entry

Analysis Results:
~ Near resistance $481.50 (2 touches, moderate strength)
~ Doji pattern (indecision)
~ Volume average (no spike)
~ Trend sideways (ADX 18)
✓ At support $479-$480

Setup Score: 68/100 (MEDIUM)
Recommendation: HOLD - wait for directional confirmation (pattern + volume)
```

---

## Best Practices

### Entry Checklist
1. ✓ Price at strong S/R zone (check price_action)
2. ✓ Bullish/bearish pattern confirmed (check patterns)
3. ✓ Volume confirms move (check volume_analysis)
4. ✓ Aligned with trend (check trend_analysis)
5. ✓ Multi-timeframe alignment (if possible)
6. ✓ Setup score ≥ 75

### Exit Checklist (Phase 5 - coming soon)
1. ✓ Hit resistance target
2. ✓ Reversal pattern forms
3. ✓ Trendline break
4. ✓ Volume divergence
5. ✓ Trailing stop hit

### Position Sizing Checklist (Phase 6 - coming soon)
1. ✓ Setup score determines multiplier
2. ✓ IV rank adjustment
3. ✓ Kelly Criterion (if available)
4. ✓ Drawdown protection active
5. ✓ Correlation check passed

---

## Configuration Profiles

### Conservative Profile
```yaml
analysis:
  support_resistance:
    min_touches: 3  # Stricter S/R
  patterns:
    require_volume_confirmation: true
  trend:
    counter_trend_severity: "high"
```

### Moderate Profile (Recommended)
```yaml
analysis:
  support_resistance:
    min_touches: 2
  patterns:
    require_volume_confirmation: true
  trend:
    counter_trend_severity: "high"
```

### Aggressive Profile
```yaml
analysis:
  support_resistance:
    min_touches: 1
  patterns:
    require_volume_confirmation: false
  trend:
    counter_trend_severity: "medium"
```

---

## Troubleshooting

### Issue: No support/resistance zones found
**Solution**:
- Increase lookback_days (try 90)
- Lower min_touches (try 1)
- Use "hybrid" method to include psychological levels

### Issue: No patterns detected
**Solution**:
- Increase lookback_bars (try 20)
- Disable volume_confirmation temporarily
- Check if data has sufficient bars

### Issue: Trend shows "unknown"
**Solution**:
- Ensure DataFrame has at least 20 bars
- Check data quality (no missing values)
- Try method='adx' instead of 'swing_points'

### Issue: Setup score always low
**Solution**:
- Check that market_context is being passed to trade_analyzer
- Verify all analysis modules are enabled in config
- Review red flags - address high severity issues

---

## Performance Monitoring

### Track These Metrics
- **Win rate by setup score bracket**:
  - 90-100: Target 75-80% win rate
  - 80-89: Target 65-70%
  - 70-79: Target 55-60%
  - 60-69: Target 45-50%

- **Avg R by setup type**:
  - With S/R confirmation: Target 2.5R+
  - With pattern confirmation: Target 2.8R+
  - With trend alignment: Target 3.0R+
  - All aligned: Target 3.5R+

- **Counter-trend vs with-trend**:
  - Counter-trend win rate should be <40%
  - With-trend win rate should be >60%

---

## Next Phases Preview

### Phase 5: Dynamic Exits (Coming Next)
- ATR-based trailing stops
- Technical level trailing (support/resistance)
- Reversal pattern exits
- Partial exits at multiple targets

### Phase 6: Smart Position Sizing (Following)
- Kelly Criterion calculation
- Setup quality multipliers (0.75x to 1.5x)
- Volatility adjustment
- Drawdown protection

### Phase 7: Advanced Patterns (Final)
- Fibonacci retracements/extensions
- Double tops/bottoms
- Head & shoulders
- Triangles and consolidations

---

## Resources

- **Implementation Status**: See IMPLEMENTATION_STATUS.md
- **Configuration**: config/config.yaml
- **Module Documentation**: Docstrings in each module
- **Examples**: Unit tests in each module's `if __name__ == "__main__"` block

---

## Support

For questions or issues:
1. Check module docstrings for detailed parameter descriptions
2. Review unit test examples in each module
3. See IMPLEMENTATION_STATUS.md for known issues
4. Test with small position sizes during validation phase
