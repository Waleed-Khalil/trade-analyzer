"""
Update a journal entry with exit premium, reason, notes; compute P/L and R multiple.
Usage: python src/journal/update_trade.py --id 1 --exit_premium 1.30 --exit_reason "hit T1" [--notes "strong breakout"]
"""

import argparse
import csv
import os
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)
_config_path = os.path.join(os.path.dirname(_repo_root), "config", "config.yaml")
if not os.path.isfile(_config_path):
    _config_path = os.path.join(_repo_root, "config", "config.yaml")


def _get_journal_path():
    from journal.journal import get_journal_path
    return get_journal_path(_config_path)


def _load_journal_config():
    from journal.journal import _load_journal_config
    return _load_journal_config(_config_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update journal entry with exit and compute P/L")
    parser.add_argument("--id", type=int, required=True, help="Journal entry id")
    parser.add_argument("--exit_premium", type=float, required=True, help="Exit premium per share")
    parser.add_argument("--exit_reason", type=str, default="", help="e.g. hit T1, stop, manual")
    parser.add_argument("--notes", type=str, default="", help="Optional notes")
    args = parser.parse_args()

    path = _get_journal_path()
    if not path or not os.path.isfile(path):
        print("Journal file not found. Run analyzer with a PLAY signal first.", file=sys.stderr)
        sys.exit(1)

    cfg = _load_journal_config()
    commission = float(cfg.get("commission_per_contract", 1.0))

    from journal.journal import JOURNAL_COLUMNS

    rows = []
    found = False
    pnl_val = 0.0
    r_mult_val = 0.0
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rid = r.get("id")
            try:
                rid = int(rid) if rid else None
            except ValueError:
                rid = None
            if rid == args.id:
                found = True
                entry_prem = _float(r.get("entry_premium"), 0)
                contracts = _int(r.get("contracts"), 1)
                risk_dollars = _float(r.get("risk_dollars"), 0)
                pnl_val = (args.exit_premium - entry_prem) * 100 * contracts - 2 * commission * contracts
                r_mult_val = (pnl_val / risk_dollars) if risk_dollars and risk_dollars > 0 else 0
                r["exit_premium"] = f"{args.exit_premium:.2f}"
                r["exit_reason"] = (args.exit_reason or "").strip()
                r["pnl"] = f"{pnl_val:.2f}"
                r["r_multiple"] = f"{r_mult_val:.2f}"
                r["notes"] = (args.notes or "").strip()
            rows.append(r)

    if not found:
        print(f"Entry id={args.id} not found in journal.", file=sys.stderr)
        sys.exit(1)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"Updated id={args.id}: exit ${args.exit_premium:.2f}, P/L ${pnl_val:.2f}, R={r_mult_val:.2f}")


def _float(s, default: float) -> float:
    try:
        return float(s) if s not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _int(s, default: int) -> int:
    try:
        return int(float(s)) if s not in (None, "") else default
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
