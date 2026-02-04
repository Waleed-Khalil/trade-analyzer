"""
Analysis Module
AI-powered trade analysis, explanations, and red-flag detection
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import yaml
import os


@dataclass
class AnalysisResult:
    """AI analysis output"""
    summary: str
    red_flags: List[Dict[str, str]]
    green_flags: List[Dict[str, str]]
    market_context: str
    setup_quality: str  # "high", "medium", "low"
    confidence: float  # 0.0 to 1.0
    setup_score: int = 0  # 0-100 weighted score; >75 suggests PLAY
    score_breakdown: Optional[Dict[str, Any]] = None  # optional component breakdown for transparency


class TradeAnalyzer:
    """
    AI-powered trade analysis module.
    Provides context, explanations, and risk flag detection.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.analysis_config = self.config.get('analysis', {})
        self.enabled = self.analysis_config.get('enabled', True)
        
        # Would initialize LLM client here
        # self.llm = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    def analyze(
        self,
        trade,
        trade_plan,
        current_price: float = None,
        market_context: Optional[Dict[str, Any]] = None,
        option_live_price: float = None,
    ) -> AnalysisResult:
        """
        Perform full AI analysis of a trade.
        """
        if not self.enabled:
            return AnalysisResult(
                summary="Analysis disabled",
                red_flags=[],
                green_flags=[],
                market_context="",
                setup_quality="unknown",
                confidence=0.0,
                setup_score=0,
            )
        market_context = market_context or {}
        # Run red flag checks (includes momentum and stale-premium when context available)
        red_flags = self._check_red_flags(
            trade, current_price,
            market_context=market_context, option_live_price=option_live_price,
        )
        summary = self._generate_summary(trade, trade_plan)
        market_context_str = self._get_market_context(trade.ticker)
        green_flags = self._check_green_flags(trade, trade_plan, current_price)
        
        # Calculate setup quality based on flags
        setup_quality = self._assess_setup_quality(red_flags, green_flags)
        
        # Confidence based on rule compliance
        confidence = self._calculate_confidence(trade_plan, red_flags)
        
        # Weighted setup score 0-100 (40% rules/technicals, 30% Greeks, 20% sentiment proxy, 10% liquidity)
        setup_score, score_breakdown = self._calculate_setup_score(
            trade, trade_plan, red_flags, green_flags, market_context
        )
        
        return AnalysisResult(
            summary=summary,
            red_flags=red_flags,
            green_flags=green_flags,
            market_context=market_context_str,
            setup_quality=setup_quality,
            confidence=confidence,
            setup_score=setup_score,
            score_breakdown=score_breakdown,
        )

    def _check_red_flags(
        self,
        trade,
        current_price: float = None,
        market_context: Optional[Dict[str, Any]] = None,
        option_live_price: float = None,
    ) -> List[Dict[str, str]]:
        """Check for known risk factors. Uses market_context for momentum and stale-premium."""
        flags = []
        checks = self.analysis_config.get('red_flag_checks', {})
        ctx = market_context or {}
        
        # IV Rank: high rank => overpriced, caution on longs (potential crush)
        iv_rank = ctx.get("iv_rank")
        iv_rank_cfg = self.analysis_config.get("iv_rank", {})
        rank_high_threshold = iv_rank_cfg.get("rank_high_threshold", 80)
        if iv_rank is not None and iv_rank >= rank_high_threshold:
            msg = checks.get("iv_rank_above_70") or "High IV rank – overpriced; caution on longs, potential crush."
            if "{rank}" in msg:
                msg = msg.replace("{rank}", f"{iv_rank:.0f}")
            elif "iv rank" in msg.lower() and "%" not in msg:
                msg = f"High IV rank ({iv_rank:.0f}%) – overpriced; caution on longs, potential crush."
            flags.append({
                "type": "iv_rank",
                "severity": "medium",
                "message": msg,
            })

        # Days to expiration check
        if trade.expiration:
            # Parse and check
            pass
        
        # Strike distance check
        if current_price and trade.strike > 0:
            if trade.option_type == "CALL":
                distance_pct = (trade.strike - current_price) / current_price
            else:
                distance_pct = (current_price - trade.strike) / current_price
                
            if distance_pct > 0.10:  # > 10% OTM
                flags.append({
                    "type": "strike_distance",
                    "severity": "medium",
                    "message": f"Strike is {distance_pct:.1%} OTM - low delta"
                })
        
        # Premium too low
        min_prem = self.config.get('sizing', {}).get('min_premium_to_consider', 0.50)
        if trade.premium < min_prem:
            flags.append({
                "type": "premium",
                "severity": "medium",
                "message": f"Premium ${trade.premium} too low - poor risk/reward"
            })

        # Underlying down >5% in 5d (momentum)
        five_d = ctx.get("five_d_return_pct")
        if five_d is not None and five_d < -5:
            flags.append({
                "type": "momentum",
                "severity": "medium",
                "message": f"Underlying down {abs(five_d):.1f}% in 5d - weak momentum"
            })

        # Pasted premium vs live differs (stale alert): flag at 15%, high severity if >25%
        diff_pct = ctx.get("premium_diff_pct")
        if diff_pct is not None and abs(diff_pct) > 15:
            direction = "higher" if diff_pct > 0 else "lower"
            severity = "high" if abs(diff_pct) > 25 else "medium"
            flags.append({
                "type": "stale_premium",
                "severity": severity,
                "message": f"Live option price is {abs(diff_pct):.0f}% {direction} than pasted - re-verify live quotes"
            })

        # DTE < 1 (same-day / very short) - HIGH RISK
        dte = ctx.get("days_to_expiration")
        if dte is not None and dte < 1:
            flags.append({
                "type": "dte",
                "severity": "high",
                "message": "DTE < 1 - HIGH RISK; consider further OTM for leverage or longer DTE"
            })

        # Event risk: earnings (high) or ex-dividend (medium) within 2 days
        events = ctx.get("events") or {}
        for event_type, details in events.items():
            if not isinstance(details, dict) or details.get("days_to", 99) > 2:
                continue
            days_to = details.get("days_to", 0)
            day_word = "day" if days_to == 1 else "days"
            if event_type == "earnings":
                flags.append({
                    "type": "event_risk",
                    "severity": "high",
                    "message": f"High event risk: earnings in {days_to} {day_word} - expect vol spike, IV crush post-event",
                })
            else:
                flags.append({
                    "type": "event_risk",
                    "severity": "medium",
                    "message": f"Ex-dividend in {days_to} {day_word} - minor downside pressure (price drop ~dividend)",
                })

        # Greeks & probabilities (config: analysis.greeks)
        greeks_cfg = self.analysis_config.get("greeks", {})
        pop_min = greeks_cfg.get("pop_min", 0.50)
        pop = ctx.get("probability_of_profit")
        if pop is not None and pop < pop_min:
            flags.append({
                "type": "probability_of_profit",
                "severity": "medium",
                "message": f"Probability of Profit {pop:.0%} below {pop_min:.0%} - consider HOLD/AVOID"
            })
        theta = (ctx.get("greeks") or {}).get("theta")
        theta_thresh = greeks_cfg.get("theta_high_decay", -0.05)
        if theta is not None and theta < theta_thresh:
            flags.append({
                "type": "theta_decay",
                "severity": "medium",
                "message": f"Theta {theta:.4f} - premium erodes quickly (high time decay)"
            })
        # High theta risk for short DTE: est. % decay if flat tomorrow
        dte = ctx.get("days_to_expiration")
        premium = getattr(trade, "premium", None) or 0.01
        if theta is not None and premium > 0 and dte is not None and dte <= 3:
            decay_pct = abs(theta) / premium * 100
            if decay_pct > 20:
                flags.append({
                    "type": "theta_risk",
                    "severity": "medium",
                    "message": f"High theta risk: est. -{decay_pct:.0f}% if flat tomorrow",
                })
        vega = (ctx.get("greeks") or {}).get("vega")
        vega_thresh = greeks_cfg.get("vega_high", 0.20)
        if vega is not None and vega > vega_thresh:
            flags.append({
                "type": "vega",
                "severity": "medium",
                "message": f"Vega {vega:.2f} - highly sensitive to IV changes"
            })
        vol_min = greeks_cfg.get("option_volume_min", 500)
        oi_min = greeks_cfg.get("open_interest_min", 1000)
        opt_vol = ctx.get("option_volume")
        if opt_vol is not None and opt_vol < vol_min:
            flags.append({
                "type": "liquidity",
                "severity": "medium",
                "message": f"Option volume {opt_vol} below {vol_min} - liquidity/slippage risk"
            })
        oi = ctx.get("open_interest")
        if oi is not None and oi < oi_min:
            flags.append({
                "type": "liquidity",
                "severity": "medium",
                "message": f"Open interest {oi} below {oi_min} - liquidity risk"
            })

        # Technical: RSI overbought (calls) / oversold (puts), MACD bearish for calls
        tech_cfg = self.analysis_config.get("technical", {})
        if tech_cfg.get("enabled", False):
            tech = ctx.get("technical", {})
            daily = (tech.get("daily") or {}) if isinstance(tech, dict) else {}
            rsi = daily.get("rsi")
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
            rsi_ob = tech_cfg.get("rsi_overbought", 70)
            rsi_os = tech_cfg.get("rsi_oversold", 30)
            if rsi is not None:
                if opt_type == "CALL" and rsi >= rsi_ob:
                    flags.append({
                        "type": "rsi_overbought",
                        "severity": "medium",
                        "message": f"Daily RSI {rsi:.0f} (overbought >= {rsi_ob}) – caution on new longs",
                    })
                elif opt_type == "PUT" and rsi <= rsi_os:
                    flags.append({
                        "type": "rsi_oversold",
                        "severity": "medium",
                        "message": f"Daily RSI {rsi:.0f} (oversold <= {rsi_os}) – caution on new puts",
                    })
            macd_bullish = daily.get("macd_bullish")
            if opt_type == "CALL" and macd_bullish is False and daily.get("macd_histogram") is not None:
                flags.append({
                    "type": "macd_bearish",
                    "severity": "low",
                    "message": "Daily MACD bearish – momentum not confirming",
                })

        # Stress test: -1% move causes loss > threshold % of risk
        stress_results = ctx.get("stress_test")
        risk_dollars = ctx.get("stress_test_risk_dollars")
        stress_cfg = self.analysis_config.get("stress", {})
        thresh_pct = stress_cfg.get("downside_1pct_loss_threshold_pct", 50)
        if stress_results is not None and risk_dollars and risk_dollars > 0:
            for pct, pl, _ in stress_results:
                if abs(pct - (-0.01)) < 0.001 and pl < 0:
                    loss_pct_risk = abs(pl) / risk_dollars * 100
                    if loss_pct_risk >= thresh_pct:
                        flags.append({
                            "type": "stress_test",
                            "severity": "medium",
                            "message": f"Vulnerable to small downside: -1% underlying move => est. loss ${abs(pl):.0f} ({loss_pct_risk:.0f}% of risk)"
                        })
                    break

        return flags
    
    def _check_green_flags(self, trade, trade_plan, current_price: float = None) -> List[Dict[str, str]]:
        """Check for positive indicators"""
        flags = []
        
        # Reasonable premium
        if trade.premium >= 1.0:
            flags.append({
                "type": "premium",
                "message": "Healthy premium for position sizing"
            })
        
        # Good risk/reward from plan
        if trade_plan.target_1_r >= 2.0:
            flags.append({
                "type": "risk_reward",
                "message": f"Target at {trade_plan.target_1_r}R - favorable risk/reward"
            })
        
        # Within risk parameters
        if trade_plan.go_no_go == "GO":
            flags.append({
                "type": "rules_compliance",
                "message": "Passes all rule-based checks"
            })
        
        return flags
    
    def _generate_summary(self, trade, trade_plan) -> str:
        """Generate human-readable trade summary"""
        return (
            f"{trade.option_type} {trade.ticker} ${trade.strike} @ ${trade.premium:.2f}. "
            f"Plan: {trade_plan.position.contracts} contracts, stop ${trade_plan.stop_loss}, "
            f"target ${trade_plan.target_1} ({trade_plan.target_1_r}R), "
            f"runner {trade_plan.runner_contracts} @ ${trade_plan.runner_target}."
        )
    
    def _get_market_context(self, ticker: str) -> str:
        """Get current market context for ticker"""
        # Would fetch real data in production
        return f"No current market data for {ticker}"
    
    def _assess_setup_quality(self, red_flags: List, green_flags: List) -> str:
        """Assess overall setup quality"""
        high_severity_red = [f for f in red_flags if f.get('severity') == 'high']
        
        if high_severity_red:
            return "low"
        elif len(red_flags) > 2:
            return "medium"
        elif len(green_flags) >= 2:
            return "high"
        else:
            return "medium"
    
    def _calculate_confidence(self, trade_plan, red_flags: List) -> float:
        """Calculate confidence score"""
        base = 0.9
        
        # Reduce for red flags
        for flag in red_flags:
            severity = flag.get('severity', 'low')
            if severity == 'high':
                base -= 0.3
            elif severity == 'medium':
                base -= 0.15
        
        # Boost for clean trades
        if trade_plan.go_no_go == "GO" and len(red_flags) == 0:
            base = min(base + 0.1, 0.95)
        
        return max(0.0, min(base, 1.0))

    def _calculate_setup_score(
        self,
        trade,
        trade_plan,
        red_flags: List,
        green_flags: List,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """
        Weighted setup score 0-100. Threshold >75 for PLAY.
        Returns (score, breakdown_dict) for transparency.
        """
        ctx = market_context or {}
        base = 70
        rules = 0
        if trade_plan.go_no_go == "GO":
            rules = 10
            base += rules
        greens = min(len(green_flags) * 3, 15)
        base += greens
        reds = 0
        for f in red_flags:
            if f.get("severity") == "high":
                reds -= 12
                base -= 12
            elif f.get("severity") == "medium":
                reds -= 6
                base -= 6
        pop_adj = 0
        pop = ctx.get("probability_of_profit")
        if pop is not None and pop >= 0.60:
            pop_adj = 5
            base += 5
        elif pop is not None and pop < 0.50:
            pop_adj = -5
            base -= 5
        liquidity = 0
        greeks_cfg = self.analysis_config.get("greeks", {})
        oi_min = greeks_cfg.get("open_interest_min", 1000)
        vol_min = greeks_cfg.get("option_volume_min", 500)
        if ctx.get("open_interest", 0) >= oi_min and ctx.get("option_volume", 0) >= vol_min:
            liquidity = 3
            base += 3
        technical = 0
        tech_cfg = self.analysis_config.get("technical", {})
        if tech_cfg.get("enabled", False):
            tech = ctx.get("technical", {})
            daily = (tech.get("daily") or {}) if isinstance(tech, dict) else {}
            bonus = tech_cfg.get("confluence_score_bonus", 15)
            rsi = daily.get("rsi")
            price_above_sma20 = daily.get("price_above_sma_20")
            macd_bullish = daily.get("macd_bullish")
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
            rsi_min_bull = tech_cfg.get("rsi_min_bullish", 50)
            rsi_max_bear = tech_cfg.get("rsi_max_bearish", 50)
            if opt_type == "CALL" and rsi is not None and price_above_sma20 and (macd_bullish is True or macd_bullish is None):
                if rsi >= rsi_min_bull:
                    technical = bonus
                    base += bonus
            elif opt_type == "PUT" and rsi is not None and price_above_sma20 is False and (macd_bullish is False or macd_bullish is None):
                if rsi <= rsi_max_bear:
                    technical = bonus
                    base += bonus
        events_adj = 0
        events_dict = ctx.get("events") or {}
        for etype, details in events_dict.items():
            if not isinstance(details, dict) or details.get("days_to", 99) > 2:
                continue
            if etype == "earnings":
                events_adj -= 10
                base -= 10
            else:
                events_adj -= 5
                base -= 5
        theta_risk_adj = 0
        dte = ctx.get("days_to_expiration")
        theta = (ctx.get("greeks") or {}).get("theta")
        prem = getattr(trade, "premium", None) or 0.01
        if dte is not None and dte <= 2 and theta is not None and prem > 0:
            if abs(theta) / prem >= 0.20:
                theta_risk_adj = -6
                base -= 6
        score = max(0, min(100, int(base)))
        breakdown = {
            "base": 70,
            "rules": rules,
            "greens": greens,
            "reds": reds,
            "pop": pop_adj,
            "liquidity": liquidity,
            "technical": technical,
            "events": events_adj,
            "theta_risk": theta_risk_adj,
        }
        return score, breakdown


# CLI test
if __name__ == "__main__":
    from parser.trade_parser import TradeParser
    from risk_engine import RiskEngine
    
    parser = TradeParser()
    engine = RiskEngine()
    analyzer = TradeAnalyzer()
    
    trade = parser.parse("BUY AAPL 01/31 215 CALL @ 3.50")
    if trade:
        plan = engine.create_trade_plan(trade, current_price=217.50)
        analysis = analyzer.analyze(trade, plan, current_price=217.50)
        
        print("="*50)
        print("AI ANALYSIS")
        print("="*50)
        print(f"Summary: {analysis.summary}")
        print(f"\nSetup Quality: {analysis.setup_quality.upper()}")
        print(f"Confidence: {analysis.confidence:.0%}")
        
        print(f"\nRed Flags ({len(analysis.red_flags)}):")
        for f in analysis.red_flags:
            print(f"  [{f['severity'].upper()}] {f['message']}")
        
        print(f"\nGreen Flags ({len(analysis.green_flags)}):")
        for f in analysis.green_flags:
            print(f"  ✓ {f['message']}")
