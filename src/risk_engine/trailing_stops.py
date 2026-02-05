"""
Dynamic Trailing Stop Management
Combines ATR-based stops with technical levels for optimal exit timing
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class TrailingStopLevel:
    """Represents a trailing stop level"""
    price: float
    type: str  # 'atr', 'technical', 'breakeven'
    reason: str
    priority: int  # Lower = higher priority


class TrailingStopManager:
    """
    Manages dynamic trailing stops that adjust based on price movement
    and technical levels.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize trailing stop manager.

        Args:
            config: Configuration dict from config.yaml
        """
        self.config = config.get('trailing_stops', {})
        self.atr_config = self.config.get('atr_trailing', {})
        self.tech_config = self.config.get('technical_trailing', {})
        self.breakeven_config = self.config.get('breakeven', {})

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        initial_stop: float,
        atr: Optional[float],
        profit_r: float,
        option_type: str,
        sr_zones: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate optimal trailing stop based on price movement and technicals.

        Args:
            entry_price: Entry premium price
            current_price: Current premium price
            initial_stop: Initial stop loss price
            atr: Average True Range
            profit_r: Current profit in R (risk units)
            option_type: 'CALL' or 'PUT'
            sr_zones: Support/resistance analysis
            market_context: Additional market context

        Returns:
            Dict with trailing stop price, type, and reasoning
        """
        candidates = []

        # 1. ATR-Based Trailing Stop
        if atr and self.atr_config.get('enabled', True):
            atr_stop = self._calculate_atr_trailing(
                entry_price,
                current_price,
                initial_stop,
                atr,
                profit_r,
                option_type
            )
            if atr_stop:
                candidates.append(atr_stop)

        # 2. Technical Level Trailing Stop
        if sr_zones and self.tech_config.get('enabled', True):
            tech_stop = self._calculate_technical_trailing(
                entry_price,
                current_price,
                initial_stop,
                sr_zones,
                option_type,
                market_context
            )
            if tech_stop:
                candidates.append(tech_stop)

        # 3. Breakeven Stop (at R trigger points)
        if profit_r >= self.breakeven_config.get('r_trigger', 2.0):
            breakeven_stop = self._calculate_breakeven_stop(
                entry_price,
                current_price,
                profit_r,
                option_type
            )
            if breakeven_stop:
                candidates.append(breakeven_stop)

        # Select best stop (highest for CALL, lowest for PUT, but above entry)
        if not candidates:
            return {
                'trailing_stop': initial_stop,
                'type': 'initial',
                'reason': 'Using initial stop loss',
                'active': False
            }

        # Sort by priority and select best
        candidates.sort(key=lambda x: x.priority)
        best_stop = candidates[0]

        # Ensure stop never goes below initial stop (risk reduction only)
        final_price = max(best_stop.price, initial_stop) if option_type == 'CALL' else \
                      min(best_stop.price, initial_stop)

        return {
            'trailing_stop': round(final_price, 2),
            'type': best_stop.type,
            'reason': best_stop.reason,
            'active': True,
            'profit_r': profit_r,
            'all_candidates': [
                {'price': c.price, 'type': c.type, 'reason': c.reason}
                for c in candidates
            ]
        }

    def _calculate_atr_trailing(
        self,
        entry_price: float,
        current_price: float,
        initial_stop: float,
        atr: float,
        profit_r: float,
        option_type: str
    ) -> Optional[TrailingStopLevel]:
        """Calculate ATR-based trailing stop that tightens with profit."""
        # Use different multipliers based on profit level
        if profit_r >= 4.0:
            mult = self.atr_config.get('high_multiplier', 2.5)
            phase = 'high profit'
        elif profit_r >= 2.0:
            mult = self.atr_config.get('mid_multiplier', 2.0)
            phase = 'mid profit'
        else:
            mult = self.atr_config.get('initial_multiplier', 1.5)
            phase = 'initial'

        # Trail at entry + profit - (ATR * multiplier)
        if option_type == 'CALL':
            profit = current_price - entry_price
            atr_stop = entry_price + profit - (mult * atr)
        else:
            profit = entry_price - current_price
            atr_stop = entry_price - profit + (mult * atr)

        # Ensure it's tighter than initial stop
        if option_type == 'CALL':
            if atr_stop <= initial_stop:
                return None
        else:
            if atr_stop >= initial_stop:
                return None

        return TrailingStopLevel(
            price=atr_stop,
            type='atr',
            reason=f"ATR trailing ({phase}): {mult}x ATR below peak",
            priority=2
        )

    def _calculate_technical_trailing(
        self,
        entry_price: float,
        current_price: float,
        initial_stop: float,
        sr_zones: Dict[str, Any],
        option_type: str,
        market_context: Optional[Dict[str, Any]] = None
    ) -> Optional[TrailingStopLevel]:
        """Trail to highest support above breakeven."""
        min_distance = self.tech_config.get('min_distance_from_entry', 0.5)

        key_levels = sr_zones.get('key_levels', {})

        if option_type == 'CALL':
            # Look for highest support above breakeven
            support_zones = sr_zones.get('support_zones', [])
            valid_supports = [
                z for z in support_zones
                if z.get('price', 0) > entry_price * (1 + min_distance / 100)
                and z.get('price', 0) < current_price
            ]

            if not valid_supports:
                return None

            # Use highest support with best strength
            best_support = max(valid_supports, key=lambda z: (z.get('price', 0), z.get('strength', 0)))
            stop_price = best_support.get('price', 0)

            return TrailingStopLevel(
                price=stop_price,
                type='technical',
                reason=f"Technical support at ${stop_price:.2f} (strength: {best_support.get('strength', 0)})",
                priority=1  # Higher priority than ATR
            )
        else:
            # For PUTs, look for lowest resistance below entry
            resistance_zones = sr_zones.get('resistance_zones', [])
            valid_resistances = [
                z for z in resistance_zones
                if z.get('price', 0) < entry_price * (1 - min_distance / 100)
                and z.get('price', 0) > current_price
            ]

            if not valid_resistances:
                return None

            best_resistance = min(valid_resistances, key=lambda z: (z.get('price', float('inf')), -z.get('strength', 0)))
            stop_price = best_resistance.get('price', 0)

            return TrailingStopLevel(
                price=stop_price,
                type='technical',
                reason=f"Technical resistance at ${stop_price:.2f} (strength: {best_resistance.get('strength', 0)})",
                priority=1
            )

    def _calculate_breakeven_stop(
        self,
        entry_price: float,
        current_price: float,
        profit_r: float,
        option_type: str
    ) -> Optional[TrailingStopLevel]:
        """Move stop to breakeven at configured R threshold."""
        r_trigger = self.breakeven_config.get('r_trigger', 2.0)

        if profit_r < r_trigger:
            return None

        # Breakeven = entry price (no loss)
        return TrailingStopLevel(
            price=entry_price,
            type='breakeven',
            reason=f"Breakeven stop at {profit_r:.1f}R (triggered at {r_trigger}R)",
            priority=3  # Lower priority than technical/ATR
        )

    def should_exit(
        self,
        current_price: float,
        trailing_stop: float,
        option_type: str
    ) -> bool:
        """
        Check if current price has hit trailing stop.

        Args:
            current_price: Current premium price
            trailing_stop: Current trailing stop level
            option_type: 'CALL' or 'PUT'

        Returns:
            True if stop hit, False otherwise
        """
        if option_type == 'CALL':
            return current_price <= trailing_stop
        else:
            return current_price >= trailing_stop


# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        'trailing_stops': {
            'enabled': True,
            'atr_trailing': {
                'initial_multiplier': 1.5,
                'mid_multiplier': 2.0,
                'high_multiplier': 2.5
            },
            'technical_trailing': {
                'enabled': True,
                'min_distance_from_entry': 0.5
            },
            'breakeven': {
                'r_trigger': 2.0
            }
        }
    }

    manager = TrailingStopManager(config)

    # Test scenario: CALL at $2.50 entry, now at $4.00 (+60% = ~2.4R)
    result = manager.calculate_trailing_stop(
        entry_price=2.50,
        current_price=4.00,
        initial_stop=1.25,
        atr=0.30,
        profit_r=2.4,
        option_type='CALL',
        sr_zones={
            'support_zones': [
                {'price': 3.20, 'strength': 75, 'touches': 3}
            ]
        }
    )

    print("Trailing Stop Result:")
    print(f"  Stop Price: ${result['trailing_stop']}")
    print(f"  Type: {result['type']}")
    print(f"  Reason: {result['reason']}")
    print(f"  Active: {result['active']}")
