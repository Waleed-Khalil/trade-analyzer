"""
Partial Exit Management
Multi-level profit taking strategy (40/30/30 scaling)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ExitLevel:
    """Represents a partial exit level"""
    price: float
    contracts_pct: float
    r_multiple: float
    trigger_type: str  # 'technical', 'r_based', 'percentage'
    reason: str


class PartialExitManager:
    """
    Manages multi-level profit taking with dynamic scaling
    based on technical levels and R multiples.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize partial exit manager.

        Args:
            config: Configuration dict from config.yaml
        """
        self.config = config.get('partial_exits', {})
        self.scaling_method = self.config.get('scaling_method', 'technical_weighted')

        # Default scaling percentages
        self.r_based_config = self.config.get('r_based', {})
        self.t1_pct = self.r_based_config.get('t1_contracts_pct', 0.40)
        self.t2_pct = self.r_based_config.get('t2_contracts_pct', 0.30)
        self.runner_pct = self.r_based_config.get('runner_contracts_pct', 0.30)

        # Percentage-based config
        self.pct_config = self.config.get('percentage', {})

    def calculate_partial_exit_plan(
        self,
        entry_price: float,
        stop_loss: float,
        total_contracts: int,
        option_type: str,
        sr_zones: Optional[Dict[str, Any]] = None,
        target_1: Optional[float] = None,
        target_2: Optional[float] = None,
        runner_target: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate partial exit plan with multiple levels.

        Args:
            entry_price: Entry premium price
            stop_loss: Stop loss price
            total_contracts: Total number of contracts
            option_type: 'CALL' or 'PUT'
            sr_zones: Support/resistance analysis
            target_1: First target price
            target_2: Second target price
            runner_target: Runner target price

        Returns:
            Dict with exit levels, contract allocation, and reasoning
        """
        risk = abs(entry_price - stop_loss)

        if self.scaling_method == 'percentage':
            return self._percentage_based_exits(
                entry_price,
                risk,
                total_contracts,
                option_type
            )
        elif self.scaling_method == 'technical_weighted' and sr_zones:
            return self._technical_weighted_exits(
                entry_price,
                risk,
                total_contracts,
                option_type,
                sr_zones
            )
        elif self.scaling_method == 'r_based':
            return self._r_based_exits(
                entry_price,
                risk,
                total_contracts,
                option_type,
                target_1,
                target_2,
                runner_target
            )
        else:
            # Equal thirds as fallback
            return self._equal_thirds_exits(
                entry_price,
                risk,
                total_contracts,
                option_type,
                target_1,
                target_2,
                runner_target
            )

    def _technical_weighted_exits(
        self,
        entry_price: float,
        risk: float,
        total_contracts: int,
        option_type: str,
        sr_zones: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create exit plan based on technical resistance/support levels."""
        exit_levels = []

        # Get relevant S/R zones
        if option_type == 'CALL':
            zones = sr_zones.get('resistance_zones', [])
            zones = sorted([z for z in zones if z.get('price', 0) > entry_price],
                          key=lambda z: z.get('price', 0))
        else:
            zones = sr_zones.get('support_zones', [])
            zones = sorted([z for z in zones if z.get('price', 0) < entry_price],
                          key=lambda z: -z.get('price', 0))

        if len(zones) >= 3:
            # Map zones to exit levels
            # T1: First resistance (40% of contracts)
            r1 = abs(zones[0]['price'] - entry_price) / risk
            exit_levels.append(ExitLevel(
                price=zones[0]['price'],
                contracts_pct=0.40,
                r_multiple=r1,
                trigger_type='technical',
                reason=f"First resistance at ${zones[0]['price']:.2f} (strength: {zones[0].get('strength', 0)})"
            ))

            # T2: Second resistance (30% of contracts)
            r2 = abs(zones[1]['price'] - entry_price) / risk
            exit_levels.append(ExitLevel(
                price=zones[1]['price'],
                contracts_pct=0.30,
                r_multiple=r2,
                trigger_type='technical',
                reason=f"Second resistance at ${zones[1]['price']:.2f} (strength: {zones[1].get('strength', 0)})"
            ))

            # Runner: Third resistance or beyond (30% of contracts)
            r3 = abs(zones[2]['price'] - entry_price) / risk
            exit_levels.append(ExitLevel(
                price=zones[2]['price'],
                contracts_pct=0.30,
                r_multiple=r3,
                trigger_type='technical',
                reason=f"Runner at ${zones[2]['price']:.2f} (major resistance, strength: {zones[2].get('strength', 0)})"
            ))
        elif len(zones) >= 2:
            # Only 2 levels available
            r1 = abs(zones[0]['price'] - entry_price) / risk
            exit_levels.append(ExitLevel(
                price=zones[0]['price'],
                contracts_pct=0.50,
                r_multiple=r1,
                trigger_type='technical',
                reason=f"First resistance at ${zones[0]['price']:.2f}"
            ))

            r2 = abs(zones[1]['price'] - entry_price) / risk
            exit_levels.append(ExitLevel(
                price=zones[1]['price'],
                contracts_pct=0.50,
                r_multiple=r2,
                trigger_type='technical',
                reason=f"Second resistance at ${zones[1]['price']:.2f}"
            ))
        else:
            # Fall back to R-based if insufficient technical levels
            return self._r_based_exits(entry_price, risk, total_contracts, option_type, None, None, None)

        return self._build_exit_plan(exit_levels, total_contracts, entry_price, option_type)

    def _percentage_based_exits(
        self,
        entry_price: float,
        risk: float,
        total_contracts: int,
        option_type: str
    ) -> Dict[str, Any]:
        """Create exit plan based on percentage profit targets."""
        exit_levels = []

        target_pct = self.pct_config.get('target_pct', 0.20)
        t1_contracts_pct = self.pct_config.get('t1_contracts_pct', 0.50)
        runner_contracts_pct = self.pct_config.get('runner_contracts_pct', 0.50)

        # T1: +20% premium (50% of contracts)
        t1_price = entry_price * (1 + target_pct)
        t1_r = (t1_price - entry_price) / risk if risk > 0 else 0
        exit_levels.append(ExitLevel(
            price=t1_price,
            contracts_pct=t1_contracts_pct,
            r_multiple=t1_r,
            trigger_type='percentage',
            reason=f"T1 at +{target_pct:.0%} premium (${t1_price:.2f}) — take {t1_contracts_pct:.0%}, move stop to breakeven"
        ))

        # Runner: +40% premium (2x the target) as stretch goal (remaining contracts)
        stretch_pct = target_pct * 2
        runner_price = entry_price * (1 + stretch_pct)
        runner_r = (runner_price - entry_price) / risk if risk > 0 else 0
        exit_levels.append(ExitLevel(
            price=runner_price,
            contracts_pct=runner_contracts_pct,
            r_multiple=runner_r,
            trigger_type='percentage',
            reason=f"Runner at +{stretch_pct:.0%} premium (${runner_price:.2f}) — trail with breakeven stop"
        ))

        return self._build_exit_plan(exit_levels, total_contracts, entry_price, option_type)

    def _r_based_exits(
        self,
        entry_price: float,
        risk: float,
        total_contracts: int,
        option_type: str,
        target_1: Optional[float],
        target_2: Optional[float],
        runner_target: Optional[float]
    ) -> Dict[str, Any]:
        """Create exit plan based on R multiples."""
        exit_levels = []

        # T1: 2R (40% of contracts)
        t1_price = target_1 or (entry_price + 2 * risk if option_type == 'CALL' else entry_price - 2 * risk)
        exit_levels.append(ExitLevel(
            price=t1_price,
            contracts_pct=self.t1_pct,
            r_multiple=2.0,
            trigger_type='r_based',
            reason=f"T1 at 2R (${t1_price:.2f})"
        ))

        # T2: 3R (30% of contracts)
        t2_price = target_2 or (entry_price + 3 * risk if option_type == 'CALL' else entry_price - 3 * risk)
        exit_levels.append(ExitLevel(
            price=t2_price,
            contracts_pct=self.t2_pct,
            r_multiple=3.0,
            trigger_type='r_based',
            reason=f"T2 at 3R (${t2_price:.2f})"
        ))

        # Runner: 5R (30% of contracts)
        runner_price = runner_target or (entry_price + 5 * risk if option_type == 'CALL' else entry_price - 5 * risk)
        exit_levels.append(ExitLevel(
            price=runner_price,
            contracts_pct=self.runner_pct,
            r_multiple=5.0,
            trigger_type='r_based',
            reason=f"Runner at 5R (${runner_price:.2f})"
        ))

        return self._build_exit_plan(exit_levels, total_contracts, entry_price, option_type)

    def _equal_thirds_exits(
        self,
        entry_price: float,
        risk: float,
        total_contracts: int,
        option_type: str,
        target_1: Optional[float],
        target_2: Optional[float],
        runner_target: Optional[float]
    ) -> Dict[str, Any]:
        """Create simple equal-thirds exit plan."""
        exit_levels = []

        # Equal 33.3% at each level
        t1_price = target_1 or (entry_price + 2 * risk if option_type == 'CALL' else entry_price - 2 * risk)
        exit_levels.append(ExitLevel(
            price=t1_price,
            contracts_pct=0.333,
            r_multiple=2.0,
            trigger_type='equal',
            reason=f"1/3 at T1 (${t1_price:.2f})"
        ))

        t2_price = target_2 or (entry_price + 3 * risk if option_type == 'CALL' else entry_price - 3 * risk)
        exit_levels.append(ExitLevel(
            price=t2_price,
            contracts_pct=0.333,
            r_multiple=3.0,
            trigger_type='equal',
            reason=f"1/3 at T2 (${t2_price:.2f})"
        ))

        runner_price = runner_target or (entry_price + 5 * risk if option_type == 'CALL' else entry_price - 5 * risk)
        exit_levels.append(ExitLevel(
            price=runner_price,
            contracts_pct=0.334,
            r_multiple=5.0,
            trigger_type='equal',
            reason=f"1/3 runner (${runner_price:.2f})"
        ))

        return self._build_exit_plan(exit_levels, total_contracts, entry_price, option_type)

    def _build_exit_plan(
        self,
        exit_levels: List[ExitLevel],
        total_contracts: int,
        entry_price: float,
        option_type: str
    ) -> Dict[str, Any]:
        """Build final exit plan with contract allocation."""
        plan = {
            'total_contracts': total_contracts,
            'exit_levels': [],
            'scaling_method': self.scaling_method,
            'expected_total_r': 0.0
        }

        remaining_contracts = total_contracts
        total_weighted_r = 0.0

        for i, level in enumerate(exit_levels):
            # Calculate contracts for this level
            if i == len(exit_levels) - 1:
                # Last level gets all remaining
                contracts = remaining_contracts
            else:
                contracts = int(total_contracts * level.contracts_pct)

            remaining_contracts -= contracts

            plan['exit_levels'].append({
                'level': i + 1,
                'price': round(level.price, 2),
                'contracts': contracts,
                'contracts_pct': round(contracts / total_contracts * 100, 1),
                'r_multiple': round(level.r_multiple, 1),
                'trigger_type': level.trigger_type,
                'reason': level.reason,
                'cumulative_contracts': total_contracts - remaining_contracts
            })

            # Calculate weighted R contribution
            total_weighted_r += level.r_multiple * (contracts / total_contracts)

        plan['expected_total_r'] = round(total_weighted_r, 1)

        return plan

    def get_next_exit(
        self,
        exit_plan: Dict[str, Any],
        contracts_remaining: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the next exit level to watch for.

        Args:
            exit_plan: Exit plan from calculate_partial_exit_plan()
            contracts_remaining: Number of contracts still open

        Returns:
            Next exit level dict or None if all exits complete
        """
        if contracts_remaining <= 0:
            return None

        for level in exit_plan['exit_levels']:
            if level['contracts'] > 0:
                # Find first level with contracts
                contracts_exited = exit_plan['total_contracts'] - contracts_remaining

                # Check if this level should be next
                if contracts_exited < level['cumulative_contracts']:
                    return level

        return None


# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        'partial_exits': {
            'enabled': True,
            'scaling_method': 'technical_weighted',
            'r_based': {
                't1_contracts_pct': 0.40,
                't2_contracts_pct': 0.30,
                'runner_contracts_pct': 0.30
            }
        }
    }

    manager = PartialExitManager(config)

    # Test scenario: CALL with 10 contracts at $2.50, stop at $1.25
    sr_zones = {
        'resistance_zones': [
            {'price': 3.50, 'strength': 75, 'touches': 3},
            {'price': 4.20, 'strength': 65, 'touches': 2},
            {'price': 5.50, 'strength': 80, 'touches': 4}
        ]
    }

    plan = manager.calculate_partial_exit_plan(
        entry_price=2.50,
        stop_loss=1.25,
        total_contracts=10,
        option_type='CALL',
        sr_zones=sr_zones
    )

    print("Partial Exit Plan:")
    print(f"  Total Contracts: {plan['total_contracts']}")
    print(f"  Scaling Method: {plan['scaling_method']}")
    print(f"  Expected Total R: {plan['expected_total_r']}R\n")

    for level in plan['exit_levels']:
        print(f"Level {level['level']}:")
        print(f"  Price: ${level['price']}")
        print(f"  Contracts: {level['contracts']} ({level['contracts_pct']}%)")
        print(f"  R Multiple: {level['r_multiple']}R")
        print(f"  Reason: {level['reason']}\n")
