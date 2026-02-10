"""
Live Trade Monitor - Real-Time Coaching After Entry
Monitors position and alerts on breakouts, rejections, stops
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import yfinance as yf
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any, Optional

from src.analysis.price_action import calculate_support_resistance_zones
from src.analysis.exit_patterns import (
    detect_resistance_breakout,
    detect_resistance_rejection,
    get_next_resistance_level
)


class LiveTradeMonitor:
    """
    Monitors a live option position and provides real-time alerts.
    """

    def __init__(
        self,
        ticker: str,
        strike: float,
        option_type: str,
        entry_premium: float,
        entry_underlying: float,
        contracts: int = 5,
        dte: int = 7,
        stop_loss_premium: Optional[float] = None,
        poll_interval: int = 300  # 5 minutes default
    ):
        """
        Initialize live monitor.

        Args:
            ticker: Stock ticker
            strike: Option strike
            option_type: CALL or PUT
            entry_premium: Entry option price
            entry_underlying: Underlying price at entry
            contracts: Number of contracts
            dte: Days to expiration
            stop_loss_premium: Stop loss price (default: 50% of premium)
            poll_interval: Seconds between checks (default: 300 = 5 min)
        """
        self.ticker = ticker.upper()
        self.strike = strike
        self.option_type = option_type.upper()
        self.entry_premium = entry_premium
        self.entry_underlying = entry_underlying
        self.contracts = contracts
        self.dte = dte
        self.poll_interval = poll_interval

        # Risk parameters
        if stop_loss_premium is None:
            self.stop_loss_premium = entry_premium * 0.5  # Default 50% stop
        else:
            self.stop_loss_premium = stop_loss_premium

        self.risk_per_contract = entry_premium - self.stop_loss_premium

        # State tracking
        self.entry_time = datetime.now()
        self.position_open = True
        self.contracts_remaining = contracts
        self.alerts_sent = []
        self.highest_premium = entry_premium
        self.trailing_stop = self.stop_loss_premium

        # Fetch initial S/R zones
        print(f"\n{'='*80}")
        print(f"  LIVE MONITOR: {self.ticker} {self.strike} {self.option_type}")
        print(f"{'='*80}")
        print(f"\nInitializing position...")
        print(f"  Entry Premium: ${self.entry_premium:.2f}")
        print(f"  Entry Underlying: ${self.entry_underlying:.2f}")
        print(f"  Contracts: {self.contracts}")
        print(f"  Stop Loss: ${self.stop_loss_premium:.2f} (-{((entry_premium - self.stop_loss_premium)/entry_premium*100):.1f}%)")
        print(f"  Risk per Contract: ${self.risk_per_contract:.2f}")
        print(f"  DTE: {self.dte} days\n")

        # Calculate initial resistance zones
        self._update_sr_zones()

        print(f"Monitoring started at {self.entry_time.strftime('%H:%M:%S')}")
        print(f"Polling every {self.poll_interval//60} minutes\n")
        print(f"{'='*80}\n")

    def _update_sr_zones(self):
        """Update support/resistance zones."""
        try:
            df = yf.download(self.ticker, period="3mo", interval="1d", progress=False)

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0].lower() for col in df.columns]
            else:
                df.columns = [str(col).lower() for col in df.columns]

            # Calculate ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]

            # Calculate zones
            current_price = df['close'].iloc[-1]
            self.sr_zones = calculate_support_resistance_zones(
                df=df,
                current_price=current_price,
                ticker=self.ticker,
                lookback_days=60,
                atr=atr,
                max_levels=5
            )

            self.current_underlying = current_price
            self.atr = atr

            # Display key levels
            if self.option_type == 'CALL':
                resistance_zones = self.sr_zones.get('resistance_zones', [])
                if resistance_zones:
                    print("Key Resistance Levels to Watch:")
                    for i, zone in enumerate(resistance_zones[:3]):
                        distance = (zone['price'] - current_price) / current_price * 100
                        print(f"  R{i+1}: ${zone['price']:.2f} (+{distance:.1f}%) - Strength: {zone['strength']:.0f}")
                    print()
            else:
                support_zones = self.sr_zones.get('support_zones', [])
                if support_zones:
                    print("Key Support Levels to Watch:")
                    for i, zone in enumerate(support_zones[:3]):
                        distance = (current_price - zone['price']) / current_price * 100
                        print(f"  S{i+1}: ${zone['price']:.2f} (-{distance:.1f}%) - Strength: {zone['strength']:.0f}")
                    print()

        except Exception as e:
            print(f"Warning: Could not update S/R zones: {e}")
            self.sr_zones = {'resistance_zones': [], 'support_zones': []}
            self.current_underlying = self.entry_underlying
            self.atr = 0

    def _estimate_current_premium(self, current_underlying: float) -> float:
        """
        Rough estimate of current option premium based on underlying move.
        Simplified - uses delta approximation.
        """
        underlying_move_pct = (current_underlying - self.entry_underlying) / self.entry_underlying

        # Rough delta approximation
        # ATM calls/puts ~0.5 delta, ITM ~0.7-0.8, OTM ~0.3-0.4
        if self.option_type == 'CALL':
            if self.strike <= self.entry_underlying:
                delta = 0.70  # ITM
            elif self.strike <= self.entry_underlying * 1.02:
                delta = 0.50  # ATM
            else:
                delta = 0.30  # OTM

            # Premium change = underlying move * delta * premium
            premium_change = underlying_move_pct * delta * self.entry_premium * 10
        else:  # PUT
            if self.strike >= self.entry_underlying:
                delta = -0.70  # ITM put
            elif self.strike >= self.entry_underlying * 0.98:
                delta = -0.50  # ATM put
            else:
                delta = -0.30  # OTM put

            # For puts, inverse relationship
            premium_change = -underlying_move_pct * abs(delta) * self.entry_premium * 10

        estimated_premium = self.entry_premium + premium_change

        # Floor at $0.01
        return max(0.01, estimated_premium)

    def _check_for_alerts(self, df: pd.DataFrame) -> list:
        """
        Check for breakout/rejection patterns and generate alerts.

        Returns:
            List of alert dicts with action, reason, urgency
        """
        alerts = []

        if self.option_type == 'CALL':
            resistance_zones = self.sr_zones.get('resistance_zones', [])
            if not resistance_zones:
                return alerts

            # Check first resistance for breakout or rejection
            first_resistance = resistance_zones[0]
            resistance_level = first_resistance['price']
            resistance_strength = first_resistance['strength']

            # Get recent bars (last 20 for breakout detection)
            recent_bars = df.tail(20)

            # Check breakout
            breakout = detect_resistance_breakout(
                df=recent_bars,
                current_price=self.current_underlying,
                resistance_level=resistance_level,
                resistance_strength=resistance_strength
            )

            if breakout['action'] == 'breakout_confirmed':
                # Find next resistance
                next_level = get_next_resistance_level(
                    resistance_zones,
                    resistance_level,
                    self.current_underlying
                )

                alert = {
                    'type': 'BREAKOUT',
                    'action': 'HOLD_RUNNER',
                    'level': resistance_level,
                    'new_stop': breakout['new_stop'],
                    'next_target': next_level,
                    'reason': breakout['reason'],
                    'urgency': 'HIGH'
                }
                alerts.append(alert)

            # Check rejection (last 3 bars)
            rejection = detect_resistance_rejection(
                df=recent_bars.tail(3),
                resistance_level=resistance_level,
                option_type=self.option_type
            )

            if rejection['action'] == 'rejection_detected':
                exit_contracts = int(self.contracts_remaining * rejection['exit_pct'])

                alert = {
                    'type': 'REJECTION',
                    'action': 'EXIT_PARTIAL',
                    'exit_contracts': exit_contracts,
                    'exit_pct': rejection['exit_pct'],
                    'pattern': rejection['pattern'],
                    'reason': rejection['reason'],
                    'urgency': 'HIGH'
                }
                alerts.append(alert)

        else:  # PUT
            support_zones = self.sr_zones.get('support_zones', [])
            if not support_zones:
                return alerts

            # Similar logic for puts (breakdown at support)
            first_support = support_zones[0]
            support_level = first_support['price']

            recent_bars = df.tail(20)

            # Check breakdown (inverse of breakout)
            if self.current_underlying < support_level * 0.995:
                # Breakdown confirmed
                alert = {
                    'type': 'BREAKDOWN',
                    'action': 'HOLD_RUNNER',
                    'level': support_level,
                    'new_stop': support_level * 1.005,
                    'reason': f'Broke support ${support_level:.2f} - hold for extended move',
                    'urgency': 'HIGH'
                }
                alerts.append(alert)

            # Check rejection at support (bullish reversal)
            rejection = detect_resistance_rejection(
                df=recent_bars.tail(3),
                resistance_level=support_level,
                option_type=self.option_type
            )

            if rejection['action'] == 'rejection_detected':
                exit_contracts = int(self.contracts_remaining * rejection['exit_pct'])

                alert = {
                    'type': 'REJECTION',
                    'action': 'EXIT_PARTIAL',
                    'exit_contracts': exit_contracts,
                    'exit_pct': rejection['exit_pct'],
                    'pattern': rejection['pattern'],
                    'reason': rejection['reason'],
                    'urgency': 'HIGH'
                }
                alerts.append(alert)

        return alerts

    def _print_alert(self, alert: Dict[str, Any]):
        """Print alert with formatting."""
        print(f"\n{'!'*80}")
        print(f"  [!] {alert['type']} ALERT - {alert['urgency']} URGENCY")
        print(f"{'!'*80}\n")

        if alert['action'] == 'HOLD_RUNNER':
            print(f"[+] BREAKOUT CONFIRMED at ${alert['level']:.2f}!")
            print(f"\n    ACTION: HOLD ALL {self.contracts_remaining} CONTRACTS")
            print(f"    → Trail stop to ${alert['new_stop']:.2f}")
            if alert.get('next_target'):
                print(f"    → New target: ${alert['next_target']:.2f}")
            print(f"\n    Reason: {alert['reason']}")

        elif alert['action'] == 'EXIT_PARTIAL':
            print(f"[-] REJECTION DETECTED at current level!")
            print(f"    Pattern: {alert['pattern']}")
            print(f"\n    ACTION: EXIT {alert['exit_contracts']} CONTRACTS ({alert['exit_pct']:.0%})")
            print(f"    → Keep {self.contracts_remaining - alert['exit_contracts']} with tight stop")
            print(f"\n    Reason: {alert['reason']}")

        print(f"\n{'!'*80}\n")

    def _print_status(self, estimated_premium: float):
        """Print current position status."""
        # Calculate P/L
        pnl_per_contract = (estimated_premium - self.entry_premium) * 100
        total_pnl = pnl_per_contract * self.contracts_remaining
        pnl_pct = (estimated_premium - self.entry_premium) / self.entry_premium * 100
        r_multiple = (estimated_premium - self.entry_premium) / self.risk_per_contract if self.risk_per_contract > 0 else 0

        # Time elapsed
        elapsed = datetime.now() - self.entry_time
        elapsed_str = f"{elapsed.seconds // 3600}h {(elapsed.seconds % 3600) // 60}m"

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Status Update")
        print(f"{'-'*80}")
        print(f"  Underlying: ${self.current_underlying:.2f} (Entry: ${self.entry_underlying:.2f})")
        print(f"  Est Premium: ${estimated_premium:.2f} (Entry: ${self.entry_premium:.2f})")
        print(f"  P/L: ${total_pnl:+.0f} ({pnl_pct:+.1f}%) | {r_multiple:+.2f}R")
        print(f"  Contracts: {self.contracts_remaining} open")
        print(f"  Stop: ${self.trailing_stop:.2f}")
        print(f"  Time: {elapsed_str} in position")
        print(f"{'-'*80}\n")

        # Check stop hit
        if estimated_premium <= self.trailing_stop:
            print(f"\n[!] STOP HIT at ${estimated_premium:.2f} (Stop: ${self.trailing_stop:.2f})")
            print(f"    EXIT ALL {self.contracts_remaining} CONTRACTS")
            print(f"    Loss: ${total_pnl:.0f} ({pnl_pct:.1f}%)\n")
            self.position_open = False

    def monitor(self):
        """
        Main monitoring loop.
        Runs until position closed or stopped by user.
        """
        try:
            while self.position_open:
                try:
                    # Fetch latest data
                    df = yf.download(
                        self.ticker,
                        period="5d",
                        interval="5m",
                        progress=False
                    )

                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [col[0].lower() for col in df.columns]
                    else:
                        df.columns = [str(col).lower() for col in df.columns]

                    if df.empty:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: No data fetched, retrying...")
                        time.sleep(self.poll_interval)
                        continue

                    # Update current price
                    self.current_underlying = df['close'].iloc[-1]

                    # Estimate option premium
                    estimated_premium = self._estimate_current_premium(self.current_underlying)

                    # Update highest premium for trailing
                    if estimated_premium > self.highest_premium:
                        self.highest_premium = estimated_premium
                        # Trail stop to 50% of profit
                        profit_from_entry = estimated_premium - self.entry_premium
                        self.trailing_stop = self.entry_premium + (profit_from_entry * 0.5)

                    # Print status
                    self._print_status(estimated_premium)

                    # Check for alerts
                    alerts = self._check_for_alerts(df)

                    for alert in alerts:
                        # Check if already sent this alert
                        alert_key = f"{alert['type']}_{alert.get('level', 'N/A')}"
                        if alert_key not in self.alerts_sent:
                            self._print_alert(alert)
                            self.alerts_sent.append(alert_key)

                            # Update state based on alert
                            if alert['action'] == 'EXIT_PARTIAL':
                                self.contracts_remaining -= alert['exit_contracts']
                                if self.contracts_remaining <= 0:
                                    self.position_open = False
                                    print(f"\n[+] All contracts exited. Position closed.\n")
                                    break

                            elif alert['action'] == 'HOLD_RUNNER':
                                # Update stop
                                self.trailing_stop = alert['new_stop']

                    # Sleep until next check
                    if self.position_open:
                        print(f"Next check in {self.poll_interval//60} minutes...")
                        time.sleep(self.poll_interval)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                    time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print(f"  MONITORING STOPPED BY USER")
            print(f"{'='*80}\n")

            # Final summary
            estimated_premium = self._estimate_current_premium(self.current_underlying)
            total_pnl = (estimated_premium - self.entry_premium) * 100 * self.contracts_remaining
            r_multiple = (estimated_premium - self.entry_premium) / self.risk_per_contract if self.risk_per_contract > 0 else 0

            print(f"Final Position Summary:")
            print(f"  Entry: ${self.entry_premium:.2f}")
            print(f"  Current Est: ${estimated_premium:.2f}")
            print(f"  P/L: ${total_pnl:+.0f} ({r_multiple:+.2f}R)")
            print(f"  Contracts: {self.contracts_remaining} still open\n")


# CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live trade monitor - Real-time alerts")
    parser.add_argument("ticker", help="Stock ticker")
    parser.add_argument("strike", type=float, help="Option strike")
    parser.add_argument("type", choices=['CALL', 'PUT', 'call', 'put'], help="Option type")
    parser.add_argument("entry_premium", type=float, help="Entry premium")
    parser.add_argument("entry_underlying", type=float, help="Underlying price at entry")
    parser.add_argument("--contracts", type=int, default=5, help="Number of contracts (default: 5)")
    parser.add_argument("--dte", type=int, default=7, help="Days to expiration (default: 7)")
    parser.add_argument("--stop", type=float, help="Stop loss premium (default: 50% of entry)")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds (default: 300 = 5min)")

    args = parser.parse_args()

    monitor = LiveTradeMonitor(
        ticker=args.ticker.upper(),
        strike=args.strike,
        option_type=args.type.upper(),
        entry_premium=args.entry_premium,
        entry_underlying=args.entry_underlying,
        contracts=args.contracts,
        dte=args.dte,
        stop_loss_premium=args.stop,
        poll_interval=args.interval
    )

    print(f"Press Ctrl+C to stop monitoring\n")
    monitor.monitor()
