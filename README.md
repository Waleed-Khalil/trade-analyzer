# Trade Analyzer

Paste an option play (e.g. from Discord); get a **Go/No-Go recommendation**, **stop loss**, **take-profit levels**, and **support/resistance**. Built for **ODE (same-day / 0DTE)** with tighter risk parameters. No Discord bot required — you provide the play, the tool analyzes it.

## What You Get

- **Should I play it?** — Clear **PLAY** or **DON'T PLAY** with reasoning
- **Stop loss** — Suggested level (rule-based + AI confirmation)
- **Take-profit levels** — T1, runner, and any extra levels
- **Support / resistance** — Key levels to watch on the underlying
- **ODE risks** — Same-day expiration notes (theta, gamma, time of day)
- **Red flags** — Premium too low, strike distance, rule violations

## Philosophy

- **Rule-driven core**: Position sizing, stops, and targets use deterministic formulas
- **AI for the recommendation**: Claude synthesizes rules + context into a clear Play/Don’t Play and levels
- **ODE-aware**: Same-day expiration uses tighter stops and faster targets

## Setup

```bash
git clone https://github.com/yourusername/trade-analyzer.git
cd trade-analyzer
pip install -r requirements.txt
```

**Optional but recommended** - for AI recommendation and context:

```bash
# Create .env in project root (optional)
echo ANTHROPIC_API_KEY=your_key_here >> .env
echo BRAVE_API_KEY=your_brave_key >> .env   # optional: news context
```

- **ANTHROPIC_API_KEY**: Enables AI recommendation (Play/Don’t Play, reasoning, stop, targets, levels). Without it, you still get rule-based analysis and levels.
- **Yahoo Finance** (yfinance): Current underlying price when available - no API key.
- **Brave Search** (BRAVE_API_KEY): Recent news/headlines for the ticker - optional; improves AI context. See [docs/APIS.md](docs/APIS.md) for all APIs and keys.

## Running

**From project root:**

```bash
# Paste play as argument
python src/main.py "NVDA 150 CALL @ 2.50 0DTE"

# Or pipe / type when prompted
python src/main.py
# Then paste: AAPL 215 CALL @ 3.50
```

**Optional flags:**

- `--verbose` / `-v` — Log market-data and AI errors to stderr.
- `--no-ai` — Use rule-based recommendation only (no API key needed).
- `--no-market` — Skip Yahoo, Polygon, and Brave; use pasted data only.
- `--dte N` / `-d N` — Set **days to expiration** (DTE) explicitly. Overrides any DTE from the play text. Analysis (stops, targets, ODE rules) uses this value.

Example: `python src/main.py --no-ai --no-market "AAPL CALL 215 @ 3.50"`  
Example with DTE: `python src/main.py --dte 2 "MSFT 430 CALL @ 0.79"`

## DTE (Days to Expiration) — Universal Input

DTE drives all time-sensitive logic: ODE vs standard rules, stop/target multipliers, PoP, and stress tests. You can set it in two ways:

1. **In the play string** — Add `DTE N` or `N DTE` (e.g. `MSFT 430 CALL @ 0.79 DTE 2` or `... 2 DTE`). Expiration date is then computed as today + N days.
2. **CLI override** — Use `--dte N` (or `-d N`). This overrides DTE from the play and applies to the whole analysis.

When DTE is 0, same-day (0DTE/ODE) rules apply (tighter stop, faster targets). For any N ≥ 0, the report and risk engine use this single value consistently.

## Supported Play Formats

- `BUY AAPL 01/31 215 CALL @ 3.50`
- `AAPL CALL 215 @ 3.50`
- `NVDA 150 CALL @ 2.50 0DTE`  (same-day)
- `SPY 600 CALL @ 1.25`
- `QQQ 628 CALL @ .63 EXP 2026-02-06`  (explicit expiration; DTE computed from date)
- `MSFT 430 CALL @ 0.79 DTE 2`  or  `MSFT 430 CALL @ 0.79 2 DTE`  (explicit DTE; analysis based on 2 DTE)

Optional **EXP YYYY-MM-DD** or **EXP MM/DD/YYYY** in any play sets expiration and DTE from the date. Optional **DTE N** or **N DTE** sets DTE directly (single source of truth for the run). Include **0DTE**, **same day**, or **ODE** to trigger same-day rules when no explicit DTE/EXP is given.

## Example Output

```
============================================================
  OPTION PLAY ANALYSIS
============================================================
  NVDA CALL $150 @ $2.50
  Same-day expiration (0DTE) — tighter stops and targets applied.
  Underlying reference: $148.20

  RECOMMENDATION: PLAY
------------------------------------------------------------
  Setup has 1.5R target and rule-based pass. Premium is acceptable for 0DTE...

  STOP LOSS
------------------------------------------------------------
  $1.62 (35% of premium). Hold to this; 0DTE can gap through stops.

  TAKE-PROFIT LEVELS
------------------------------------------------------------
  • T1: $3.72 (1.5R) — take 50% off
  • Runner: 1 @ $4.50

  SUPPORT / RESISTANCE
------------------------------------------------------------
  • Support: $146, $144
  • Resistance: $150, $152

  ODE / SAME-DAY EXPIRATION RISKS
------------------------------------------------------------
  • Theta decay accelerates into close; consider exiting before last hour.
  • Gamma can move option price sharply; use tight stops.
============================================================
```

## Configuration

Edit `config/config.yaml`:

- **account** — Capital, max risk per trade, max positions
- **stops** — Default stop % and max loss per contract; **stops.atr** — ATR period, days_back, sl_multiplier, t1/t2_multiplier, use_delta_adjust for vol-adjusted levels
- **ode** — Same-day rules: tighter `stop_pct`, lower `profit_target_r`, etc.
- **targets** — Standard target 1R, runner, max runner R
- **alert_formats** — Regex patterns for parsing different play formats
- **analysis.greeks** — PoP min (0.50), theta/vega thresholds, option volume/OI minimums for liquidity flags
- **analysis.stress** — Scenario % moves (e.g. -2%, -1%, +1%, +2%) for stress-test P/L; risk-free rate; optional red-flag threshold for -1% loss vs risk

## Architecture

```
trade-analyzer/
├── config/
│   └── config.yaml          # Risk params, ODE params, alert formats
├── src/
│   ├── parser/              # Parse play text → OptionTrade (incl. is_ode)
│   ├── market_data/         # yfinance: underlying price, context
│   ├── risk_engine/        # Position size, stops, targets (ODE-aware)
│   ├── analysis/           # Red/green flags, setup quality
│   ├── ai_agent/           # Anthropic: recommendation, stop, targets, levels
│   ├── report/             # Console report (no Discord)
│   └── main.py             # CLI: paste play → full report
├── requirements.txt
└── README.md
```

## Risk Engine (Rule-Based)

- **Position sizing**: Max risk per trade ÷ (premium × 100) → contracts
- **Stop**: 50% of premium (or 35% for ODE) OR max $ loss per contract
- **Target 1**: 2R (or 1.5R for ODE)
- **Runner**: Half off at 3R (or 2R for ODE), max 5R (or 3R for ODE)
- **Go/No-Go**: Min premium, risk %, position limits

## License

MIT
