"""
Trade Analyzer — Option Play Analysis (no Discord)
Paste an option play; get Go/No-Go, stop loss, take-profit levels, and support/resistance.
Supports ODE (same-day / 0DTE) with tighter risk parameters.
"""

import os
import sys
from datetime import date, timedelta
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.trade_parser import TradeParser, OptionTrade
from risk_engine.risk_engine import RiskEngine
from analysis.trade_analyzer import TradeAnalyzer
from report.report import print_analysis_report

# Load .env first so API keys are available everywhere
def _load_env(repo_root: str) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(repo_root, ".env"))
    except ImportError:
        pass


def _parse_args(argv: list) -> tuple:
    """Parse argv into (verbose, no_ai, no_market, dte_override, play_parts)."""
    verbose = False
    no_ai = False
    no_market = False
    dte_override = None
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--verbose", "-v"):
            verbose = True
        elif arg == "--no-ai":
            no_ai = True
        elif arg == "--no-market":
            no_market = True
        elif arg in ("--dte", "-d") and i + 1 < len(argv):
            try:
                dte_override = max(0, int(argv[i + 1]))
            except ValueError:
                pass
            i += 1
        else:
            rest.append(arg)
        i += 1
    return verbose, no_ai, no_market, dte_override, rest


def get_option_play_input(play_parts: list) -> str:
    """Read option play from play_parts, stdin, or interactive prompt."""
    if play_parts:
        return " ".join(play_parts).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    print("Paste your option play (e.g. NVDA 150 CALL @ 2.50 0DTE) and press Enter:")
    return input().strip()


def _supported_formats(config_path: str) -> list:
    """Load supported format examples from config for error message."""
    try:
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        formats = config.get("alert_formats", [])
        return [f.get("example", "") for f in formats if f.get("example")]
    except Exception:
        return [
            "BUY AAPL 01/31 215 CALL @ 3.50",
            "AAPL CALL 215 @ 3.50",
            "NVDA 150 CALL @ 2.50 0DTE",
            "QQQ 630 CALL @ .20",
        ]


def _rule_based_recommendation(trade, trade_plan):
    """Build recommendation from rule-based plan when AI is skipped or fails."""
    max_risk = getattr(trade_plan.position, "max_risk_dollars", None)
    max_risk_str = f"${max_risk:.0f}" if isinstance(max_risk, (int, float)) else "N/A"
    max_gain = getattr(trade_plan, "max_gain_dollars", None)
    max_gain_str = f"${max_gain:.0f}" if isinstance(max_gain, (int, float)) else "N/A"
    is_ode = getattr(trade, "is_ode", False)
    risk_assess = (
        f"MAX LOSS: {max_risk_str} if stop at ${trade_plan.stop_loss} is hit.\n"
        f"MAX GAIN: ~{max_gain_str} if target at ${trade_plan.target_1} is hit ({trade_plan.target_1_r}R).\n"
        "PROBABILITY: Based on rule-based setup and volatility context above."
    )
    entry = (
        f"ENTRY ZONE: ${trade.premium - 0.05:.2f} - ${trade.premium + 0.05:.2f}\n"
        "CONFIRMATION: Wait for price at or below entry zone before entering.\n"
        + ("TIMING: Trade early in day for 0DTE." if is_ode else "TIMING: Best during market hours.")
    )
    exit_strat = (
        f"PRIMARY STOP: ${trade_plan.stop_loss} ({trade_plan.stop_risk_pct}% of premium)"
        + (" - sooner for 0DTE.\n" if is_ode else ".\n")
        + f"TARGET 1: ${trade_plan.target_1} ({trade_plan.target_1_r}R) - take 50% off here.\n"
        + f"RUNNER: {trade_plan.runner_contracts} contracts @ ${trade_plan.runner_target} - trail after partial.\n"
        + ("TIME EXIT: Exit 1 hour before close if not profitable." if is_ode else "TIME EXIT: Exit at 50% DTE if not near targets.")
    )
    market_ctx = "TREND/VOLATILITY: See technicals and IV rank above. SENTIMENT: Rule-based only; set AI key for full context."
    class RuleRecommendation:
        recommendation = trade_plan.go_no_go
        reasoning = "; ".join(getattr(trade_plan, "go_no_go_reasons", None) or []) or "Rule-based pass/fail."
        risk_assessment = risk_assess
        entry_criteria = entry
        exit_strategy = exit_strat
        market_context = market_ctx
        stop_loss_suggestion = f"${trade_plan.stop_loss} ({trade_plan.stop_risk_pct}% of premium)"
        take_profit_levels = [
            f"T1: ${trade_plan.target_1} ({trade_plan.target_1_r}R)",
            f"Runner: {trade_plan.runner_contracts} @ ${trade_plan.runner_target}" if trade_plan.runner_contracts else "",
        ]
        support_resistance = []
        ode_risks = ["Consider theta decay and time of day."] if is_ode else []
    return RuleRecommendation()


def run_analysis(
    play_text: str,
    config_path: str,
    no_ai: bool = False,
    no_market: bool = False,
    dte_override: Optional[int] = None,
    verbose: bool = False,
):
    """
    Run full analysis pipeline. Returns a dict:
    - On parse failure: {"ok": False, "error": str, "supported_formats": list}
    - On success: {"ok": True, "trade", "trade_plan", "analysis", "recommendation", "market_context", "current_price", "option_quote"}
    """
    parser = TradeParser(config_path)
    trade = parser.parse(play_text)
    if not trade:
        return {
            "ok": False,
            "error": "Could not parse the option play.",
            "supported_formats": _supported_formats(config_path),
        }
    if dte_override is not None:
        exp_date = (date.today() + timedelta(days=dte_override)).strftime("%Y-%m-%d")
        trade = OptionTrade(
            ticker=trade.ticker,
            option_type=trade.option_type,
            strike=trade.strike,
            premium=trade.premium,
            contracts=trade.contracts,
            expiration=exp_date,
            entry_price=trade.entry_price,
            direction=trade.direction,
            raw_message=trade.raw_message,
            parsed_at=trade.parsed_at,
            is_ode=(dte_override == 0),
            days_to_expiration=dte_override,
        )
    current_price = None
    market_context = {}
    news_context = []
    option_quote = None
    if not no_market:
        try:
            from market_data.market_data import get_market_context, get_news_context
            from market_data.polygon_client import (
                get_option_live_price,
                get_option_quotes_latest,
                get_option_last_trade,
                get_market_status,
            )
            market_context = get_market_context(trade.ticker)
            current_price = market_context.get("current_price")
            news_context = get_news_context(trade.ticker)
            option_quote = get_option_live_price(trade)
            if option_quote:
                market_context["option_live"] = option_quote.get("last")
                market_context["option_ticker"] = option_quote.get("option_ticker")
                if option_quote.get("implied_volatility") is not None:
                    market_context["implied_volatility"] = option_quote.get("implied_volatility")
                if option_quote.get("break_even_price") is not None:
                    market_context["break_even_price"] = option_quote.get("break_even_price")
                if any(option_quote.get(g) is not None for g in ("delta", "gamma", "theta", "vega")):
                    market_context["greeks"] = {
                        k: option_quote[k] for k in ("delta", "gamma", "theta", "vega")
                        if option_quote.get(k) is not None
                    }
                if option_quote.get("open_interest") is not None:
                    market_context["open_interest"] = option_quote.get("open_interest")
                if option_quote.get("volume") is not None:
                    market_context["option_volume"] = option_quote.get("volume")
                # Quotes (bid/ask) and Last Trade for spread + staleness
                opt_ticker = option_quote.get("option_ticker")
                if opt_ticker:
                    try:
                        latest_quote = get_option_quotes_latest(opt_ticker)
                        if latest_quote:
                            market_context["option_quote"] = latest_quote
                        last_trade = get_option_last_trade(opt_ticker)
                        if last_trade:
                            market_context["option_last_trade"] = last_trade
                    except Exception:
                        pass
            # Market status (open/closed/extended-hours)
            try:
                status = get_market_status()
                if status:
                    market_context["market_status"] = status
            except Exception:
                pass
            market_context["days_to_expiration"] = getattr(trade, "days_to_expiration", None)
            # Strike context (ITM/OTM %), time to close (0DTE), pasted vs live
            from analysis.context import get_strike_context, get_time_to_close_et_minutes, pasted_vs_live_premium_diff_pct
            market_context.update(get_strike_context(trade, current_price))
            if getattr(trade, "is_ode", False):
                mins = get_time_to_close_et_minutes()
                if mins is not None:
                    market_context["minutes_to_close_et"] = mins
            if option_quote and (live := option_quote.get("last")) is not None:
                market_context["premium_diff_pct"] = pasted_vs_live_premium_diff_pct(trade.premium, live)
            # Break-even at expiration if not from Massive (call: strike + premium, put: strike - premium)
            if market_context.get("break_even_price") is None and trade.strike and trade.premium:
                opt = (getattr(trade, "option_type", "CALL") or "CALL").upper()
                if opt == "CALL":
                    market_context["break_even_price"] = trade.strike + trade.premium
                else:
                    market_context["break_even_price"] = trade.strike - trade.premium
            # Required move to break-even (% total and % per day)
            be = market_context.get("break_even_price")
            dte_req = market_context.get("days_to_expiration")
            if current_price and be is not None and dte_req is not None and dte_req >= 0 and current_price != 0:
                required_pct = (be - current_price) / current_price
                market_context["required_move_pct"] = required_pct
                market_context["required_move_per_day_pct"] = required_pct / max(dte_req, 1)
            # Expected move (1 SD to expiration): spot * IV * sqrt(DTE/365)
            dte_for_move = market_context.get("days_to_expiration")
            iv_for_move = market_context.get("implied_volatility")
            if current_price and iv_for_move is not None and dte_for_move is not None and dte_for_move >= 0:
                import math
                iv_dec = iv_for_move if iv_for_move <= 2 else iv_for_move / 100.0
                t_years = max(dte_for_move / 365.0, 1 / 365.0)
                expected_move_pct = iv_dec * math.sqrt(t_years)
                market_context["expected_move_pct"] = expected_move_pct
                market_context["expected_move_1sd"] = current_price * expected_move_pct
            # Probability of Profit (Black-Scholes) when we have IV, spot, and DTE
            dte = market_context.get("days_to_expiration")
            if current_price and trade.strike and market_context.get("implied_volatility") is not None:
                from analysis.greeks import probability_of_profit, days_to_years
                t = days_to_years(dte if dte is not None else 0)
                if t is not None and t > 0:
                    iv = market_context["implied_volatility"]
                    if iv <= 2:
                        iv = iv  # already decimal
                    else:
                        iv = iv / 100.0
                    pop = probability_of_profit(
                        spot=current_price,
                        strike=trade.strike,
                        time_years=t,
                        risk_free_rate=0.05,
                        implied_vol=iv,
                        option_type=getattr(trade, "option_type", "call"),
                    )
                    if pop is not None:
                        market_context["probability_of_profit"] = round(pop, 2)
                # Scenario probabilities (prob of +1%/+2%/-1%/-2% move by exp)
                if current_price and market_context.get("implied_volatility") is not None:
                    from analysis.greeks import scenario_probabilities, days_to_years
                    iv_sc = market_context["implied_volatility"]
                    iv_sc = iv_sc if iv_sc <= 2 else iv_sc / 100.0
                    t_sc = days_to_years(dte if dte is not None else 0)
                    if t_sc and t_sc > 0:
                        probs = scenario_probabilities(
                            spot=current_price,
                            time_years=t_sc,
                            risk_free_rate=0.05,
                            implied_vol=iv_sc,
                            option_type=getattr(trade, "option_type", "call"),
                        )
                        if probs:
                            market_context["scenario_probs"] = probs
                elif dte is not None and dte == 0:
                    t_same_day = 0.5 / 365.0  # half day as proxy
                    iv = market_context["implied_volatility"]
                    if iv > 2:
                        iv = iv / 100.0
                    pop = probability_of_profit(
                        spot=current_price,
                        strike=trade.strike,
                        time_years=t_same_day,
                        risk_free_rate=0.05,
                        implied_vol=iv,
                        option_type=getattr(trade, "option_type", "call"),
                    )
                    if pop is not None:
                        market_context["probability_of_profit"] = round(pop, 2)
            # Multi-timeframe technical (RSI, MACD, SMA) when enabled
            try:
                import yaml
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
                if (cfg.get("analysis") or {}).get("technical", {}).get("enabled", False):
                    from market_data.technical import get_technical_context
                    tech_ctx = get_technical_context(trade.ticker, cfg)
                    if tech_ctx:
                        market_context["technical"] = tech_ctx
            except Exception:
                pass
        except Exception as e:
            if verbose:
                print(f"[verbose] Market data skipped: {e}", file=sys.stderr)
            # Run without market data; AI and rules still work
    if not no_market and market_context.get("current_price") is None and trade.ticker:
        print("  Warning: Underlying price not fetched (check network or try again).", file=sys.stderr)

    # Event risk: earnings / ex-dividend within DTE window (yfinance)
    if not no_market and trade.ticker:
        try:
            from market_data.market_data import get_events
            dte = getattr(trade, "days_to_expiration", None)
            dte = dte if dte is not None else 0
            market_context["events"] = get_events(trade.ticker, dte)
        except Exception as e:
            if verbose:
                print(f"[verbose] Events fetch skipped: {e}", file=sys.stderr)
            market_context["events"] = {}

    # IV Rank & realized vol (historical IV from Massive when available; realized from Yahoo)
    if not no_market and trade.ticker:
        try:
            import yaml
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f)
            iv_cfg = (cfg.get("analysis") or {}).get("iv_rank", {})
            lookback = iv_cfg.get("lookback_days", 365)
            rv_window = iv_cfg.get("realized_vol_window", 30)
            market_context["iv_rank_high_threshold"] = iv_cfg.get("rank_high_threshold", 80)
            market_context["iv_rank_low_threshold"] = iv_cfg.get("rank_low_threshold", 30)
            from analysis.volatility import get_iv_rank, get_realized_volatility, get_historical_ivs_polygon
            current_iv = market_context.get("implied_volatility")
            option_ticker = market_context.get("option_ticker")
            use_recompute = iv_cfg.get("use_historical_recompute", False)
            max_iv_days = iv_cfg.get("max_historical_iv_days", 126)
            min_samples = iv_cfg.get("min_historical_samples", 30)
            sigma_low = iv_cfg.get("solver_sigma_low", 0.001)
            sigma_high = iv_cfg.get("solver_sigma_high", 5.0)
            historical_ivs = []
            if use_recompute and option_ticker and current_iv is not None:
                stress_cfg = (cfg.get("analysis") or {}).get("stress", {})
                risk_free = stress_cfg.get("risk_free_rate", 0.05)
                historical_ivs = get_historical_ivs_polygon(
                    trade,
                    option_ticker,
                    lookback_days=min(lookback, max_iv_days),
                    risk_free_rate=risk_free,
                    max_days=max_iv_days,
                    min_historical_samples=min_samples,
                    sigma_low=sigma_low,
                    sigma_high=sigma_high,
                )
            if current_iv is not None:
                iv_dec = float(current_iv) if current_iv <= 2 else float(current_iv) / 100.0
                iv_rank = get_iv_rank(iv_dec, historical_ivs)
                if iv_rank is not None:
                    market_context["iv_rank"] = round(iv_rank, 1)
                    market_context["iv_rank_sample_count"] = len(historical_ivs)
                    market_context["iv_rank_partial"] = max_iv_days < lookback
                    market_context["iv_rank_max_days"] = max_iv_days
                    market_context["iv_rank_min_samples"] = min_samples
            realized = get_realized_volatility(trade.ticker, window_days=rv_window, days_back=min(lookback, 252))
            if realized is not None:
                market_context["realized_vol_30d"] = round(realized, 4)
            # HV rank fallback when historical IV is N/A (52w realized-vol rank as IV proxy)
            if market_context.get("iv_rank") is None and iv_cfg.get("use_hv_rank_fallback", False) and realized is not None:
                from analysis.volatility import compute_hv_rank
                hv_rank = compute_hv_rank(trade.ticker, realized, period=252, rolling_window=21)
                if hv_rank is not None:
                    market_context["iv_rank"] = round(hv_rank, 1)
                    market_context["iv_rank_proxy"] = "HV"
        except Exception as e:
            if verbose:
                print(f"[verbose] IV rank / realized vol block skipped: {e}", file=sys.stderr)

    # ATR-based vol-adjusted levels (Yahoo daily OHLC); augments rule-based SL/targets
    if not no_market and trade.ticker:
        try:
            import yaml
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f)
            atr_cfg = (cfg.get("stops") or {}).get("atr", {})
            period = atr_cfg.get("period", 14)
            days_back = atr_cfg.get("days_back", 60)
            sl_mult = atr_cfg.get("sl_multiplier", 1.5)
            t1_mult = atr_cfg.get("t1_multiplier", 2.0)
            t2_mult = atr_cfg.get("t2_multiplier", 4.0)
            use_delta = atr_cfg.get("use_delta_adjust", True)
            fallback_delta = atr_cfg.get("fallback_delta", 0.5)
            min_atr = atr_cfg.get("min_atr_threshold", 1.0)
            floor_fraction = atr_cfg.get("atr_sl_floor_fraction", 0.2)
            low_delta_threshold = atr_cfg.get("low_delta_threshold", 0.3)
            from market_data.market_data import get_atr
            atr = get_atr(trade.ticker, period=period, days_back=days_back)
            if atr is not None:
                market_context["atr"] = round(atr, 2)
                market_context["atr_period"] = period
                if atr < min_atr:
                    market_context["atr_low_vol"] = True
                delta = None
                if use_delta:
                    g = (market_context.get("greeks") or {}).get("delta")
                    if g is not None:
                        delta = float(g)
                    else:
                        delta = fallback_delta
                if delta is not None:
                    entry_prem = trade.premium
                    opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
                    if opt_type == "CALL":
                        atr_stop = entry_prem - delta * sl_mult * atr
                        atr_t1 = entry_prem + delta * t1_mult * atr
                        atr_t2 = entry_prem + delta * t2_mult * atr
                    else:
                        atr_stop = entry_prem - abs(delta) * sl_mult * atr
                        atr_t1 = entry_prem + abs(delta) * t1_mult * atr
                        atr_t2 = entry_prem + abs(delta) * t2_mult * atr
                    market_context["atr_stop_was_negative"] = atr_stop < 0
                    if atr_stop <= 0:
                        # Floor: min stop as fraction of premium; use higher fraction for low-delta OTM
                        frac = max(floor_fraction, 0.5) if (delta is not None and abs(delta) < low_delta_threshold) else floor_fraction
                        atr_stop = entry_prem * frac
                        market_context["atr_stop_floored"] = True
                        market_context["atr_stop_floor_fraction"] = frac
                    market_context["atr_stop"] = max(0.0, round(atr_stop, 2))
                    market_context["atr_t1"] = max(0.0, round(atr_t1, 2))
                    market_context["atr_t2"] = max(0.0, round(atr_t2, 2))
                    market_context["atr_sl_multiplier"] = sl_mult
                    market_context["atr_put"] = opt_type == "PUT"
        except Exception as e:
            if verbose:
                print(f"[verbose] ATR block skipped: {e}", file=sys.stderr)

    # Enhanced Technical Analysis (Phase 1-4: Price Action, Volume, Patterns, Trend)
    if not no_market and current_price and trade.ticker:
        try:
            import yaml
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}

            analysis_cfg = cfg.get("analysis", {})

            # Fetch historical OHLC data for technical analysis
            from market_data.market_data import get_historical_data
            hist_df = get_historical_data(trade.ticker, period="3mo", interval="1d")

            if hist_df is not None and len(hist_df) >= 20:
                # Get ATR if not already calculated
                atr = market_context.get("atr")
                if atr is None:
                    from market_data.market_data import get_atr
                    atr = get_atr(trade.ticker, period=14, days_back=60)
                    if atr:
                        market_context["atr"] = round(atr, 2)

                # Phase 1: Price Action S/R Analysis
                sr_cfg = analysis_cfg.get("support_resistance", {})
                if sr_cfg.get("enabled", True):
                    try:
                        from analysis.price_action import calculate_support_resistance_zones
                        sr_zones = calculate_support_resistance_zones(
                            hist_df,
                            current_price,
                            ticker=trade.ticker,
                            lookback_days=sr_cfg.get("lookback_days", 60),
                            swing_window=5,
                            min_touches=sr_cfg.get("min_touches", 2),
                            zone_clustering_pct=sr_cfg.get("zone_clustering_pct", 0.5),
                            atr=atr,
                            max_levels=sr_cfg.get("max_levels", 5)
                        )
                        if sr_zones:
                            market_context["sr_analysis"] = sr_zones
                    except Exception as e:
                        if verbose:
                            print(f"[verbose] Price action analysis skipped: {e}", file=sys.stderr)

                # Phase 2: Volume Analysis
                vol_cfg = analysis_cfg.get("volume", {})
                if vol_cfg.get("enabled", True):
                    try:
                        from analysis.volume_analysis import (
                            calculate_vwap,
                            build_volume_profile,
                            check_price_vs_vwap,
                            analyze_volume_trend
                        )

                        # VWAP
                        if vol_cfg.get("vwap_enabled", True):
                            vwap_series = calculate_vwap(hist_df)
                            if not vwap_series.empty and len(vwap_series) > 0:
                                # Get the most recent VWAP value
                                vwap = float(vwap_series.iloc[-1])
                                market_context["vwap"] = round(vwap, 2)
                                vwap_position = check_price_vs_vwap(current_price, vwap)
                                if vwap_position:
                                    market_context["vwap_position"] = vwap_position

                        # Volume Profile
                        if vol_cfg.get("volume_profile_enabled", True):
                            vol_profile = build_volume_profile(
                                hist_df,
                                price_bins=vol_cfg.get("price_bins", 50),
                                value_area_pct=0.70
                            )
                            if vol_profile:
                                market_context["volume_profile"] = vol_profile

                        # Volume Trend
                        vol_trend = analyze_volume_trend(hist_df, period=20)
                        if vol_trend:
                            market_context["volume_trend"] = vol_trend

                    except Exception as e:
                        if verbose:
                            print(f"[verbose] Volume analysis skipped: {e}", file=sys.stderr)

                # Phase 3: Candlestick Pattern Recognition
                pattern_cfg = analysis_cfg.get("patterns", {})
                if pattern_cfg.get("enabled", True):
                    try:
                        from analysis.candlestick_patterns import get_pattern_signals
                        patterns = get_pattern_signals(
                            hist_df,
                            lookback=pattern_cfg.get("lookback_bars", 10),
                            require_volume_confirmation=pattern_cfg.get("require_volume_confirmation", True)
                        )
                        if patterns:
                            market_context["candlestick_patterns"] = patterns
                    except Exception as e:
                        if verbose:
                            print(f"[verbose] Pattern analysis skipped: {e}", file=sys.stderr)

                # Phase 4: Trend Analysis
                trend_cfg = analysis_cfg.get("trend", {})
                if trend_cfg.get("enabled", True):
                    try:
                        from analysis.trend_analysis import identify_trend, calculate_adx

                        # Identify trend structure
                        trend = identify_trend(
                            hist_df,
                            method="swing_points",
                            adx_threshold=trend_cfg.get("adx_trending_threshold", 25)
                        )
                        if trend:
                            market_context["trend_analysis"] = trend

                        # Calculate ADX
                        adx_series = calculate_adx(hist_df, period=trend_cfg.get("adx_period", 14))
                        if not adx_series.empty and len(adx_series) > 0:
                            # Get the most recent ADX value
                            adx = float(adx_series.iloc[-1])
                            if not np.isnan(adx):
                                market_context["adx"] = round(adx, 1)

                    except Exception as e:
                        if verbose:
                            print(f"[verbose] Trend analysis skipped: {e}", file=sys.stderr)

                # Phase 7: Fibonacci Analysis
                fib_cfg = analysis_cfg.get("fibonacci", {})
                if fib_cfg.get("enabled", True) and current_price:
                    try:
                        from analysis.fibonacci import get_fib_analysis
                        fib_analysis = get_fib_analysis(
                            trade.ticker,
                            current_price,
                            df=hist_df,
                            lookback=fib_cfg.get("lookback_days", 60)
                        )
                        if fib_analysis:
                            market_context["fibonacci_analysis"] = fib_analysis
                    except Exception as e:
                        if verbose:
                            print(f"[verbose] Fibonacci analysis skipped: {e}", file=sys.stderr)

        except Exception as e:
            if verbose:
                print(f"[verbose] Enhanced technical analysis skipped: {e}", file=sys.stderr)

    # Rule-based plan (ODE params applied automatically when is_ode)
    engine = RiskEngine(config_path)

    # First pass: Create preliminary trade_plan with fixed sizing
    # (needed for analyzer.analyze() to calculate setup_score)
    trade_plan = engine.create_trade_plan(trade, current_price=current_price, market_context=market_context)

    # Stress test: P/L for instant underlying moves (Black-Scholes reprice)
    iv_for_stress = market_context.get("implied_volatility")
    if iv_for_stress is None and market_context.get("realized_vol_30d") is not None:
        iv_for_stress = market_context["realized_vol_30d"]
        market_context["stress_test_iv_proxy"] = "30d realized"
    if current_price and trade.strike and iv_for_stress is not None:
        try:
            import yaml
            from analysis.greeks import stress_test_scenarios, days_to_years
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f)
            stress_cfg = (cfg.get("analysis") or {}).get("stress", {})
            scenarios = stress_cfg.get("scenarios", [-0.02, -0.01, 0.01, 0.02])
            r = stress_cfg.get("risk_free_rate", 0.05)
            iv = iv_for_stress
            if iv > 2:
                iv = iv / 100.0
            dte = market_context.get("days_to_expiration")
            if dte is None:
                dte = getattr(trade, "days_to_expiration", 0) or 0
            t = days_to_years(dte)
            if t is None or t <= 0:
                t = 0.5 / 365.0  # same-day proxy
            risk_dollars = getattr(trade_plan.position, "max_risk_dollars", 0) or (
                (trade.premium - trade_plan.stop_loss) * trade_plan.position.contracts * 100
            )
            stress_results = stress_test_scenarios(
                spot=current_price,
                strike=trade.strike,
                entry_premium=trade.premium,
                time_years=t,
                risk_free_rate=r,
                implied_vol=iv,
                option_type=getattr(trade, "option_type", "call"),
                contracts=trade_plan.position.contracts,
                risk_dollars=risk_dollars,
                scenario_pct_changes=scenarios,
            )
            if stress_results is not None:
                market_context["stress_test"] = stress_results
                market_context["stress_test_risk_dollars"] = risk_dollars
        except Exception as e:
            if verbose:
                print(f"[verbose] Stress test block skipped: {e}", file=sys.stderr)

    # 1-day theta-adjusted stress (flat and spot-move estimates; DTE >= 0)
    if current_price and trade.premium and trade.strike:
        try:
            from analysis.greeks import theta_stress_1d
            dte = market_context.get("days_to_expiration")
            dte = dte if dte is not None else getattr(trade, "days_to_expiration", 0) or 0
            g = market_context.get("greeks") or {}
            theta = g.get("theta")
            delta = g.get("delta")
            premium = (option_quote.get("last") if option_quote else None) or trade.premium
            theta_1d = theta_stress_1d(
                current_premium=premium,
                spot=current_price,
                dte=dte,
                theta=theta,
                delta=delta,
            )
            if theta_1d is not None:
                market_context["theta_stress_1d"] = theta_1d
                market_context["theta_stress_1d_premium"] = premium
        except Exception as e:
            if verbose:
                print(f"[verbose] Theta stress 1d skipped: {e}", file=sys.stderr)

    # Rule-based analysis (red/green flags, setup quality)
    analyzer = TradeAnalyzer(config_path)
    analysis = analyzer.analyze(
        trade, trade_plan, current_price=current_price,
        market_context=market_context, option_live_price=option_quote.get("last") if option_quote else None,
    )

    # Second pass: Recalculate position sizing with smart sizing if enabled
    # Now that we have setup_score from analysis, use it for optimal position sizing
    try:
        import yaml
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        sizing_config = cfg.get('sizing', {})

        if sizing_config.get('method') == 'composite' and hasattr(analysis, 'setup_score'):
            # Store analysis result in market_context for RiskEngine
            market_context['analysis_result'] = {
                'setup_score': analysis.setup_score,
                'setup_quality': analysis.setup_quality,
                'confidence': analysis.confidence
            }

            # Recalculate position with smart sizing
            new_position = engine.calculate_position(
                trade,
                current_price,
                setup_score=analysis.setup_score,
                iv_rank=market_context.get('iv_rank_percentile'),
                trade_history=market_context.get('trade_history', []),
                current_drawdown_pct=market_context.get('current_drawdown_pct', 0.0),
                stop_loss=trade_plan.stop_loss
            )

            # Update trade_plan with new position sizing
            # Recalculate dependent values (max_loss, max_gain)
            max_loss_dollars = new_position.contracts * (trade.premium - trade_plan.stop_loss) * 100
            max_gain_dollars = new_position.contracts * (trade_plan.target_1 - trade.premium) * 100
            runner_contracts = int(new_position.contracts * cfg.get('targets', {}).get('runner_remaining_pct', 0.50))

            # Create updated trade_plan with smart-sized position
            from dataclasses import replace
            trade_plan = replace(
                trade_plan,
                position=new_position,
                max_loss_dollars=round(max_loss_dollars, 2),
                max_gain_dollars=round(max_gain_dollars, 2),
                runner_contracts=runner_contracts
            )

            if verbose:
                print(f"[verbose] Smart sizing applied: {new_position.contracts} contracts (score: {analysis.setup_score})", file=sys.stderr)
    except Exception as e:
        if verbose:
            print(f"[verbose] Smart sizing recalculation skipped: {e}", file=sys.stderr)

    # AI recommendation (Anthropic) — Go/No-Go, reasoning, stop, targets, levels
    if no_ai:
        recommendation = _rule_based_recommendation(trade, trade_plan)
    else:
        try:
            from ai_agent.ai_agent import OptionAIAgent, RecommendationResult
            agent = OptionAIAgent(config_path)
            recommendation = agent.get_recommendation(
                trade=trade,
                trade_plan=trade_plan,
                analysis=analysis,
                current_price=current_price,
                market_context=market_context,
                news_context=news_context,
            )
        except ValueError as e:
            print(f"  Note: {e}")
            print("  Showing rule-based analysis only. Set ANTHROPIC_API_KEY for AI recommendation.\n")
            recommendation = _rule_based_recommendation(trade, trade_plan)
        except Exception as e:
            if verbose:
                print(f"[verbose] AI recommendation failed: {e}", file=sys.stderr)
            recommendation = _rule_based_recommendation(trade, trade_plan)

    # Sanity override: if pasted vs live differs by >100%, force DON'T PLAY (stale alert)
    diff_pct = market_context.get("premium_diff_pct")
    if diff_pct is not None and abs(diff_pct) > 100:
        rec = getattr(recommendation, "recommendation", "")
        if rec in ("PLAY", "GO"):
            class OverrideRecommendation:
                recommendation = "DON'T PLAY"
                reasoning = (
                    f"Overridden: Pasted vs live option price differs by {abs(diff_pct):.0f}% - "
                    "alert is likely stale. Verify current premium before trading."
                )
                stop_loss_suggestion = getattr(recommendation, "stop_loss_suggestion", f"${trade_plan.stop_loss}")
                take_profit_levels = getattr(recommendation, "take_profit_levels", [])
                support_resistance = getattr(recommendation, "support_resistance", [])
                ode_risks = getattr(recommendation, "ode_risks", [])
            recommendation = OverrideRecommendation()

    return {
        "ok": True,
        "trade": trade,
        "trade_plan": trade_plan,
        "analysis": analysis,
        "recommendation": recommendation,
        "market_context": market_context,
        "current_price": current_price,
        "option_quote": option_quote,
    }


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(repo_root, "config", "config.yaml")
    _load_env(repo_root)

    verbose, no_ai, no_market, dte_override, play_parts = _parse_args(sys.argv[1:])
    play_text = get_option_play_input(play_parts)
    if not play_text:
        print("No option play provided. Usage: python main.py [--verbose] [--no-ai] [--no-market] [--dte N] \"NVDA 150 CALL @ 2.50 0DTE\"")
        sys.exit(1)

    result = run_analysis(play_text, config_path, no_ai, no_market, dte_override, verbose)
    if not result["ok"]:
        print(result["error"])
        for ex in result.get("supported_formats", []):
            print(f"  {ex}")
        sys.exit(1)

    trade = result["trade"]
    trade_plan = result["trade_plan"]
    analysis = result["analysis"]
    recommendation = result["recommendation"]
    market_context = result["market_context"]
    current_price = result["current_price"]
    option_quote = result["option_quote"]

    # Log PLAY signals to journal when enabled (min_score_to_log from config)
    rec = getattr(recommendation, "recommendation", "")
    if rec in ("PLAY", "GO"):
        try:
            from journal.journal import log_play_signal
            log_id = log_play_signal(
                trade, trade_plan, analysis, recommendation,
                market_context=market_context,
                config_path=config_path,
            )
            if log_id is not None and verbose:
                print(f"[verbose] Journal logged signal id={log_id}", file=sys.stderr)
        except Exception as ex:
            if verbose:
                print(f"[verbose] Journal log skipped: {ex}", file=sys.stderr)

    print_analysis_report(
        trade, trade_plan, analysis, recommendation,
        current_price=current_price,
        option_live_price=option_quote.get("last") if option_quote else None,
        market_context=market_context,
    )


if __name__ == "__main__":
    main()
