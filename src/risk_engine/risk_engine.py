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
    partial_exit_plan: Optional[Dict[str, Any]] = None  # Multi-level profit taking plan
    trailing_stop_plan: Optional[Dict[str, Any]] = None  # Dynamic trailing stop strategy
    exit_monitoring: Optional[list] = None  # Patterns/signals to monitor for exits


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
    
    def calculate_position(
        self,
        trade,
        current_price: float = None,
        setup_score: Optional[int] = None,
        iv_rank: Optional[float] = None,
        trade_history: Optional[list] = None,
        current_drawdown_pct: float = 0.0,
        stop_loss: Optional[float] = None
    ) -> PositionSize:
        """
        Calculate optimal contract count based on risk parameters.

        If smart sizing is enabled (sizing.method = 'composite'), uses PositionSizer
        with Kelly Criterion, volatility adjustment, setup quality multipliers, etc.
        Otherwise falls back to fixed percentage sizing.

        Args:
            trade: OptionTrade object
            current_price: Current underlying price
            setup_score: Setup quality score (0-100) from TradeAnalyzer
            iv_rank: IV rank percentile (0-100)
            trade_history: List of recent trades for Kelly calculation
            current_drawdown_pct: Current account drawdown percentage
            stop_loss: Stop loss price (for risk calculation)
        """
        total_capital = self.account.get('total_capital', 100000)
        risk_per_contract = trade.premium * 100

        # Check if smart sizing is enabled
        sizing_config = self.sizing if hasattr(self, 'sizing') else self.config.get('sizing', {})
        sizing_method = sizing_config.get('method', 'fixed')

        # Use smart PositionSizer if configured and setup_score available
        if sizing_method == 'composite' and setup_score is not None:
            try:
                from risk_engine.position_sizer import PositionSizer

                sizer = PositionSizer(self.config)

                # Calculate stop loss if not provided
                if stop_loss is None:
                    stop_pct = self._get_stop_params(trade)[0]
                    stop_loss = trade.premium * (1 - stop_pct)

                # Call smart position sizer
                result = sizer.calculate_position_size(
                    account_value=total_capital,
                    entry_price=trade.premium,
                    stop_loss=stop_loss,
                    setup_score=setup_score,
                    trade_history=trade_history or [],
                    iv_rank=iv_rank,
                    current_drawdown_pct=current_drawdown_pct
                )

                # Convert PositionSizer result to PositionSize dataclass
                contracts = result['contracts']
                total_premium = contracts * trade.premium * 100
                capital_used = total_premium
                actual_risk_pct = result['risk_pct']
                max_risk_dollars = contracts * risk_per_contract

                # Build detailed reasoning from all components
                reasoning_parts = [f"Smart sizing (score: {setup_score})"]
                if result.get('kelly_pct'):
                    reasoning_parts.append(f"Kelly: {result['kelly_pct']:.1%}")
                if result.get('volatility_multiplier', 1.0) != 1.0:
                    reasoning_parts.append(f"IV adj: {result['volatility_multiplier']:.2f}x")
                if result.get('setup_multiplier', 1.0) != 1.0:
                    reasoning_parts.append(f"Quality: {result['setup_multiplier']:.2f}x")
                if result.get('equity_multiplier', 1.0) != 1.0:
                    reasoning_parts.append(f"Equity: {result['equity_multiplier']:.2f}x")
                if result.get('drawdown_multiplier', 1.0) != 1.0:
                    reasoning_parts.append(f"DD: {result['drawdown_multiplier']:.2f}x")

                reasoning = " | ".join(reasoning_parts) + f" → {contracts} contracts"

                return PositionSize(
                    contracts=contracts,
                    total_premium=total_premium,
                    max_risk_dollars=max_risk_dollars,
                    risk_per_contract=risk_per_contract,
                    capital_used=capital_used,
                    risk_percentage=actual_risk_pct,
                    reasoning=reasoning
                )

            except Exception as e:
                # Fallback to fixed sizing if PositionSizer fails
                print(f"Warning: Smart sizing failed ({e}), using fixed sizing")
                pass

        # Fallback: Fixed percentage sizing (original logic)
        max_risk_pct = self.account.get('max_risk_per_trade', 0.02)
        max_risk_dollars = total_capital * max_risk_pct

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
                reasoning = f"Fixed sizing: ${max_risk_dollars:.0f} risk / ${risk_per_contract:.0f} per contract = {raw_contracts:.1f} → {contracts}"
        else:
            contracts = sizing_config.get('default_contracts', 1)
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

    def _generate_exit_plans(
        self,
        trade,
        position: PositionSize,
        stop_loss: float,
        atr: Optional[float],
        sr_zones: Optional[Dict],
    ) -> tuple:
        """
        Generate partial exit plan and trailing stop plan.

        Returns:
            tuple: (partial_exit_plan, trailing_stop_plan, exit_monitoring)
        """
        partial_exit_plan = None
        trailing_stop_plan = None
        exit_monitoring = []

        # Check if exit planning features are enabled
        partial_exits_cfg = self.config.get('partial_exits', {})
        trailing_stops_cfg = self.config.get('trailing_stops', {})

        # Generate partial exit plan
        if partial_exits_cfg.get('enabled', True):
            try:
                from risk_engine.partial_exits import PartialExitManager
                partial_manager = PartialExitManager(self.config)
                partial_exit_plan = partial_manager.calculate_partial_exit_plan(
                    entry_price=trade.premium,
                    stop_loss=stop_loss,
                    total_contracts=position.contracts,
                    option_type=getattr(trade, 'option_type', 'CALL'),
                    sr_zones=sr_zones
                )
            except Exception:
                pass  # Module not available or failed

        # Generate trailing stop plan
        if trailing_stops_cfg.get('enabled', True) and atr:
            try:
                from risk_engine.trailing_stops import TrailingStopManager
                trailing_manager = TrailingStopManager(self.config)

                # Initial trailing stop plan (will update as trade progresses)
                trailing_stop_plan = {
                    'initial_stop': stop_loss,
                    'atr': atr,
                    'phases': {
                        'initial': f"Trail at {trailing_stops_cfg.get('atr_trailing', {}).get('initial_multiplier', 1.5)}x ATR below entry",
                        'mid_profit': f"At 2R+, trail at {trailing_stops_cfg.get('atr_trailing', {}).get('mid_multiplier', 2.0)}x ATR",
                        'high_profit': f"At 4R+, trail at {trailing_stops_cfg.get('atr_trailing', {}).get('high_multiplier', 2.5)}x ATR"
                    },
                    'breakeven_trigger': f"Move to breakeven at {trailing_stops_cfg.get('breakeven', {}).get('r_trigger', 2.0)}R",
                    'technical_trailing': trailing_stops_cfg.get('technical_trailing', {}).get('enabled', True)
                }
            except Exception:
                pass  # Module not available or failed

        # Add exit monitoring suggestions
        exit_patterns_cfg = self.config.get('exit_patterns', {})
        if exit_patterns_cfg.get('enabled', True):
            exit_monitoring.append("Monitor for reversal patterns (evening star, shooting star, bearish engulfing)")
            exit_monitoring.append(f"Watch for volume spikes >{exit_patterns_cfg.get('volume_spike_threshold', 1.5)}x average")
            if sr_zones and sr_zones.get('resistance_zones'):
                exit_monitoring.append("Watch for rejection at resistance levels")

        return partial_exit_plan, trailing_stop_plan, exit_monitoring if exit_monitoring else None

    def calculate_targets(self, trade, stop_info: Dict, position: PositionSize,
                          current_price: float = None,
                          market_context: Dict = None) -> Dict[str, Any]:
        """
        Calculate profit targets using technical analysis when available.
        Falls back to R-based targets if technical levels unavailable.
        Also generates partial exit plan and trailing stop strategy.
        """
        profit_target_r, runner_activation_r, runner_remaining_pct, max_runner_target_r = self._get_target_params(trade)

        stop_loss = stop_info.get('stop_loss', trade.premium * 0.5)
        risk_per_share = trade.premium - stop_loss

        # Get S/R zones for exit planning
        sr_zones = None
        if market_context:
            sr_zones = market_context.get('sr_analysis')

        # Get ATR for trailing stops
        atr = None
        if market_context:
            atr = market_context.get('atr')
        
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
        
        # Generate exit plans
        partial_exit_plan, trailing_stop_plan, exit_monitoring = self._generate_exit_plans(
            trade, position, stop_loss, atr, sr_zones
        )

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
                "partial_exit_plan": partial_exit_plan,
                "trailing_stop_plan": trailing_stop_plan,
                "exit_monitoring": exit_monitoring,
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
            "reasoning": f"R-based targets ({profit_target_r}R - {max_runner_target_r}R)",
            "partial_exit_plan": partial_exit_plan,
            "trailing_stop_plan": trailing_stop_plan,
            "exit_monitoring": exit_monitoring,
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
        Integrates smart position sizing when setup_score is provided in market_context.
        """
        # Extract smart sizing parameters from market_context
        setup_score = None
        iv_rank = None
        trade_history = None
        current_drawdown_pct = 0.0

        if market_context:
            # Get setup_score from analysis (Phase 1-4 integration)
            analysis_result = market_context.get('analysis_result', {})
            if isinstance(analysis_result, dict):
                setup_score = analysis_result.get('setup_score')

            # Get IV rank from market data
            iv_rank_pct = market_context.get('iv_rank_percentile')
            if iv_rank_pct is not None:
                iv_rank = iv_rank_pct

            # Get trade history if available (from journal or elsewhere)
            trade_history = market_context.get('trade_history', [])

            # Get current drawdown if tracked
            current_drawdown_pct = market_context.get('current_drawdown_pct', 0.0)

        # Step 1: Position sizing (with smart sizing if setup_score available)
        position = self.calculate_position(
            trade,
            current_price,
            setup_score=setup_score,
            iv_rank=iv_rank,
            trade_history=trade_history,
            current_drawdown_pct=current_drawdown_pct
        )

        # Step 2: Stop losses
        stop_info = self.calculate_stops(trade, position, current_price)

        # Step 3: Targets (pass market_context for technical targets)
        target_info = self.calculate_targets(trade, stop_info, position, current_price, market_context)

        # Step 4: Go/No-Go check
        go_check = self.check_go_no_go(trade, position, current_price)

        # Store technical reasoning and exit plans if available
        technical_reasoning = target_info.get("technical_reasoning", "")
        is_technical = target_info.get("is_technical", False)
        partial_exit_plan = target_info.get("partial_exit_plan")
        trailing_stop_plan = target_info.get("trailing_stop_plan")
        exit_monitoring = target_info.get("exit_monitoring")

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
            partial_exit_plan=partial_exit_plan,
            trailing_stop_plan=trailing_stop_plan,
            exit_monitoring=exit_monitoring,
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
