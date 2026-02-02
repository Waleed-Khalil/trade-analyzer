"""
Backtest CLI: run historical simulation for configured tickers and print metrics.
Usage: python src/backtest/run_backtest.py [ticker ...]
  With no args, uses config.backtest.tickers. With args, runs only those tickers.
"""

import os
import sys

# Add src to path so backtest and analysis modules resolve
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

# Config: repo_root/config/config.yaml (repo_root = parent of src)
_repo_root_parent = os.path.dirname(_repo_root)
_config_path = os.path.join(_repo_root_parent, "config", "config.yaml")
if not os.path.isfile(_config_path):
    _config_path = os.path.join(_repo_root, "config", "config.yaml")


def _load_backtest_config():
    try:
        import yaml
        with open(_config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("backtest", {})
    except Exception:
        return {}


def _print_result(r) -> None:
    sep = "=" * 60
    sub = "-" * 60
    print()
    print(sep)
    print(f"  BACKTEST: {r.ticker}")
    print(sep)
    print(f"  Trades: {r.n_trades}  |  Wins: {r.wins}  |  Losses: {r.losses}")
    print(f"  Win rate: {r.win_rate_pct}%")
    print(sub)
    print(f"  Avg win:  ${r.avg_win_dollars:,.2f}  |  Avg loss: ${r.avg_loss_dollars:,.2f}")
    print(f"  Expectancy per trade: ${r.expectancy_dollars:,.2f}")
    print(f"  Total P/L: ${r.total_pnl_dollars:,.2f}")
    print(sub)
    print(f"  Max drawdown: ${r.max_drawdown_dollars:,.2f}")
    print(f"  Sharpe (annualized): {r.sharpe_annual:.2f}")
    print(sep)
    print()


def main() -> None:
    from backtest.backtest import run_backtest

    bt_cfg = _load_backtest_config()
    tickers = bt_cfg.get("tickers", ["QQQ", "SPY"])
    min_trades = bt_cfg.get("min_trades", 30)

    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]

    for ticker in tickers:
        result = run_backtest(ticker, _config_path)
        _print_result(result)
        if result.n_trades < min_trades and result.n_trades > 0:
            print(f"  Note: Fewer than {min_trades} trades; stats are indicative only.")
            print()
        elif result.n_trades == 0:
            print("  No setups matched filters in the lookback period.")
            print()


if __name__ == "__main__":
    main()
