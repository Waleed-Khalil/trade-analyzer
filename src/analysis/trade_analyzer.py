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
    
    def analyze(self, trade, trade_plan, current_price: float = None) -> AnalysisResult:
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
                confidence=0.0
            )
        
        # Run red flag checks
        red_flags = self._check_red_flags(trade, current_price)
        
        # Generate analysis (would call LLM in production)
        summary = self._generate_summary(trade, trade_plan)
        market_context = self._get_market_context(trade.ticker)
        green_flags = self._check_green_flags(trade, trade_plan, current_price)
        
        # Calculate setup quality based on flags
        setup_quality = self._assess_setup_quality(red_flags, green_flags)
        
        # Confidence based on rule compliance
        confidence = self._calculate_confidence(trade_plan, red_flags)
        
        return AnalysisResult(
            summary=summary,
            red_flags=red_flags,
            green_flags=green_flags,
            market_context=market_context,
            setup_quality=setup_quality,
            confidence=confidence
        )
    
    def _check_red_flags(self, trade, current_price: float = None) -> List[Dict[str, str]]:
        """Check for known risk factors"""
        flags = []
        checks = self.analysis_config.get('red_flag_checks', {})
        
        # IV Rank check (would need market data)
        # iv_rank = get_iv_rank(trade.ticker)
        # if iv_rank > 70:
        #     flags.append({
        #         "type": "iv_rank",
        #         "severity": "high",
        #         "message": checks.get("iv_rank_above_70", "High IV detected")
        #     })
        
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
        
        # Size exceeds calculated max (duplicate check with risk engine)
        # This is more for AI context
        
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
