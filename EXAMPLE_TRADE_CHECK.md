# Example Trade Check Output
## Real-Time Pre-Trade Analysis

---

## Example 1: AAPL 280 CALL @ $4.00 (Current: Feb 9, 2026)

```
================================================================================
  QUICK TRADE CHECK: AAPL 280.0 CALL @ $4.00
================================================================================

Underlying: $272.17
DTE: 7 days
Premium: $4.00

================================================================================
  RECOMMENDATION: CAUTIOUS / SMALL SIZE
  Confidence: 45%
================================================================================

GREEN FLAGS:
  [+] Good support at $270.50 (strength: 78)
  [+] Good time buffer (7d)
  [+] Adequate premium for risk management

RED FLAGS:
  [-] Strike $280 is 2.9% OTM - moderate barrier
  [-] Near resistance $278.50 (strength: 75) - overhead supply
  [-] Negative momentum: -1.8% (5d)
  [-] Low volume: 0.8x average

IF YOU TAKE IT - KEY WATCH LEVELS:
----------------------------------------
  BREAKOUT ALERT: $278.50
    → If breaks above with volume >1.5x avg:
       - HOLD RUNNER (don't exit early)
       - Trail stop to $277.10
       - New target: $285.20

  REJECTION ALERT: Watch for bearish candles near resistance
    → Shooting star, bearish engulfing, long upper wick:
       - EXIT 60-80% immediately
       - Lock partial profit before reversal

  STOP LOSS: Below $270.50
    → Or -1R on premium (~$2.00)

  TIME RISK: If no move in 2 days → theta decay accelerates

================================================================================
```

**Interpretation**:
- **MARGINAL** setup - strike 2.9% OTM with resistance nearby
- Recent weakness (-1.8% in 5 days) + low volume = risky
- **IF you take it**: Watch $278.50 resistance closely
  - Breakout above = HOLD for $285+
  - Rejection = EXIT 60-80% immediately

---

## Example 2: NVDA 145 CALL @ $2.50 (Strong Setup)

```
================================================================================
  QUICK TRADE CHECK: NVDA 145.0 CALL @ $2.50
================================================================================

Underlying: $146.80
DTE: 5 days
Premium: $2.50

================================================================================
  RECOMMENDATION: TAKE THE TRADE
  Confidence: 75%
================================================================================

GREEN FLAGS:
  [+] Strike $145.0 ITM by 1.2%
  [+] With the trend (uptrend)
  [+] Strong 5-day momentum: +4.3%
  [+] High volume: 1.8x average
  [+] Good support at $143.50 (strength: 82)

RED FLAGS:
  [-] Short DTE (5d) - high theta decay risk
  [-] Near resistance $149.50 - watch for rejection

IF YOU TAKE IT - KEY WATCH LEVELS:
----------------------------------------
  BREAKOUT ALERT: $149.50
    → If breaks above with volume >1.5x avg:
       - HOLD RUNNER (don't exit early)
       - Trail stop to $148.80
       - New target: $155.00

  REJECTION ALERT: Watch for bearish candles near $149.50
    → Shooting star, bearish engulfing, long upper wick:
       - EXIT 60-80% immediately
       - Lock partial profit before reversal

  STOP LOSS: Below $143.50
    → Or -1R on premium (~$1.25)

  TIME RISK: If no move in 1 day → theta decay accelerates

================================================================================
```

**Interpretation**:
- **STRONG** setup - ITM, momentum, volume all positive
- Uptrend confirmed, good support below
- **Watch**: $149.50 resistance for breakout or rejection
- **Risk**: Short 5 DTE means fast decay if it stalls

---

## Example 3: SPY 600 CALL @ $1.25 (Pass)

```
================================================================================
  QUICK TRADE CHECK: SPY 600.0 CALL @ $1.25
================================================================================

Underlying: $594.50
DTE: 3 days
Premium: $1.25

================================================================================
  RECOMMENDATION: PASS
  Confidence: 25%
================================================================================

GREEN FLAGS:
  [+] Good support at $592.00 (strength: 85)

RED FLAGS:
  [-] Strike $600 is 0.9% OTM - moderate barrier
  [-] At resistance $596.50 (strength: 88) - likely rejection
  [-] Counter-trend trade (downtrend, taking calls)
  [-] Negative momentum: -2.4% (5d)
  [-] Short DTE (3d) - high theta decay risk
  [-] Low premium - poor R/R for stops

STRONG PASS:
----------------------------------------
  Setup quality too low. Look for better opportunities.

================================================================================
```

**Interpretation**:
- **AVOID** - Too many red flags
- Counter-trend + at strong resistance + short DTE = high risk
- Wait for better setup

---

## Example 4: QQQ 610 PUT @ $3.20 (Good Short Setup)

```
================================================================================
  QUICK TRADE CHECK: QQQ 610.0 PUT @ $3.20
================================================================================

Underlying: $608.20
DTE: 7 days
Premium: $3.20

================================================================================
  RECOMMENDATION: TAKE THE TRADE
  Confidence: 70%
================================================================================

GREEN FLAGS:
  [+] Strike near current price (ATM)
  [+] With the trend (downtrend)
  [+] Bearish momentum: -3.2% (5d)
  [+] High volume: 1.6x average
  [+] Good time buffer (7d)
  [+] Adequate premium for risk management

RED FLAGS:
  [-] At support $607.50 - may bounce

IF YOU TAKE IT - KEY WATCH LEVELS:
----------------------------------------
  BREAKDOWN ALERT: $607.50
    → If breaks below with volume >1.5x avg:
       - HOLD RUNNER
       - Trail stop to $610.50
       - Target next support ~$600

  REJECTION ALERT: Watch for bullish candles near support
    → Hammer, bullish engulfing:
       - EXIT 60-80% immediately
       - Support may hold, cut loss

  STOP LOSS: Above $613.00
    → Or -1R on premium (~$1.60)

  TIME RISK: If no move in 2 days → theta decay accelerates

================================================================================
```

**Interpretation**:
- **SOLID PUT** setup - downtrend, momentum, volume all aligned
- ATM strike, good premium for stops
- **Watch**: $607.50 support - break below = strong downside
- **Risk**: Rejection at support could reverse quickly

---

## How To Use This

### **Morning Routine** (Discord Alerts Come In)
1. Alert: "AAPL 280 CALL @ $4.00"
2. Run: `python src/tools/quick_trade_check.py AAPL 280 CALL 4.00 --dte 7`
3. See: Confidence 45% → MARGINAL → Take small size or pass
4. Decision: Pass (too many red flags) or 1/2 size if feeling it

### **Alternative** (Use Main Bot)
```bash
python src/main.py "AAPL 280 CALL @ 4.00"
```
Bot now includes quick check in report!

---

## Key Patterns

### **TAKE (70%+ confidence)**
- ITM or ATM strike
- With the trend
- Positive momentum
- High volume
- Good support/resistance structure

### **MARGINAL (50-70%)**
- Mixed signals
- Some red flags but manageable
- **Action**: Small size, tight stops, active management

### **PASS (<50%)**
- Too many red flags
- Counter-trend
- At strong resistance (calls) / support (puts)
- Low volume, negative momentum
- **Action**: Wait for better setup

---

## Next: Live Monitoring

Once you enter a trade, switch to **Live Monitor** mode:
```bash
python src/tools/live_monitor.py AAPL 280 CALL 4.00 --entry-time "2026-02-09 10:30"
```

Monitor will:
- Poll price every 5-15 min
- Alert on breakouts (HOLD RUNNER!)
- Alert on rejections (EXIT 60-80%!)
- Track P/L and R multiples
- Auto-suggest stop adjustments

---

**Bottom Line**:
Quick check gives you instant "go/no-go" + watch levels. No more guessing "should I take this?" - the bot tells you, with clear reasons why.
