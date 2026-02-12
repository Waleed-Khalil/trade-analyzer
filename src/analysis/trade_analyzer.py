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
    recommendation_tier: str = ""  # STRONG PLAY, PLAY, CAUTIOUS PLAY, SKIP
    recommendation_guidance: str = ""  # Strategy guidance for the tier
    # LLM-enhanced fields
    enhanced_summary: Optional[str] = None  # LLM-generated natural language summary
    market_narrative: Optional[str] = None  # LLM explanation of market conditions
    trade_reasoning: Optional[str] = None  # LLM detailed reasoning
    recommendations: Optional[str] = None  # LLM specific actionable recommendations
    full_llm_analysis: Optional[str] = None  # Complete LLM response


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

        # Initialize LLM client for enhanced explanations
        self.llm_enabled = self.analysis_config.get('llm_enabled', True)
        if self.llm_enabled:
            try:
                from anthropic import Anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                base_url = os.getenv('ANTHROPIC_BASE_URL')

                if api_key:
                    if base_url:
                        self.llm = Anthropic(api_key=api_key, base_url=base_url)
                    else:
                        self.llm = Anthropic(api_key=api_key)

                    self.llm_model = self.analysis_config.get('model', 'claude-sonnet-4-5')
                else:
                    self.llm_enabled = False
                    print("Warning: ANTHROPIC_API_KEY not found, LLM features disabled")
            except ImportError:
                self.llm_enabled = False
                print("Warning: anthropic package not installed, LLM features disabled")
    
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
        
        # Run enhanced red flag checks with new indicators
        red_flags = self._check_red_flags(
            trade, current_price,
            market_context=market_context, option_live_price=option_live_price,
        )
        
        summary = self._generate_summary(trade, trade_plan)
        market_context_str = self._get_market_context(trade.ticker)
        green_flags = self._check_green_flags(trade, trade_plan, current_price, market_context)
        
        # Calculate setup quality based on flags
        setup_quality = self._assess_setup_quality(red_flags, green_flags)
        
        # Confidence based on rule compliance
        confidence = self._calculate_confidence(trade_plan, red_flags)
        
        # Weighted setup score 0-100
        setup_score, score_breakdown = self._calculate_setup_score(
            trade, trade_plan, red_flags, green_flags, market_context, current_price
        )

        # Generate LLM-enhanced analysis
        llm_analysis = self._generate_llm_enhanced_analysis(
            trade=trade,
            trade_plan=trade_plan,
            red_flags=red_flags,
            green_flags=green_flags,
            market_context=market_context,
            setup_score=setup_score,
            current_price=current_price
        )

        # Get recommendation tier based on score
        tier_label, tier_guidance = self._get_recommendation_tier(setup_score)

        return AnalysisResult(
            summary=summary,
            red_flags=red_flags,
            green_flags=green_flags,
            market_context=market_context_str,
            setup_quality=setup_quality,
            confidence=confidence,
            setup_score=setup_score,
            score_breakdown=score_breakdown,
            recommendation_tier=tier_label,
            recommendation_guidance=tier_guidance,
            # LLM-enhanced fields
            enhanced_summary=llm_analysis.get('enhanced_summary'),
            market_narrative=llm_analysis.get('market_narrative'),
            trade_reasoning=llm_analysis.get('trade_reasoning'),
            recommendations=llm_analysis.get('recommendations'),
            full_llm_analysis=llm_analysis.get('full_analysis'),
        )

    def _check_red_flags(
        self,
        trade,
        current_price: float = None,
        market_context: Optional[Dict[str, Any]] = None,
        option_live_price: float = None,
    ) -> List[Dict[str, str]]:
        """Check for risk indicators with ENHANCED checks."""
        flags = []
        ctx = market_context or {}
        opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()

        # ===== 1. COUNTER-TREND TRADE (existing) =====
        trend_analysis = ctx.get('trend_analysis', {})
        if trend_analysis:
            trend_direction = trend_analysis.get('direction', 'unknown')
            trend_cfg = self.analysis_config.get('trend', {})
            counter_trend_severity = trend_cfg.get('counter_trend_severity', 'high')

            if opt_type == 'CALL' and trend_direction == 'downtrend':
                flags.append({
                    "type": "counter_trend",
                    "severity": counter_trend_severity,
                    "message": f"Counter-trend trade: call entry in downtrend (strength: {trend_analysis.get('strength', 0)})"
                })
            elif opt_type == 'PUT' and trend_direction == 'uptrend':
                flags.append({
                    "type": "counter_trend",
                    "severity": counter_trend_severity,
                    "message": f"Counter-trend trade: put entry in uptrend (strength: {trend_analysis.get('strength', 0)})"
                })

        # ===== 2. NEW: MA ALIGNMENT CHECK =====
        # If price is BELOW all major MAs, short-term trend is BEARISH
        daily_tech = ctx.get('technical', {}).get('daily', {})
        if daily_tech:
            sma_20 = daily_tech.get('sma_20')
            sma_50 = daily_tech.get('sma_50')
            sma_200 = daily_tech.get('sma_200')
            
            if current_price and sma_20 and sma_50:
                mas_below = []
                if current_price < sma_20:
                    mas_below.append('SMA_20')
                if sma_50 and current_price < sma_50:
                    mas_below.append('SMA_50')
                if sma_200 and current_price < sma_200:
                    mas_below.append('SMA_200')
                
                if len(mas_below) >= 2:
                    severity = 'high' if len(mas_below) == 3 else 'medium'
                    flags.append({
                        "type": "ma_alignment",
                        "severity": severity,
                        "message": f"Price BELOW {'/'.join(mas_below)} - short-term BEARISH ({len(mas_below)}/3 MAs)"
                    })

        # ===== 3. NEW: MACD ZERO-LINE CHECK =====
        daily_tech = ctx.get('technical', {}).get('daily', {})
        if daily_tech:
            macd = daily_tech.get('macd')
            if macd is not None:
                if opt_type == 'CALL' and macd < 0:
                    flags.append({
                        "type": "macd_bearish",
                        "severity": "medium",
                        "message": f"MACD below zero ({macd:.3f}) - bearish momentum"
                    })
                elif opt_type == 'PUT' and macd > 0:
                    flags.append({
                        "type": "macd_bullish",
                        "severity": "medium", 
                        "message": f"MACD above zero ({macd:.3f}) - bullish momentum (counter for puts)"
                    })

        # ===== 4. NEW: SUPPORT/RESISTANCE FAILURE CHECK =====
        sr_analysis = ctx.get('sr_analysis', {})
        if sr_analysis:
            key_levels = sr_analysis.get('key_levels', {})
            support_levels = sr_analysis.get('support_zones', [])
            
            if opt_type == 'CALL':
                nearest_support = key_levels.get('nearest_support')
                # Check if support was recently broken
                if support_levels and nearest_support:
                    for zone in support_levels[:3]:  # Check recent zones
                        zone_price = zone.get('price')
                        zone_strength = zone.get('strength', 50)
                        if zone_price and current_price:
                            # If current price is well below a support zone, it was broken
                            if current_price < zone_price * 0.99:
                                flags.append({
                                    "type": "support_broken",
                                    "severity": "high",
                                    "message": f"Support zone at ${zone_price:.2f} (strength: {zone_strength}) was BROKEN - now resistance"
                                })

        # ===== 5. NEW: VOLUME DISTRIBUTION CHECK =====
        vol_trend = ctx.get('volume_trend', {})
        if vol_trend:
            trend = vol_trend.get('trend', '')
            strength = vol_trend.get('strength', '')
            decline_volume = vol_trend.get('decline_volume', 0)
            rise_volume = vol_trend.get('rise_volume', 0)
            
            # Check if volume is higher on declines (distribution)
            if decline_volume > 0 and rise_volume > 0:
                vol_ratio = decline_volume / rise_volume
                if vol_ratio > 1.2:  # 20% more volume on declines
                    flags.append({
                        "type": "distribution",
                        "severity": "medium",
                        "message": f"Higher volume on DECLINES ({vol_ratio:.1f}x) - distribution pattern"
                    })

        # ===== 6. NEW: MARKET CONTEXT CHECK =====
        market_ctx = ctx.get('market_context', {})
        if market_ctx:
            vix_change = market_ctx.get('vix_change_pct', 0)
            spy_trend = market_ctx.get('spy_trend', 'neutral')
            
            # VIX spiking during market decline = fear
            if vix_change > 5:
                flags.append({
                    "type": "market_fear",
                    "severity": "medium",
                    "message": f"VIX rising {vix_change:.1f}% - increasing market fear"
                })
            
            # If trading tech (QQQ), check if SPY is diverging
            if trade.ticker.upper() in ['QQQ', 'NVDA', 'AAPL', 'MSFT']:
                if spy_trend == 'bearish':
                    flags.append({
                        "type": "market_breadth",
                        "severity": "low",
                        "message": "SPY in downtrend - broad market weakness"
                    })

        # ===== EXISTING CHECKS =====
        
        # VWAP deviation
        vol_analysis = ctx.get('volume_analysis', {})
        if vol_analysis:
            vwap_check = vol_analysis.get('vwap_check', {})
            if vwap_check and vwap_check.get('signal') == 'mean_reversion_risk':
                flags.append({
                    "type": "vwap_deviation",
                    "severity": "medium",
                    "message": vwap_check.get('interpretation', 'Price far from VWAP - mean reversion risk')
                })

        # Volume divergence
        if vol_analysis:
            vol_conf = vol_analysis.get('volume_confirmation', {})
            if vol_conf and not vol_conf.get('confirmed') and vol_conf.get('strength') == 'weak':
                flags.append({
                    "type": "volume_divergence",
                    "severity": "medium",
                    "message": vol_conf.get('reasoning', 'Price move not confirmed by volume')
                })

        # Conflicting candlestick patterns
        patterns = ctx.get('candlestick_patterns', [])
        if patterns:
            for pattern in patterns:
                if opt_type == 'CALL' and pattern.get('direction') == 'bearish':
                    flags.append({
                        "type": "conflicting_pattern",
                        "severity": "medium",
                        "message": f"Bearish {pattern.get('pattern')} pattern conflicts with call entry"
                    })
                elif opt_type == 'PUT' and pattern.get('direction') == 'bullish':
                    flags.append({
                        "type": "conflicting_pattern",
                        "severity": "medium",
                        "message": f"Bullish {pattern.get('pattern')} pattern conflicts with put entry"
                    })

        return flags
    
    def _check_green_flags(self, trade, trade_plan, current_price: float = None,
                           market_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Check for positive indicators including ENHANCED checks."""
        flags = []
        ctx = market_context or {}

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

        # ===== ENHANCED: MA ALIGNMENT (bullish) =====
        opt_type = getattr(trade, 'option_type', 'CALL').upper()
        daily_tech = ctx.get('technical', {}).get('daily', {})
        if daily_tech and current_price:
            sma_20 = daily_tech.get('sma_20')
            sma_50 = daily_tech.get('sma_50')
            
            mas_above = []
            if sma_20 and current_price > sma_20:
                mas_above.append('SMA_20')
            if sma_50 and current_price > sma_50:
                mas_above.append('SMA_50')
            
            if len(mas_above) >= 2:
                flags.append({
                    "type": "ma_alignment_bullish",
                    "message": f"Price ABOVE {'/'.join(mas_above)} - short-term BULLISH ({len(mas_above)}/2 MAs)"
                })

        # ===== ENHANCED: MACD BULLISH =====
        if daily_tech:
            macd = daily_tech.get('macd')
            if macd is not None:
                if opt_type == 'CALL' and macd > 0:
                    flags.append({
                        "type": "macd_bullish",
                        "message": f"MACD above zero ({macd:.3f}) - bullish momentum"
                    })
                elif opt_type == 'PUT' and macd < 0:
                    flags.append({
                        "type": "macd_bearish_for_put",
                        "message": f"MACD below zero ({macd:.3f}) - bearish momentum (aligned with put)"
                    })

        # ===== ENHANCED: VOLUME CONFIRMATION =====
        vol_trend = ctx.get('volume_trend', {})
        if vol_trend:
            trend = vol_trend.get('trend', '')
            strength = vol_trend.get('strength', '')
            rise_volume = vol_trend.get('rise_volume', 0)
            decline_volume = vol_trend.get('decline_volume', 0)
            
            if rise_volume > decline_volume * 1.2:
                flags.append({
                    "type": "volume_accumulation",
                    "message": f"Higher volume on RISES ({(rise_volume/decline_volume):.1f}x) - accumulation pattern"
                })

        # Price action: at strong support/resistance
        sr_analysis = ctx.get('sr_analysis', {})
        if sr_analysis:
            if opt_type == 'CALL':
                nearest_support = sr_analysis.get('key_levels', {}).get('nearest_support')
                if nearest_support and current_price:
                    distance_pct = abs(current_price - nearest_support) / current_price * 100
                    if distance_pct < 1.0:
                        flags.append({
                            "type": "price_action_support",
                            "message": f"Price at strong support ${nearest_support:.2f} - bounce opportunity"
                        })
            elif opt_type == 'PUT':
                nearest_resistance = sr_analysis.get('key_levels', {}).get('nearest_resistance')
                if nearest_resistance and current_price:
                    distance_pct = abs(current_price - nearest_resistance) / current_price * 100
                    if distance_pct < 1.0:
                        flags.append({
                            "type": "price_action_resistance",
                            "message": f"Price at strong resistance ${nearest_resistance:.2f} - reversal setup"
                        })

        # Bullish patterns aligned
        patterns = ctx.get('candlestick_patterns', [])
        if patterns:
            for pattern in patterns:
                if opt_type == 'CALL' and pattern.get('direction') == 'bullish':
                    flags.append({
                        "type": "bullish_pattern",
                        "message": f"Bullish {pattern.get('pattern')} pattern detected (strength: {pattern.get('strength', 0)}/100)"
                    })
                elif opt_type == 'PUT' and pattern.get('direction') == 'bearish':
                    flags.append({
                        "type": "bearish_pattern",
                        "message": f"Bearish {pattern.get('pattern')} pattern detected (strength: {pattern.get('strength', 0)}/100)"
                    })

        # Aligned with trend
        trend_analysis = ctx.get('trend_analysis', {})
        if trend_analysis:
            direction = trend_analysis.get('direction', 'unknown')
            if opt_type == 'CALL' and direction == 'uptrend':
                flags.append({
                    "type": "trend_aligned",
                    "message": f"Aligned with uptrend (strength: {trend_analysis.get('strength', 0)}/100)"
                })
            elif opt_type == 'PUT' and direction == 'downtrend':
                flags.append({
                    "type": "trend_aligned",
                    "message": f"Aligned with downtrend (strength: {trend_analysis.get('strength', 0)}/100)"
                })

        # Multi-timeframe alignment
        mtf = ctx.get('multi_timeframe_alignment', {})
        if mtf and mtf.get('aligned'):
            flags.append({
                "type": "mtf_alignment",
                "message": f"Multi-timeframe alignment: {mtf.get('timeframes_checked', 3)}/3 timeframes aligned"
            })

        return flags

    def _generate_summary(self, trade, trade_plan):
        """Generate brief summary."""
        opt_type = getattr(trade, 'option_type', 'CALL')
        direction = 'bullish' if opt_type.upper() == 'CALL' else 'bearish'
        return f"{direction.upper()} {trade.ticker} {trade.strike} {opt_type} @ ${trade.premium}. {trade_plan.go_no_go} - Risk ${trade_plan.position.max_risk_dollars:.0f}"

    def _get_market_context(self, ticker: str) -> str:
        """Get general market context."""
        return f"Analysing {ticker} - See detailed analysis for market context"

    def _assess_setup_quality(self, red_flags: List, green_flags: List) -> str:
        """Assess overall setup quality with ENHANCED logic."""
        high_severity_red = [f for f in red_flags if f.get('severity') == 'high']
        critical_red = [f for f in red_flags if f.get('type') in ['support_broken', 'distribution', 'market_fear']]
        
        # Critical issues trump everything
        if critical_red:
            return "low"
        
        # Count serious issues
        serious_issues = len([f for f in red_flags if f.get('severity') in ['high', 'medium']])
        
        if high_severity_red:
            return "low"
        elif serious_issues > 2:
            return "medium"
        elif len(green_flags) >= 3:
            return "high"
        elif len(green_flags) >= 2:
            return "medium"
        else:
            return "medium"
    
    def _calculate_confidence(self, trade_plan, red_flags: List) -> float:
        """Calculate confidence score."""
        base = 0.9
        
        for flag in red_flags:
            severity = flag.get('severity', 'low')
            if severity == 'high':
                base -= 0.3
            elif severity == 'medium':
                base -= 0.15
        
        if trade_plan.go_no_go == "GO" and len(red_flags) == 0:
            base = min(base + 0.1, 0.95)
        
        return max(0.0, min(base, 1.0))

    def _get_recommendation_tier(self, score: int) -> tuple:
        """Return recommendation tier based on score."""
        scoring_cfg = self.analysis_config.get('scoring', {})
        tiers = scoring_cfg.get('recommendation_tiers', {})

        strong_min = tiers.get('strong_play_min', 85)
        play_min = tiers.get('play_min', 70)
        cautious_min = tiers.get('cautious_play_min', 55)

        if score >= strong_min:
            return (
                tiers.get('strong_play_label', 'STRONG PLAY'),
                tiers.get('strong_play_guidance', 'Full size. Let winners run past +20%. Trail with breakeven stop after T1.'),
            )
        elif score >= play_min:
            return (
                tiers.get('play_label', 'PLAY'),
                tiers.get('play_guidance', 'Normal size. Take 50% at +20%, trail rest with breakeven stop.'),
            )
        elif score >= cautious_min:
            return (
                tiers.get('cautious_play_label', 'CAUTIOUS PLAY'),
                tiers.get('cautious_play_guidance', 'Reduced size. Tight stop. Take +20% on full position.'),
            )
        else:
            return (
                tiers.get('skip_label', 'SKIP'),
                tiers.get('skip_guidance', 'Setup quality too low. Wait for better entry.'),
            )

    def _calculate_setup_score(
        self,
        trade,
        trade_plan,
        red_flags: List,
        green_flags: List,
        market_context: Optional[Dict[str, Any]] = None,
        current_price: float = None,
    ) -> tuple:
        """Calculate weighted setup score with ENHANCED penalties."""
        ctx = market_context or {}
        scoring_cfg = self.analysis_config.get('scoring', {})

        base_start = scoring_cfg.get('base_score', 55)
        high_penalty = scoring_cfg.get('high_severity_penalty', 10)
        base = base_start

        # GO bonus
        if trade_plan.go_no_go == "GO":
            base += 10

        # Green flags
        green_pts = scoring_cfg.get('green_flag_points', 4)
        green_max = scoring_cfg.get('green_flag_max', 20)
        greens = min(len(green_flags) * green_pts, green_max)
        base += greens

        # Red flags with enhanced penalties
        for f in red_flags:
            severity = f.get("severity", "low")
            flag_type = f.get("type", "")
            
            if severity == "high":
                base -= high_penalty
            elif severity == "medium":
                # Enhanced penalties for new checks
                if flag_type in ['support_broken', 'distribution', 'ma_alignment']:
                    base -= 8  # Higher penalty for these
                else:
                    base -= 5

        # PoP adjustment
        pop = ctx.get("probability_of_profit")
        if pop is not None and pop >= 0.60:
            base += 5
        elif pop is not None and pop < 0.50:
            base -= 5

        # Technical confluence
        technical = 0
        tech_cfg = self.analysis_config.get("technical", {})
        if tech_cfg.get("enabled", False):
            daily = (ctx.get("technical", {}) or {}).get("daily", {})
            confirming = 0
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
            
            if daily:
                if opt_type == "CALL":
                    if daily.get("price_above_sma_20"):
                        confirming += 1
                    if daily.get("macd") and daily.get("macd") > 0:
                        confirming += 1
                elif opt_type == "PUT":
                    if not daily.get("price_above_sma_20", True):
                        confirming += 1
                    if daily.get("macd") and daily.get("macd") < 0:
                        confirming += 1
            
            if confirming >= 2:
                base += 15

        # Enhanced checks bonuses
        for g in green_flags:
            if g.get('type') in ['ma_alignment_bullish', 'macd_bullish', 'volume_accumulation']:
                base += 5  # Bonus for bullish MA/MACD/volume alignment

        score = max(0, min(100, int(base)))
        breakdown = {
            "base": base_start,
            "greens": greens,
            "red_penalty": base_start - base - greens,
            "technical_bonus": technical,
        }
        return score, breakdown

    def _generate_llm_enhanced_analysis(self, **kwargs):
        """Generate LLM-enhanced analysis (placeholder)."""
        return {
            'enhanced_summary': 'See detailed flag analysis above.',
            'market_narrative': 'Market context from enhanced checks.',
            'trade_reasoning': 'Trade reasoning based on comprehensive analysis.',
            'recommendations': 'See red/green flags for actionable insights.',
            'full_analysis': str(kwargs),
        }


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
        print("ENHANCED AI ANALYSIS")
        print("="*50)
        print(f"Summary: {analysis.summary}")
        print(f"\nSetup Quality: {analysis.setup_quality.upper()}")
        print(f"Confidence: {analysis.confidence:.0%}")
        print(f"Score: {analysis.setup_score}/100")
        
        print(f"\nRed Flags ({len(analysis.red_flags)}):")
        for f in analysis.red_flags:
            print(f"  [{f['severity'].upper()}] {f['message']}")
        
        print(f"\nGreen Flags ({len(analysis.green_flags)}):")
        for f in analysis.green_flags:
            print(f"  ✓ {f['message']}")
