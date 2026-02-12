"""
Market Data Module
Fetch underlying price and rich context (yfinance) and optional news (Brave Search) for option analysis.
"""

from datetime import date, datetime
from typing import Optional, Dict, Any, List


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_underlying_price(ticker: str) -> Optional[float]:
    """Fetch current underlying stock price. Returns None if unavailable."""
    ctx = get_market_context(ticker)
    return ctx.get("current_price")


def get_market_context(ticker: str) -> Dict[str, Any]:
    """
    Fetch rich market context for ticker from Yahoo Finance.
    Returns dict with: current_price, open, high, low, volume, day_range, prev_close,
    fifty_two_week_high, fifty_two_week_low, market_cap (when available).
    Empty dict on failure.
    """
    ctx: Dict[str, Any] = {}
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # 1) Try info dict (most reliable in yfinance 1.x for current price)
        try:
            info = t.info
            if isinstance(info, dict):
                price = _safe_float(
                    info.get("regularMarketPrice")
                    or info.get("currentPrice")
                    or info.get("previousClose")
                )
                if price is not None:
                    ctx["current_price"] = price
                prev = _safe_float(info.get("previousClose"))
                if prev is not None:
                    ctx["prev_close"] = prev
                hi52 = _safe_float(info.get("fiftyTwoWeekHigh"))
                if hi52 is not None:
                    ctx["fifty_two_week_high"] = hi52
                lo52 = _safe_float(info.get("fiftyTwoWeekLow"))
                if lo52 is not None:
                    ctx["fifty_two_week_low"] = lo52
                cap = info.get("marketCap")
                if cap is not None:
                    ctx["market_cap"] = _safe_int(cap)
        except Exception:
            pass

        # 2) Try fast_info for current price if not yet set
        if ctx.get("current_price") is None:
            try:
                fi = getattr(t, "fast_info", None)
                if fi is not None:
                    lp = getattr(fi, "last_price", None)
                    if lp is not None:
                        ctx["current_price"] = _safe_float(lp)
            except Exception:
                pass

        # 3) History: 1d for today's OHLCV, 5d for recent context
        for period, key_prefix in (("1d", "today"), ("5d", "recent")):
            try:
                hist = t.history(period=period)
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    last = hist.iloc[-1]
                    close = _safe_float(last.get("Close"))
                    if close is not None and ctx.get("current_price") is None:
                        ctx["current_price"] = close
                    if key_prefix == "today":
                        ctx["open"] = _safe_float(last.get("Open"))
                        ctx["high"] = _safe_float(last.get("High"))
                        ctx["low"] = _safe_float(last.get("Low"))
                        ctx["volume"] = _safe_int(last.get("Volume"))
                        if ctx.get("high") is not None and ctx.get("low") is not None:
                            ctx["day_range"] = (ctx["high"], ctx["low"])
                    break
            except Exception:
                continue

        # 4) If we still have no price, try 5d history
        if ctx.get("current_price") is None:
            try:
                hist = t.history(period="5d")
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    ctx["current_price"] = _safe_float(hist["Close"].iloc[-1])
                    last = hist.iloc[-1]
                    if ctx.get("open") is None:
                        ctx["open"] = _safe_float(last.get("Open"))
                    if ctx.get("high") is None:
                        ctx["high"] = _safe_float(last.get("High"))
                    if ctx.get("low") is None:
                        ctx["low"] = _safe_float(last.get("Low"))
                    if ctx.get("volume") is None:
                        ctx["volume"] = _safe_int(last.get("Volume"))
            except Exception:
                pass

        # 5) 5d return and 5d range (for momentum and S/R context)
        try:
            hist = t.history(period="5d")
            if hist is not None and len(hist) >= 2 and "Close" in hist.columns:
                first_close = _safe_float(hist["Close"].iloc[0])
                last_close = _safe_float(hist["Close"].iloc[-1])
                if first_close and last_close and first_close != 0:
                    ctx["five_d_return_pct"] = round((last_close - first_close) / first_close * 100, 2)
                if "High" in hist.columns and "Low" in hist.columns:
                    ctx["recent_5d_high"] = _safe_float(hist["High"].max())
                    ctx["recent_5d_low"] = _safe_float(hist["Low"].min())
        except Exception:
            pass
    except Exception:
        pass
    return ctx


def get_news_context(ticker: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Fetch recent news/headlines for the ticker via Brave Search API.
    Returns list of {"title": ..., "url": ..., "description": ...}.
    Empty list if BRAVE_API_KEY not set or request fails.
    """
    import os
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return []
    try:
        from brave import Brave
        client = Brave(api_key=api_key)
        query = f"{ticker} stock news"
        result = client.search(q=query, count=max_results)
        news = []
        for source in ("news_results", "web_results"):
            items = getattr(result, source, None) or []
            for n in items[:max_results]:
                item = {}
                if getattr(n, "title", None):
                    item["title"] = str(n.title)
                if getattr(n, "url", None):
                    item["url"] = str(n.url)
                if getattr(n, "description", None):
                    item["description"] = str(n.description)
                if item:
                    news.append(item)
            if news:
                break
        return news
    except Exception:
        return []


def get_historical_data(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d"
) -> Optional[Any]:
    """
    Fetch OHLC historical data for technical analysis.

    Args:
        ticker: Stock symbol
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

    Returns:
        DataFrame with standardized lowercase columns (open, high, low, close, volume)
        or None if fetch fails
    """
    try:
        import yfinance as yf
        import pandas as pd

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period=period, interval=interval)

        if df is None or df.empty or len(df) < 5:
            return None

        # Standardize column names to lowercase
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).lower() for col in df.columns]

        # Ensure required columns exist
        required = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required):
            return None

        return df

    except Exception:
        return None


def get_atr(
    ticker: str,
    period: int = 14,
    days_back: int = 60,
) -> Optional[float]:
    """
    Compute 14-day (or period) ATR for the underlying using Yahoo Finance daily OHLC.
    True Range = max(H-L, |H-prev_close|, |L-prev_close|); ATR = rolling mean(TR).
    Returns ATR in same units as price (e.g. $ for QQQ). None if insufficient data or fetch fails.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{days_back}d", interval="1d")
        if hist is None or len(hist) < period:
            return None
        high = hist.get("High", hist.get("high"))
        low = hist.get("Low", hist.get("low"))
        close = hist.get("Close", hist.get("close"))
        if high is None or low is None or close is None:
            return None
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = tr1.combine(tr2, max).combine(tr3, max)
        tr = tr.fillna(tr1)  # first row: no prev_close, use H-L only
        atr_series = tr.rolling(window=period).mean()
        valid = atr_series.dropna()
        if len(valid) == 0:
            return None
        atr = _safe_float(valid.iloc[-1])
        if atr is None or (atr != atr):  # reject NaN
            return None
        return atr
    except Exception:
        return None


def get_events(ticker: str, dte: int) -> Dict[str, Any]:
    """
    Fetch upcoming earnings and ex-dividend dates within the option's DTE window.
    Uses yfinance. Returns dict of events: {'earnings': {'date': 'YYYY-MM-DD', 'days_to': n}, ...}
    or {} if none in window / fetch fails. dte is days to expiration (0 = today).
    """
    events: Dict[str, Any] = {}
    today = date.today()
    window_end = dte + 1

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # Earnings: earliest future date within [0, dte+1] days (some sources show Apr 27/28/29 variants; we take soonest in window)
        try:
            cal = t.get_earnings_dates(limit=12)
            if cal is not None and not cal.empty:
                next_earnings: Optional[Dict[str, Any]] = None
                for idx in cal.index:
                    try:
                        if hasattr(idx, "to_pydatetime"):
                            ed = idx.to_pydatetime().date()
                        elif hasattr(idx, "date"):
                            ed = idx.date()
                        else:
                            continue
                        days_to = (ed - today).days
                        if 0 <= days_to <= window_end:
                            if next_earnings is None or days_to < next_earnings["days_to"]:
                                next_earnings = {"date": ed.strftime("%Y-%m-%d"), "days_to": days_to}
                    except Exception:
                        continue
                if next_earnings:
                    events["earnings"] = next_earnings
        except Exception:
            pass

        # Dividend: exDividendDate from info (Unix timestamp)
        try:
            info = t.info
            if isinstance(info, dict):
                ex_ts = info.get("exDividendDate")
                if ex_ts is not None and isinstance(ex_ts, (int, float)):
                    ex_dt = datetime.fromtimestamp(ex_ts)
                    ex_d = ex_dt.date()
                    days_to_div = (ex_d - today).days
                    if 0 <= days_to_div <= window_end:
                        events["dividend"] = {"date": ex_d.strftime("%Y-%m-%d"), "days_to": days_to_div}
        except Exception:
            pass
    except Exception:
        pass
    return events


def get_enhanced_technical_context(ticker: str) -> Dict[str, Any]:
    """
    Get enhanced technical indicators for better analysis.
    
    Returns dict with:
    - daily: {sma_20, sma_50, sma_200, rsi, macd, macd_signal, above_sma_20, above_sma_50}
    - volume_trend: {trend, strength, rise_volume, decline_volume, change_pct}
    - market_context: {vix, spy_trend, vix_change_pct}
    """
    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        ctx = {}
        
        # Get daily data for indicators
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        
        if df is None or df.empty:
            return ctx
        
        # Standardize columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).lower() for col in df.columns]
        
        if 'close' not in df.columns:
            return ctx
        
        close = df['close']
        high = df.get('high', close)
        low = df.get('low', close)
        volume = df.get('volume', pd.Series([0] * len(df)))
        
        # Calculate SMAs
        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1] if len(df) >= 200 else None
        
        current_price = close.iloc[-1]
        
        # Calculate RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1] if len(rsi) > 0 else None
        
        # Calculate MACD
        ema_12 = close.ewm(span=12).mean()
        ema_26 = close.ewm(span=26).mean()
        macd_line = ema_12 - ema_26
        macd_signal_line = macd_line.ewm(span=9).mean()
        macd_val = macd_line.iloc[-1]
        signal_val = macd_signal_line.iloc[-1]
        
        # Daily technical summary
        ctx['daily'] = {
            'sma_20': float(sma_20) if sma_20 and not np.isnan(sma_20) else None,
            'sma_50': float(sma_50) if sma_50 and not np.isnan(sma_50) else None,
            'sma_200': float(sma_200) if sma_200 and not np.isnan(sma_200) else None,
            'rsi': float(rsi_val) if rsi_val and not np.isnan(rsi_val) else None,
            'macd': float(macd_val) if macd_val and not np.isnan(macd_val) else None,
            'macd_signal': float(signal_val) if signal_val and not np.isnan(signal_val) else None,
            'price_above_sma_20': current_price > sma_20 if sma_20 and not np.isnan(sma_20) else None,
            'price_above_sma_50': current_price > sma_50 if sma_50 and not np.isnan(sma_50) else None,
        }
        
        # Volume analysis
        if len(volume) >= 5:
            avg_vol = volume.rolling(5).mean().iloc[-1]
            latest_vol = volume.iloc[-1]
            vol_change = (latest_vol - avg_vol) / avg_vol * 100 if avg_vol > 0 else 0
            
            # Rise vs decline volume
            price_change = close.diff()
            rise_vol = volume[price_change > 0].sum()
            decline_vol = volume[price_change < 0].sum()
            
            # Volume trend
            if vol_change > 20:
                vol_trend = 'increasing'
                vol_strength = 'strong'
            elif vol_change > 10:
                vol_trend = 'increasing'
                vol_strength = 'moderate'
            elif vol_change > -10:
                vol_trend = 'stable'
                vol_strength = 'normal'
            else:
                vol_trend = 'decreasing'
                vol_strength = 'low'
            
            ctx['volume_trend'] = {
                'trend': vol_trend,
                'strength': vol_strength,
                'rise_volume': int(rise_vol),
                'decline_volume': int(decline_vol),
                'change_pct': round(vol_change, 1),
            }
        
        # Market context (SPY, VIX)
        try:
            spy = yf.Ticker('SPY')
            spy_close = spy.history(period="5d")['Close']
            if len(spy_close) >= 2:
                spy_now = spy_close.iloc[-1]
                spy_5d_ago = spy_close.iloc[-6] if len(spy_close) >= 6 else spy_close.iloc[0]
                spy_change = (spy_now - spy_5d_ago) / spy_5d_ago * 100
                
                if spy_change > 2:
                    spy_trend = 'bullish'
                elif spy_change > 0.5:
                    spy_trend = 'slight_bullish'
                elif spy_change < -2:
                    spy_trend = 'bearish'
                elif spy_change < -0.5:
                    spy_trend = 'slight_bearish'
                else:
                    spy_trend = 'neutral'
                
                ctx['market_context'] = {
                    'spy_trend': spy_trend,
                    'spy_change_pct': round(spy_change, 2),
                }
        except:
            pass
        
        # VIX
        try:
            vix_ticker = yf.Ticker('^VIX')
            vix_close = vix_ticker.history(period="5d")['Close']
            if len(vix_close) >= 2:
                vix_now = vix_close.iloc[-1]
                vix_5d_ago = vix_close.iloc[-5] if len(vix_close) >= 5 else vix_close.iloc[0]
                vix_change = (vix_now - vix_5d_ago) / vix_5d_ago * 100
                
                if 'market_context' not in ctx:
                    ctx['market_context'] = {}
                ctx['market_context']['vix'] = float(vix_now)
                ctx['market_context']['vix_change_pct'] = round(vix_change, 2)
        except:
            pass
        
        return ctx
        
    except Exception:
        return {}
