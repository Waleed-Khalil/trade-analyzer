#!/usr/bin/env python3
"""
Quick test that Massive API is reachable and options endpoints work.
Run from repo root: python scripts/test_massive.py

Uses POLYGON_API_KEY or MASSIVE_API_KEY (same key) and MASSIVE_BASE_URL (default https://api.massive.com).
"""
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "src"))
os.chdir(repo_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    key = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
    if not key:
        print("POLYGON_API_KEY (or MASSIVE_API_KEY) not set in .env - same key for both")
        return 1
    print("API key: set (Polygon/Massive same key)")
    base = os.getenv("MASSIVE_BASE_URL", "https://api.massive.com")
    print("Base URL:", base)

    from market_data.polygon_client import (
        get_option_contract_ticker,
        get_option_snapshot,
        get_option_live_price,
        get_option_quotes_latest,
        get_option_last_trade,
        get_market_status,
    )

    # 1) Options reference
    ticker = get_option_contract_ticker("MSFT", "call", 430, "2026-02-06")
    if not ticker:
        print("FAIL: options/contracts returned no ticker")
        return 1
    print("OK: options/contracts ->", ticker)

    # 2) Snapshot (price + Greeks)
    snap = get_option_snapshot("MSFT", 430, "2026-02-06", "call")
    if not snap or snap.get("last") is None:
        print("FAIL: options snapshot missing price")
        return 1
    print("OK: snapshot last=${:.2f} delta={} theta={}".format(
        snap["last"],
        round(snap.get("delta", 0), 3) if snap.get("delta") is not None else "N/A",
        round(snap.get("theta", 0), 3) if snap.get("theta") is not None else "N/A",
    ))

    # 3) Full flow (trade-like)
    class T:
        ticker, strike, option_type = "MSFT", 430, "CALL"
        expiration, is_ode = "2026-02-06", False

    out = get_option_live_price(T())
    if not out:
        print("FAIL: get_option_live_price returned None")
        return 1
    print("OK: get_option_live_price -> last=${:.2f} iv={:.1%}".format(
        out["last"], out.get("implied_volatility") or 0
    ))

    # 4) Quotes (bid/ask) and Last Trade
    opt_ticker = out.get("option_ticker") or ticker
    quote = get_option_quotes_latest(opt_ticker)
    if quote:
        bid = quote.get("bid_price")
        ask = quote.get("ask_price")
        pct = quote.get("spread_pct_of_mid")
        print("OK: quotes -> bid=${:.2f} ask=${:.2f} spread={}% of mid".format(
            bid or 0, ask or 0, pct if pct is not None else "N/A"
        ))
    else:
        print("SKIP: quotes (optional)")
    last_tr = get_option_last_trade(opt_ticker)
    if last_tr:
        print("OK: last trade -> price=${:.2f} size={}".format(last_tr.get("price", 0), last_tr.get("size")))
    else:
        print("SKIP: last trade (optional)")

    # 5) Market status
    status = get_market_status()
    if status:
        print("OK: market status ->", status.get("market", "N/A"))
    else:
        print("SKIP: market status (optional)")

    print("\nMassive options endpoints are working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
