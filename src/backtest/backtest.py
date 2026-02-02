"""
Backtest engine: find historical setups matching rules, simulate exit at T1/SL/expiry, aggregate metrics.
Uses yfinance for underlying OHLC; Black-Scholes for option pricing and PoP (IV proxy = 30d realized vol).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import math


@dataclass
class BacktestResult:
    """Aggregated backtest output."""
    ticker: str
    n_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    avg_win_dollars: float
    avg_loss_dollars: float
    expectancy_dollars: float
    total_pnl_dollars: float
    max_drawdown_dollars: float
    sharpe_annual: float
    trades: List[Dict[str, Any]] = field(default_factory=list)


def _load_config(config_path: str) -> Dict[str, Any]:
    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_underlying_history(ticker: str, years: int) -> Optional[Any]:
    """Fetch daily OHLC for ticker over years. Returns DataFrame with Close and date index."""
    try:
        import yfinance as yf
        period = f"{max(1, years) * 365}d"
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval="1d", auto_adjust=True)
        if hist is None or len(hist) < 60 or "Close" not in hist.columns:
            return None
        hist = hist[["Open", "High", "Low", "Close"]].copy()
        hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
        return hist
    except Exception:
        return None


def _atr_series(high: Any, low: Any, close: Any, period: int) -> Any:
    """Wilder ATR (rolling mean of true range)."""
    prev = close.shift(1)
    tr = (high - low).combine((high - prev).abs(), max).combine((low - prev).abs(), max)
    return tr.rolling(period).mean()


def _realized_vol_series(close: Any, window: int) -> Any:
    """Annualized realized vol (rolling std of log returns * sqrt(252))."""
    log_ret = close.pct_change().dropna()
    return log_ret.rolling(window).std() * (252 ** 0.5)


def _find_setups(
    df: Any,
    config: Dict[str, Any],
    risk_free_rate: float,
) -> List[Dict[str, Any]]:
    """
    For each date with enough history, check if we have a valid setup (0-2% OTM call, PoP>=50%,
    RV rank<=60%, ATR R/R>=2). Return list of setup dicts (entry_date, spot, strike, dte, entry_premium, stop_premium, target_premium, risk_dollars, rv_30).
    """
    bt = config.get("backtest", {})
    otm_max = bt.get("otm_pct_max", 0.02)
    pop_min = bt.get("pop_min", 0.50)
    rv_rank_max = bt.get("rv_rank_max", 60)
    atr_rr_min = bt.get("atr_rr_min", 2.0)
    dte = bt.get("dte_approx", 21)
    target_r = bt.get("target_r", 2.0)
    stop_pct = bt.get("stop_pct", 0.50)

    try:
        from analysis.greeks import black_scholes_call_price, probability_of_profit
    except ImportError:
        return []

    df = df.copy()
    df["atr14"] = _atr_series(df["High"], df["Low"], df["Close"], 14)
    df["rv30"] = _realized_vol_series(df["Close"], 30)
    df["rv252_min"] = df["rv30"].rolling(252).min()
    df["rv252_max"] = df["rv30"].rolling(252).max()
    rv_range = df["rv252_max"] - df["rv252_min"]
    df["rv_pct"] = (df["rv30"] - df["rv252_min"]) / (rv_range + 1e-12)
    df["rv_pct"] = (df["rv_pct"] * 100).clip(0, 100)

    setups = []
    for i in range(252, len(df) - dte - 1):
        row = df.iloc[i]
        spot = float(row["Close"])
        atr = row["atr14"]
        rv30 = row["rv30"]
        rv_pct = row["rv_pct"]
        if spot <= 0:
            continue
        try:
            atr_val = float(atr)
            rv30_val = float(rv30)
            rv_pct_val = float(rv_pct)
        except (TypeError, ValueError):
            continue
        if math.isnan(atr_val) or atr_val <= 0:
            continue
        if math.isnan(rv30_val) or rv30_val <= 0 or math.isnan(rv_pct_val):
            continue
        if rv_pct_val > rv_rank_max:
            continue

        strike = round(spot * (1 + otm_max), 2)
        if strike <= 0:
            continue
        time_years = dte / 365.0
        entry_premium = black_scholes_call_price(
            spot, strike, time_years, risk_free_rate, rv30_val
        )
        if entry_premium <= 0:
            continue
        pop = probability_of_profit(
            spot, strike, time_years, risk_free_rate, rv30_val, "call"
        )
        if pop is None or pop < pop_min:
            continue

        stop_premium = entry_premium * (1 - stop_pct)
        risk_per_share = entry_premium - stop_premium
        if risk_per_share <= 0:
            continue
        target_premium = entry_premium + risk_per_share * target_r
        rr = (target_premium - entry_premium) / risk_per_share if risk_per_share else 0
        if rr < atr_rr_min:
            continue

        risk_dollars = risk_per_share * 100
        entry_date = df.index[i]
        setups.append({
            "entry_date": entry_date,
            "spot": spot,
            "strike": strike,
            "dte": dte,
            "entry_premium": entry_premium,
            "stop_premium": stop_premium,
            "target_premium": target_premium,
            "risk_dollars": risk_dollars,
            "rv_30": rv30_val,
        })
    return setups


def _simulate_trade(
    setup: Dict[str, Any],
    df: Any,
    risk_free_rate: float,
    max_holding_days: int,
) -> Dict[str, Any]:
    """
    From entry_date, walk forward. Each day: price option with BS(spot, strike, T_remaining, r, IV=rv30).
    Exit at first of: premium <= stop, premium >= target, or expiry.
    """
    entry_date = setup["entry_date"]
    spot = setup["spot"]
    strike = setup["strike"]
    dte = setup["dte"]
    entry_premium = setup["entry_premium"]
    stop_premium = setup["stop_premium"]
    target_premium = setup["target_premium"]
    risk_dollars = setup["risk_dollars"]
    rv_30_entry = setup["rv_30"]

    try:
        from analysis.greeks import black_scholes_call_price
    except ImportError:
        return {"exit_date": entry_date, "pnl": 0.0, "exit_reason": "error"}

    try:
        loc = df.index.get_loc(entry_date)
    except (KeyError, TypeError):
        return {"exit_date": entry_date, "pnl": 0.0, "exit_reason": "no_data"}
    start_idx = loc + 1
    end_idx = min(loc + max_holding_days + 1, len(df))
    expiry_idx = min(loc + dte + 1, len(df))

    for j in range(start_idx, end_idx):
        if j >= len(df):
            break
        row = df.iloc[j]
        spot_today = float(row["Close"])
        days_held = j - loc
        t_remaining = max(0, (dte - days_held) / 365.0)
        rv_today = row.get("rv30")
        if rv_today is None or (hasattr(rv_today, "item") and math.isnan(rv_today)):
            rv_today = rv_30_entry
        rv_today = float(rv_today) if rv_today > 0 else rv_30_entry

        if t_remaining <= 0:
            prem = max(0.0, spot_today - strike)
            exit_date = df.index[j]
            pnl = (prem - entry_premium) * 100
            return {"exit_date": exit_date, "pnl": pnl, "exit_reason": "expiry", "exit_premium": prem}

        prem = black_scholes_call_price(
            spot_today, strike, t_remaining, risk_free_rate, rv_today
        )
        if prem <= stop_premium:
            exit_date = df.index[j]
            return {"exit_date": exit_date, "pnl": (prem - entry_premium) * 100, "exit_reason": "stop", "exit_premium": prem}
        if prem >= target_premium:
            exit_date = df.index[j]
            return {"exit_date": exit_date, "pnl": (prem - entry_premium) * 100, "exit_reason": "target", "exit_premium": prem}

    j = min(expiry_idx - 1, len(df) - 1)
    if j >= start_idx:
        row = df.iloc[j]
        spot_today = float(row["Close"])
        prem = max(0.0, spot_today - strike)
        exit_date = df.index[j]
        return {"exit_date": exit_date, "pnl": (prem - entry_premium) * 100, "exit_reason": "expiry", "exit_premium": prem}
    return {"exit_date": entry_date, "pnl": 0.0, "exit_reason": "no_exit", "exit_premium": entry_premium}


def run_backtest(
    ticker: str,
    config_path: str,
) -> BacktestResult:
    """
    Load config, fetch underlying history, find setups, simulate trades, return aggregated metrics.
    """
    config = _load_config(config_path)
    bt = config.get("backtest", {})
    lookback_years = bt.get("lookback_years", 2)
    risk_free_rate = bt.get("risk_free_rate", 0.0367)
    max_holding_days = bt.get("max_holding_days", 30)

    df = _get_underlying_history(ticker, lookback_years)
    if df is None or len(df) < 300:
        return BacktestResult(
            ticker=ticker,
            n_trades=0,
            wins=0,
            losses=0,
            win_rate_pct=0.0,
            avg_win_dollars=0.0,
            avg_loss_dollars=0.0,
            expectancy_dollars=0.0,
            total_pnl_dollars=0.0,
            max_drawdown_dollars=0.0,
            sharpe_annual=0.0,
            trades=[],
        )

    setups = _find_setups(df, config, risk_free_rate)
    trades = []
    for s in setups:
        out = _simulate_trade(s, df, risk_free_rate, max_holding_days)
        trades.append({
            "entry_date": s["entry_date"],
            "exit_date": out["exit_date"],
            "pnl": out["pnl"],
            "exit_reason": out["exit_reason"],
            "entry_premium": s["entry_premium"],
            "risk_dollars": s["risk_dollars"],
        })

    if not trades:
        return BacktestResult(
            ticker=ticker,
            n_trades=0,
            wins=0,
            losses=0,
            win_rate_pct=0.0,
            avg_win_dollars=0.0,
            avg_loss_dollars=0.0,
            expectancy_dollars=0.0,
            total_pnl_dollars=0.0,
            max_drawdown_dollars=0.0,
            sharpe_annual=0.0,
            trades=[],
        )

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    n = len(pnls)
    win_rate = (len(wins) / n * 100) if n else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    total_pnl = sum(pnls)

    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    risk_dollars_list = [t["risk_dollars"] for t in trades]
    avg_risk = sum(risk_dollars_list) / len(risk_dollars_list) if risk_dollars_list else 1.0
    returns_r = [(p / (t["risk_dollars"] or 1.0)) for t, p in zip(trades, pnls)]
    mean_r = sum(returns_r) / len(returns_r) if returns_r else 0.0
    var_r = sum((x - mean_r) ** 2 for x in returns_r) / len(returns_r) if returns_r else 0.0
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    avg_holding = max_holding_days * 0.5
    trades_per_year = 252 / avg_holding if avg_holding else 0
    sharpe = (mean_r / std_r * math.sqrt(trades_per_year)) if std_r > 0 else 0.0

    return BacktestResult(
        ticker=ticker,
        n_trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=round(win_rate, 1),
        avg_win_dollars=round(avg_win, 2),
        avg_loss_dollars=round(avg_loss, 2),
        expectancy_dollars=round(expectancy, 2),
        total_pnl_dollars=round(total_pnl, 2),
        max_drawdown_dollars=round(max_dd, 2),
        sharpe_annual=round(sharpe, 2),
        trades=trades,
    )
