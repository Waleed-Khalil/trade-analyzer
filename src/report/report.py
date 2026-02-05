"""
Report Module
Print detailed option analysis to console with comprehensive reasoning.
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
    Print a full analysis report with detailed reasoning, risk assessment, 
    entry/exit criteria, and comprehensive market context.
    """
    sep = "=" * 64
    sub = "-" * 64
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
        print("  Same-day expiration (0DTE) - tighter stops and targets apply.")
    # One-line summary
    ctx_summary = market_context or {}
    rec = getattr(recommendation, "recommendation", getattr(trade_plan, "go_no_go", ""))
    summary_parts = []
    if dte is not None:
        summary_parts.append(f"{dte} DTE")
    summary_parts.append(ctx_summary.get("moneyness_label", "option") or "option")
    pop_s = ctx_summary.get("probability_of_profit")
    if pop_s is not None:
        summary_parts.append(f"PoP {pop_s:.0%}")
    g = ctx_summary.get("greeks") or {}
    prem = getattr(trade, "premium", 0) or 0.01
    theta_s = g.get("theta")
    if theta_s is not None and prem > 0:
        decay = abs(theta_s) / prem * 100
        summary_parts.append(f"Theta ~{decay:.0f}%/day")
    r_mult = getattr(trade_plan, "target_1_r", None)
    if r_mult is not None:
        summary_parts.append(f"R:R 1:{r_mult:.1f}")
    summary_parts.append("[PLAY]" if rec in ("PLAY", "GO") else "[DON'T PLAY]")
    print("  " + " | ".join(summary_parts))
    print()

    # ============================================================
    # DATA USED
    # ============================================================
    print("  DATA USED")
    print(sub)
    ctx = market_context or {}
    
    if current_price is not None:
        line = f"  Underlying (live): ${current_price:.2f} (Yahoo Finance)"
        if ctx.get("high") is not None and ctx.get("low") is not None:
            line += f" | Day ${ctx['low']:.2f}-${ctx['high']:.2f}"
        if ctx.get("volume") is not None:
            line += f" | Vol {ctx['volume']:,}"
        if ctx.get("fifty_two_week_high") and ctx.get("fifty_two_week_low"):
            line += f" | 52w ${ctx['fifty_two_week_low']:.0f}-${ctx['fifty_two_week_high']:.0f}"
        print(line)
    else:
        print("  Underlying: not fetched")
    
    if option_live_price is not None:
        pasted = getattr(trade, "premium", None)
        diff = ctx.get("premium_diff_pct")
        line = f"  Option (live): ${option_live_price:.2f} (Massive)"
        if pasted:
            line += f" | Pasted: ${pasted:.2f}"
        if diff is not None:
            line += f" | Diff: {diff:+.0f}%"
        print(line)
        # Bid/Ask and Last Trade from Quotes + Last Trade APIs
        oq = ctx.get("option_quote")
        if oq and (oq.get("bid_price") is not None or oq.get("ask_price") is not None):
            bid = oq.get("bid_price")
            ask = oq.get("ask_price")
            parts = []
            if bid is not None:
                parts.append(f"Bid ${bid:.2f}")
            if ask is not None:
                parts.append(f"Ask ${ask:.2f}")
            if oq.get("spread") is not None and oq.get("spread_pct_of_mid") is not None:
                parts.append(f"Spread ${oq['spread']:.2f} ({oq['spread_pct_of_mid']:.0f}% of mid)")
            if parts:
                print("  " + " | ".join(parts))
        lt = ctx.get("option_last_trade")
        if lt and lt.get("price") is not None:
            age = ""
            if lt.get("sip_timestamp") is not None:
                import time
                ns = lt["sip_timestamp"]
                age_sec = max(0, (time.time_ns() - ns) // 1_000_000_000)
                if age_sec < 60:
                    age = f" ({age_sec}s ago)"
                else:
                    age = f" ({age_sec // 60}m ago)"
            print(f"  Last trade: ${lt['price']:.2f}" + (f" x{lt['size']}" if lt.get("size") is not None else "") + age)
    else:
        print("  Option: pasted value only")

    ms = ctx.get("market_status") or {}
    if ms.get("market"):
        print(f"  Market: {ms['market']}")
    
    if ctx.get("moneyness_label"):
        print(f"  Strike: {ctx['moneyness_label']}")
    be = ctx.get("break_even_price")
    if be is not None:
        print(f"  Break-even (exp): ${be:.2f}")
    req_pct = ctx.get("required_move_pct")
    req_per_day = ctx.get("required_move_per_day_pct")
    dte_d = getattr(trade, "days_to_expiration", None)
    if req_pct is not None and dte_d is not None and dte_d > 0 and req_per_day is not None:
        sign = "+" if req_pct >= 0 else ""
        print(f"  Required: {sign}{req_pct * 100:.1f}% by exp (~{req_per_day * 100:.1f}%/day)")
    if ctx.get("five_d_return_pct") is not None:
        sign = "+" if ctx["five_d_return_pct"] >= 0 else ""
        print(f"  5d Return: {sign}{ctx['five_d_return_pct']:.1f}%")
    
    if is_ode and ctx.get("minutes_to_close_et") is not None:
        m = ctx["minutes_to_close_et"]
        h, mins = m // 60, m % 60
        print(f"  Time to Close: {h}h {mins}m")
    print()

    # ============================================================
    # GREEKS & PROBABILITIES
    # ============================================================
    g = ctx.get("greeks") or {}
    pop = ctx.get("probability_of_profit")
    iv = ctx.get("implied_volatility")
    
    if g or pop is not None or iv is not None:
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
            parts.append(f"V {g['vega']:.2f}")
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append(f"IV {iv_pct:.1f}%")
        if parts:
            print("  " + " | ".join(parts))
        
        if pop is not None:
            flag = " [!] <50%" if pop < 0.50 else ""
            print(f"  PoP (prob ITM at exp): {pop:.0%}{flag}")
        theta = g.get("theta")
        if theta is not None:
            prem = getattr(trade, "premium", 0) or 0.01
            decay_pct = abs(theta) / prem * 100
            print(f"  Theta (1d): ~${abs(theta):.2f}/share decay if flat (~{decay_pct:.0f}% of premium)")
        oi = ctx.get("open_interest")
        opt_vol = ctx.get("option_volume")
        if oi is not None or opt_vol is not None:
            liq = []
            if opt_vol is not None:
                liq.append(f"Vol {opt_vol:,}")
            if oi is not None:
                liq.append(f"OI {oi:,}")
            print("  Liquidity: " + " | ".join(liq))
        print()

    # ============================================================
    # VOLATILITY CONTEXT
    # ============================================================
    iv_rank = ctx.get("iv_rank")
    rv = ctx.get("realized_vol_30d")
    
    if iv is not None or iv_rank is not None or rv is not None:
        print("  VOLATILITY CONTEXT")
        print(sub)
        parts = []
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append(f"IV: {iv_pct:.1f}%")
        if iv_rank is not None:
            label = " (HV proxy)" if ctx.get("iv_rank_proxy") == "HV" else ""
            parts.append(f"IV Rank{label}: {iv_rank:.0f}%")
        if rv is not None:
            rv_pct = rv * 100 if rv <= 2 else rv
            parts.append(f"30d HV: {rv_pct:.1f}%")
        print("  " + " | ".join(parts))
        if iv is not None and rv is not None:
            iv_dec = iv if iv <= 2 else iv / 100.0
            rv_dec = rv if rv <= 2 else rv / 100.0
            if iv_dec > rv_dec * 1.1:
                print("  -> IV vs 30d HV: rich (premium may be expensive; IV crush risk on long)")
            elif iv_dec < rv_dec * 0.9:
                print("  -> IV vs 30d HV: cheap (favorable for buying options)")
            else:
                print("  -> IV vs 30d HV: in line")
        exp_move = ctx.get("expected_move_1sd")
        exp_pct = ctx.get("expected_move_pct")
        if exp_move is not None and current_price:
            pct = (exp_pct * 100) if exp_pct is not None else (exp_move / current_price * 100)
            print(f"  Expected move (1 SD to exp): ${exp_move:.2f} ({pct:.1f}%)")
        scenario_probs = ctx.get("scenario_probs")
        if scenario_probs:
            probs_str = " | ".join(
                f"{pct * 100:+.0f}%: {prob:.0%}" for pct, prob in scenario_probs
            )
            print(f"  Prob move by exp (IV): {probs_str}")
        if iv_rank is not None:
            if iv_rank >= 80:
                print("  -> High IV = overpriced options, IV crush risk on long")
            elif iv_rank < 30:
                print("  -> Low IV = favorable for buying options")
        print()

    # ============================================================
    # EVENT RISK
    # ============================================================
    events = ctx.get("events")
    if events is None:
        events = {}
    print("  EVENT RISK")
    print(sub)
    if not events:
        print("  N/A - no major catalysts in DTE window")
    else:
        for event_type, details in events.items():
            if not isinstance(details, dict):
                continue
            ev_date = details.get("date", "?")
            days_to = details.get("days_to", 0)
            day_label = "1 day away" if days_to == 1 else f"{days_to} days away"
            if event_type == "earnings":
                risk_note = "high vol risk, potential IV crush post-event"
            else:
                risk_note = "minor impact expected"
            print(f"  Upcoming {event_type} on {ev_date} ({day_label}) - {risk_note}")
    print()

    # ============================================================
    # TECHNICALS
    # ============================================================
    tech = ctx.get("technical", {})
    if isinstance(tech, dict) and (tech.get("daily") or tech.get("1h")):
        print("  TECHNICALS")
        print(sub)
        daily = tech.get("daily") or {}
        
        parts = []
        if daily.get("rsi") is not None:
            parts.append(f"RSI {daily['rsi']:.0f}")
        if daily.get("price_above_sma_20") is not None:
            parts.append(">20SMA" if daily["price_above_sma_20"] else "<20SMA")
        if daily.get("price_above_sma_50") is not None:
            parts.append(">50SMA" if daily["price_above_sma_50"] else "<50SMA")
        if daily.get("macd_bullish") is not None:
            parts.append("MACD ^" if daily["macd_bullish"] else "MACD v")
        if parts:
            print("  Daily: " + " | ".join(parts))
        print()

    # ============================================================
    # STRESS TEST
    # ============================================================
    stress = ctx.get("stress_test")
    if stress:
        print("  STRESS TEST (Instant Move, No Theta)")
        print(sub)
        spot = current_price or 0
        for pct, pl, pct_ror in stress:
            sign = "+" if pct >= 0 else ""
            dollar = f" (${spot * pct:+.2f})" if spot else ""
            print(f"  {sign}{pct * 100:.1f}%{dollar}: ${pl:+.0f} ({pct_ror:+.1f}% of risk)")
        print()

    # 1-DAY HOLD ESTIMATES (theta decay, no IV change)
    theta_1d = ctx.get("theta_stress_1d")
    theta_1d_premium = ctx.get("theta_stress_1d_premium")
    if theta_1d and theta_1d_premium is not None:
        print("  1-DAY HOLD ESTIMATES (incl. theta decay, no IV change)")
        print(sub)
        for label, est_prem, pct_chg in theta_1d:
            sign = "+" if pct_chg >= 0 else ""
            print(f"  {label} underlying: est. option ${est_prem:.2f} ({sign}{pct_chg:.1f}% from ${theta_1d_premium:.2f})")
        print()
    elif stress and ctx.get("greeks", {}).get("theta") is None:
        print("  Theta-adjusted est. N/A (Greeks unavailable)")
        print()

    # ============================================================
    # AI RECOMMENDATION - DETAILED
    # ============================================================
    rec = getattr(recommendation, "recommendation", trade_plan.go_no_go)
    emoji = "[PLAY]" if rec in ("PLAY", "GO") else "[DON'T PLAY]"
    
    print(sep)
    print(f"  {emoji}")
    print(sep)
    
    # WHY - Detailed reasoning
    reasoning = getattr(recommendation, "reasoning", "")
    if reasoning:
        print()
        print("  WHY - DETAILED REASONING")
        print(sub)
        for line in reasoning.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("-"):
                print(f"  {line}")
            elif line.startswith("-"):
                print(f"  {line}")
        print()
    
    # Risk Assessment
    risk_assess = getattr(recommendation, "risk_assessment", "")
    if risk_assess:
        print("  RISK ASSESSMENT")
        print(sub)
        for line in risk_assess.strip().split("\n"):
            line = line.strip()
            if line:
                print(f"  {line}")
        print()

    # Entry Criteria
    entry = getattr(recommendation, "entry_criteria", "")
    if entry:
        print("  ENTRY CRITERIA")
        print(sub)
        for line in entry.strip().split("\n"):
            line = line.strip()
            if line:
                print(f"  {line}")
        print()

    # Exit Strategy
    exit_strat = getattr(recommendation, "exit_strategy", "")
    if exit_strat:
        print("  EXIT STRATEGY")
        print(sub)
        for line in exit_strat.strip().split("\n"):
            line = line.strip()
            if line:
                print(f"  {line}")
        print()

    # Market Context
    market_ctx = getattr(recommendation, "market_context", "")
    if market_ctx:
        print("  MARKET CONTEXT")
        print(sub)
        for line in market_ctx.strip().split("\n"):
            line = line.strip()
            if line:
                print(f"  {line}")
        print()

    # ============================================================
    # RULE-BASED PLAN
    # ============================================================
    print("  RULE-BASED PLAN")
    print(sub)
    print(f"  Position: {trade_plan.position.contracts} contracts")
    print(f"  Risk: ${trade_plan.position.max_risk_dollars:.0f} ({trade_plan.position.risk_percentage:.1%})")
    r_mult = getattr(trade_plan, "target_1_r", None)
    if r_mult is not None:
        print(f"  R:R at T1: 1:{r_mult:.1f}")
    prem = getattr(trade, "premium", 0)
    sl = getattr(trade_plan, "stop_loss", 0)
    t1 = getattr(trade_plan, "target_1", 0)
    contracts = getattr(trade_plan.position, "contracts", 1)
    if prem and sl < prem:
        max_loss = (prem - sl) * contracts * 100
        print(f"  Max loss (at stop): ${max_loss:.0f}")
    if t1 and prem:
        max_gain_t1 = (t1 - prem) * contracts * 100
        print(f"  Max gain at T1: ${max_gain_t1:.0f}")
    print(f"  Entry: {trade_plan.entry_zone}")
    print(f"  Decision: {trade_plan.go_no_go}")
    if trade_plan.go_no_go_reasons:
        for r in trade_plan.go_no_go_reasons:
            print(f"    -> {r}")
    print()

    # ============================================================
    # STOP LOSS
    # ============================================================
    stop_text = getattr(recommendation, "stop_loss_suggestion", f"${trade_plan.stop_loss}")
    print("  STOP LOSS")
    print(sub)
    print(f"  {stop_text}")
    
    if ctx.get("atr_stop") is not None:
        mult = ctx.get("atr_sl_multiplier", 1.5)
        period = ctx.get("atr_period", 14)
        print(f"  ATR-based: ${ctx['atr_stop']:.2f} ({mult}x{period}d ATR)")
    print()

    # ============================================================
    # TAKE-PROFIT LEVELS
    # ============================================================
    levels = getattr(recommendation, "take_profit_levels", None)
    if levels:
        print("  TAKE-PROFIT LEVELS")
        print(sub)
        for level in levels:
            if level:
                print(f"  {level}")
    else:
        print("  TAKE-PROFIT LEVELS")
        print(sub)
        print(f"  T1: ${trade_plan.target_1} ({trade_plan.target_1_r}R)")
        if trade_plan.runner_contracts:
            print(f"  Runner: {trade_plan.runner_contracts} @ ${trade_plan.runner_target}")
    
    # Show technical reasoning if available
    if getattr(trade_plan, "technical_reasoning", ""):
        print()
        print("  TECHNICAL TARGET BASIS")
        print(sub)
        print(f"  {trade_plan.technical_reasoning}")
    
    print()

    # ============================================================
    # SUPPORT & RESISTANCE
    # ============================================================
    sr = getattr(recommendation, "support_resistance", [])
    if sr:
        print("  SUPPORT & RESISTANCE")
        print(sub)
        for s in sr:
            s = s.strip().lstrip("- ")
            if s:
                print(f"  {s}")
        print()

    # ============================================================
    # FIBONACCI LEVELS
    # ============================================================
    fib = market_context.get("fibonacci_analysis") if market_context else None
    if fib:
        print("  FIBONACCI LEVELS")
        print(sub)
        print(f"  Swing: ${fib['swing_low']:.2f} - ${fib['swing_high']:.2f} (${fib['swing_range']:.2f} range)")
        print(f"  Current: ${fib['current_price']:.2f} ({fib['position'].replace('_', ' ')})")

        # Retracements (support on pullbacks)
        print()
        print("  Retracements (pullback support):")
        for level in [0.236, 0.382, 0.5, 0.618, 0.786]:
            if level in fib['retracements']:
                price = fib['retracements'][level]
                marker = " <--" if abs(fib['current_price'] - price) < fib['swing_range'] * 0.02 else ""
                print(f"    {level:.3f}: ${price:.2f}{marker}")

        # Extensions (profit targets)
        print()
        print("  Extensions (profit targets):")
        for level in [1.272, 1.414, 1.618, 2.618]:
            if level in fib['extensions']:
                price = fib['extensions'][level]
                print(f"    {level:.3f}: ${price:.2f}")
        print()

    # ============================================================
    # RED FLAGS
    # ============================================================
    if analysis and analysis.red_flags:
        print("  RED FLAGS")
        print(sub)
        for f in analysis.red_flags:
            msg = f.get("message", str(f))
            sev = f.get("severity", "")
            print(f"  [!]  {msg}" + (f" [{sev}]" if sev else ""))
        print()

    # ============================================================
    # ODE RISKS
    # ============================================================
    ode_risks = getattr(recommendation, "ode_risks", [])
    if ode_risks or is_ode:
        print("  ODE / SAME-DAY RISKS")
        print(sub)
        for r in ode_risks:
            if r and r != "N/A":
                print(f"  -> {r}")
        if is_ode and not ode_risks:
            print("  -> Theta decay accelerates near close")
            print("  -> Gamma risk - sharp price moves")
            print("  -> Liquidity thins in final hours")
        print()

    # ============================================================
    # SETUP QUALITY
    # ============================================================
    if analysis:
        print("  SETUP QUALITY")
        print(sub)
        score = getattr(analysis, "setup_score", 0)
        qual = getattr(analysis, "setup_quality", "UNKNOWN").upper()
        conf = getattr(analysis, "confidence", 0)
        
        bar_length = 20
        filled = int((score / 100) * bar_length)
        bar = "#" * filled + "-" * (bar_length - filled)
        print(f"  {qual} | Score: {score}/100 | Confidence: {conf:.0%}")
        print(f"  [{bar}]")
        breakdown = getattr(analysis, "score_breakdown", None)
        if breakdown:
            b = breakdown
            parts = [f"{b['base']} base", f"+{b['rules']} rules", f"+{b['greens']} greens",
                     f"{b['reds']} reds", f"{b['pop']:+d} pop", f"+{b['liquidity']} liq",
                     f"+{b['technical']} tech"]
            if "events" in b:
                parts.append(f"{b['events']} events")
            if "theta_risk" in b and b["theta_risk"] != 0:
                parts.append(f"{b['theta_risk']} theta")
            print("  " + " ".join(parts) + f" = {score}")
        if analysis.green_flags:
            print("  [+] " + ", ".join(f.get("message", "") for f in analysis.green_flags if f.get("message")))
        if analysis.red_flags:
            print("  [!]  " + ", ".join(f.get("message", "") for f in analysis.red_flags if f.get("message")))
    print()
    print(sep)
    print()
