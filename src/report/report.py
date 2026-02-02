"""
Report Module
Print detailed option analysis to console (no Discord).
"""

from typing import Any, Optional


def print_analysis_report(
    trade: Any,
    trade_plan: Any,
    analysis: Any,
    recommendation: Any,
    current_price: Optional[float] = None,
    option_live_price: Optional[float] = None,
    market_context: Optional[Any] = None,
) -> None:
    """
    Print a full analysis report: decision, why, stop, targets, levels, red flags, ODE risks.
    """
    sep = "=" * 60
    sub = "-" * 60
    is_ode = getattr(trade, "is_ode", False)

    print()
    print(sep)
    print("  OPTION PLAY ANALYSIS")
    print(sep)
    print(f"  {trade.ticker} {trade.option_type} ${trade.strike} @ ${trade.premium}")
    exp = getattr(trade, "expiration", None)
    dte = getattr(trade, "days_to_expiration", None)
    if exp:
        print(f"  Expiration: {exp}" + (f" ({dte} DTE)" if dte is not None else ""))
    if is_ode:
        print("  Same-day expiration (0DTE) - tighter stops and targets applied.")
    # Data used: make it clear what is live vs pasted
    print()
    print("  DATA USED")
    print(sub)
    if current_price is not None:
        line = f"  - Underlying (live): ${current_price:.2f} (Yahoo Finance)"
        ctx = market_context or {}
        if ctx.get("high") is not None and ctx.get("low") is not None:
            line += f" | Day range ${ctx['low']:.2f}-${ctx['high']:.2f}"
        if ctx.get("volume") is not None:
            vol = ctx["volume"]
            line += f" | Vol {vol:,}"
        if ctx.get("fifty_two_week_high") is not None and ctx.get("fifty_two_week_low") is not None:
            line += f" | 52w ${ctx['fifty_two_week_low']:.0f}-${ctx['fifty_two_week_high']:.0f}"
        print(line)
    else:
        print("  - Underlying: not fetched (Yahoo Finance unavailable or not installed)")
    if option_live_price is not None:
        pasted = getattr(trade, "premium", None)
        diff = (market_context or {}).get("premium_diff_pct")
        line = f"  - Option: Pasted ${pasted:.2f} | Live ${option_live_price:.2f} (Polygon)"
        if diff is not None:
            line += f" | {diff:+.0f}% vs pasted"
        print(line)
    else:
        print("  - Option: from pasted play only (Polygon unavailable or no contract match)")
    ctx = market_context or {}
    if ctx.get("moneyness_label"):
        print(f"  - Strike: {ctx['moneyness_label']} (vs live underlying)")
    if ctx.get("five_d_return_pct") is not None:
        pct = ctx["five_d_return_pct"]
        sign = "+" if pct >= 0 else ""
        print(f"  - Underlying 5d: {sign}{pct}%")
    if ctx.get("recent_5d_high") is not None and ctx.get("recent_5d_low") is not None:
        print(f"  - Recent 5d range: ${ctx['recent_5d_low']:.2f}-${ctx['recent_5d_high']:.2f}")
    if getattr(trade, "is_ode", False) and ctx.get("minutes_to_close_et") is not None:
        m = ctx["minutes_to_close_et"]
        h, m = m // 60, m % 60
        print(f"  - Time to close (ET): {h}h {m}m")
    if ctx.get("greeks") or ctx.get("implied_volatility") is not None or ctx.get("break_even_price") is not None:
        parts = []
        g = ctx.get("greeks") or {}
        if g:
            parts.append("Delta {:.2f}".format(g["delta"]) if g.get("delta") is not None else "")
            if g.get("theta") is not None:
                parts.append("Theta {:.4f}".format(g["theta"]))
            if g.get("vega") is not None:
                parts.append("Vega {:.2f}".format(g["vega"]))
        iv = ctx.get("implied_volatility")
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append("IV {:.1f}%".format(iv_pct))
        be = ctx.get("break_even_price")
        if be is not None:
            parts.append("Break-even ${:.2f}".format(be))
        line = " | ".join(p for p in parts if p)
        if line:
            print(f"  - Option chain (Polygon snapshot): {line}")
    # Greeks & Probabilities section when we have greeks or PoP
    g = ctx.get("greeks") or {}
    pop = ctx.get("probability_of_profit")
    iv = ctx.get("implied_volatility")
    if g or pop is not None or iv is not None:
        print()
        print("  GREEKS & PROBABILITIES")
        print(sub)
        parts = []
        if g.get("delta") is not None:
            parts.append(f"Delta {g['delta']:.2f}")
        if g.get("gamma") is not None:
            parts.append(f"Gamma {g['gamma']:.4f}")
        if g.get("theta") is not None:
            parts.append(f"Theta {g['theta']:.4f}")
        if g.get("vega") is not None:
            parts.append(f"Vega {g['vega']:.2f}")
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append(f"IV {iv_pct:.1f}%")
        if parts:
            print("  " + " | ".join(parts))
        if pop is not None:
            print(f"  Probability of Profit (PoP): {pop:.0%}" + (" (below 50% => consider HOLD)" if pop < 0.50 else ""))
        oi = ctx.get("open_interest")
        opt_vol = ctx.get("option_volume")
        if oi is not None or opt_vol is not None:
            liq = []
            if opt_vol is not None:
                liq.append(f"Volume {opt_vol:,}")
            if oi is not None:
                liq.append(f"OI {oi:,}")
            print("  Liquidity: " + " | ".join(liq))
    # IV Rank & vol context (when we have IV and/or realized vol)
    iv = ctx.get("implied_volatility")
    iv_rank = ctx.get("iv_rank")
    rv = ctx.get("realized_vol_30d")
    if iv is not None or iv_rank is not None or rv is not None:
        print()
        print("  IV RANK & VOL CONTEXT")
        print(sub)
        parts = []
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append(f"Current IV: {iv_pct:.1f}%")
        if iv_rank is not None:
            parts.append(f"52w Rank: {iv_rank:.0f}%")
        else:
            parts.append("52w Rank: N/A (historical IV not in use)")
        if rv is not None:
            rv_pct = rv * 100 if rv <= 2 else rv
            parts.append(f"30d Realized: {rv_pct:.1f}%")
        print("  " + " | ".join(parts))
        high_thresh = ctx.get("iv_rank_high_threshold", 80)
        low_thresh = ctx.get("iv_rank_low_threshold", 30)
        if iv_rank is not None:
            if iv_rank >= high_thresh:
                print("  High IV rank – overpriced; caution on longs, potential crush.")
            elif iv_rank < low_thresh:
                print("  Low IV rank – favorable for buys.")
            if ctx.get("iv_rank_partial"):
                cap = ctx.get("iv_rank_max_days", 126)
                print(f"  Partial history (capped at {cap} days or available data); rank approximate.")
            sample_count = ctx.get("iv_rank_sample_count")
            min_samples = ctx.get("iv_rank_min_samples", 30)
            if sample_count is not None and min_samples is not None and min_samples <= sample_count < min_samples + 30:
                print(f"  Limited samples (~{sample_count} days) – rank less reliable.")
        if iv is not None and rv is not None:
            iv_dec = iv if iv <= 2 else iv / 100.0
            if iv_dec > rv * 1.2:
                print("  IV above realized – options rich vs recent vol.")
            elif iv_dec < rv * 0.8:
                print("  IV below realized – options cheap vs recent vol.")
    # Technical confluence (RSI, MACD, SMA)
    tech = ctx.get("technical", {})
    if isinstance(tech, dict) and (tech.get("daily") or tech.get("1h")):
        print()
        print("  TECHNICAL CONFLUENCE")
        print(sub)
        daily = tech.get("daily") or {}
        rsi_d = daily.get("rsi")
        sma20 = daily.get("sma_20")
        sma50 = daily.get("sma_50")
        above20 = daily.get("price_above_sma_20")
        above50 = daily.get("price_above_sma_50")
        macd_bull = daily.get("macd_bullish")
        parts_d = []
        if rsi_d is not None:
            label = "bullish" if rsi_d >= 50 else "bearish"
            parts_d.append(f"RSI {rsi_d:.0f} ({label})")
        if above20 is not None:
            parts_d.append("Price > 20 SMA" if above20 else "Price < 20 SMA")
        if above50 is not None:
            parts_d.append("Price > 50 SMA" if above50 else "Price < 50 SMA")
        if macd_bull is not None:
            parts_d.append("MACD bullish" if macd_bull else "MACD bearish")
        if parts_d:
            print("  Daily: " + " | ".join(parts_d))
        oneh = tech.get("1h") or {}
        rsi_1h = oneh.get("rsi")
        macd_1h = oneh.get("macd_bullish")
        if rsi_1h is not None or macd_1h is not None:
            parts_1h = []
            if rsi_1h is not None:
                parts_1h.append(f"RSI {rsi_1h:.0f}")
            if macd_1h is not None:
                parts_1h.append("MACD bullish" if macd_1h else "MACD bearish")
            if parts_1h:
                print("  1H: " + " | ".join(parts_1h))
    print()

    # Decision
    rec = getattr(recommendation, "recommendation", trade_plan.go_no_go)
    emoji = "[GO]" if rec in ("PLAY", "GO") else "[NO-GO]"
    print(f"  {emoji} RECOMMENDATION: {rec}")
    # Warn when recommendation is PLAY but red flag says alert may be stale
    if analysis and rec in ("PLAY", "GO"):
        stale_flags = [f for f in analysis.red_flags if "stale" in (f.get("message") or "").lower()]
        if stale_flags:
            print("  [!] Warning: Alert may be stale (pasted vs live premium). Verify current price before trading.")
    print(sub)
    reasoning = getattr(recommendation, "reasoning", "")
    if reasoning:
        for line in reasoning.split("\n"):
            print(f"  {line.strip()}")
    print()

    # Rule-based summary
    print("  RULE-BASED PLAN")
    print(sub)
    print(f"  Position: {trade_plan.position.contracts} contracts")
    print(f"  Risk: ${trade_plan.position.max_risk_dollars:.0f} ({trade_plan.position.risk_percentage:.1%})")
    print(f"  Entry zone: {trade_plan.entry_zone}")
    if trade_plan.go_no_go_reasons:
        print(f"  Rule check: {trade_plan.go_no_go} - {', '.join(trade_plan.go_no_go_reasons)}")
    # Risk summary one-liner
    try:
        max_gain_t1 = trade_plan.position.contracts * (trade_plan.target_1 - trade.premium) * 100
    except Exception:
        max_gain_t1 = 0
    print(f"  Risk summary: Max loss ${trade_plan.position.max_risk_dollars:.0f} | Max gain at T1 ~${max_gain_t1:.0f} | Risk {trade_plan.position.risk_percentage:.1%} of capital")
    print()

    # Stress test scenarios (instant underlying move => est. P/L; sorted worst to best)
    stress_results = (market_context or {}).get("stress_test")
    if stress_results:
        print("  STRESS TEST SCENARIOS (instant move, no theta adjustment)")
        print(sub)
        spot = current_price or 0
        for pct, pl, pct_ror in stress_results:
            sign = "+" if pct >= 0 else ""
            dollar_move = spot * pct if spot else 0
            dollar_str = f" (${dollar_move:+.2f})" if spot else ""
            print(f"  - {sign}{pct * 100:.1f}% underlying{dollar_str}: Est. P/L ${pl:.0f} ({pct_ror:+.1f}% of risk)")
        # Theta decay hint when Greeks available
        ctx = market_context or {}
        g = ctx.get("greeks") or {}
        theta = g.get("theta") if isinstance(g, dict) else None
        if theta is not None and trade_plan and getattr(trade_plan, "position", None):
            contracts = getattr(trade_plan.position, "contracts", 1)
            daily_decay = max(0.0, -float(theta) * 100 * contracts)
            print(f"  Approx. daily theta decay (if held 1 day): ~${daily_decay:.0f}")
        dte = ctx.get("days_to_expiration")
        if dte is not None and dte < 3:
            print("  Note: Theta decay accelerates significantly near expiration—daily estimate is approximate.")
        print()

    # Stop loss
    stop_text = getattr(recommendation, "stop_loss_suggestion", f"${trade_plan.stop_loss}")
    print("  STOP LOSS")
    print(sub)
    print(f"  {stop_text}")
    ctx = market_context or {}
    if ctx.get("atr_stop") is not None and ctx.get("atr") is not None:
        period = ctx.get("atr_period", 14)
        mult = ctx.get("atr_sl_multiplier", 1.5)
        print(f"  Vol-adjusted ({mult}x{period}d ATR): ${ctx['atr_stop']:.2f} (underlying {period}d ATR = ${ctx['atr']:.2f})")
        print(f"  Vol-adjusted levels use current {period}d ATR of ${ctx['atr']:.2f}. If ATR rises, stops widen.")
        if ctx.get("atr_low_vol"):
            print("  [Low vol] ATR below threshold – static levels may be preferred.")
        if ctx.get("atr_stop_was_negative"):
            print("  Vol-adjusted SL below $0 – use intrinsic or static fallback.")
        dte = ctx.get("days_to_expiration")
        if dte is not None and dte < 3:
            print("  ATR-based levels approximate; theta decay may dominate near expiration.")
        if ctx.get("atr_put"):
            print("  (|delta| used for puts.)")
    print()

    # ATR-based targets (when available)
    if ctx.get("atr_t1") is not None or ctx.get("atr_t2") is not None:
        print("  ATR-BASED TARGETS (vol-adjusted)")
        print(sub)
        if ctx.get("atr_t1") is not None:
            print(f"  - T1: ${ctx['atr_t1']:.2f}")
        if ctx.get("atr_t2") is not None:
            print(f"  - T2/Runner: ${ctx['atr_t2']:.2f}")
        print()

    # Take-profit levels
    levels = getattr(recommendation, "take_profit_levels", None) or [
        f"T1: ${trade_plan.target_1} ({trade_plan.target_1_r}R)",
        f"Runner: {trade_plan.runner_contracts} @ ${trade_plan.runner_target}" if trade_plan.runner_contracts else "",
    ]
    print("  TAKE-PROFIT LEVELS")
    print(sub)
    for level in levels:
        if level:
            print(f"  - {level}")
    print()

    # Support / resistance
    sr = getattr(recommendation, "support_resistance", [])
    if sr:
        print("  SUPPORT / RESISTANCE")
        print(sub)
        for s in sr:
            s = (s or "").strip().lstrip("- ")
            if s:
                print(f"  - {s}")
        print()

    # Red flags
    if analysis and analysis.red_flags:
        print("  RED FLAGS")
        print(sub)
        for f in analysis.red_flags:
            msg = f.get("message", str(f))
            sev = f.get("severity", "")
            print(f"  [!] {msg}" + (f" [{sev}]" if sev else ""))
        print()

    # ODE risks
    ode_risks = getattr(recommendation, "ode_risks", [])
    if ode_risks or is_ode:
        print("  ODE / SAME-DAY EXPIRATION RISKS")
        print(sub)
        for r in ode_risks:
            if r:
                print(f"  - {r}")
        if is_ode and not ode_risks:
            print("  - Theta decay accelerates into close; consider exiting before last hour.")
            print("  - Gamma can move option price sharply; use tight stops.")
        print()

    # Setup quality, score (0-100), and confidence breakdown
    if analysis:
        print("  SETUP QUALITY")
        print(sub)
        score = getattr(analysis, "setup_score", 0)
        print(f"  {analysis.setup_quality.upper()} | Score: {score}/100 | Confidence: {analysis.confidence:.0%}")
        if score > 0:
            print("  (PLAY suggested if score > 75; combine with recommendation above.)")
        if analysis.green_flags:
            print("  Green flags:", "; ".join(f.get("message", "") for f in analysis.green_flags if f.get("message")))
        if analysis.red_flags:
            print("  Red flags:", "; ".join(f.get("message", "") for f in analysis.red_flags if f.get("message")))
    print()
    print(sep)
    print()
