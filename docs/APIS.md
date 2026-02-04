# APIs Used by Trade Analyzer

The analyzer uses **four data sources** to give you a full recommendation. Only the **LLM** is required for AI recommendations; the others improve context.

| API | Purpose | Key | Required? |
|-----|---------|-----|-----------|
| **Yahoo Finance** (yfinance) | Underlying price, day range, volume | None | No — improves price context |
| **Massive/Polygon** | Live option price, Quotes, Last Trade, Market Status (contract lookup + OHLC) | `POLYGON_API_KEY` or `MASSIVE_API_KEY` (same key) | No — improves option context |
| **Brave Search** | Recent news/headlines for the ticker | `BRAVE_API_KEY` | No — improves news/catalyst context |
| **LLM (Anthropic)** | Play/Don't Play, reasoning, stop, targets, levels | `ANTHROPIC_API_KEY` | Yes, for AI recommendation |

---

## 1. Yahoo Finance (yfinance)

- **What it provides**: Current underlying stock price, open/high/low, volume. Used for strike distance (ITM/OTM), entry context, and support/resistance hints.
- **Key**: None. Uses the free `yfinance` library (not an official Yahoo API key).
- **Required**: No. Without it, the analyzer still runs; the AI just won’t have live price in the prompt.
- **Install**: `pip install yfinance` (in `requirements.txt`).

---

## 2. Brave Search

- **What it provides**: Recent news and headlines for the ticker (e.g. earnings, catalysts, sector news). Fed into the LLM so the recommendation can account for events.
- **Key**: **BRAVE_API_KEY** — get it at [Brave Search API](https://brave.com/search/api/). Free tier: 2,000 requests/month.
- **Required**: No. Without it, the AI recommendation still runs; it just won’t have recent news in the prompt.
- **Install**: `pip install brave-search` (in `requirements.txt`).
- **Usage**: Set `BRAVE_API_KEY` in your environment or `.env`. The app fetches a small number of news results per ticker when the key is set.

---

## 3. Massive (options data)

- **What it provides**: Live option price for the pasted play. Resolves the option contract (underlying + strike + type + expiration) via `/v3/reference/options/contracts`, then fetches OHLC via previous-day bar or daily open/close. Shown as "Option (live)" in the report and passed to the AI. Also fetches Quotes (bid/ask), Last Trade, and Market Status when available.
- **Key**: **MASSIVE_API_KEY** or **POLYGON_API_KEY** (same key for both; either name works). Base URL: **https://api.massive.com** (override with **MASSIVE_BASE_URL** in `.env` if needed).
- **Required**: No. Without it, option data in the report is "from pasted play only."
- **Endpoints used**: Options contracts (contract lookup), Option Chain Snapshot (greeks, IV, break-even, last, volume, OI), previous day bar or open-close (option price), **Quotes** (`/v3/quotes/{optionsTicker}`) for latest bid/ask and spread, **Last Trade** (`/v2/last/trade/{optionsTicker}`) for most recent trade and staleness, **Market Status** (`/v1/marketstatus/now`) for open/closed/extended-hours, and when IV Rank recompute is enabled: `/v2/aggs/ticker/{optionTicker}/range/1/day/{from}/{to}` for historical daily bars. No extra install (uses `urllib`).

**Quotes & Last Trade:** When an option ticker is available, the app fetches the latest quote (bid/ask) and last trade. Bid/ask spread as a percentage of mid is shown in the report and triggers a red flag when above `analysis.greeks.quote_spread_pct_max` (default 15%). Last-trade price and age (e.g. "2m ago") help detect stale data. **Market Status** is fetched once per run and shown as "Market: open/closed/extended-hours" so you know whether live data is current.

### Historical IV Recompute (IV Rank)

When `analysis.iv_rank.use_historical_recompute: true`, the app uses **one** Massive range-aggregates call per run to fetch option daily closes over the lookback window (capped at `max_historical_iv_days`, e.g. 126). Underlying daily closes come from yfinance. IV is recomputed per day via Black-Scholes inversion (scipy); IV Rank = (current IV − min) / (max − min) × 100. Requires at least `min_historical_samples` valid IVs; otherwise the report shows "52w Rank: N/A". Falls back gracefully on Massive API timeout or rate-limit.

---

## 4. LLM (Anthropic Claude)

- **What it provides**: The main AI output: **PLAY or DON’T PLAY**, **why**, **stop loss**, **take-profit levels**, **support/resistance**, **ODE risks**. Synthesizes rules + price + news into one recommendation.
- **Key**: **ANTHROPIC_API_KEY** — get it at [Anthropic Console](https://console.anthropic.com/).
- **Required**: Yes, for the AI recommendation. Without it, you only get rule-based analysis (Go/No-Go, stop, targets from config).
- **Install**: `pip install anthropic` (in `requirements.txt`).
- **Config**: Model in `config/config.yaml` under `analysis.model`. For **MiniMax** use `MiniMax-M2.1` and set **ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic** in `.env`. For Anthropic use `claude-sonnet-4-5` (no base URL).

---

## Summary: What you need

- **Minimum (rule-based only)**: No keys. Paste a play; get rule-based Go/No-Go, stop, and targets.
- **Full AI recommendation**: Set **ANTHROPIC_API_KEY**. For MiniMax also set **ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic** and `analysis.model: MiniMax-M2.1` in config.
- **Better context**: **yfinance** (no key) for underlying price, **POLYGON_API_KEY** (or MASSIVE_API_KEY; same key) for live option price (Quotes, Last Trade, Market Status), **BRAVE_API_KEY** for news. All optional.

**.env example:**

```bash
# MiniMax: use Anthropic-compatible API
ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
ANTHROPIC_API_KEY=your_minimax_key
POLYGON_API_KEY=your_key   # same key for Polygon/Massive
BRAVE_API_KEY=BSA...
# Optional: if using Massive, base URL defaults to https://api.massive.com
# MASSIVE_BASE_URL=https://api.massive.com
```

No key is needed for Yahoo Finance; it’s used via the `yfinance` library.
