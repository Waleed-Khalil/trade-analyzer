"""
Journal: log PLAY signals to CSV; path and options from config.
"""

import csv
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


JOURNAL_COLUMNS = [
    "id", "timestamp", "ticker", "option_type", "strike", "entry_premium", "live_premium",
    "dte", "pop", "iv_rank", "atr", "sl_premium", "t1_premium", "score", "risk_dollars",
    "contracts", "exit_premium", "exit_reason", "pnl", "r_multiple", "notes",
]


def _load_journal_config(config_path: str) -> Dict[str, Any]:
    try:
        import yaml
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("journal", {})
    except Exception:
        return {}


def get_journal_path(config_path: str) -> Optional[str]:
    """Resolve journal log path from config (absolute or relative to repo root)."""
    cfg = _load_journal_config(config_path)
    path = cfg.get("log_path", "logs/journal.csv")
    if not path:
        return None
    if os.path.isabs(path):
        return path
    # config_path is repo/config/config.yaml -> repo_root = dirname(dirname(...))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(config_path)))
    return os.path.join(repo_root, path)


def log_play_signal(
    trade: Any,
    trade_plan: Any,
    analysis: Any,
    recommendation: Any,
    market_context: Dict[str, Any],
    config_path: str,
) -> Optional[int]:
    """
    Append a PLAY signal row to the journal CSV. Returns assigned id or None on failure.
    Only logs when journal.enabled and (optionally) setup_score >= min_score_to_log.
    """
    cfg = _load_journal_config(config_path)
    if not cfg.get("enabled", True):
        return None
    rec = getattr(recommendation, "recommendation", "")
    if rec not in ("PLAY", "GO"):
        return None
    min_score = cfg.get("min_score_to_log", 75)
    score = getattr(analysis, "setup_score", 0)
    if min_score > 0 and score < min_score:
        return None

    path = get_journal_path(config_path)
    if not path:
        return None
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    ctx = market_context or {}
    live_prem = ctx.get("option_live") or trade.premium
    dte = ctx.get("days_to_expiration")
    pop = ctx.get("probability_of_profit")
    iv_rank = ctx.get("iv_rank")
    atr = ctx.get("atr")
    sl_prem = getattr(trade_plan, "stop_loss", None)
    t1_prem = getattr(trade_plan, "target_1", None)
    risk_dollars = getattr(trade_plan.position, "max_risk_dollars", None)
    contracts = getattr(trade_plan.position, "contracts", 1)

    next_id = 1
    if os.path.isfile(path):
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    ids = [int(r.get("id", 0)) for r in rows if str(r.get("id", "")).isdigit()]
                    next_id = max(ids, default=0) + 1
        except Exception:
            pass

    ts = datetime.now(timezone.utc).isoformat()
    row = {
        "id": next_id,
        "timestamp": ts,
        "ticker": getattr(trade, "ticker", ""),
        "option_type": (getattr(trade, "option_type", "CALL") or "CALL").upper(),
        "strike": getattr(trade, "strike", ""),
        "entry_premium": getattr(trade, "premium", ""),
        "live_premium": live_prem if live_prem is not None else "",
        "dte": dte if dte is not None else "",
        "pop": f"{pop:.2f}" if pop is not None else "",
        "iv_rank": f"{iv_rank:.0f}" if iv_rank is not None else "",
        "atr": f"{atr:.2f}" if atr is not None else "",
        "sl_premium": f"{sl_prem:.2f}" if sl_prem is not None else "",
        "t1_premium": f"{t1_prem:.2f}" if t1_prem is not None else "",
        "score": score,
        "risk_dollars": f"{risk_dollars:.0f}" if risk_dollars is not None else "",
        "contracts": contracts,
        "exit_premium": "",
        "exit_reason": "",
        "pnl": "",
        "r_multiple": "",
        "notes": "",
    }

    write_header = not os.path.isfile(path)
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=JOURNAL_COLUMNS)
            if write_header:
                w.writeheader()
            w.writerow(row)
        return next_id
    except Exception:
        return None
