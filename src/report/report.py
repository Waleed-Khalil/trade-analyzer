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
        line = f"  Option (live): ${option_live_price:.2f} (Polygon)"
        if pasted:
            line += f" | Pasted: ${pasted:.2f}"
        if diff is not None:
            line += f" | Diff: {diff:+.0f}%"
        print(line)
    else:
        print("  Option: pasted value only")
    
    if ctx.get("moneyness_label"):
        print(f"  Strike: {ctx['moneyness_label']}")
    
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
            parts.append(f"Δ {g['delta']:.2f}")
        if g.get("gamma") is not None:
            parts.append(f"Γ {g['gamma']:.4f}")
        if g.get("theta") is not None:
            parts.append(f"Θ {g['theta']:.4f}")
        if g.get("vega") is not None:
            parts.append(f"V {g['vega']:.2f}")
        if iv is not None:
            iv_pct = iv * 100 if iv <= 2 else iv
            parts.append(f"IV {iv_pct:.1f}%")
        if parts:
            print("  " + " | ".join(parts))
        
        if pop is not None:
            flag = " ⚠️ <50%" if pop < 0.50 else ""
            print(f"  PoP: {pop:.0%}{flag}")
        
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
        
        if iv_rank is not None:
            if iv_rank >= 80:
                print("  → High IV = overpriced options, IV crush risk on long")
            elif iv_rank < 30:
                print("  → Low IV = favorable for buying options")
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
            parts.append("MACD ▲" if daily["macd_bullish"] else "MACD ▼")
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

    # ============================================================
    # AI RECOMMENDATION - DETAILED
    # ============================================================
    rec = getattr(recommendation, "recommendation", trade_plan.go_no_go)
    emoji = "✅ PLAY" if rec in ("PLAY", "GO") else "❌ DON'T PLAY"
    
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
            if line.startswith("-"):
                print(f"  {line}")
        print()
    
    # Entry Criteria
    entry = getattr(recommendation, "entry_criteria", "")
    if entry:
        print("  ENTRY CRITERIA")
        print(sub)
        for line in entry.strip().split("\n"):
            line = line.strip()
            if line.startswith("-"):
                print(f"  {line}")
        print()
    
    # Exit Strategy
    exit_strat = getattr(recommendation, "exit_strategy", "")
    if exit_strat:
        print("  EXIT STRATEGY")
        print(sub)
        for line in exit_strat.strip().split("\n"):
            line = line.strip()
            if line.startswith("-"):
                print(f"  {line}")
        print()
    
    # Market Context
    market_ctx = getattr(recommendation, "market_context", "")
    if market_ctx:
        print("  MARKET CONTEXT")
        print(sub)
        for line in market_ctx.strip().split("\n"):
            line = line.strip()
            if line.startswith("-"):
                print(f"  {line}")
        print()

    # ============================================================
    # RULE-BASED PLAN
    # ============================================================
    print("  RULE-BASED PLAN")
    print(sub)
    print(f"  Position: {trade_plan.position.contracts} contracts")
    print(f"  Risk: ${trade_plan.position.max_risk_dollars:.0f} ({trade_plan.position.risk_percentage:.1%})")
    print(f"  Entry: {trade_plan.entry_zone}")
    print(f"  Decision: {trade_plan.go_no_go}")
    if trade_plan.go_no_go_reasons:
        for r in trade_plan.go_no_go_reasons:
            print(f"    → {r}")
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
    # RED FLAGS
    # ============================================================
    if analysis and analysis.red_flags:
        print("  RED FLAGS")
        print(sub)
        for f in analysis.red_flags:
            msg = f.get("message", str(f))
            sev = f.get("severity", "")
            print(f"  ⚠️  {msg}" + (f" [{sev}]" if sev else ""))
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
                print(f"  → {r}")
        if is_ode and not ode_risks:
            print("  → Theta decay accelerates near close")
            print("  → Gamma risk - sharp price moves")
            print("  → Liquidity thins in final hours")
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
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"  {qual} | Score: {score}/100 | Confidence: {conf:.0%}")
        print(f"  [{bar}]")
        
        if analysis.green_flags:
            print("  ✅ " + ", ".join(f.get("message", "") for f in analysis.green_flags if f.get("message")))
        if analysis.red_flags:
            print("  ⚠️  " + ", ".join(f.get("message", "") for f in analysis.red_flags if f.get("message")))
    print()
    print(sep)
    print()
