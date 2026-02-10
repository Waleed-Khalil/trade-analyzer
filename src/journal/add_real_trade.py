"""
Manual Trade Entry Helper
Easily add completed trades to journal for backtesting
"""

import pandas as pd
import os
from datetime import datetime

JOURNAL_PATH = "logs/journal.csv"


def add_real_trade(
    ticker: str,
    option_type: str,  # CALL or PUT
    strike: float,
    entry_premium: float,
    entry_date: str,  # YYYY-MM-DD or MM/DD/YYYY
    exit_premium: float,
    exit_date: str,  # YYYY-MM-DD or MM/DD/YYYY
    contracts: int = 5,
    exit_reason: str = "",
    notes: str = "",
    stop_loss_pct: float = 0.50,  # Default 50% stop
    dte: int = None
):
    """
    Add a completed trade to the journal.

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        option_type: "CALL" or "PUT"
        strike: Strike price
        entry_premium: Entry price per contract
        entry_date: Entry date (YYYY-MM-DD or MM/DD/YYYY)
        exit_premium: Exit price per contract
        exit_date: Exit date
        contracts: Number of contracts (default: 5)
        exit_reason: Why you exited (e.g., "Hit target", "Stopped out", "Manual exit")
        notes: Additional notes
        stop_loss_pct: Stop loss as % of premium (default: 0.50 = 50%)
        dte: Days to expiration at entry (optional)

    Example:
        add_real_trade(
            ticker="AAPL",
            option_type="CALL",
            strike=220,
            entry_premium=3.50,
            entry_date="2024-11-15",
            exit_premium=5.20,
            exit_date="2024-11-18",
            contracts=5,
            exit_reason="Hit 2R target",
            notes="Clean breakout at R1"
        )
    """

    # Parse dates
    try:
        if '/' in entry_date:
            entry_dt = pd.to_datetime(entry_date, format='%m/%d/%Y')
        else:
            entry_dt = pd.to_datetime(entry_date)

        if '/' in exit_date:
            exit_dt = pd.to_datetime(exit_date, format='%m/%d/%Y')
        else:
            exit_dt = pd.to_datetime(exit_date)
    except Exception as e:
        print(f"Error parsing dates: {e}")
        print("Use format: YYYY-MM-DD or MM/DD/YYYY")
        return

    # Calculate metrics
    sl_premium = entry_premium * (1 - stop_loss_pct)
    t1_premium = entry_premium + (entry_premium - sl_premium) * 2  # 2R target
    risk = entry_premium - sl_premium
    pnl = (exit_premium - entry_premium) * contracts * 100
    r_multiple = (exit_premium - entry_premium) / risk if risk > 0 else 0
    risk_dollars = risk * contracts * 100

    # Create trade entry
    trade = {
        'timestamp': entry_dt.isoformat(),
        'ticker': ticker.upper(),
        'option_type': option_type.upper(),
        'strike': strike,
        'entry_premium': entry_premium,
        'live_premium': entry_premium,
        'dte': dte if dte else '',
        'pop': '',
        'iv_rank': '',
        'atr': '',
        'sl_premium': sl_premium,
        't1_premium': t1_premium,
        'score': '',
        'risk_dollars': risk_dollars,
        'contracts': contracts,
        'exit_premium': exit_premium,
        'exit_reason': exit_reason,
        'pnl': pnl,
        'r_multiple': r_multiple,
        'notes': notes
    }

    # Load existing journal
    if os.path.exists(JOURNAL_PATH):
        journal = pd.read_csv(JOURNAL_PATH)

        # Get next ID
        if 'id' in journal.columns and len(journal) > 0:
            next_id = journal['id'].max() + 1
        else:
            next_id = 1
    else:
        # Create new journal
        journal = pd.DataFrame(columns=[
            'id', 'timestamp', 'ticker', 'option_type', 'strike',
            'entry_premium', 'live_premium', 'dte', 'pop', 'iv_rank',
            'atr', 'sl_premium', 't1_premium', 'score', 'risk_dollars',
            'contracts', 'exit_premium', 'exit_reason', 'pnl', 'r_multiple', 'notes'
        ])
        next_id = 1

    trade['id'] = next_id

    # Add to journal
    new_row = pd.DataFrame([trade])
    journal = pd.concat([journal, new_row], ignore_index=True)

    # Save
    journal.to_csv(JOURNAL_PATH, index=False)

    # Print confirmation
    print(f"\n[+] Added trade #{next_id} to journal:")
    print(f"    {ticker} {option_type} ${strike} @ ${entry_premium:.2f}")
    print(f"    Entry: {entry_date}")
    print(f"    Exit:  {exit_date} @ ${exit_premium:.2f}")
    print(f"    P/L:   ${pnl:.0f} ({r_multiple:+.2f}R)")
    print(f"    Saved to: {JOURNAL_PATH}\n")


def batch_add_trades_from_list(trades_list):
    """
    Add multiple trades at once from a list of dicts.

    Args:
        trades_list: List of trade dicts (same format as add_real_trade params)

    Example:
        trades = [
            {
                'ticker': 'AAPL',
                'option_type': 'CALL',
                'strike': 220,
                'entry_premium': 3.50,
                'entry_date': '2024-11-15',
                'exit_premium': 5.20,
                'exit_date': '2024-11-18',
                'contracts': 5,
                'exit_reason': 'Hit 2R target'
            },
            {
                'ticker': 'NVDA',
                'option_type': 'CALL',
                'strike': 150,
                'entry_premium': 2.50,
                'entry_date': '2024-11-20',
                'exit_premium': 1.75,
                'exit_date': '2024-11-22',
                'contracts': 10,
                'exit_reason': 'Stopped out'
            }
        ]

        batch_add_trades_from_list(trades)
    """
    print(f"\nAdding {len(trades_list)} trades to journal...")

    for i, trade in enumerate(trades_list, 1):
        print(f"\n[{i}/{len(trades_list)}]")
        add_real_trade(**trade)

    print(f"\n[+] Successfully added {len(trades_list)} trades!")


def import_from_csv(csv_path: str):
    """
    Import trades from a CSV file.

    CSV should have columns:
    ticker, option_type, strike, entry_premium, entry_date,
    exit_premium, exit_date, contracts, exit_reason, notes

    Example CSV:
        ticker,option_type,strike,entry_premium,entry_date,exit_premium,exit_date,contracts,exit_reason,notes
        AAPL,CALL,220,3.50,2024-11-15,5.20,2024-11-18,5,Hit 2R target,Clean breakout
        NVDA,CALL,150,2.50,2024-11-20,1.75,2024-11-22,10,Stopped out,Rejection at R1
    """
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path)

        required_cols = ['ticker', 'option_type', 'strike', 'entry_premium',
                        'entry_date', 'exit_premium', 'exit_date']

        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"Error: Missing required columns: {missing}")
            return

        # Convert to list of dicts
        trades = df.to_dict('records')

        # Add each trade
        batch_add_trades_from_list(trades)

    except Exception as e:
        print(f"Error importing CSV: {e}")


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("  MANUAL TRADE ENTRY HELPER")
    print("="*80)

    # Example: Add a single trade
    print("\nExample 1: Add single trade")
    print("-" * 40)

    add_real_trade(
        ticker="AAPL",
        option_type="CALL",
        strike=220,
        entry_premium=3.50,
        entry_date="2024-11-15",
        exit_premium=5.20,
        exit_date="2024-11-18",
        contracts=5,
        exit_reason="Hit 2R target",
        notes="Clean breakout at resistance, held to next level"
    )

    # Example: Batch add multiple trades
    print("\nExample 2: Batch add trades")
    print("-" * 40)

    example_trades = [
        {
            'ticker': 'NVDA',
            'option_type': 'CALL',
            'strike': 150,
            'entry_premium': 2.50,
            'entry_date': '2024-11-20',
            'exit_premium': 4.00,
            'exit_date': '2024-11-22',
            'contracts': 10,
            'exit_reason': 'Breakout confirmed, held runner',
            'notes': 'Volume spike at R1, trailed stop'
        },
        {
            'ticker': 'SPY',
            'option_type': 'CALL',
            'strike': 600,
            'entry_premium': 1.25,
            'entry_date': '2024-12-01',
            'exit_premium': 0.75,
            'exit_date': '2024-12-03',
            'contracts': 8,
            'exit_reason': 'Rejection at resistance',
            'notes': 'Bearish engulfing at R1, exited early'
        }
    ]

    batch_add_trades_from_list(example_trades)

    print("\n" + "="*80)
    print("  USAGE")
    print("="*80)
    print("""
To add your own trades:

1. Single trade:
   from src.journal.add_real_trade import add_real_trade

   add_real_trade(
       ticker="AAPL",
       option_type="CALL",
       strike=220,
       entry_premium=3.50,
       entry_date="2024-11-15",
       exit_premium=5.20,
       exit_date="2024-11-18",
       contracts=5,
       exit_reason="Hit target",
       notes="Your notes here"
   )

2. Batch from list:
   from src.journal.add_real_trade import batch_add_trades_from_list

   trades = [
       {...trade 1...},
       {...trade 2...},
   ]
   batch_add_trades_from_list(trades)

3. Import from CSV:
   from src.journal.add_real_trade import import_from_csv

   import_from_csv("path/to/your_trades.csv")

Then run backtest:
   python src/backtest/journal_analyzer.py
    """)
