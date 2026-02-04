#!/usr/bin/env python3
"""
Trade Journal & Database
Tracks all trades, outcomes, and provides analytics.
"""

import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Database file
DB_PATH = Path(__file__).parent.parent / "logs" / "trade_journal.json"


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeType(Enum):
    CALL = "CALL"
    PUT = "PUT"


class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class Trade:
    """Trade record"""
    id: str
    ticker: str
    strike: float
    option_type: str  # CALL/PUT
    direction: str  # LONG/SHORT
    entry_price: float
    exit_price: Optional[float]
    contracts: int
    entry_time: str  # ISO format
    exit_time: Optional[str]
    expiration: str
    dte: int
    status: str  # OPEN/CLOSED/CANCELLED
    pnl: Optional[float]
    pnl_pct: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    notes: Optional[str]
    screenshot: Optional[str]  # Path to screenshot
    source: str  # How trade was entered (text/screenshot/manual)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TradeJournal:
    """Trade journal database"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.trades: List[Trade] = []
        self._load()
    
    def _load(self):
        """Load trades from JSON file"""
        if self.db_path.exists():
            with open(self.db_path) as f:
                data = json.load(f)
                self.trades = [Trade(**t) for t in data]
        else:
            self.trades = []
    
    def _save(self):
        """Save trades to JSON file"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump([t.to_dict() for t in self.trades], f, indent=2)
    
    def add_trade(self, trade: Trade):
        """Add a new trade"""
        self.trades.append(trade)
        self._save()
    
    def update_trade(self, trade_id: str, **kwargs):
        """Update a trade"""
        for trade in self.trades:
            if trade.id == trade_id:
                for key, value in kwargs.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)
                self._save()
                return True
        return False
    
    def close_trade(self, trade_id: str, exit_price: float, notes: str = None):
        """Close a trade and calculate P/L"""
        for trade in self.trades:
            if trade.id == trade_id and trade.status == TradeStatus.OPEN.value:
                trade.exit_price = exit_price
                trade.exit_time = datetime.now().isoformat()
                trade.status = TradeStatus.CLOSED.value
                
                # Calculate P/L
                if trade.option_type.upper() == "CALL":
                    pnl_per_contract = (exit_price - trade.entry_price) * 100
                else:  # PUT
                    pnl_per_contract = (trade.entry_price - exit_price) * 100
                
                trade.pnl = pnl_per_contract * trade.contracts
                trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
                
                if notes:
                    trade.notes = notes
                
                self._save()
                return trade
        
        return None
    
    def get_open_trades(self) -> List[Trade]:
        """Get all open trades"""
        return [t for t in self.trades if t.status == TradeStatus.OPEN.value]
    
    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades"""
        return [t for t in self.trades if t.status == TradeStatus.CLOSED.value]
    
    def get_trades_by_date(self, start_date: date, end_date: date = None) -> List[Trade]:
        """Get trades within date range"""
        if end_date is None:
            end_date = date.today()
        
        result = []
        for t in self.trades:
            entry_dt = datetime.fromisoformat(t.entry_time)
            if start_date <= entry_dt.date() <= end_date:
                result.append(t)
        return result
    
    def get_trades_by_ticker(self, ticker: str) -> List[Trade]:
        """Get all trades for a ticker"""
        return [t for t in self.trades if t.ticker.upper() == ticker.upper()]
    
    def get_monthly_stats(self, year: int = None, month: int = None) -> Dict:
        """Get monthly statistics"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        month_trades = self.get_trades_by_date(
            date(year, month, 1),
            date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
        )
        
        closed = [t for t in month_trades if t.status == TradeStatus.CLOSED.value]
        open_trades = [t for t in month_trades if t.status == TradeStatus.OPEN.value]
        
        total_pnl = sum(t.pnl for t in closed if t.pnl)
        win_trades = [t for t in closed if t.pnl and t.pnl > 0]
        loss_trades = [t for t in closed if t.pnl and t.pnl <= 0]
        
        win_rate = len(win_trades) / len(closed) * 100 if closed else 0
        avg_win = sum(t.pnl for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = sum(t.pnl for t in loss_trades) / len(loss_trades) if loss_trades else 0
        
        return {
            "month": f"{year}-{month:02d}",
            "total_trades": len(month_trades),
            "closed_trades": len(closed),
            "open_trades": len(open_trades),
            "win_trades": len(win_trades),
            "loss_trades": len(loss_trades),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": abs(avg_win / avg_loss) if avg_loss else 0,
        }
    
    def get_all_time_stats(self) -> Dict:
        """Get all-time statistics"""
        closed = [t for t in self.trades if t.status == TradeStatus.CLOSED.value]
        
        total_pnl = sum(t.pnl for t in closed if t.pnl)
        win_trades = [t for t in closed if t.pnl and t.pnl > 0]
        loss_trades = [t for t in closed if t.pnl and t.pnl <= 0]
        
        win_rate = len(win_trades) / len(closed) * 100 if closed else 0
        
        # Monthly breakdown
        monthly_stats = {}
        for t in closed:
            month_key = datetime.fromisoformat(t.entry_time).strftime("%Y-%m")
            if month_key not in monthly_stats:
                monthly_stats[month_key] = 0
            monthly_stats[month_key] += t.pnl if t.pnl else 0
        
        return {
            "total_trades": len(self.trades),
            "closed_trades": len(closed),
            "open_trades": len(self.get_open_trades()),
            "win_trades": len(win_trades),
            "loss_trades": len(loss_trades),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(t.pnl for t in win_trades) / len(win_trades), 2) if win_trades else 0,
            "avg_loss": round(sum(t.pnl for t in loss_trades) / len(loss_trades), 2) if loss_trades else 0,
            "best_month": max(monthly_stats.items(), key=lambda x: x[1]) if monthly_stats else None,
            "worst_month": min(monthly_stats.items(), key=lambda x: x[1]) if monthly_stats else None,
            "monthly_breakdown": monthly_stats,
        }
    
    def get_performance_report(self, days: int = 30) -> str:
        """Generate a performance report"""
        from datetime import timedelta
        
        start_date = date.today() - timedelta(days=days)
        trades = self.get_trades_by_date(start_date)
        closed = [t for t in trades if t.status == TradeStatus.CLOSED.value]
        
        total_pnl = sum(t.pnl for t in closed if t.pnl)
        wins = [t for t in closed if t.pnl and t.pnl > 0]
        losses = [t for t in closed if t.pnl and t.pnl <= 0]
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           TRADE JOURNAL PERFORMANCE REPORT                  ║
║                    Last {days} Days                        ║
╚══════════════════════════════════════════════════════════════╝

📊 SUMMARY
─────────────────────────────────────────────────────────────
Total Trades: {len(trades)}
Closed: {len(closed)}
Open: {len(trades) - len(closed)}
Win Rate: {len(wins) / len(closed) * 100:.1f}%" if closed else "N/A"

💰 P&L
─────────────────────────────────────────────────────────────
Total P/L: ${total_pnl:+.2f}
Wins: ${sum(t.pnl for t in wins):+.2f} ({len(wins)} trades)
Losses: ${sum(t.pnl for t in losses):.2f} ({len(losses)} trades)

📈 BEST TRADES
─────────────────────────────────────────────────────────────
""".strip()
        
        if wins:
            sorted_wins = sorted(wins, key=lambda t: t.pnl, reverse=True)[:3]
            for i, t in enumerate(sorted_wins, 1):
                report += f"\n{i}. {t.ticker} {t.strike}{t.option_type} @ ${t.entry_price:.2f} → ${t.exit_price:.2f}"
                report += f"\n   ${t.pnl:+.2f} ({t.pnl_pct:+.1f}%) | {t.contracts} contracts"
        
        if losses:
            report += f"\n\n📉 WORST TRADES"
            sorted_losses = sorted(losses, key=lambda t: t.pnl)[:3]
            for i, t in enumerate(sorted_losses, 1):
                report += f"\n{i}. {t.ticker} {t.strike}{t.option_type} @ ${t.entry_price:.2f} → ${t.exit_price:.2f}"
                report += f"\n   ${t.pnl:.2f} ({t.pnl_pct:.1f}%) | {t.contracts} contracts"
        
        return report
    
    def export_csv(self, filepath: Path = None):
        """Export trades to CSV"""
        import csv
        
        filepath = filepath or self.db_path.with_suffix(".csv")
        
        fieldnames = [
            "id", "ticker", "strike", "option_type", "direction",
            "entry_price", "exit_price", "contracts",
            "entry_time", "exit_time", "expiration", "dte",
            "status", "pnl", "pnl_pct", "stop_loss", "target", "notes"
        ]
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in self.trades:
                writer.writerow(t.to_dict())
        
        return filepath


def create_trade_from_screenshot(screenshot_data: Dict, screenshot_path: str = None) -> Trade:
    """Create a Trade from screenshot analysis"""
    import uuid
    
    trade_id = f"TRD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    # Parse expiration
    exp_date = screenshot_data.get("expiration", "")
    try:
        # Try different formats
        for fmt in ["%m/%d", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                exp_dt = datetime.strptime(exp_date, fmt)
                expiration = exp_dt.strftime("%Y-%m-%d")
                dte = max(0, (exp_dt.date() - date.today()).days)
                break
            except ValueError:
                continue
        else:
            expiration = datetime.now().strftime("%Y-%m-%d")
            dte = 0
    except:
        expiration = datetime.now().strftime("%Y-%m-%d")
        dte = 0
    
    return Trade(
        id=trade_id,
        ticker=screenshot_data.get("ticker", "").upper(),
        strike=float(screenshot_data.get("strike", 0)),
        option_type=screenshot_data.get("option_type", "CALL").upper(),
        direction=TradeDirection.LONG.value,
        entry_price=float(screenshot_data.get("mark", 0)),
        exit_price=None,
        contracts=int(screenshot_data.get("contracts", 1)),
        entry_time=datetime.now().isoformat(),
        exit_time=None,
        expiration=expiration,
        dte=dte,
        status=TradeStatus.OPEN.value,
        pnl=None,
        pnl_pct=None,
        stop_loss=None,
        target=None,
        notes=None,
        screenshot=screenshot_path,
        source="screenshot",
    )


def create_trade_from_text(ticker: str, strike: float, option_type: str, 
                           premium: float, contracts: int = 1,
                           expiration: str = None, dte: int = 0,
                           stop: float = None, target: float = None) -> Trade:
    """Create a Trade from text input"""
    import uuid
    
    trade_id = f"TRD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    return Trade(
        id=trade_id,
        ticker=ticker.upper(),
        strike=float(strike),
        option_type=option_type.upper(),
        direction=TradeDirection.LONG.value,
        entry_price=float(premium),
        exit_price=None,
        contracts=int(contracts),
        entry_time=datetime.now().isoformat(),
        exit_time=None,
        expiration=expiration or datetime.now().strftime("%Y-%m-%d"),
        dte=int(dte),
        status=TradeStatus.OPEN.value,
        pnl=None,
        pnl_pct=None,
        stop_loss=stop,
        target=target,
        notes=None,
        screenshot=None,
        source="text",
    )


# CLI interface
if __name__ == "__main__":
    import sys
    
    journal = TradeJournal()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python trade_journal.py add <ticker> <strike> <type> <premium> [contracts]")
        print("  python trade_journal.py close <trade_id> <exit_price>")
        print("  python trade_journal.py stats")
        print("  python trade_journal.py monthly")
        print("  python trade_journal.py report [days]")
        print("  python trade_journal.py list")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "add":
        ticker = sys.argv[2]
        strike = float(sys.argv[3])
        option_type = sys.argv[4]
        premium = float(sys.argv[5])
        contracts = int(sys.argv[6]) if len(sys.argv) > 6 else 1
        
        trade = create_trade_from_text(ticker, strike, option_type, premium, contracts)
        journal.add_trade(trade)
        print(f"✅ Trade added: {trade.id}")
        print(f"   {ticker} {strike}{option_type} @ ${premium} x{contracts}")
    
    elif command == "close":
        trade_id = sys.argv[2]
        exit_price = float(sys.argv[3])
        trade = journal.close_trade(trade_id, exit_price)
        if trade:
            print(f"✅ Trade closed: {trade_id}")
            print(f"   P/L: ${trade.pnl:.2f} ({trade.pnl_pct:+.1f}%)")
        else:
            print(f"❌ Trade not found: {trade_id}")
    
    elif command == "stats":
        stats = journal.get_all_time_stats()
        print(f"\n📊 All-Time Stats:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']}%")
        print(f"   Total P/L: ${stats['total_pnl']:+.2f}")
    
    elif command == "monthly":
        for month in range(1, 13):
            stats = journal.get_monthly_stats(datetime.now().year, month)
            if stats["total_trades"] > 0:
                print(f"{stats['month']}: ${stats['total_pnl']:+.2f} ({stats['total_trades']} trades, {stats['win_rate']}% win rate)")
    
    elif command == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(journal.get_performance_report(days))
    
    elif command == "list":
        for t in journal.trades[-10:]:
            status = "🟢" if t.status == "OPEN" else "🔴"
            pnl_str = f"${t.pnl:+.2f}" if t.pnl else "---"
            print(f"{status} {t.id}: {t.ticker} {t.strike}{t.option_type} @ ${t.entry_price} → {pnl_str}")
    
    elif command == "export":
        filepath = journal.export_csv()
        print(f"✅ Exported to: {filepath}")
    
    else:
        print(f"Unknown command: {command}")
