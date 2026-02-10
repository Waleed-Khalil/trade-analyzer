# Live Monitor - Example Output
## Real-Time Trade Coaching After Entry

---

## Example: Monitoring AAPL 280 CALL

### **Entry**
- **Time**: 10:30 AM
- **Underlying**: $274.50
- **Premium**: $4.00
- **Contracts**: 5
- **Stop**: $2.00 (50%)

### **Command**:
```bash
python src/tools/live_monitor.py AAPL 280 CALL 4.00 274.50 --contracts 5 --dte 7
```

---

## **Initial Output** (10:30 AM)

```
================================================================================
  LIVE MONITOR: AAPL 280.0 CALL
================================================================================

Initializing position...
  Entry Premium: $4.00
  Entry Underlying: $274.50
  Contracts: 5
  Stop Loss: $2.00 (-50.0%)
  Risk per Contract: $2.00
  DTE: 7 days

Key Resistance Levels to Watch:
  R1: $278.50 (+1.5%) - Strength: 75
  R2: $285.20 (+3.9%) - Strength: 68
  R3: $290.00 (+5.6%) - Strength: 62

Monitoring started at 10:30:15
Polling every 5 minutes

================================================================================
```

---

## **Status Update #1** (10:35 AM - No Movement)

```
[10:35:22] Status Update
--------------------------------------------------------------------------------
  Underlying: $275.10 (Entry: $274.50)
  Est Premium: $4.12 (Entry: $4.00)
  P/L: $+60 (+3.0%) | +0.06R
  Contracts: 5 open
  Stop: $2.00
  Time: 0h 5m in position
--------------------------------------------------------------------------------

Next check in 5 minutes...
```

---

## **Status Update #2** (10:40 AM - Approaching Resistance)

```
[10:40:18] Status Update
--------------------------------------------------------------------------------
  Underlying: $277.80 (Entry: $274.50)
  Est Premium: $4.85 (Entry: $4.00)
  P/L: $+425 (+21.3%) | +0.42R
  Contracts: 5 open
  Stop: $2.00
  Time: 0h 10m in position
--------------------------------------------------------------------------------

Next check in 5 minutes...
```

---

## **BREAKOUT ALERT!** (10:45 AM - Breaks R1)

```
[10:45:31] Status Update
--------------------------------------------------------------------------------
  Underlying: $279.20 (Entry: $274.50)
  Est Premium: $5.20 (Entry: $4.00)
  P/L: $+600 (+30.0%) | +0.60R
  Contracts: 5 open
  Stop: $2.00
  Time: 0h 15m in position
--------------------------------------------------------------------------------

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  [!] BREAKOUT ALERT - HIGH URGENCY
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

[+] BREAKOUT CONFIRMED at $278.50!

    ACTION: HOLD ALL 5 CONTRACTS
    → Trail stop to $277.60
    → New target: $285.20

    Reason: Broke $278.50 (strength: 75) on 1.8x volume - now support

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Next check in 5 minutes...
```

**What You Do**:
- DON'T exit at your planned T1!
- Hold full position for R2 ($285)
- Trail stop to $277.60 (below broken R1)

---

## **Status Update #3** (10:50 AM - Continued Move)

```
[10:50:15] Status Update
--------------------------------------------------------------------------------
  Underlying: $281.50 (Entry: $274.50)
  Est Premium: $6.10 (Entry: $4.00)
  P/L: $+1,050 (+52.5%) | +1.05R
  Contracts: 5 open
  Stop: $3.05 (trailing from profit)
  Time: 0h 20m in position
--------------------------------------------------------------------------------

Next check in 5 minutes...
```

**Notice**: Stop automatically trailed from $2.00 → $3.05 as profit grows

---

## **Alternative Scenario: REJECTION ALERT** (Instead of Breakout)

If price had REJECTED at $278.50 instead of breaking:

```
[10:45:31] Status Update
--------------------------------------------------------------------------------
  Underlying: $278.80 (Entry: $274.50)
  Est Premium: $4.95 (Entry: $4.00)
  P/L: $+475 (+23.8%) | +0.48R
  Contracts: 5 open
  Stop: $2.00
  Time: 0h 15m in position
--------------------------------------------------------------------------------

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  [!] REJECTION ALERT - HIGH URGENCY
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

[-] REJECTION DETECTED at current level!
    Pattern: shooting_star

    ACTION: EXIT 3 CONTRACTS (60%)
    → Keep 2 with tight stop

    Reason: shooting_star at $278.50 - take increased profit

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Next check in 5 minutes...
```

**What You Do**:
- EXIT 3/5 contracts immediately @ ~$4.95
- Lock in $475 profit on 60%
- Hold 2 contracts with tight stop in case it still breaks

---

## **Stop Hit Scenario**

```
[11:20:45] Status Update
--------------------------------------------------------------------------------
  Underlying: $273.50 (Entry: $274.50)
  Est Premium: $1.90 (Entry: $4.00)
  P/L: $-1,050 (-52.5%) | -1.05R
  Contracts: 5 open
  Stop: $2.00
  Time: 0h 50m in position
--------------------------------------------------------------------------------

[!] STOP HIT at $1.90 (Stop: $2.00)
    EXIT ALL 5 CONTRACTS
    Loss: $-1050 (-52.5%)
```

**What You Do**:
- Exit all contracts
- Accept loss at -1.05R
- Move on to next setup

---

## **Manual Stop (Ctrl+C)**

```
^C

================================================================================
  MONITORING STOPPED BY USER
================================================================================

Final Position Summary:
  Entry: $4.00
  Current Est: $5.80
  P/L: $+900 (+45.0% / +0.90R)
  Contracts: 5 still open

```

---

## **Real-World Usage Flow**

### **Morning: Discord Alert**
```
[9:45 AM] Alert: "AAPL 280 CALL @ $4.00"
```

**Step 1: Quick Check**
```bash
python src/tools/quick_trade_check.py AAPL 280 CALL 4.00 --dte 7
```
→ Result: 65% confidence → **TAKE THE TRADE**

**Step 2: Enter Position**
- Buy 5 contracts @ $4.00
- Note entry time: 10:30 AM
- Underlying: $274.50

**Step 3: Start Monitor**
```bash
python src/tools/live_monitor.py AAPL 280 CALL 4.00 274.50 --contracts 5 --dte 7
```

**Step 4: Let It Run**
- Monitor runs in background
- Alerts pop up when something happens
- You make decisions: hold or exit

**Step 5: Close When Done**
- Breakout → Hold to next target
- Rejection → Exit partial per alert
- Stop hit → Auto-notify
- Ctrl+C when ready to close

---

## **Key Benefits**

### **Before (Manual Monitoring)**:
- "Is it breaking resistance?" → Check TradingView every 10 min
- "Should I hold or exit?" → Emotional decision
- "Where's my stop?" → Maybe forgot to update
- **Time**: 30-60 min actively watching
- **Stress**: High - constant uncertainty

### **After (Live Monitor)**:
- Alerts tell you: "BREAKOUT - HOLD!"
- Clear action: "EXIT 60% NOW"
- Stop auto-trails on profit
- **Time**: 0 min - just respond to alerts
- **Stress**: Low - bot watches for you

---

## **Monitor Settings**

### **Poll Interval** (How often to check)
- `--interval 300` (5 min) - Default, good balance
- `--interval 180` (3 min) - More responsive, faster alerts
- `--interval 600` (10 min) - Less spam, slower alerts
- `--interval 60` (1 min) - High frequency (use for 0DTE)

### **Stop Loss**
- Default: 50% of premium
- Custom: `--stop 1.50` (set exact stop price)

### **Example Commands**

**Standard 7 DTE trade**:
```bash
python src/tools/live_monitor.py AAPL 280 CALL 4.00 274.50
```

**0DTE fast monitoring**:
```bash
python src/tools/live_monitor.py SPY 600 CALL 1.25 598.50 --dte 0 --interval 60
```

**Large position with tight stop**:
```bash
python src/tools/live_monitor.py NVDA 195 CALL 6.20 193.40 --contracts 10 --stop 4.00
```

---

## **What The Bot Watches For**

### **For CALLS**:
1. **Breakout above resistance** → Volume >1.5x avg → HOLD RUNNER
2. **Rejection at resistance** → Bearish candle → EXIT 60-80%
3. **Stop hit** → Below trailing stop → EXIT ALL
4. **Profit trailing** → Moves stop up as profit grows

### **For PUTS**:
1. **Breakdown below support** → Volume >1.5x avg → HOLD RUNNER
2. **Rejection at support** → Bullish candle → EXIT 60-80%
3. **Stop hit** → Above trailing stop → EXIT ALL
4. **Profit trailing** → Moves stop down as profit grows

---

## **Tips**

1. **Run in separate terminal** - Keep monitoring window visible
2. **Check alerts immediately** - Breakout/rejection = time-sensitive
3. **Trust the stop** - If hit, exit (don't hope it recovers)
4. **Manual override OK** - Ctrl+C anytime if you want manual control
5. **Paper log** - Note what bot said vs what you did for learning

---

## **Next Level: Discord Integration**

Future: Bot posts alerts to Discord channel:
```
@Waleed BREAKOUT ALERT: AAPL 280 CALL
→ HOLD all 5 contracts
→ Trail stop to $277.60
→ Target: $285.20
```

Or text/email notifications for critical alerts.

---

**Bottom Line**:
Live Monitor = Your real-time coach. Watches resistance zones 24/7, alerts on breakouts/rejections, trails stops automatically. No more constant chart watching - just respond to alerts and execute.

**Ready to test on your next trade!** 🚀
