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
        # Run red flag checks (includes momentum and stale-premium when context available)
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
        
        # Weighted setup score 0-100 (40% rules/technicals, 30% Greeks, 20% sentiment proxy, 10% liquidity)
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
        # Wide bid/ask spread (slippage risk)
        oq = ctx.get("option_quote") or {}
        spread_pct = oq.get("spread_pct_of_mid")
        spread_pct_max = greeks_cfg.get("quote_spread_pct_max", 15)
        if spread_pct is not None and spread_pct > spread_pct_max:
            flags.append({
                "type": "wide_spread",
                "severity": "high" if spread_pct > 25 else "medium",
                "message": f"Wide bid/ask spread ({spread_pct:.0f}% of mid) - execution/slippage risk"
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

        # Counter-trend trade check
        trend_analysis = ctx.get('trend_analysis', {})
        if trend_analysis:
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
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

        # VWAP deviation check
        vol_analysis = ctx.get('volume_analysis', {})
        if vol_analysis:
            vwap_check = vol_analysis.get('vwap_check', {})
            if vwap_check and vwap_check.get('signal') == 'mean_reversion_risk':
                flags.append({
                    "type": "vwap_deviation",
                    "severity": "medium",
                    "message": vwap_check.get('interpretation', 'Price far from VWAP - mean reversion risk')
                })

        # Volume divergence (strong move without volume)
        if vol_analysis:
            vol_conf = vol_analysis.get('volume_confirmation', {})
            if vol_conf and not vol_conf.get('confirmed') and vol_conf.get('strength') == 'weak':
                flags.append({
                    "type": "volume_divergence",
                    "severity": "medium",
                    "message": vol_conf.get('reasoning', 'Price move not confirmed by volume')
                })

        # Bearish patterns (for calls) or Bullish patterns (for puts)
        patterns = ctx.get('candlestick_patterns', [])
        if patterns:
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
            for pattern in patterns:
                # Conflicting pattern
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
        """Check for positive indicators including price action, volume, patterns, trend"""
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

        # Price action: at strong support/resistance
        sr_analysis = ctx.get('sr_analysis', {})
        if sr_analysis:
            opt_type = getattr(trade, 'option_type', 'CALL').upper()
            if opt_type == 'CALL':
                # Check if at support
                nearest_support = sr_analysis.get('key_levels', {}).get('nearest_support')
                if nearest_support and current_price:
                    distance_pct = abs(current_price - nearest_support) / current_price * 100
                    if distance_pct < 1.0:  # Within 1%
                        flags.append({
                            "type": "price_action",
                            "message": f"Price at strong support ${nearest_support:.2f} - bounce opportunity"
                        })
            elif opt_type == 'PUT':
                # Check if at resistance
                nearest_resistance = sr_analysis.get('key_levels', {}).get('nearest_resistance')
                if nearest_resistance and current_price:
                    distance_pct = abs(current_price - nearest_resistance) / current_price * 100
                    if distance_pct < 1.0:
                        flags.append({
                            "type": "price_action",
                            "message": f"Price at strong resistance ${nearest_resistance:.2f} - reversal setup"
                        })

        # Candlestick patterns aligned with trade direction
        patterns = ctx.get('candlestick_patterns', [])
        if patterns:
            opt_type = getattr(trade, 'option_type', 'CALL').upper()
            for pattern in patterns:
                if opt_type == 'CALL' and pattern.get('direction') == 'bullish':
                    flags.append({
                        "type": "pattern",
                        "message": f"Bullish {pattern.get('pattern')} pattern detected (strength: {pattern.get('strength', 0):.0f}/100)"
                    })
                elif opt_type == 'PUT' and pattern.get('direction') == 'bearish':
                    flags.append({
                        "type": "pattern",
                        "message": f"Bearish {pattern.get('pattern')} pattern detected (strength: {pattern.get('strength', 0):.0f}/100)"
                    })

        # Volume confirmation
        vol_analysis = ctx.get('volume_analysis', {})
        if vol_analysis:
            vol_trend = vol_analysis.get('volume_trend', {})
            if vol_trend.get('trend') == 'increasing' and vol_trend.get('strength') in ['strong', 'moderate']:
                flags.append({
                    "type": "volume",
                    "message": f"Volume increasing ({vol_trend.get('change_pct', 0):.0f}%) - strong institutional interest"
                })

        # Trend alignment
        trend_analysis = ctx.get('trend_analysis', {})
        if trend_analysis:
            opt_type = getattr(trade, 'option_type', 'CALL').upper()
            trend_direction = trend_analysis.get('direction', 'unknown')

            if opt_type == 'CALL' and trend_direction == 'uptrend':
                flags.append({
                    "type": "trend",
                    "message": f"Aligned with uptrend (strength: {trend_analysis.get('strength', 0)}/100)"
                })
            elif opt_type == 'PUT' and trend_direction == 'downtrend':
                flags.append({
                    "type": "trend",
                    "message": f"Aligned with downtrend (strength: {trend_analysis.get('strength', 0)}/100)"
                })

        # Multi-timeframe alignment
        mtf_alignment = ctx.get('multi_timeframe_alignment', {})
        if mtf_alignment and mtf_alignment.get('aligned'):
            flags.append({
                "type": "multi_timeframe",
                "message": f"Multi-timeframe alignment: {mtf_alignment.get('direction')} across all timeframes"
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

    def _generate_llm_enhanced_analysis(
        self,
        trade,
        trade_plan,
        red_flags: List,
        green_flags: List,
        market_context: Optional[Dict[str, Any]] = None,
        setup_score: int = 0,
        current_price: float = None
    ) -> Dict[str, str]:
        """
        Generate LLM-enhanced natural language analysis.

        Returns:
            Dict with enhanced_summary, market_narrative, trade_reasoning, recommendations
        """
        if not self.llm_enabled:
            return {
                'enhanced_summary': self._generate_summary(trade, trade_plan),
                'market_narrative': 'LLM analysis not available',
                'trade_reasoning': 'Using rule-based analysis only',
                'recommendations': 'N/A'
            }

        ctx = market_context or {}

        # Build comprehensive context for LLM
        analysis_data = {
            'ticker': trade.ticker,
            'option_type': getattr(trade, 'option_type', 'CALL'),
            'strike': getattr(trade, 'strike', 0),
            'premium': getattr(trade, 'premium', 0),
            'current_price': current_price,
            'setup_score': setup_score,
            'red_flags': red_flags,
            'green_flags': green_flags,
        }

        # Add technical analysis results
        if ctx.get('sr_analysis'):
            sr = ctx['sr_analysis']
            analysis_data['support_resistance'] = {
                'method': sr.get('method'),
                'nearest_support': sr.get('key_levels', {}).get('nearest_support'),
                'nearest_resistance': sr.get('key_levels', {}).get('nearest_resistance'),
                'support_zones': len(sr.get('support_zones', [])),
                'resistance_zones': len(sr.get('resistance_zones', [])),
            }

        if ctx.get('volume_analysis'):
            vol = ctx['volume_analysis']
            analysis_data['volume'] = {
                'vwap': vol.get('vwap'),
                'vwap_signal': vol.get('vwap_check', {}).get('signal'),
                'volume_trend': vol.get('vol_trend', {}).get('trend'),
                'volume_change_pct': vol.get('vol_trend', {}).get('change_pct'),
            }

        if ctx.get('candlestick_patterns'):
            patterns = ctx['candlestick_patterns']
            if patterns:
                analysis_data['patterns'] = [
                    {
                        'name': p.get('pattern'),
                        'direction': p.get('direction'),
                        'strength': p.get('strength'),
                        'volume_confirmed': p.get('volume_confirmed')
                    }
                    for p in patterns[-3:]  # Last 3 patterns
                ]

        if ctx.get('trend_analysis'):
            trend = ctx['trend_analysis']
            analysis_data['trend'] = {
                'direction': trend.get('direction'),
                'strength': trend.get('strength'),
                'confidence': trend.get('confidence'),
            }

        # Create LLM prompt
        prompt = self._build_analysis_prompt(analysis_data)

        try:
            # Call LLM
            response = self.llm.messages.create(
                model=self.llm_model,
                max_tokens=2000,
                system="You are an expert options trader analyzing trade setups with technical analysis.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response - handle multiple content blocks (MiniMax M2.1 format)
            content = ""
            for block in response.content:
                if hasattr(block, 'type'):
                    if block.type == "text" and hasattr(block, 'text'):
                        content += block.text
                    elif block.type == "thinking" and hasattr(block, 'thinking'):
                        # Include thinking for transparency (optional)
                        pass  # Skip thinking blocks for now
                elif hasattr(block, 'text'):
                    # Fallback for standard format
                    content += block.text

            # Extract sections (assuming structured response)
            sections = self._parse_llm_response(content)

            return {
                'enhanced_summary': sections.get('summary', content[:200]),
                'market_narrative': sections.get('market_context', 'See analysis above'),
                'trade_reasoning': sections.get('reasoning', 'See analysis above'),
                'recommendations': sections.get('recommendations', 'See analysis above'),
                'full_analysis': content
            }

        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return {
                'enhanced_summary': self._generate_summary(trade, trade_plan),
                'market_narrative': 'LLM analysis unavailable',
                'trade_reasoning': f"Error: {str(e)}",
                'recommendations': 'Fallback to rule-based analysis'
            }

    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build comprehensive prompt for LLM analysis."""
        prompt = f"""You are an expert options trader analyzing a trade setup. Provide a comprehensive analysis.

TRADE SETUP:
- Ticker: {data['ticker']}
- Option: {data['option_type']} ${data['strike']}
- Premium: ${data['premium']:.2f}
- Current Price: ${data.get('current_price', 'N/A')}
- Setup Score: {data['setup_score']}/100

TECHNICAL ANALYSIS RESULTS:
"""

        # Support/Resistance
        if 'support_resistance' in data:
            sr = data['support_resistance']
            prompt += f"""
Support/Resistance Analysis:
- Method: {sr['method']}
- Nearest Support: ${sr.get('nearest_support', 'N/A')}
- Nearest Resistance: ${sr.get('nearest_resistance', 'N/A')}
- Support zones found: {sr['support_zones']}
- Resistance zones found: {sr['resistance_zones']}
"""

        # Volume
        if 'volume' in data:
            vol = data['volume']
            prompt += f"""
Volume Analysis:
- VWAP: ${vol.get('vwap', 'N/A')}
- Signal: {vol.get('vwap_signal', 'N/A')}
- Volume Trend: {vol.get('volume_trend', 'N/A')} ({vol.get('volume_change_pct', 0):.1f}%)
"""

        # Patterns
        if 'patterns' in data:
            prompt += "\nCandlestick Patterns:\n"
            for p in data['patterns']:
                vol_conf = "✓" if p['volume_confirmed'] else "✗"
                prompt += f"- {p['name']}: {p['direction']} (strength: {p['strength']}/100, volume: {vol_conf})\n"

        # Trend
        if 'trend' in data:
            trend = data['trend']
            prompt += f"""
Trend Analysis:
- Direction: {trend['direction']}
- Strength: {trend['strength']}/100
- Confidence: {trend['confidence']}%
"""

        # Red Flags
        prompt += f"\nRED FLAGS ({len(data['red_flags'])}):\n"
        for flag in data['red_flags']:
            prompt += f"- [{flag['severity'].upper()}] {flag['message']}\n"

        # Green Flags
        prompt += f"\nGREEN FLAGS ({len(data['green_flags'])}):\n"
        for flag in data['green_flags']:
            prompt += f"- {flag['message']}\n"

        prompt += """
Please provide a structured analysis in the following format:

## SUMMARY
[2-3 sentence overview of the trade setup]

## MARKET CONTEXT
[Explain what the technical analysis reveals about current market conditions, price action, volume, and trend. Why is the price where it is? What's the market telling us?]

## TRADE REASONING
[Explain why this trade has the score it does. Address the red flags and green flags. What are the specific risks? What are the potential catalysts? For counter-trend trades, explain the reversal thesis or warn about fighting the trend.]

## RECOMMENDATIONS
[Specific, actionable recommendations:
- Should they take this trade? At what size?
- What should they watch for?
- Entry strategy (now vs wait for confirmation)?
- What would make you change your mind?
- Specific price levels to monitor]

Be direct, specific, and practical. Focus on actionable insights based on the technical analysis provided.
"""

        return prompt

    def _parse_llm_response(self, content: str) -> Dict[str, str]:
        """Parse structured LLM response into sections."""
        sections = {}

        # Simple parsing - look for section headers
        current_section = None
        current_content = []

        for line in content.split('\n'):
            line = line.strip()

            if line.startswith('## SUMMARY'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'summary'
                current_content = []
            elif line.startswith('## MARKET CONTEXT'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'market_context'
                current_content = []
            elif line.startswith('## TRADE REASONING'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'reasoning'
                current_content = []
            elif line.startswith('## RECOMMENDATIONS'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'recommendations'
                current_content = []
            elif line and not line.startswith('##'):
                current_content.append(line)

        # Add last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections
    
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

    def _get_recommendation_tier(self, score: int) -> tuple:
        """
        Return (tier_label, guidance_string) based on score and config thresholds.
        """
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
        """
        Weighted setup score 0-100 with config-driven penalties/bonuses.
        Returns (score, breakdown_dict) for transparency.
        """
        ctx = market_context or {}
        scoring_cfg = self.analysis_config.get('scoring', {})

        # Config-driven base and penalty values
        base_start = scoring_cfg.get('base_score', 55)
        high_penalty = scoring_cfg.get('high_severity_penalty', 10)
        std_med_penalty = scoring_cfg.get('standard_medium_penalty', 4)
        hi_impact_med_penalty = scoring_cfg.get('high_impact_medium_penalty', 6)
        lo_impact_med_penalty = scoring_cfg.get('low_impact_medium_penalty', 2)
        hi_impact_flags = scoring_cfg.get('high_impact_medium_flags', ['stale_premium', 'wide_spread', 'stress_test', 'theta_risk'])
        lo_impact_flags = scoring_cfg.get('low_impact_medium_flags', ['macd_bearish', 'vwap_deviation', 'volume_divergence'])
        green_pts = scoring_cfg.get('green_flag_points', 4)
        green_max = scoring_cfg.get('green_flag_max', 20)

        base = base_start

        # GO bonus
        rules = 0
        if trade_plan.go_no_go == "GO":
            rules = 10
            base += rules

        # Green flags (config-driven points and cap)
        greens = min(len(green_flags) * green_pts, green_max)
        base += greens

        # Red flags with tiered penalties
        reds = 0
        for f in red_flags:
            severity = f.get("severity", "low")
            flag_type = f.get("type", "")
            if severity == "high":
                reds -= high_penalty
                base -= high_penalty
            elif severity == "medium":
                if flag_type in hi_impact_flags:
                    reds -= hi_impact_med_penalty
                    base -= hi_impact_med_penalty
                elif flag_type in lo_impact_flags:
                    reds -= lo_impact_med_penalty
                    base -= lo_impact_med_penalty
                else:
                    reds -= std_med_penalty
                    base -= std_med_penalty

        # PoP adjustment
        pop_adj = 0
        pop = ctx.get("probability_of_profit")
        if pop is not None and pop >= 0.60:
            pop_adj = 5
            base += 5
        elif pop is not None and pop < 0.50:
            pop_adj = -5
            base -= 5

        # Liquidity adjustment
        liquidity = 0
        greeks_cfg = self.analysis_config.get("greeks", {})
        oi_min = greeks_cfg.get("open_interest_min", 1000)
        vol_min = greeks_cfg.get("option_volume_min", 500)
        has_liquidity_red = any(f.get("type") == "liquidity" for f in red_flags)
        if has_liquidity_red:
            liquidity = -3
            base -= 3
        elif ctx.get("open_interest", 0) >= oi_min and ctx.get("option_volume", 0) >= vol_min:
            liquidity = 3
            base += 3

        # Technical confluence (2-of-3 indicators instead of requiring all 3)
        technical = 0
        tech_cfg = self.analysis_config.get("technical", {})
        if tech_cfg.get("enabled", False):
            tech = ctx.get("technical", {})
            daily = (tech.get("daily") or {}) if isinstance(tech, dict) else {}
            bonus = tech_cfg.get("confluence_score_bonus", 15)
            min_indicators = tech_cfg.get("min_confluence_indicators", 2)
            rsi = daily.get("rsi")
            price_above_sma20 = daily.get("price_above_sma_20")
            macd_bullish = daily.get("macd_bullish")
            opt_type = (getattr(trade, "option_type", "CALL") or "CALL").upper()
            rsi_min_bull = tech_cfg.get("rsi_min_bullish", 50)
            rsi_max_bear = tech_cfg.get("rsi_max_bearish", 50)

            # Count how many indicators confirm
            confirming = 0
            if opt_type == "CALL":
                if rsi is not None and rsi >= rsi_min_bull:
                    confirming += 1
                if price_above_sma20 is True:
                    confirming += 1
                if macd_bullish is True or macd_bullish is None:
                    confirming += 1
            elif opt_type == "PUT":
                if rsi is not None and rsi <= rsi_max_bear:
                    confirming += 1
                if price_above_sma20 is False:
                    confirming += 1
                if macd_bullish is False or macd_bullish is None:
                    confirming += 1

            if confirming >= min_indicators:
                technical = bonus
                base += bonus

        # Events adjustment
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

        # Theta risk adjustment
        theta_risk_adj = 0
        dte = ctx.get("days_to_expiration")
        theta = (ctx.get("greeks") or {}).get("theta")
        prem = getattr(trade, "premium", None) or 0.01
        if dte is not None and dte <= 2 and theta is not None and prem > 0:
            if abs(theta) / prem >= 0.20:
                theta_risk_adj = -6
                base -= 6

        # Price action bonus (at strong S/R zone)
        price_action_bonus = 0
        sr_analysis = ctx.get('sr_analysis', {})
        if sr_analysis and current_price:
            opt_type = (getattr(trade, 'option_type', 'CALL') or 'CALL').upper()
            key_levels = sr_analysis.get('key_levels', {})

            if opt_type == 'CALL':
                nearest_support = key_levels.get('nearest_support')
                if nearest_support:
                    distance_pct = abs(current_price - nearest_support) / current_price * 100
                    if distance_pct < 1.0:
                        price_action_bonus = 15
                        base += 15
            elif opt_type == 'PUT':
                nearest_resistance = key_levels.get('nearest_resistance')
                if nearest_resistance:
                    distance_pct = abs(current_price - nearest_resistance) / current_price * 100
                    if distance_pct < 1.0:
                        price_action_bonus = 15
                        base += 15

        # Candlestick pattern bonus
        pattern_bonus = 0
        patterns_cfg = self.analysis_config.get('patterns', {})
        bonus_at_sr = patterns_cfg.get('bonus_at_sr', 12)
        patterns = ctx.get('candlestick_patterns', [])
        if patterns:
            opt_type = (getattr(trade, 'option_type', 'CALL') or 'CALL').upper()
            for pattern in patterns:
                if opt_type == 'CALL' and pattern.get('direction') == 'bullish':
                    pattern_bonus = bonus_at_sr
                    base += bonus_at_sr
                    break
                elif opt_type == 'PUT' and pattern.get('direction') == 'bearish':
                    pattern_bonus = bonus_at_sr
                    base += bonus_at_sr
                    break

        # Multi-timeframe alignment bonus
        mtf_bonus = 0
        trend_cfg = self.analysis_config.get('trend', {})
        alignment_bonus_cfg = trend_cfg.get('alignment_bonus', 20)
        mtf_alignment = ctx.get('multi_timeframe_alignment', {})
        if mtf_alignment and mtf_alignment.get('aligned'):
            opt_type = (getattr(trade, 'option_type', 'CALL') or 'CALL').upper()
            mtf_direction = mtf_alignment.get('direction', '')

            if (opt_type == 'CALL' and mtf_direction == 'uptrend') or \
               (opt_type == 'PUT' and mtf_direction == 'downtrend'):
                mtf_bonus = alignment_bonus_cfg
                base += alignment_bonus_cfg

        # Volume confirmation bonus
        volume_bonus = 0
        vol_trend = ctx.get('volume_trend', {})
        if vol_trend:
            if vol_trend.get('trend') == 'increasing' and vol_trend.get('strength') in ['strong', 'moderate']:
                volume_bonus = 5
                base += 5

        # NOTE: Counter-trend penalty is NOT applied separately here.
        # It is already counted in red flags (HIGH severity) above.
        # The old code double-penalized counter-trend trades.

        score = max(0, min(100, int(base)))
        breakdown = {
            "base": base_start,
            "rules": rules,
            "greens": greens,
            "reds": reds,
            "pop": pop_adj,
            "liquidity": liquidity,
            "technical": technical,
            "events": events_adj,
            "theta_risk": theta_risk_adj,
            "price_action": price_action_bonus,
            "pattern": pattern_bonus,
            "mtf_alignment": mtf_bonus,
            "volume": volume_bonus,
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
