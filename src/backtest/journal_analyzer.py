"""
Simple Journal Analyzer - Backtest Resistance-Based Exits
Compares OLD exit strategy vs NEW (breakout/rejection) strategy on historical trades
"""

import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import yaml

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.analysis.price_action import calculate_support_resistance_zones
from src.analysis.exit_patterns import (
    detect_resistance_breakout,
    detect_resistance_rejection,
    get_next_resistance_level
)


class JournalAnalyzer:
    """
    Analyzes historical trades and compares OLD vs NEW exit strategies.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize analyzer with config."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.journal_config = self.config.get('journal', {})
        self.journal_path = self.journal_config.get('log_path', 'logs/journal.csv')

    def load_journal(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Load trade journal from CSV.

        Args:
            limit: Optional limit on number of trades to analyze

        Returns:
            DataFrame with trade data
        """
        if not os.path.exists(self.journal_path):
            raise FileNotFoundError(f"Journal not found: {self.journal_path}")

        df = pd.read_csv(self.journal_path)

        if limit:
            df = df.head(limit)

        # Parse timestamps and remove timezone for comparison
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)

        print(f"Loaded {len(df)} trades from journal")
        return df

    def fetch_price_history(
        self,
        ticker: str,
        start_date: datetime,
        days_forward: int = 30
    ) -> pd.DataFrame:
        """
        Fetch historical price data for analysis.

        Args:
            ticker: Stock ticker
            start_date: Trade entry date
            days_forward: Days to fetch forward from entry

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Fetch from 60 days before (for S/R zones) to 30 days after entry
            lookback_start = start_date - timedelta(days=60)
            end_date = start_date + timedelta(days=days_forward)

            df = yf.download(
                ticker,
                start=lookback_start.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )

            # Flatten columns if MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0].lower() for col in df.columns]
            else:
                df.columns = [str(col).lower() for col in df.columns]

            return df

        except Exception as e:
            print(f"  Warning: Could not fetch data for {ticker}: {e}")
            return pd.DataFrame()

    def simulate_old_exit(
        self,
        trade: pd.Series,
        price_df: pd.DataFrame,
        entry_date: datetime
    ) -> Dict[str, Any]:
        """
        Simulate OLD exit strategy (simple target-based).

        Uses the t1_premium from journal as first target.

        Args:
            trade: Trade row from journal
            price_df: Historical price data
            entry_date: Entry datetime

        Returns:
            Dict with exit results
        """
        entry_premium = trade['entry_premium']
        t1_premium = trade['t1_premium']
        sl_premium = trade['sl_premium']
        contracts = trade['contracts']

        # Calculate risk
        risk = entry_premium - sl_premium

        # Simple simulation: assume hit T1 if underlying moved favorably
        # This is simplified - in reality would use Black-Scholes
        try:
            # Find entry bar
            entry_idx = price_df.index[price_df.index >= entry_date][0]
            entry_price = price_df.loc[entry_idx, 'close']

            # Look at next 5-10 days
            future_bars = price_df.loc[entry_idx:].head(10)

            # For CALL: look for upward move
            if trade['option_type'] == 'CALL':
                # Check if price moved up enough to hit target
                max_price = future_bars['high'].max()
                price_move_pct = (max_price - entry_price) / entry_price

                # Rough approximation: 2% underlying move = ~40% option premium gain for ATM calls
                # This is simplified - real backtest would use Greeks
                option_gain_pct = price_move_pct * 20  # Rough delta approximation

                if option_gain_pct >= (t1_premium - entry_premium) / entry_premium:
                    # Hit target
                    exit_premium = t1_premium
                    exit_date = future_bars.index[
                        future_bars['high'] >= entry_price * (1 + price_move_pct * 0.5)
                    ][0]
                    r_achieved = (exit_premium - entry_premium) / risk
                    exit_reason = "Hit T1 target"
                else:
                    # Assume held for 5 days, modest gain
                    exit_premium = entry_premium * 1.1
                    exit_date = future_bars.index[min(5, len(future_bars) - 1)]
                    r_achieved = (exit_premium - entry_premium) / risk
                    exit_reason = "Time exit (5 days)"

            else:  # PUT
                # Similar logic for puts
                min_price = future_bars['low'].min()
                price_move_pct = (entry_price - min_price) / entry_price
                option_gain_pct = price_move_pct * 20

                if option_gain_pct >= (t1_premium - entry_premium) / entry_premium:
                    exit_premium = t1_premium
                    exit_date = future_bars.index[0]
                    r_achieved = (exit_premium - entry_premium) / risk
                    exit_reason = "Hit T1 target"
                else:
                    exit_premium = entry_premium * 1.1
                    exit_date = future_bars.index[min(5, len(future_bars) - 1)]
                    r_achieved = (exit_premium - entry_premium) / risk
                    exit_reason = "Time exit (5 days)"

            pnl = (exit_premium - entry_premium) * contracts * 100

            return {
                'exit_premium': exit_premium,
                'exit_date': exit_date,
                'r_achieved': r_achieved,
                'pnl': pnl,
                'exit_reason': exit_reason
            }

        except Exception as e:
            print(f"    Error simulating old exit: {e}")
            return {
                'exit_premium': entry_premium,
                'exit_date': entry_date,
                'r_achieved': 0.0,
                'pnl': 0.0,
                'exit_reason': 'Simulation error'
            }

    def simulate_new_exit(
        self,
        trade: pd.Series,
        price_df: pd.DataFrame,
        entry_date: datetime
    ) -> Dict[str, Any]:
        """
        Simulate NEW exit strategy with breakout/rejection detection.

        Args:
            trade: Trade row from journal
            price_df: Historical price data
            entry_date: Entry datetime

        Returns:
            Dict with exit results
        """
        entry_premium = trade['entry_premium']
        sl_premium = trade['sl_premium']
        contracts = trade['contracts']
        risk = entry_premium - sl_premium

        try:
            # Find entry bar
            entry_idx = price_df.index[price_df.index >= entry_date][0]
            entry_price = price_df.loc[entry_idx, 'close']

            # Calculate resistance zones at entry
            historical_df = price_df.loc[:entry_idx]

            # Calculate ATR
            high_low = historical_df['high'] - historical_df['low']
            high_close = abs(historical_df['high'] - historical_df['close'].shift())
            low_close = abs(historical_df['low'] - historical_df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]

            sr_zones = calculate_support_resistance_zones(
                df=historical_df,
                current_price=entry_price,
                ticker=trade['ticker'],
                lookback_days=60,
                atr=atr
            )

            resistance_zones = sr_zones.get('resistance_zones', [])

            if not resistance_zones:
                # No resistance zones - fall back to old logic
                return self.simulate_old_exit(trade, price_df, entry_date)

            # Simulate walking forward day by day
            future_bars = price_df.loc[entry_idx:].head(10)
            first_resistance = resistance_zones[0]['price']

            exit_triggered = False
            exit_premium = entry_premium
            exit_reason = ""
            current_contracts = contracts

            for i, (date, bar) in enumerate(future_bars.iterrows()):
                if i == 0:
                    continue  # Skip entry bar

                current_price = bar['close']

                # Check for breakout
                recent_bars = future_bars.iloc[max(0, i - 20):i + 1]
                breakout = detect_resistance_breakout(
                    df=recent_bars,
                    current_price=current_price,
                    resistance_level=first_resistance,
                    resistance_strength=resistance_zones[0].get('strength', 50)
                )

                if breakout['action'] == 'breakout_confirmed':
                    # Breakout! Hold for next level
                    next_level = get_next_resistance_level(
                        resistance_zones, first_resistance, current_price
                    )

                    if next_level:
                        # Continue to next resistance
                        # Approximate premium gain
                        price_gain_pct = (current_price - entry_price) / entry_price
                        exit_premium = entry_premium * (1 + price_gain_pct * 15)  # Rough delta
                        exit_reason = f"Breakout at R1, held to ${next_level:.2f}"
                    else:
                        # No next level, take profit
                        price_gain_pct = (current_price - entry_price) / entry_price
                        exit_premium = entry_premium * (1 + price_gain_pct * 15)
                        exit_reason = "Breakout confirmed, no next R"

                    exit_triggered = True
                    exit_date = date
                    break

                # Check for rejection
                rejection = detect_resistance_rejection(
                    df=recent_bars.tail(3),
                    resistance_level=first_resistance,
                    option_type=trade['option_type']
                )

                if rejection['action'] == 'rejection_detected':
                    # Rejection! Exit more contracts
                    exit_pct = rejection['exit_pct']
                    price_gain_pct = (current_price - entry_price) / entry_price
                    exit_premium = entry_premium * (1 + price_gain_pct * 15)  # Rough delta
                    exit_reason = f"Rejection at R1 ({rejection['pattern']}), exit {exit_pct:.0%}"
                    exit_triggered = True
                    exit_date = date
                    break

                # Check if hit first resistance (standard exit)
                if current_price >= first_resistance * 0.995:
                    price_gain_pct = (current_price - entry_price) / entry_price
                    exit_premium = entry_premium * (1 + price_gain_pct * 15)
                    exit_reason = "Hit R1 (standard exit)"
                    exit_triggered = True
                    exit_date = date
                    break

            if not exit_triggered:
                # Time exit after 5 days
                exit_date = future_bars.index[min(5, len(future_bars) - 1)]
                final_price = future_bars.loc[exit_date, 'close']
                price_gain_pct = (final_price - entry_price) / entry_price
                exit_premium = entry_premium * (1 + price_gain_pct * 15)
                exit_reason = "Time exit (5 days)"

            r_achieved = (exit_premium - entry_premium) / risk if risk > 0 else 0
            pnl = (exit_premium - entry_premium) * contracts * 100

            return {
                'exit_premium': exit_premium,
                'exit_date': exit_date,
                'r_achieved': r_achieved,
                'pnl': pnl,
                'exit_reason': exit_reason,
                'resistance_zones': resistance_zones
            }

        except Exception as e:
            print(f"    Error simulating new exit: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to old exit
            return self.simulate_old_exit(trade, price_df, entry_date)

    def analyze_trades(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Main analysis function - compare OLD vs NEW for all trades.

        Args:
            limit: Optional limit on trades to analyze

        Returns:
            DataFrame with comparison results
        """
        journal = self.load_journal(limit)

        results = []

        print("\nAnalyzing trades...")
        print("=" * 80)

        for idx, trade in journal.iterrows():
            print(f"\n[Trade #{trade['id']}] {trade['ticker']} {trade['option_type']} "
                  f"${trade['strike']} @ ${trade['entry_premium']:.2f}")

            # Fetch price data
            entry_date = trade['timestamp']
            price_df = self.fetch_price_history(trade['ticker'], entry_date)

            if price_df.empty:
                print("  Skipping - no price data")
                continue

            # Simulate both strategies
            print("  Simulating OLD exit strategy...")
            old_result = self.simulate_old_exit(trade, price_df, entry_date)

            print("  Simulating NEW exit strategy...")
            new_result = self.simulate_new_exit(trade, price_df, entry_date)

            # Calculate deltas
            r_delta = new_result['r_achieved'] - old_result['r_achieved']
            pnl_delta = new_result['pnl'] - old_result['pnl']
            pnl_delta_pct = (pnl_delta / abs(old_result['pnl'])) * 100 if old_result['pnl'] != 0 else 0

            # Print comparison
            print(f"\n  OLD: Exit @ ${old_result['exit_premium']:.2f} | "
                  f"{old_result['r_achieved']:.2f}R | ${old_result['pnl']:.0f}")
            print(f"      Reason: {old_result['exit_reason']}")

            print(f"  NEW: Exit @ ${new_result['exit_premium']:.2f} | "
                  f"{new_result['r_achieved']:.2f}R | ${new_result['pnl']:.0f}")
            print(f"      Reason: {new_result['exit_reason']}")

            print(f"  DELTA: {r_delta:+.2f}R | ${pnl_delta:+.0f} ({pnl_delta_pct:+.1f}%)")

            # Store results
            results.append({
                'trade_id': trade['id'],
                'ticker': trade['ticker'],
                'option_type': trade['option_type'],
                'strike': trade['strike'],
                'entry_premium': trade['entry_premium'],
                'entry_date': entry_date,
                'score': trade['score'],
                # OLD
                'old_exit_premium': old_result['exit_premium'],
                'old_r': old_result['r_achieved'],
                'old_pnl': old_result['pnl'],
                'old_reason': old_result['exit_reason'],
                # NEW
                'new_exit_premium': new_result['exit_premium'],
                'new_r': new_result['r_achieved'],
                'new_pnl': new_result['pnl'],
                'new_reason': new_result['exit_reason'],
                # DELTA
                'r_delta': r_delta,
                'pnl_delta': pnl_delta,
                'pnl_delta_pct': pnl_delta_pct
            })

        return pd.DataFrame(results)

    def print_summary(self, results_df: pd.DataFrame):
        """Print aggregate summary statistics."""
        if results_df.empty:
            print("\nNo trades to summarize")
            return

        print("\n" + "=" * 80)
        print("  BACKTEST SUMMARY")
        print("=" * 80)

        total_trades = len(results_df)

        # OLD stats
        old_avg_r = results_df['old_r'].mean()
        old_total_pnl = results_df['old_pnl'].sum()
        old_win_rate = (results_df['old_r'] > 0).sum() / total_trades * 100

        # NEW stats
        new_avg_r = results_df['new_r'].mean()
        new_total_pnl = results_df['new_pnl'].sum()
        new_win_rate = (results_df['new_r'] > 0).sum() / total_trades * 100

        # Deltas
        r_improvement = new_avg_r - old_avg_r
        pnl_improvement = new_total_pnl - old_total_pnl
        pnl_improvement_pct = (pnl_improvement / abs(old_total_pnl)) * 100 if old_total_pnl != 0 else 0
        win_rate_delta = new_win_rate - old_win_rate

        print(f"\nTotal Trades Analyzed: {total_trades}")
        print(f"\n{'Metric':<30} {'OLD':<15} {'NEW':<15} {'Delta':<15}")
        print("-" * 75)
        print(f"{'Win Rate':<30} {old_win_rate:>12.1f}%  {new_win_rate:>12.1f}%  {win_rate_delta:>+12.1f}%")
        print(f"{'Avg R per Trade':<30} {old_avg_r:>12.2f}R {new_avg_r:>12.2f}R {r_improvement:>+12.2f}R")
        print(f"{'Total P/L':<30} ${old_total_pnl:>11.0f}  ${new_total_pnl:>11.0f}  ${pnl_improvement:>+11.0f}")
        print(f"{'P/L Improvement':<30} {'':>12}   {'':>12}   {pnl_improvement_pct:>+11.1f}%")

        # Breakdown by improvement
        print(f"\nTrade Outcomes:")
        improved = (results_df['pnl_delta'] > 0).sum()
        worsened = (results_df['pnl_delta'] < 0).sum()
        unchanged = (results_df['pnl_delta'] == 0).sum()

        print(f"  Improved:  {improved}/{total_trades} ({improved/total_trades*100:.1f}%)")
        print(f"  Worsened:  {worsened}/{total_trades} ({worsened/total_trades*100:.1f}%)")
        print(f"  Unchanged: {unchanged}/{total_trades} ({unchanged/total_trades*100:.1f}%)")

        # Best/worst trades
        if improved > 0:
            best_improvement = results_df.loc[results_df['pnl_delta'].idxmax()]
            print(f"\nBest Improvement:")
            print(f"  Trade #{best_improvement['trade_id']}: {best_improvement['ticker']} "
                  f"{best_improvement['option_type']} - ${best_improvement['pnl_delta']:.0f} improvement")
            print(f"  Reason: {best_improvement['new_reason']}")

        if worsened > 0:
            worst_trade = results_df.loc[results_df['pnl_delta'].idxmin()]
            print(f"\nWorst Trade:")
            print(f"  Trade #{worst_trade['trade_id']}: {worst_trade['ticker']} "
                  f"{worst_trade['option_type']} - ${worst_trade['pnl_delta']:.0f}")
            print(f"  OLD: {worst_trade['old_reason']}")
            print(f"  NEW: {worst_trade['new_reason']}")

        print("\n" + "=" * 80)

        # Reality check
        if pnl_improvement_pct > 60:
            print("\n[!]  REALITY CHECK:")
            print(f"   {pnl_improvement_pct:.0f}% improvement is very high.")
            print("   This could indicate:")
            print("   - Favorable sample (only 13 trades)")
            print("   - Simplified simulation (not using real Greeks)")
            print("   - Need for more trades to validate")
            print("\n   Recommended: Test on 30-50+ trades for statistical significance")
        elif pnl_improvement_pct > 30:
            print("\n[+]  Strong improvement detected!")
            print("   Phase A+B showing meaningful edge.")
            print("   Consider: Phase C (strength-weighted) or live paper trading")
        else:
            print("\n[+]  Modest improvement")
            print("   Consider: More data, parameter tuning, or Phase C")

        print("\n" + "=" * 80 + "\n")


def main():
    """Run backtest analysis."""
    print("\n" + "=" * 80)
    print("  SIMPLE JOURNAL ANALYZER")
    print("  Comparing OLD vs NEW exit strategies")
    print("=" * 80)

    analyzer = JournalAnalyzer()

    # Analyze all trades (or limit for testing)
    results = analyzer.analyze_trades(limit=None)

    # Save results
    if not results.empty:
        output_path = "logs/backtest_results.csv"
        results.to_csv(output_path, index=False)
        print(f"\nResults saved to: {output_path}")

        # Print summary
        analyzer.print_summary(results)
    else:
        print("\nNo trades analyzed")


if __name__ == "__main__":
    main()
