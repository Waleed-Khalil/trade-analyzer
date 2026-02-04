"""
Massive (options data) client: contract lookup, OHLC, Option Chain Snapshot, Quotes, Last Trade, Market Status.
Uses: /v3/reference/options/contracts, /v3/snapshot/options/{underlying}, /v2/aggs/.../prev, /v1/open-close/...,
/v3/quotes/{optionsTicker}, /v2/last/trade/{optionsTicker}, /v1/marketstatus/now.
"""

import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.getenv("MASSIVE_BASE_URL", "https://api.massive.com")


def _get_api_key() -> Optional[str]:
    # Polygon and Massive use the same API key; either env var works.
    return os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")


def _request(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """GET request to Massive API. Adds apiKey. Returns JSON or None."""
    key = _get_api_key()
    if not key:
        return None
    params = dict(params or {})
    params["apiKey"] = key
    try:
        import urllib.request
        import urllib.parse
        import json
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_option_contract_ticker(
    underlying_ticker: str,
    contract_type: str,
    strike_price: float,
    expiration_date: str,
) -> Optional[str]:
    """
    Resolve option contract ticker from Massive (e.g. O:AAPL250202C00215000).
    expiration_date: YYYY-MM-DD.
    contract_type: 'call' or 'put'.
    Returns options ticker string or None.
    """
    ct = (contract_type or "").lower()
    if ct not in ("call", "put"):
        ct = "call"
    payload = _request("/v3/reference/options/contracts", params={
        "underlying_ticker": underlying_ticker.upper(),
        "contract_type": ct,
        "strike_price": strike_price,
        "expiration_date": expiration_date,
        "expired": "false",
        "limit": 1,
    })
    if not payload or payload.get("status") != "OK":
        return None
    results = payload.get("results") or []
    if not results:
        return None
    return results[0].get("ticker")


def get_option_contract_nearest(
    underlying_ticker: str,
    contract_type: str,
    strike_price: float,
    expiration_gte: str,
) -> Optional[str]:
    """
    Get the nearest-term option contract (soonest expiration on or after expiration_gte).
    Returns options ticker string or None.
    """
    out = _get_option_contract_nearest_with_exp(underlying_ticker, contract_type, strike_price, expiration_gte)
    return out.get("ticker") if out else None


def _get_option_contract_nearest_with_exp(
    underlying_ticker: str,
    contract_type: str,
    strike_price: float,
    expiration_gte: str,
) -> Optional[Dict[str, Any]]:
    """
    Get nearest-term option contract; returns dict with ticker and expiration_date (YYYY-MM-DD).
    """
    ct = (contract_type or "").lower()
    if ct not in ("call", "put"):
        ct = "call"
    payload = _request("/v3/reference/options/contracts", params={
        "underlying_ticker": underlying_ticker.upper(),
        "contract_type": ct,
        "strike_price": strike_price,
        "expiration_date.gte": expiration_gte,
        "expired": "false",
        "sort": "expiration_date",
        "order": "asc",
        "limit": 1,
    })
    if not payload or payload.get("status") != "OK":
        return None
    results = payload.get("results") or []
    if not results:
        return None
    r = results[0]
    return {"ticker": r.get("ticker"), "expiration_date": r.get("expiration_date")}


def get_option_prev_close(options_ticker: str) -> Optional[Dict[str, Any]]:
    """
    GET /v2/aggs/ticker/{optionsTicker}/prev - previous day OHLC for option.
    Returns dict with c, h, l, o, v, vw or None.
    """
    path = f"/v2/aggs/ticker/{options_ticker}/prev"
    payload = _request(path)
    if not payload or payload.get("status") != "OK":
        return None
    results = (payload.get("results") or [])
    if not results:
        return None
    return results[0]


def get_option_snapshot(
    underlying_asset: str,
    strike_price: float,
    expiration_date: str,
    contract_type: str,
) -> Optional[Dict[str, Any]]:
    """
    GET /v3/snapshot/options/{underlyingAsset} - Option Chain Snapshot.
    Returns first matching contract with greeks, implied_volatility, break_even_price,
    and price from last_trade or day.close. Plan-dependent (Options Starter+).
    """
    ct = (contract_type or "").lower()
    if ct not in ("call", "put"):
        ct = "call"
    path = f"/v3/snapshot/options/{underlying_asset.upper()}"
    payload = _request(path, params={
        "strike_price": strike_price,
        "expiration_date": expiration_date,
        "contract_type": ct,
        "limit": 1,
        "order": "asc",
        "sort": "ticker",
    })
    if not payload or payload.get("status") != "OK":
        return None
    results = payload.get("results") or []
    if not results:
        return None
    r = results[0]
    out: Dict[str, Any] = {}
    # Price: last_trade > day.close
    lt = r.get("last_trade") or {}
    day_obj = r.get("day") or {}
    if lt.get("price") is not None:
        out["last"] = float(lt["price"])
    elif day_obj.get("close") is not None:
        out["last"] = float(day_obj["close"])
    if day_obj.get("open") is not None:
        out["open"] = float(day_obj["open"])
    if day_obj.get("high") is not None:
        out["high"] = float(day_obj["high"])
    if day_obj.get("low") is not None:
        out["low"] = float(day_obj["low"])
    if day_obj.get("volume") is not None:
        out["volume"] = int(day_obj["volume"])
    if r.get("break_even_price") is not None:
        out["break_even_price"] = float(r["break_even_price"])
    if r.get("implied_volatility") is not None:
        out["implied_volatility"] = float(r["implied_volatility"])
    greeks = r.get("greeks") or {}
    if greeks.get("delta") is not None:
        out["delta"] = float(greeks["delta"])
    if greeks.get("gamma") is not None:
        out["gamma"] = float(greeks["gamma"])
    if greeks.get("theta") is not None:
        out["theta"] = float(greeks["theta"])
    if greeks.get("vega") is not None:
        out["vega"] = float(greeks["vega"])
    if r.get("details", {}).get("ticker"):
        out["option_ticker"] = r["details"]["ticker"]
    if r.get("open_interest") is not None:
        out["open_interest"] = int(r["open_interest"])
    return out if out else None


def get_option_open_close(options_ticker: str, date: str) -> Optional[Dict[str, Any]]:
    """
    GET /v1/open-close/{optionsTicker}/{date} - daily open/close for option.
    date: YYYY-MM-DD. Returns dict with open, close, high, low, volume or None.
    """
    path = f"/v1/open-close/{options_ticker}/{date}"
    payload = _request(path)
    if not payload or payload.get("status") != "OK":
        return None
    return payload


def get_option_historical_aggs(
    option_ticker: str,
    from_date: str,
    to_date: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to} - historical daily OHLC for option.
    from_date, to_date: YYYY-MM-DD. Returns list of {"date": "YYYY-MM-DD", "close": float, ...}
    sorted oldest first, or None on failure. Used to recompute historical IV for IV Rank.
    """
    import urllib.parse
    path = f"/v2/aggs/ticker/{urllib.parse.quote(option_ticker, safe='')}/range/1/day/{from_date}/{to_date}"
    payload = _request(path, params={"sort": "asc", "limit": 50000})
    if not payload or payload.get("status") != "OK":
        return None
    results = payload.get("results") or []
    out = []
    for r in results:
        t_ms = r.get("t")
        c = r.get("c")
        if t_ms is None or c is None:
            continue
        try:
            dt = datetime.utcfromtimestamp(int(t_ms) / 1000)
            date_str = dt.strftime("%Y-%m-%d")
            out.append({
                "date": date_str,
                "close": float(c),
                "open": r.get("o"),
                "high": r.get("h"),
                "low": r.get("l"),
                "volume": r.get("v"),
            })
        except (TypeError, ValueError, OSError):
            continue
    return out if out else None


def get_option_quotes_latest(options_ticker: str) -> Optional[Dict[str, Any]]:
    """
    GET /v3/quotes/{optionsTicker} - latest quote (bid/ask) for the option.
    Params: limit=1, sort=sip_timestamp, order=desc.
    Returns dict with: bid_price, ask_price, bid_size, ask_size, spread, spread_pct_of_mid, sip_timestamp; or None.
    """
    if not options_ticker:
        return None
    path = f"/v3/quotes/{options_ticker}"
    payload = _request(path, params={"limit": 1, "sort": "sip_timestamp", "order": "desc"})
    if not payload or payload.get("status") != "OK":
        return None
    results = payload.get("results") or []
    if not results:
        return None
    r = results[0]
    bid = r.get("bid_price")
    ask = r.get("ask_price")
    if bid is None and ask is None:
        return None
    bid = float(bid) if bid is not None else None
    ask = float(ask) if ask is not None else None
    out: Dict[str, Any] = {}
    if bid is not None:
        out["bid_price"] = bid
    if ask is not None:
        out["ask_price"] = ask
    if r.get("bid_size") is not None:
        out["bid_size"] = int(r["bid_size"])
    if r.get("ask_size") is not None:
        out["ask_size"] = int(r["ask_size"])
    if r.get("sip_timestamp") is not None:
        out["sip_timestamp"] = int(r["sip_timestamp"])
    if bid is not None and ask is not None:
        spread = ask - bid
        mid = (bid + ask) / 2.0
        out["spread"] = round(spread, 4)
        out["spread_pct_of_mid"] = round((spread / mid * 100.0), 1) if mid else None
    return out if out else None


def get_option_last_trade(options_ticker: str) -> Optional[Dict[str, Any]]:
    """
    GET /v2/last/trade/{optionsTicker} - latest trade for the option.
    Returns dict with: price (p), size (s), sip_timestamp (t, nanoseconds); or None.
    """
    if not options_ticker:
        return None
    path = f"/v2/last/trade/{options_ticker}"
    payload = _request(path)
    if not payload or payload.get("status") != "OK":
        return None
    r = payload.get("results")
    if not r or r.get("p") is None:
        return None
    out: Dict[str, Any] = {"price": float(r["p"])}
    if r.get("s") is not None:
        out["size"] = int(r["s"])
    if r.get("t") is not None:
        out["sip_timestamp"] = int(r["t"])
    return out


def get_market_status() -> Optional[Dict[str, Any]]:
    """
    GET /v1/marketstatus/now - current market open/closed/extended-hours.
    Returns dict with: market, earlyHours, afterHours, serverTime, exchanges; or None.
    """
    payload = _request("/v1/marketstatus/now")
    if not payload:
        return None
    out: Dict[str, Any] = {}
    if payload.get("market") is not None:
        out["market"] = payload["market"]
    if payload.get("earlyHours") is not None:
        out["early_hours"] = payload["earlyHours"]
    if payload.get("afterHours") is not None:
        out["after_hours"] = payload["afterHours"]
    if payload.get("serverTime") is not None:
        out["server_time"] = payload["serverTime"]
    if payload.get("exchanges") is not None:
        out["exchanges"] = payload["exchanges"]
    return out if out else None


def get_option_live_price(trade: Any) -> Optional[Dict[str, Any]]:
    """
    Get latest option price and, when available, greeks/IV/break-even from Polygon.
    - If trade has expiration (e.g. from EXP 2026-02-06): use that date.
    - ODE / 0DTE: exact expiration = today.
    - Else: nearest-term contract on or after today.
    Tries Option Chain Snapshot first (greeks, IV, break_even); falls back to prev/open-close for price. Uses Massive API.
    Returns dict with: last, open, high, low, volume, option_ticker; and when snapshot available:
    delta, gamma, theta, vega, implied_volatility, break_even_price, open_interest.
    """
    key = _get_api_key()
    if not key:
        return None
    underlying = getattr(trade, "ticker", "").upper()
    strike = getattr(trade, "strike", 0)
    if not underlying or not strike:
        return None
    ct = getattr(trade, "option_type", "CALL").lower()
    ct = "call" if ct == "call" else "put"
    is_ode = getattr(trade, "is_ode", False)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    explicit_exp = getattr(trade, "expiration", None)  # YYYY-MM-DD if parsed from EXP
    expiration_date = today
    option_ticker = None
    if explicit_exp and re.match(r"\d{4}-\d{2}-\d{2}", str(explicit_exp)):
        expiration_date = str(explicit_exp)
        option_ticker = get_option_contract_ticker(underlying, ct, strike, expiration_date)
    elif is_ode:
        option_ticker = get_option_contract_ticker(underlying, ct, strike, today)
    else:
        with_exp = _get_option_contract_nearest_with_exp(underlying, ct, strike, today)
        if with_exp:
            option_ticker = with_exp.get("ticker")
            expiration_date = with_exp.get("expiration_date") or today
    if not option_ticker:
        return None
    # Prefer Option Chain Snapshot (greeks, IV, break-even, price)
    snapshot = get_option_snapshot(underlying, strike, expiration_date, ct)
    if snapshot and snapshot.get("last") is not None:
        return snapshot
    # Fallback: open-close then prev
    ohlc = get_option_open_close(option_ticker, today)
    if ohlc is not None:
        close = ohlc.get("close")
        if close is not None:
            return {
                "last": close,
                "open": ohlc.get("open"),
                "high": ohlc.get("high"),
                "low": ohlc.get("low"),
                "volume": ohlc.get("volume"),
                "option_ticker": option_ticker,
            }
    prev = get_option_prev_close(option_ticker)
    if prev is not None:
        c = prev.get("c")
        if c is not None:
            return {
                "last": c,
                "open": prev.get("o"),
                "high": prev.get("h"),
                "low": prev.get("l"),
                "volume": prev.get("v"),
                "option_ticker": option_ticker,
            }
    return None
