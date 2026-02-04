# Possible Improvements

Ideas to make the trade-analyzer even better, roughly by impact and effort.

## Done (recent)

- **Load .env at startup** — API keys available before parsing and market/AI calls.
- **Supported formats from config** — Parse-fail message shows examples from `alert_formats` in config.
- **Parser validation for ODE** — 0DTE plays use `ode.min_premium` (e.g. 0.30) instead of standard min.
- **CLI flags** — `--verbose` / `-v` (log market/AI errors to stderr), `--no-ai` (rule-only), `--no-market` (skip Yahoo/Massive/Brave).
- **.gitignore** — `__pycache__/`, `venv/`, `.pytest_cache/`, coverage artifacts.

## Done (Greeks / quantitative)

- **Expiration parsing** — Optional `EXP YYYY-MM-DD` or `EXP MM/DD/YYYY` in play string; DTE computed and shown; Massive uses explicit exp when provided.
- **Greeks & PoP** — Black-Scholes Probability of Profit (scipy); Greeks summary in report (Delta, Gamma, Theta, Vega, IV, PoP); liquidity (volume, OI).
- **Red flags** — PoP &lt; 50%, high theta decay, high vega, option volume &lt; 500, OI &lt; 1000; DTE &lt; 1 = HIGH RISK. Thresholds in `config.analysis.greeks`.
- **Setup score 0–100** — Weighted (rules, Greeks, liquidity); "PLAY suggested if score &gt; 75" in report.
- **Stress test scenarios** — Instant underlying move P/L via Black-Scholes reprice; configurable scenarios (e.g. -2%, -1%, +1%, +2%); "STRESS TEST SCENARIOS" section in report; red flag when -1% move causes loss &gt; 50% of risk.
- **ATR-based dynamic stops/targets** — 14d ATR from Yahoo daily OHLC; vol-adjusted SL (entry - sl_mult × ATR × delta) and T1/T2 (entry + mult × ATR × delta); config under `stops.atr`; report shows "Vol-adjusted (1.5x14d ATR)" and "ATR-BASED TARGETS" when available.
- **Backtest skeleton** — Historical simulation (yfinance + Black-Scholes). Scans past dates for setups (0–2% OTM call, PoP &gt;= min, RV percentile &lt;= max, R/R &gt;= 2). Simulates exit at T1/SL/expiry. Output: win %, avg win/loss, expectancy, max drawdown, Sharpe. Config: `backtest`; CLI: `python src/backtest/run_backtest.py [ticker ...]`.
- **Trading journal** — Auto-log PLAY signals (timestamp, ticker, strike, entry/live premium, DTE, PoP, IV rank, ATR, score, risk, contracts) to CSV. Update with exit premium/reason/notes via `python src/journal/update_trade.py --id N --exit_premium X --exit_reason "hit T1"`. Summary: `python src/journal/summary.py [--period last_30d|last_90d|all]` for win %, expectancy, max consecutive losses, by-ticker. Config: `journal.log_path`, `journal.min_score_to_log`, `journal.commission_per_contract`.
- **Multi-timeframe TA** — RSI(14), MACD(12,26,9), SMA(20,50) from yfinance daily + 1h. Config: `analysis.technical` (enabled, rsi_period, rsi_overbought/oversold, rsi_min_bullish/rsi_max_bearish, sma_periods, macd_*, confluence_score_bonus). Red flags: RSI overbought (calls) / oversold (puts), MACD bearish for calls. Setup score: +confluence_score_bonus when RSI + price vs SMA + MACD align (bullish for calls, bearish for puts). Report: "TECHNICAL CONFLUENCE" (Daily / 1H).

## High value, medium effort

- **Unit tests** — Pytest for parser (all formats, .20 premium, 0DTE), risk_engine (position size, ODE vs standard), analysis (red/green flags). Mock market and AI in integration-style test.
- **JSON output** — `--json` flag to print a single structured object (trade, plan, recommendation, red flags) for piping into other tools or dashboards.
- **Config loaded once** — Load `config.yaml` in main and pass the dict (or a small config module) into Parser, RiskEngine, TradeAnalyzer, AI agent to avoid repeated file reads and allow env overrides.
- **Logging instead of silent pass** — Use Python `logging`; `--verbose` sets level to DEBUG so market/AI failures are logged instead of swallowed.

## Medium value

- **Retries for external APIs** — Simple retry with backoff for Massive, Yahoo, Brave to handle transient failures.
- **Type hints and Protocols** — Replace `Any` for `trade`, `trade_plan`, `recommendation` with proper types or Protocols so IDEs and mypy catch errors.
- **Help flag** — `--help` / `-h` prints usage and supported formats (from config).
- **Validate after parse** — Call `parser.validate(trade)` after parse and surface warnings (e.g. premium below min) in the report without blocking.

## Lower priority

- **Multiple plays in one run** — Accept multiple play strings (e.g. from a file or stdin lines) and run analysis for each; optional `--json` array output.
- **IV rank / volatility context** — Done: recompute from Massive + yfinance; see "Historical IV Recompute for IV Rank" above.
- **Expiration date parsing** — Done: EXP YYYY-MM-DD or MM/DD/YYYY; DTE in report.
- **Discord output** — Re-enable optional Discord webhook output (module exists) via config or flag for users who want to post the report to a channel.

## Usage (CLI)

```bash
# Full run (market data + AI)
python src/main.py "NVDA 150 CALL @ 2.50 0DTE"

# Rule-only, no API calls
python src/main.py --no-ai --no-market "AAPL CALL 215 @ 3.50"

# Debug market/AI failures
python src/main.py --verbose "QQQ 630 CALL @ .20"

# Backtest (config.backtest.tickers or pass tickers)
python src/backtest/run_backtest.py
python src/backtest/run_backtest.py QQQ SPY

# Journal: update exit (after closing a trade)
python src/journal/update_trade.py --id 1 --exit_premium 1.30 --exit_reason "hit T1" --notes "strong breakout"

# Journal summary (closed trades only)
python src/journal/summary.py
python src/journal/summary.py --period last_30d
```
