"""
Smart Position Sizing
Kelly Criterion, volatility adjustments, and setup quality-based sizing
"""

from typing import Dict, Any, Optional, List
import math


class PositionSizer:
    """
    Advanced position sizing that optimizes capital allocation based on:
    - Kelly Criterion (win rate and avg R)
    - IV Rank (volatility adjustment)
    - Setup Quality Score (confluence multiplier)
    - Equity Curve (drawdown protection)
    - Correlation (avoid overconcentration)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize position sizer.

        Args:
            config: Configuration dict from config.yaml
        """
        self.config = config
        self.sizing_config = config.get('sizing', {})
        self.method = self.sizing_config.get('method', 'composite')

        # Component configs
        self.kelly_config = self.sizing_config.get('kelly', {})
        self.volatility_config = self.sizing_config.get('volatility', {})
        self.quality_config = self.sizing_config.get('setup_quality', {})
        self.equity_config = self.sizing_config.get('equity_curve', {})

        # Risk management limits
        self.risk_config = config.get('risk_management', {})
        self.max_position_pct = self.risk_config.get('limits', {}).get('max_position_pct', 0.25)
        self.max_risk_per_trade = self.risk_config.get('limits', {}).get('max_risk_per_trade', 0.05)

    def calculate_position_size(
        self,
        account_value: float,
        entry_price: float,
        stop_loss: float,
        setup_score: int,
        trade_history: Optional[List[Dict[str, Any]]] = None,
        iv_rank: Optional[float] = None,
        current_drawdown_pct: float = 0.0,
        open_positions: Optional[List[Dict[str, Any]]] = None,
        ticker: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate optimal position size using selected method.

        Args:
            account_value: Total portfolio value
            entry_price: Entry premium price
            stop_loss: Stop loss price
            setup_score: Quality score (0-100)
            trade_history: Historical trades for Kelly calculation
            iv_rank: IV Rank (0-100) for volatility adjustment
            current_drawdown_pct: Current drawdown percentage
            open_positions: List of currently open positions
            ticker: Stock symbol for correlation check

        Returns:
            Dict with contracts, risk_pct, sizing breakdown, and reasoning
        """
        risk_per_contract = abs(entry_price - stop_loss)

        if self.method == 'composite':
            return self._composite_sizing(
                account_value,
                entry_price,
                risk_per_contract,
                setup_score,
                trade_history,
                iv_rank,
                current_drawdown_pct,
                open_positions,
                ticker
            )
        elif self.method == 'kelly':
            return self._kelly_sizing(
                account_value,
                risk_per_contract,
                trade_history
            )
        else:
            # Fixed percentage sizing (fallback)
            return self._fixed_sizing(
                account_value,
                risk_per_contract
            )

    def _composite_sizing(
        self,
        account_value: float,
        entry_price: float,
        risk_per_contract: float,
        setup_score: int,
        trade_history: Optional[List[Dict[str, Any]]],
        iv_rank: Optional[float],
        current_drawdown_pct: float,
        open_positions: Optional[List[Dict[str, Any]]],
        ticker: Optional[str]
    ) -> Dict[str, Any]:
        """Composite sizing combining multiple factors."""
        base_risk_pct = 0.02  # 2% base risk
        adjustments = {}

        # 1. Kelly Criterion adjustment
        kelly_multiplier = 1.0
        if self.kelly_config.get('enabled', True) and trade_history:
            kelly_pct = self._calculate_kelly(trade_history)
            if kelly_pct:
                kelly_multiplier = kelly_pct / base_risk_pct
                adjustments['kelly'] = {
                    'multiplier': round(kelly_multiplier, 2),
                    'kelly_pct': round(kelly_pct * 100, 2)
                }

        # 2. Volatility adjustment
        volatility_multiplier = 1.0
        if self.volatility_config.get('enabled', True) and iv_rank is not None:
            volatility_multiplier = self._calculate_volatility_adjustment(iv_rank)
            adjustments['volatility'] = {
                'multiplier': round(volatility_multiplier, 2),
                'iv_rank': iv_rank
            }

        # 3. Setup quality multiplier
        quality_multiplier = 1.0
        if self.quality_config.get('enabled', True):
            quality_multiplier = self._calculate_quality_multiplier(setup_score)
            adjustments['setup_quality'] = {
                'multiplier': round(quality_multiplier, 2),
                'setup_score': setup_score
            }

        # 4. Equity curve adjustment
        equity_multiplier = 1.0
        if self.equity_config.get('enabled', True) and trade_history:
            equity_multiplier = self._calculate_equity_adjustment(
                trade_history,
                current_drawdown_pct
            )
            adjustments['equity_curve'] = {
                'multiplier': round(equity_multiplier, 2),
                'recent_performance': 'calculated'
            }

        # 5. Drawdown protection
        drawdown_multiplier = 1.0
        if current_drawdown_pct > 0:
            drawdown_multiplier = self._calculate_drawdown_multiplier(current_drawdown_pct)
            adjustments['drawdown'] = {
                'multiplier': round(drawdown_multiplier, 2),
                'current_dd_pct': round(current_drawdown_pct, 2)
            }

        # Calculate final risk percentage
        final_risk_pct = (base_risk_pct * kelly_multiplier * volatility_multiplier *
                         quality_multiplier * equity_multiplier * drawdown_multiplier)

        # Apply absolute limits
        final_risk_pct = min(final_risk_pct, self.max_risk_per_trade)
        final_risk_pct = max(final_risk_pct, 0.005)  # Min 0.5% risk

        # Calculate contracts (options trade in 100-share lots)
        risk_dollars = account_value * final_risk_pct
        risk_per_contract_dollars = risk_per_contract * 100  # Convert to contract risk
        contracts = int(risk_dollars / risk_per_contract_dollars)
        contracts = max(1, contracts)  # At least 1 contract

        # Check position size limit (position value = contracts * entry_price * 100)
        position_value = contracts * entry_price * 100
        position_pct = position_value / account_value

        if position_pct > self.max_position_pct:
            # Scale down to meet position size limit
            contracts = int((account_value * self.max_position_pct) / (entry_price * 100))
            contracts = max(1, contracts)
            adjustments['position_limit'] = {
                'applied': True,
                'max_pct': self.max_position_pct,
                'reduced_from': int(risk_dollars / risk_per_contract_dollars)
            }

        # 6. Correlation check
        if open_positions and ticker:
            correlation_limit = self._check_correlation(
                ticker,
                open_positions,
                contracts,
                entry_price,
                account_value
            )
            if correlation_limit['limited']:
                contracts = correlation_limit['max_contracts']
                adjustments['correlation'] = correlation_limit

        actual_risk_dollars = contracts * risk_per_contract * 100  # Risk in dollars
        actual_risk_pct = actual_risk_dollars / account_value
        position_value_dollars = contracts * entry_price * 100  # Position value in dollars

        return {
            'contracts': contracts,
            'risk_pct': round(actual_risk_pct * 100, 2),
            'risk_dollars': round(actual_risk_dollars, 2),
            'position_value': round(position_value_dollars, 2),
            'position_pct': round((position_value_dollars / account_value) * 100, 2),
            'sizing_method': 'composite',
            'base_risk_pct': round(base_risk_pct * 100, 2),
            'adjustments': adjustments,
            'reasoning': self._build_sizing_reasoning(adjustments, setup_score),
            'kelly_pct': adjustments.get('kelly', {}).get('kelly_pct'),
            'volatility_multiplier': adjustments.get('volatility', {}).get('multiplier'),
            'setup_multiplier': adjustments.get('setup_quality', {}).get('multiplier'),
            'equity_multiplier': adjustments.get('equity_curve', {}).get('multiplier'),
            'drawdown_multiplier': adjustments.get('drawdown', {}).get('multiplier'),
        }

    def _calculate_kelly(
        self,
        trade_history: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate Kelly percentage from trade history."""
        min_trades = self.kelly_config.get('min_trades_for_kelly', 30)

        if len(trade_history) < min_trades:
            return None

        # Calculate win rate and average R
        wins = [t for t in trade_history if t.get('pnl', 0) > 0]
        losses = [t for t in trade_history if t.get('pnl', 0) < 0]

        if not wins or not losses:
            return None

        win_rate = len(wins) / len(trade_history)

        # Calculate average R (profit / initial risk)
        avg_win_r = sum(t.get('r_multiple', 1) for t in wins) / len(wins)
        avg_loss_r = abs(sum(t.get('r_multiple', -1) for t in losses) / len(losses))

        # Kelly formula: f = (p*b - q) / b
        # where p=win_rate, q=loss_rate, b=avg_win/avg_loss
        if avg_loss_r == 0:
            return None

        b = avg_win_r / avg_loss_r
        kelly_pct = (win_rate * b - (1 - win_rate)) / b

        # Apply fractional Kelly (safer)
        fractional = self.kelly_config.get('fractional_kelly', 0.25)
        kelly_pct = kelly_pct * fractional

        # Ensure positive and reasonable
        kelly_pct = max(0.001, min(0.10, kelly_pct))  # Cap at 10%

        return kelly_pct

    def _calculate_volatility_adjustment(self, iv_rank: float) -> float:
        """Adjust size based on IV Rank."""
        adjustment_range = self.volatility_config.get('adjustment_range', [0.5, 1.5])
        min_mult, max_mult = adjustment_range

        high_iv_threshold = self.volatility_config.get('high_iv_threshold', 70)
        low_iv_threshold = self.volatility_config.get('low_iv_threshold', 30)

        if iv_rank >= high_iv_threshold:
            # High IV = reduce size (more risk)
            return min_mult
        elif iv_rank <= low_iv_threshold:
            # Low IV = increase size (less risk)
            return max_mult
        else:
            # Linear interpolation between thresholds
            # As IV goes up, multiplier goes down
            normalized = (iv_rank - low_iv_threshold) / (high_iv_threshold - low_iv_threshold)
            return max_mult - (normalized * (max_mult - min_mult))

    def _calculate_quality_multiplier(self, setup_score: int) -> float:
        """Adjust size based on setup quality score."""
        brackets = self.quality_config.get('score_brackets', {})

        # Default brackets
        if not brackets:
            brackets = {
                'exceptional': [90, 100, 1.5],
                'high': [80, 89, 1.25],
                'good': [70, 79, 1.0],
                'medium': [60, 69, 0.75]
            }

        for bracket_name, (min_score, max_score, multiplier) in brackets.items():
            if min_score <= setup_score <= max_score:
                return multiplier

        # Below all brackets = minimum size
        return 0.5

    def _calculate_equity_adjustment(
        self,
        trade_history: List[Dict[str, Any]],
        current_drawdown_pct: float
    ) -> float:
        """Adjust size based on recent performance."""
        lookback = self.equity_config.get('lookback_trades', 10)
        adjustment_range = self.equity_config.get('adjustment_range', [0.5, 1.3])
        min_mult, max_mult = adjustment_range

        if len(trade_history) < lookback:
            return 1.0  # Not enough history

        recent_trades = trade_history[-lookback:]

        # Calculate recent win rate
        wins = len([t for t in recent_trades if t.get('pnl', 0) > 0])
        recent_win_rate = wins / len(recent_trades)

        # Calculate recent average R
        avg_r = sum(t.get('r_multiple', 0) for t in recent_trades) / len(recent_trades)

        # Winning streak: increase size
        # Losing streak: decrease size
        if recent_win_rate >= 0.7 and avg_r > 1.0:
            return max_mult
        elif recent_win_rate <= 0.3 or avg_r < 0:
            return min_mult
        else:
            # Linear interpolation
            normalized = (recent_win_rate - 0.3) / (0.7 - 0.3)
            return min_mult + (normalized * (max_mult - min_mult))

    def _calculate_drawdown_multiplier(self, drawdown_pct: float) -> float:
        """Reduce size during drawdowns."""
        tiers = self.risk_config.get('drawdown', {}).get('tiers', {})

        # Default tiers
        if not tiers:
            tiers = {
                'normal': [0, 5, 1.0],
                'caution': [5, 10, 0.75],
                'warning': [10, 15, 0.5],
                'critical': [15, 100, 0.25]
            }

        for tier_name, (min_dd, max_dd, multiplier) in tiers.items():
            if min_dd <= drawdown_pct < max_dd:
                return multiplier

        return 0.25  # Maximum drawdown protection

    def _check_correlation(
        self,
        ticker: str,
        open_positions: List[Dict[str, Any]],
        proposed_contracts: int,
        entry_price: float,
        account_value: float
    ) -> Dict[str, Any]:
        """Check if adding position would exceed correlation limits."""
        if not self.risk_config.get('correlation', {}).get('enabled', False):
            return {'limited': False}

        max_correlated_risk = self.risk_config.get('correlation', {}).get('max_correlated_risk_pct', 0.06)

        # Define correlation groups (simplified)
        correlation_groups = {
            'TECH': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA'],
            'SPY_RELATED': ['SPY', 'SPX', 'QQQ', 'DIA', 'IWM'],
            'FINANCE': ['JPM', 'BAC', 'GS', 'MS', 'C'],
        }

        # Find ticker's group
        ticker_group = None
        for group, tickers in correlation_groups.items():
            if ticker in tickers:
                ticker_group = group
                break

        if not ticker_group:
            return {'limited': False}  # No known correlations

        # Calculate current exposure in this group
        group_risk = 0.0
        for pos in open_positions:
            pos_ticker = pos.get('ticker', '')
            if pos_ticker in correlation_groups.get(ticker_group, []):
                pos_risk = pos.get('risk_dollars', 0)
                group_risk += pos_risk

        # Calculate proposed new risk
        new_risk = proposed_contracts * abs(entry_price - proposed_contracts)  # Simplified

        # Check if adding would exceed limit
        total_risk_pct = (group_risk + new_risk) / account_value

        if total_risk_pct > max_correlated_risk:
            # Calculate max allowed contracts
            allowed_risk = (max_correlated_risk * account_value) - group_risk
            max_contracts = max(1, int(allowed_risk / abs(entry_price * 0.5)))  # Rough estimate

            return {
                'limited': True,
                'group': ticker_group,
                'current_group_risk_pct': round(group_risk / account_value * 100, 2),
                'max_allowed_pct': round(max_correlated_risk * 100, 2),
                'max_contracts': max_contracts,
                'original_contracts': proposed_contracts
            }

        return {'limited': False}

    def _fixed_sizing(
        self,
        account_value: float,
        risk_per_contract: float
    ) -> Dict[str, Any]:
        """Simple fixed percentage sizing."""
        risk_pct = 0.02  # 2%
        risk_dollars = account_value * risk_pct
        contracts = max(1, int(risk_dollars / risk_per_contract))

        return {
            'contracts': contracts,
            'risk_pct': round(risk_pct * 100, 2),
            'risk_dollars': round(risk_dollars, 2),
            'sizing_method': 'fixed',
            'reasoning': 'Fixed 2% risk per trade'
        }

    def _build_sizing_reasoning(
        self,
        adjustments: Dict[str, Any],
        setup_score: int
    ) -> str:
        """Build human-readable reasoning for sizing decision."""
        reasons = []

        if 'kelly' in adjustments:
            kelly_data = adjustments['kelly']
            reasons.append(f"Kelly: {kelly_data['multiplier']}x (optimal: {kelly_data['kelly_pct']}%)")

        if 'volatility' in adjustments:
            vol_data = adjustments['volatility']
            if vol_data['multiplier'] < 1.0:
                reasons.append(f"High IV (rank {vol_data['iv_rank']}): size reduced to {vol_data['multiplier']}x")
            elif vol_data['multiplier'] > 1.0:
                reasons.append(f"Low IV (rank {vol_data['iv_rank']}): size increased to {vol_data['multiplier']}x")

        if 'setup_quality' in adjustments:
            qual_data = adjustments['setup_quality']
            if qual_data['multiplier'] > 1.0:
                reasons.append(f"Exceptional setup ({setup_score}/100): size increased to {qual_data['multiplier']}x")
            elif qual_data['multiplier'] < 1.0:
                reasons.append(f"Lower quality ({setup_score}/100): size reduced to {qual_data['multiplier']}x")

        if 'equity_curve' in adjustments:
            eq_data = adjustments['equity_curve']
            if eq_data['multiplier'] != 1.0:
                reasons.append(f"Recent performance: {eq_data['multiplier']}x")

        if 'drawdown' in adjustments:
            dd_data = adjustments['drawdown']
            reasons.append(f"Drawdown protection ({dd_data['current_dd_pct']}%): {dd_data['multiplier']}x")

        if 'correlation' in adjustments:
            corr_data = adjustments['correlation']
            reasons.append(f"Correlation limit ({corr_data['group']}): reduced to {corr_data['max_contracts']} contracts")

        if 'position_limit' in adjustments:
            reasons.append("Position size limit applied")

        return " | ".join(reasons) if reasons else "Standard sizing"


# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        'sizing': {
            'method': 'composite',
            'kelly': {
                'enabled': True,
                'fractional_kelly': 0.25,
                'min_trades_for_kelly': 30
            },
            'volatility': {
                'enabled': True,
                'adjustment_range': [0.5, 1.5],
                'high_iv_threshold': 70,
                'low_iv_threshold': 30
            },
            'setup_quality': {
                'enabled': True,
                'score_brackets': {
                    'exceptional': [90, 100, 1.5],
                    'high': [80, 89, 1.25],
                    'good': [70, 79, 1.0],
                    'medium': [60, 69, 0.75]
                }
            }
        },
        'risk_management': {
            'limits': {
                'max_position_pct': 0.25,
                'max_risk_per_trade': 0.05
            },
            'drawdown': {
                'tiers': {
                    'normal': [0, 5, 1.0],
                    'caution': [5, 10, 0.75]
                }
            }
        }
    }

    sizer = PositionSizer(config)

    # Test scenario: Exceptional setup (95/100), low IV (25), good recent performance
    result = sizer.calculate_position_size(
        account_value=100000,
        entry_price=2.50,
        stop_loss=1.25,
        setup_score=95,
        iv_rank=25,
        current_drawdown_pct=0.0
    )

    print("Position Sizing Result:")
    print(f"  Contracts: {result['contracts']}")
    print(f"  Risk: {result['risk_pct']}% (${result['risk_dollars']})")
    print(f"  Position: {result['position_pct']}% (${result['position_value']})")
    print(f"  Method: {result['sizing_method']}")
    print(f"\nReasoning: {result['reasoning']}")
    print(f"\nAdjustments:")
    for key, val in result.get('adjustments', {}).items():
        print(f"  {key}: {val}")
