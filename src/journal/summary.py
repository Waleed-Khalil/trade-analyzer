"""
Journal summary: win %, avg R, expectancy, max consecutive losses, optional period filter.
Usage: python src/journal/summary.py [--period last_30d|last_90d|all]
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)
_config_path = os.path.join(os.path.dirname(_repo_root), "config", "config.yaml")
if not os.path.isfile(_config_path):
    _config_path = os.path.join(_repo_root, "config", "config.yaml")


def _get_journal_path():
    from journal.journal import get_journal_path
    return get_journal_path(_config_path)


def _float(s, default: float) -> float:
    try:
        return float(s) if s not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _parse_ts(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Journal summary: win %, expectancy, streaks")
    parser.add_argument("--period", type=str, default="all", choices=["all", "last_30d", "last_90d"], help="Filter closed trades by period")
    args = parser.parse_args()

    path = _get_journal_path()
    if not path or not os.path.isfile(path):
        print("Journal file not found. No closed trades to summarize.", file=sys.stderr)
        sys.exit(0)

    cutoff = None
    if args.period == "last_30d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    elif args.period == "last_90d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    closed = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            exit_prem = r.get("exit_premium", "").strip()
            if not exit_prem:
                continue
            ts = _parse_ts(r.get("timestamp", ""))
            if cutoff and (ts is None or ts < cutoff):
                continue
            pnl = _float(r.get("pnl"), 0)
            closed.append({"pnl": pnl, "ticker": r.get("ticker", "")})

    if not closed:
        print(f"No closed trades in period: {args.period}")
        sys.exit(0)

    n = len(closed)
    wins = [x["pnl"] for x in closed if x["pnl"] > 0]
    losses = [x["pnl"] for x in closed if x["pnl"] <= 0]
    win_rate = (len(wins) / n * 100) if n else 0
    avg_win = (sum(wins) / len(wins)) if wins else 0
    avg_loss = (sum(losses) / len(losses)) if losses else 0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    total_pnl = sum(x["pnl"] for x in closed)

    streak = 0
    max_streak = 0
    for x in closed:
        if x["pnl"] <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    by_ticker = {}
    for x in closed:
        t = x["ticker"] or "?"
        by_ticker.setdefault(t, []).append(x["pnl"])
    ticker_summary = {t: (len(pnls), sum(pnls)) for t, pnls in by_ticker.items()}

    sep = "=" * 50
    print()
    print(sep)
    print(f"  JOURNAL SUMMARY ({args.period})")
    print(sep)
    print(f"  Closed trades: {n}")
    print(f"  Win rate: {win_rate:.1f}%  |  Wins: {len(wins)}  |  Losses: {len(losses)}")
    print(f"  Avg win: ${avg_win:,.2f}  |  Avg loss: ${avg_loss:,.2f}")
    print(f"  Expectancy per trade: ${expectancy:,.2f}")
    print(f"  Total P/L: ${total_pnl:,.2f}")
    print(f"  Max consecutive losses: {max_streak}")
    if ticker_summary:
        print("  By ticker: " + " | ".join(f"{t}: {c} trades, ${pl:,.0f}" for t, (c, pl) in sorted(ticker_summary.items())))
    print(sep)
    print()


if __name__ == "__main__":
    main()
