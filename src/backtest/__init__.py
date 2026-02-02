"""
Backtest module: historical simulation of option setups using yfinance + Black-Scholes.
Validates rules (PoP, RV rank, ATR R/R) and outputs win rate, avg R, drawdown, Sharpe.
"""

from backtest.backtest import BacktestResult, run_backtest  # noqa: F401

__all__ = ["run_backtest", "BacktestResult"]
