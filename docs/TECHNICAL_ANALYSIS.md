# Comprehensive Technical Analysis Module

Detailed technical analysis for options trading with explanations of all indicators.

## Features

1. **Price Action Analysis** - Current price, daily range, 52-week extremes
2. **Pivot Point Analysis** - Key S/R levels (PP, R1-R3, S1-S3)
3. **Moving Averages** - SMA 20, 50, 200 with trend signals
4. **Fibonacci Retracements** - Key levels from recent high/low
5. **RSI (Relative Strength Index)** - Overbought/oversold conditions
6. **MACD** - Momentum and trend direction
7. **ATR (Average True Range)** - Volatility measurement
8. **Volume Analysis** - Relative volume signals
9. **Trend Analysis** - Short/medium/long-term trends
10. **Options Analysis** - IV, Greeks, Probability of Profit

## Quick Start

```bash
# Basic analysis
python scripts/technical_analysis_cli.py QQQ

# With option details
python scripts/technical_analysis_cli.py QQQ --strike 590 --type PUT --premium 0.70 --dte 0

# AAPL call analysis
python scripts/technical_analysis_cli.py AAPL --strike 280 --type CALL --premium 0.49 --dte 1
```

## Programmatic Usage

```python
from analysis.technical_analysis import run_full_analysis

# Run complete analysis
setup = run_full_analysis(
    ticker='QQQ',
    strike=590,
    option_type='PUT',
    premium=0.70,
    dte=0
)

# Access individual components
print(f"Score: {setup.overall_score}/100")
print(f"Direction: {setup.direction_preference}")
print(f"Trend: {setup.trend.short_term}")
print(f"IV Signal: {setup.options.iv_signal}")
print(f"PoP: {setup.options.probability_of_profit}%")
```

## Indicator Explanations

### RSI (Relative Strength Index)
| Value | Signal | Meaning |
|-------|--------|---------|
| > 70 | Overbought | Price may reverse lower |
| 50-70 | Neutral Bullish | Momentum favoring buyers |
| 30-50 | Neutral Bearish | Momentum favoring sellers |
| < 30 | Oversold | Price may reverse higher |

### MACD
| Condition | Signal | Meaning |
|-----------|---------|---------|
| MACD > Signal | Bullish | Upward momentum |
| MACD < Signal | Bearish | Downward momentum |
| Histogram Growing | Strengthening | Momentum accelerating |
| Histogram Shrinking | Weakening | Momentum slowing |

### IV Rank
| Rank | Signal | Options Pricing |
|------|--------|-----------------|
| 0-30 | Low | Cheap - favorable for buyers |
| 30-70 | Normal | Fair pricing |
| 70-100 | High | Expensive - IV crush risk |

### Probability of Profit (PoP)
| PoP | Signal | Trade Suitability |
|-----|--------|-------------------|
| > 70% | Excellent | Great odds |
| 55-70% | Good | Favorable |
| 45-55% | Acceptable | Neutral |
| 30-45% | Poor | Risky |
| < 30% | Terrible | Avoid |

## Greeks Explained

| Greek | Measures | For 0DTE |
|-------|----------|----------|
| Delta | Stock move → Option move | High (0.3-0.7) = good |
| Gamma | Delta's rate of change | High = fast moves |
| Theta | Daily time decay | More negative = faster decay |
| Vega | Sensitivity to IV | High = IV moves matter |

## Pivot Points

| Level | Calculation | Usage |
|-------|-------------|-------|
| PP | (High + Low + Close) / 3 | Neutral point |
| R1 | 2 × PP - Low | First resistance |
| R2 | PP + (High - Low) | Second resistance |
| R3 | High + 2 × (PP - Low) | Strong resistance |
| S1 | 2 × PP - High | First support |
| S2 | PP - (High - Low) | Second support |
| S3 | Low - 2 × (High - PP) | Strong support |

## Fibonacci Retracements

| Level | Usage |
|-------|-------|
| 38.2% | Shallow retracement |
| 50% | Halfway point (psychological) |
| 61.8% | Golden ratio - key support/resistance |

## Output Sections

1. **Price Action** - Current price context
2. **Key Levels** - Pivot-based S/R
3. **Moving Averages** - Trend filters
4. **Fibonacci** - Reversal levels
5. **Technical Indicators** - RSI, MACD, ATR
6. **Trend Analysis** - Multi-timeframe direction
7. **Options Analysis** - IV, Greeks, PoP
8. **Summary** - Score, recommendation, pros/cons

## Example Output

```
================================================================================
COMPREHENSIVE TECHNICAL ANALYSIS: QQQ
================================================================================

--------------------------------------------------------------------------------
PRICE ACTION
--------------------------------------------------------------------------------
Current Price:     $600.88
Day Range:        $594.77 - $604.81
52w High:         $636.60
52w Low:          $579.99

--------------------------------------------------------------------------------
KEY LEVELS
--------------------------------------------------------------------------------
Resistance 1:     $605.54
Pivot Point:      $600.15
Support 1:        $595.50

--------------------------------------------------------------------------------
TECHNICAL INDICATORS
--------------------------------------------------------------------------------
RSI (14):         36.9  [neutral_bearish]
  → RSI Interpretation:
     Bearish bias. Momentum favoring sellers.

MACD:             -1.614
Signal Line:      0.844
Histogram:        -2.458  [bearish]

--------------------------------------------------------------------------------
OPTIONS ANALYSIS
--------------------------------------------------------------------------------
IV Rank:          0/100
Probability of Profit: 32%  [poor]

================================================================================
SUMMARY & RECOMMENDATION
================================================================================
OVERALL SCORE:     45/100  [AVERAGE]
DIRECTION:         NEUTRAL
RISK LEVEL:        HIGH

RECOMMENDATION:    CAUTION - Slight bearish bias
```

## Files

- `src/analysis/technical_analysis.py` - Main module
- `scripts/technical_analysis_cli.py` - CLI interface
- `docs/TECHNICAL_ANALYSIS.md` - This documentation
