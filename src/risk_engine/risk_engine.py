"""
Risk Engine Module
Deterministic position sizing, stop losses, and target calculation
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
import yaml


@dataclass
class PositionSize:
    """Calculated position sizing result"""
    contracts: int
    total_premium: float
    max_risk_dollars: float
    risk_per_contract: float
    capital_used: float
    risk_percentage: float
    reasoning: str


@dataclass
class TradePlan:
    """Complete trade execution plan"""
    trade: Any  # OptionTrade
    position: PositionSize
    entry_zone: str
    stop_loss: float
    stop_risk_pct: float
    target_1: float
    target_1_r: float
    runner_activated: bool
    runner_contracts: int
    runner_target: float
    max_loss_dollars: float
    max_gain_dollars: float
    go_no_go: str
    go_no_go_reasons: list
    technical_reasoning: str = ""  # Technical analysis for targets
    is_technical: bool = False  # True if using technical targets


class RiskEngine:
    """
    Deterministic risk management engine.
    All calculations are rule-based - no discretion.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.account = self.config.get('account', {})
        self.sizing = self.config.get('sizing', {})
        self.stops = self.config.get('stops', {})
        self.targets = self.config.get('targets', {})
        self.ode = self.config.get('ode', {})
    
    def calculate_position(self, trade, current_price: float = None) -> PositionSize:
        """
        Calculate optimal contract count based on risk parameters.
        """
        max_risk_pct = self.account.get('max_risk_per_trade', 0.02)
        total_capital = self.account.get('total_capital', 100000)
        max_risk_dollars = total_capital * max_risk_pct
        
        # Risk per contract = premium × 100 (per contract)
        risk_per_contract = trade.premium * 100
        
        # Calculate contracts based on risk
        if risk_per_contract > 0:
            raw_contracts = max_risk_dollars / risk_per_contract
            contracts = int(raw_contracts)  # Floor to whole contracts
            
            # Apply minimum constraints
            min_contracts = 1
            contracts = max(contracts, min_contracts)
            
            # Check max position limit
            max_positions = self.account.get('max_open_positions', 5)
            if contracts > max_positions:
                contracts = max_positions
                reasoning = f"Capped at {max_positions} contracts (max positions)"
            else:
                reasoning = f"Calculated: ${max_risk_dollars:.0f} risk / ${risk_per_contract:.0f} per contract = {raw_contracts:.1f} → {contracts}"
        else:
            contracts = self.sizing.get('default_contracts', 1)
            reasoning = "Could not calculate risk - using default"
        
        total_premium = contracts * trade.premium * 100
        capital_used = total_premium  # For long options, premium = capital at risk initially
        actual_risk_pct = (contracts * risk_per_contract) / total_capital
        
        return PositionSize(
            contracts=contracts,
            total_premium=total_premium,
            max_risk_dollars=contracts * risk_per_contract,
            risk_per_contract=risk_per_contract,
            capital_used=capital_used,
            risk_percentage=actual_risk_pct,
            reasoning=reasoning
        )
    
    def _get_stop_params(self, trade) -> tuple:
        """Return (stop_pct, max_loss_per_contract) — use ODE params if same-day expiration."""
        use_ode = getattr(trade, "is_ode", False) and self.ode.get("enabled", True)
        if use_ode:
            return (
                self.ode.get("stop_pct", 0.35),
                self.ode.get("max_loss_per_contract", 300),
            )
        return (
            self.stops.get("default_pct", 0.50),
            self.stops.get("max_loss_per_contract", 500),
        )

    def calculate_stops(self, trade, position: PositionSize, current_price: float = None) -> Dict[str, float]:
        """
        Calculate stop loss levels. Uses tighter ODE params for same-day expiration.
        """
        stop_pct, max_loss_per_contract = self._get_stop_params(trade)

        # Calculate stop based on premium
        premium_stop = trade.premium * (1 - stop_pct)

        # Calculate stop based on max loss cap
        dollar_stop = trade.premium - (max_loss_per_contract / 100)

        # Use whichever is tighter (more conservative)
        stop_loss = max(premium_stop, dollar_stop)

        # Calculate risk percentage
        entry_risk = trade.premium - stop_loss
        risk_pct = (entry_risk / trade.premium) * 100 if trade.premium > 0 else 0

        return {
            "stop_loss": round(stop_loss, 2),
            "risk_pct": round(risk_pct, 1),
            "max_loss_dollars": round(position.contracts * (trade.premium - stop_loss) * 100, 2),
            "reasoning": f"Stop at ${stop_loss:.2f} ({risk_pct:.1f}% of premium)"
        }
    
    def _get_target_params(self, trade) -> tuple:
        """Return target params — use ODE params if same-day expiration."""
        use_ode = getattr(trade, "is_ode", False) and self.ode.get("enabled", True)
        if use_ode:
            return (
                self.ode.get("profit_target_r", 1.5),
                self.ode.get("runner_activation_r", 2.0),
                self.ode.get("runner_remaining_pct", 0.50),
                self.ode.get("max_runner_target_r", 3.0),
            )
        return (
            self.targets.get("profit_target_r", 2.0),
            self.targets.get("runner_activation_r", 3.0),
            self.targets.get("runner_remaining_pct", 0.50),
            self.targets.get("max_runner_target_r", 5.0),
        )

    def calculate_targets(self, trade, stop_info: Dict, position: PositionSize, 
                          current_price: float = None,
                          market_context: Dict = None) -> Dict[str, Any]:
        """
        Calculate profit targets using technical analysis when available.
        Falls back to R-based targets if technical levels unavailable.
        """
        profit_target_r, runner_activation_r, runner_remaining_pct, max_runner_target_r = self._get_target_params(trade)

        stop_loss = stop_info.get('stop_loss', trade.premium * 0.5)
        risk_per_share = trade.premium - stop_loss
        
        # Try to get technically-grounded targets
        technical_targets = None
        if current_price and market_context:
            try:
                from analysis.technical_targets import (
                    get_support_resistance_levels,
                    get_technical_target_recommendation,
                )
                
                # Get S/R levels
                sr_levels = get_support_resistance_levels(
                    trade.ticker, current_price, period=20
                )
                support_levels = sr_levels.get("support_levels", [])
                resistance_levels = sr_levels.get("resistance_levels", [])
                
                # Get technical target recommendation
                iv_percent = market_context.get("implied_volatility", 0.30)
                if iv_percent > 2:
                    iv_percent = iv_percent / 100
                
                technical_targets = get_technical_target_recommendation(
                    trade=trade,
                    current_price=current_price,
                    entry_premium=trade.premium,
                    stop_premium=stop_loss,
                    support_levels=support_levels,
                    resistance_levels=resistance_levels,
                    option_type=getattr(trade, "option_type", "CALL"),
                    days_to_expiration=getattr(trade, "days_to_expiration", 0) or 0,
                    iv_percent=iv_percent,
                )
            except ImportError:
                pass  # Technical targets module not available
        
        # Use technical targets if available, otherwise use R-based
        if technical_targets and technical_targets.get("conservative_target"):
            cons = technical_targets["conservative_target"]
            mod = technical_targets.get("moderate_target")
            agg = technical_targets.get("aggressive_target")
            
            # Use conservative (first technical level) as T1
            target_1 = cons.get("premium", trade.premium + risk_per_share * profit_target_r)
            target_1_r = cons.get("r_multiple", profit_target_r)
            
            # Use moderate as runner if available
            runner_target = mod.get("premium", trade.premium + risk_per_share * max_runner_target_r)
            
            return {
                "target_1": round(target_1, 2),
                "target_1_r": round(target_1_r, 1),
                "runner_activated": True,
                "runner_contracts": int(position.contracts * runner_remaining_pct),
                "runner_target": round(runner_target, 2),
                "max_runner_target_r": max_runner_target_r,
                "technical_reasoning": technical_targets.get("reasoning", ""),
                "is_technical": True,
                "reasoning": f"Technical targets: {technical_targets.get('reasoning', 'S/R-based')}",
            }
        
        # Fallback to R-based targets
        target_1 = trade.premium + (risk_per_share * profit_target_r)
        target_1_r = profit_target_r
        runner_target = trade.premium + (risk_per_share * max_runner_target_r)

        return {
            "target_1": round(target_1, 2),
            "target_1_r": target_1_r,
            "runner_activated": True,
            "runner_contracts": int(position.contracts * runner_remaining_pct),
            "runner_target": round(runner_target, 2),
            "max_runner_target_r": max_runner_target_r,
            "is_technical": False,
            "reasoning": f"R-based targets ({profit_target_r}R - {max_runner_target_r}R)"
        }
    
    def check_go_no_go(self, trade, position: PositionSize, current_price: float = None) -> Dict[str, Any]:
        """
        Rule-based go/no-go evaluation.
        Returns pass/fail with specific reasons.
        """
        reasons = []
        passed = True
        
        # Check risk percentage
        max_risk = self.account.get('max_risk_per_trade', 0.02)
        if position.risk_percentage > max_risk:
            passed = False
            reasons.append(f"Risk {position.risk_percentage:.2%} exceeds max {max_risk:.2%}")
        
        # Check minimum premium (ODE allows lower)
        min_prem = self.sizing.get('min_premium_to_consider', 0.50)
        if getattr(trade, "is_ode", False) and self.ode.get("enabled", True):
            min_prem = self.ode.get("min_premium", 0.30)
        if trade.premium < min_prem:
            reasons.append(f"Premium ${trade.premium} below minimum ${min_prem}")
            passed = False
        
        # Check position size
        if position.contracts < 1:
            reasons.append("Position size calculation resulted in < 1 contract")
            passed = False
        
        # Check capital available (simplified - would need to track open positions)
        total_capital = self.account.get('total_capital', 100000)
        if position.capital_used > total_capital * 0.25:  # Max 25% in single trade
            reasons.append(f"Position size {position.capital_used:.0f} exceeds 25% of capital")
            passed = False
        
        return {
            "decision": "GO" if passed else "NO-GO",
            "reasons": reasons,
            "is_pass": passed
        }
    
    def create_trade_plan(self, trade, current_price: float = None, market_context: Dict = None) -> TradePlan:
        """
        Create complete trade plan with all calculations.
        Uses technical targets when market_context with S/R levels is available.
        """
        # Step 1: Position sizing
        position = self.calculate_position(trade, current_price)
        
        # Step 2: Stop losses
        stop_info = self.calculate_stops(trade, position, current_price)
        
        # Step 3: Targets (pass market_context for technical targets)
        target_info = self.calculate_targets(trade, stop_info, position, current_price, market_context)
        
        # Step 4: Go/No-Go check
        go_check = self.check_go_no_go(trade, position, current_price)
        
        # Store technical reasoning if available
        technical_reasoning = target_info.get("technical_reasoning", "")
        is_technical = target_info.get("is_technical", False)
        
        return TradePlan(
            trade=trade,
            position=position,
            entry_zone=f"${trade.premium - 0.05:.2f} - ${trade.premium + 0.05:.2f}",
            stop_loss=stop_info['stop_loss'],
            stop_risk_pct=stop_info['risk_pct'],
            target_1=target_info['target_1'],
            target_1_r=target_info['target_1_r'],
            runner_activated=target_info['runner_activated'],
            runner_contracts=target_info['runner_contracts'],
            runner_target=target_info['runner_target'],
            max_loss_dollars=stop_info['max_loss_dollars'],
            max_gain_dollars=position.contracts * (target_info['target_1'] - trade.premium) * 100,
            go_no_go=go_check['decision'],
            go_no_go_reasons=go_check['reasons'],
            technical_reasoning=technical_reasoning,
            is_technical=is_technical,
        )


# CLI test
if __name__ == "__main__":
    from parser.trade_parser import TradeParser
    
    parser = TradeParser()
    engine = RiskEngine()
    
    test_trades = [
        "BUY AAPL 01/31 215 CALL @ 3.50",
        "TSLA PUT 800 @ 12.50",
    ]
    
    for msg in test_trades:
        trade = parser.parse(msg)
        if trade:
            plan = engine.create_trade_plan(trade, current_price=217.50)
            print(f"\n{'='*50}")
            print(f"Trade: {trade.ticker} {trade.option_type} ${trade.strike}")
            print(f"Premium: ${trade.premium}")
            print(f"\n{'GO' if plan.go_no_go == 'GO' else 'NO-GO'}: {plan.go_no_go}")
            if plan.go_no_go_reasons:
                for r in plan.go_no_go_reasons:
                    print(f"  - {r}")
            print(f"\nPosition: {plan.position.contracts} contracts")
            print(f"  Risk: ${plan.position.max_risk_dollars:.0f} ({plan.position.risk_percentage:.1%})")
            print(f"  Reasoning: {plan.position.reasoning}")
            print(f"\nStop: ${plan.stop_loss} ({plan.stop_risk_pct}% risk)")
            print(f"Target 1: ${plan.target_1} ({plan.target_1_r}R)")
            print(f"Runner: {plan.runner_contracts} contracts @ ${plan.runner_target}")
