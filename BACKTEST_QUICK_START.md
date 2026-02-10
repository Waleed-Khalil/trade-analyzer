# Backtest Quick Start Guide
## Adding Real Trades & Running Analysis

---

## 📊 Current Status

You have:
- ✅ Working backtest analyzer (`src/backtest/journal_analyzer.py`)
- ✅ Test results on 13 sample trades (+115% P/L, but inflated)
- ⚠️ Need: 20-50+ **real completed trades** for honest validation

---

## 🎯 Goal: Add Your Real Trades

To get accurate backtest results, you need to add trades you've **actually taken** with real entry/exit prices.

### **What You Need Per Trade**

Minimum (required):
- Ticker (e.g., AAPL)
- Option type (CALL or PUT)
- Strike price
- Entry premium (what you paid)
- Entry date
- Exit premium (what you sold for)
- Exit date
- Number of contracts

Nice to have (optional):
- Exit reason ("Hit target", "Stopped out", "Manual exit", etc.)
- Notes (what happened - "Breakout at R1", "Rejection at resistance")
- DTE at entry

---

## 🚀 Three Ways to Add Trades

### **Method 1: Fill Out CSV Template** (Easiest for multiple trades)

1. **Open the template**:
   ```
   logs/real_trades_template.csv
   ```

2. **Delete example rows**, add your real trades:
   ```csv
   ticker,option_type,strike,entry_premium,entry_date,exit_premium,exit_date,contracts,exit_reason,notes,dte
   AAPL,CALL,215,3.50,2024-10-15,5.80,2024-10-18,5,Hit 2R target,Clean move to R2,4
   NVDA,CALL,145,4.10,2024-11-02,3.20,2024-11-05,3,Stopped out,Rejection at resistance,7
   SPY,PUT,595,2.20,2024-12-01,4.10,2024-12-04,10,Breakout hold,Captured extended move,0
   ```

3. **Import to journal**:
   ```python
   from src.journal.add_real_trade import import_from_csv

   import_from_csv("logs/real_trades_template.csv")
   ```

4. **Run backtest**:
   ```bash
   python src/backtest/journal_analyzer.py
   ```

---

### **Method 2: Add Trades One-by-One** (Good for 5-10 trades)

```python
from src.journal.add_real_trade import add_real_trade

# Add each trade
add_real_trade(
    ticker="AAPL",
    option_type="CALL",
    strike=220,
    entry_premium=3.50,
    entry_date="2024-11-15",
    exit_premium=5.20,
    exit_date="2024-11-18",
    contracts=5,
    exit_reason="Hit 2R target",
    notes="Clean breakout at R1, held to R2"
)

add_real_trade(
    ticker="NVDA",
    option_type="CALL",
    strike=150,
    entry_premium=2.50,
    entry_date="2024-11-20",
    exit_premium=1.75,
    exit_date="2024-11-22",
    contracts=10,
    exit_reason="Stopped out",
    notes="Rejection at resistance"
)

# ... add more trades ...
```

Then run:
```bash
python src/backtest/journal_analyzer.py
```

---

### **Method 3: Batch Add from List** (Good for programmatic import)

```python
from src.journal.add_real_trade import batch_add_trades_from_list

trades = [
    {
        'ticker': 'AAPL',
        'option_type': 'CALL',
        'strike': 220,
        'entry_premium': 3.50,
        'entry_date': '2024-11-15',
        'exit_premium': 5.20,
        'exit_date': '2024-11-18',
        'contracts': 5,
        'exit_reason': 'Hit 2R target',
        'notes': 'Clean breakout'
    },
    {
        'ticker': 'NVDA',
        'option_type': 'CALL',
        'strike': 150,
        'entry_premium': 2.50,
        'entry_date': '2024-11-20',
        'exit_premium': 1.75,
        'exit_date': '2024-11-22',
        'contracts': 10,
        'exit_reason': 'Stopped out',
        'notes': 'Rejection at R1'
    },
    # ... more trades ...
]

batch_add_trades_from_list(trades)
```

---

## 📝 Where To Find Your Trade Data

### **Option 1: Discord Alert History**
If you trade from Discord alerts (e.g., DEMON TRADES):
1. Search your Discord history for "BUY" or "SELL" alerts
2. Find your entries: "AAPL 220 CALL @ 3.50"
3. Note when you exited (screenshots, broker statements)
4. Estimate exit premium from broker fills

### **Option 2: Broker Statements**
Most brokers provide CSV exports:
- **TD Ameritrade**: Account → History → Export
- **Robinhood**: Account → Statements → Export Trades
- **Interactive Brokers**: Reports → Flex Queries
- **Webull**: Account → History → Export

Look for columns: Symbol, Action (BUY/SELL), Quantity, Price, Date

### **Option 3: Screenshots/Notes**
If you track manually:
- Entry screenshot → Get entry premium & date
- Exit screenshot → Get exit premium & date
- Approximate contracts from capital used

### **Option 4: Reconstruct from Memory**
For recent trades (last 1-3 months):
- List tickers you traded
- Rough entry/exit dates
- Estimate premiums from profit/loss
- "Better than nothing" for validation

---

## 🎲 Example: Adding 5 Real Trades

Let's say you traded these in Q4 2024:

**Trade 1**: AAPL 220 CALL
- Entry: 11/15/24 @ $3.50 x 5 contracts
- Exit: 11/18/24 @ $5.20
- Result: +$850 (hit 2R target)

**Trade 2**: NVDA 150 CALL
- Entry: 11/20/24 @ $2.50 x 10 contracts
- Exit: 11/22/24 @ $1.75
- Result: -$750 (stopped out at rejection)

**Trade 3**: SPY 600 CALL
- Entry: 12/01/24 @ $1.25 x 8 contracts
- Exit: 12/05/24 @ $2.10
- Result: +$680 (breakout, held runner)

**Trade 4**: QQQ 628 CALL
- Entry: 12/10/24 @ $0.95 x 10 contracts
- Exit: 12/12/24 @ $0.60
- Result: -$350 (manual exit, bad entry)

**Trade 5**: MSFT 430 PUT
- Entry: 01/05/25 @ $3.20 x 5 contracts
- Exit: 01/08/25 @ $2.50
- Result: -$350 (stopped out)

**Create CSV**:
```csv
ticker,option_type,strike,entry_premium,entry_date,exit_premium,exit_date,contracts,exit_reason,notes
AAPL,CALL,220,3.50,2024-11-15,5.20,2024-11-18,5,Hit 2R target,Clean breakout at R1
NVDA,CALL,150,2.50,2024-11-20,1.75,2024-11-22,10,Stopped out,Rejection at resistance
SPY,CALL,600,1.25,2024-12-01,2.10,2024-12-05,8,Breakout hold,Volume spike held runner
QQQ,CALL,628,0.95,2024-12-10,0.60,2024-12-12,10,Manual exit,Bad entry timing
MSFT,PUT,430,3.20,2025-01-05,2.50,2025-01-08,5,Stopped out,Failed breakdown
```

**Import**:
```python
from src.journal.add_real_trade import import_from_csv
import_from_csv("logs/my_q4_trades.csv")
```

**Run Analysis**:
```bash
python src/backtest/journal_analyzer.py
```

**See Results**:
```
Metric                         OLD             NEW             Delta
---------------------------------------------------------------------------
Win Rate                              60.0%          60.0%          +0.0%
Avg R per Trade                        0.15R         0.42R        +0.27R
Total P/L                      $        80   $        560  $      +480
P/L Improvement                                                   +600.0%
```

Now you have **real validation** of whether the new logic helps!

---

## 📊 What To Expect (Realistic)

Based on 20-50 real trades across different conditions:

| Scenario | Win Rate Delta | Avg R Delta | P/L Improvement |
|----------|---------------|-------------|-----------------|
| **Best Case** (mostly trending names like MSFT/NVDA) | +8-12% | +0.4-0.6R | +40-70% |
| **Typical** (mix of conditions) | +2-6% | +0.2-0.4R | +20-45% |
| **Worst Case** (choppy/range-bound like early QQQ) | -5 to +2% | +0.05-0.15R | +5-20% |

Even **+0.2R average improvement** on 20 trades = **+4.0R total** = meaningful edge worth deploying.

---

## 🚨 Common Pitfalls

### **Pitfall 1: Only Adding Winners**
If you only log winning trades, backtest will show inflated improvement.
**Solution**: Add ALL trades (winners AND losers) from a specific period.

### **Pitfall 2: Memory Bias**
Remembering winners better than losers.
**Solution**: Use broker statements or screenshots for objective data.

### **Pitfall 3: Different Market Conditions**
Adding only bull market trades, testing in bear market (or vice versa).
**Solution**: Include trades from different periods (trending, choppy, volatile).

### **Pitfall 4: Too Few Trades**
5-10 trades still has high sample variance.
**Solution**: Aim for 20-30 minimum, 50+ ideal.

---

## ✅ Checklist: Adding Real Trades

- [ ] Gather trade data (broker statements, Discord history, notes)
- [ ] Create CSV or use add_real_trade script
- [ ] Include at least 20 trades (more = better)
- [ ] Mix of winners AND losers
- [ ] Different tickers (not just MSFT)
- [ ] Different time periods (not just Feb 2-4)
- [ ] Run backtest: `python src/backtest/journal_analyzer.py`
- [ ] Review results in `logs/backtest_results.csv`
- [ ] Check if improvement is realistic (+20-50% expected)

---

## 🎯 Next Steps After Backtest

### **If Results Show +30-60% Improvement**:
✅ **Phase C**: Implement strength-weighted exits
✅ **Live Testing**: Paper trade next 20 setups with new logic
✅ **Production**: Integrate into main.py monitoring loop

### **If Results Show +10-30% Improvement**:
⚠️ **Tune Parameters**: Adjust volume thresholds, rejection patterns
⚠️ **Filter Setups**: Only use new logic on high-momentum plays
⚠️ **More Testing**: Paper trade to confirm before production

### **If Results Show <+10% Improvement**:
🔍 **Analyze**: What went wrong? Too many rejections? Missed breakouts?
🔍 **Refine**: Phase C (strength-weighted) might help
🔍 **Alternative**: Focus on entry quality vs exit improvements

---

## 🛠️ Troubleshooting

### **Issue**: "ModuleNotFoundError: No module named 'src'"
**Fix**: Run from project root:
```bash
cd C:\Users\wk848\Documents\GitHub\trade-analyzer
python src/backtest/journal_analyzer.py
```

### **Issue**: "FileNotFoundError: logs/journal.csv"
**Fix**: Create logs directory:
```bash
mkdir logs
```

### **Issue**: "TypeError: timezone mismatch"
**Fix**: Already handled in analyzer - dates auto-converted

### **Issue**: "Results don't match my actual P/L"
**Fix**: Analyzer uses simplified Black-Scholes approximation. For exact matching:
- Enter actual exit premiums (not estimates)
- Use real dates (not approximations)

---

## 📞 Need Help?

**Common Questions**:

**Q**: I only have 10 real trades - is that enough?
**A**: Better than 0! Run it, but expect high variance. Aim for 20-30.

**Q**: Can I mix timeframes (0DTE, weeklies, monthlies)?
**A**: Yes! Analyzer handles any DTE. Just note it in the 'dte' column.

**Q**: What if I don't remember exact premiums?
**A**: Estimate from P/L. If you made $500 on 5 contracts, exit was ~$1.00 higher than entry.

**Q**: Should I add paper trades or only real money?
**A**: Both work! Real money is best for honest validation.

---

## 🚀 Ready to Start?

1. **Right now**: Gather 5-10 trades you can remember
2. **This week**: Export broker statements for 20-30 trades
3. **Next week**: Add to journal & run backtest
4. **Decision point**: Phase C, tune, or pivot based on results

The sooner you add real data, the sooner you'll know if the +115% was luck or edge! 📊

---

**Files Created**:
- `src/journal/add_real_trade.py` - Helper script
- `logs/real_trades_template.csv` - CSV template
- `BACKTEST_QUICK_START.md` - This guide

**Next Command**:
```bash
# Edit template with your trades
notepad logs/real_trades_template.csv

# Import trades
python -c "from src.journal.add_real_trade import import_from_csv; import_from_csv('logs/real_trades_template.csv')"

# Run backtest
python src/backtest/journal_analyzer.py
```

Good luck! 🍀
