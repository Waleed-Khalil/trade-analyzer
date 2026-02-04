#!/usr/bin/env python3
"""
Trade Journal v2 - With Bankroll & Risk Management
Tracks trades, bankroll, and provides smarter analytics.
"""

import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

# Database file
DB_PATH = Path(__file__).parent.parent / "logs" / "trade_journal.json"
BANKROLL_PATH = Path(__file__).parent.parent / "logs" / "bankroll.json"


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
class Bankroll:
    """Bankroll tracking"""
    starting_balance: float
    current_balance: float
    deposits: float = 0
    withdrawals: float = 0
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)


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
    risk_pct: Optional[float]  # % of bankroll at risk
    risk_amount: Optional[float]  # $ at risk
    stop_loss: Optional[float]
    target: Optional[float]
    notes: Optional[str]
    screenshot: Optional[str]
    source: str  # How trade was entered (text/screenshot/manual)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TradeJournal:
    """Trade journal with bankroll tracking"""
    
    def __init__(self, db_path: Path = None, bankroll_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.bankroll_path = bankroll_path or BANKROLL_PATH
        self.trades: List[Trade] = []
        self.bankroll: Bankroll = Bankroll(starting_balance=10000, current_balance=10000)
        self._load()
    
    def _load(self):
        """Load trades and bankroll from files"""
        # Load trades
        if self.db_path.exists():
            with open(self.db_path) as f:
                data = json.load(f)
                self.trades = [Trade(**t) for t in data]
        
        # Load bankroll
        if self.bankroll_path.exists():
            with open(self.bankroll_path) as f:
                data = json.load(f)
                self.bankroll = Bankroll(**data)
    
    def _save(self):
        """Save trades and bankroll to files"""
        # Save trades
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump([t.to_dict() for t in self.trades], f, indent=2)
        
        # Save bankroll
        with open(self.bankroll_path, "w") as f:
            json.dump(self.bankroll.to_dict(), f, indent=2)
    
    def set_bankroll(self, starting: float, current: float = None, deposits: float = 0, withdrawals: float = 0):
        """Set bankroll balance"""
        self.bankroll = Bankroll(
            starting_balance=starting,
            current_balance=current or starting,
            deposits=deposits,
            withdrawals=withdrawals,
        )
        self._save()
    
    def add_trade(self, trade: Trade):
        """Add a new trade with risk calculation"""
        # Calculate risk amount and percentage
        if trade.entry_price and trade.stop_loss and self.bankroll.current_balance:
            risk_per_contract = (trade.entry_price - trade.stop_loss) * 100
            risk_amount = risk_per_contract * trade.contracts
            trade.risk_amount = round(risk_amount, 2)
            trade.risk_pct = round(risk_amount / self.bankroll.current_balance * 100, 2)
        
        self.trades.append(trade)
        self._save()
    
    def close_trade(self, trade_id: str, exit_price: float, notes: str = None):
        """Close a trade, update bankroll, calculate P/L"""
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
                
                trade.pnl = round(pnl_per_contract * trade.contracts, 2)
                trade.pnl_pct = round((exit_price - trade.entry_price) / trade.entry_price * 100, 2)
                
                # Update bankroll
                self.bankroll.current_balance += trade.pnl
                self.bankroll.updated_at = datetime.now().isoformat()
                
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
    
    def get_bankroll_stats(self) -> Dict:
        """Get bankroll statistics"""
        return {
            "starting_balance": self.bankroll.starting_balance,
            "current_balance": self.bankroll.current_balance,
            "total_deposits": self.bankroll.deposits,
            "total_withdrawals": self.bankroll.withdrawals,
            "bankroll_change": round(self.bankroll.current_balance - self.bankroll.starting_balance, 2),
            "bankroll_change_pct": round(
                (self.bankroll.current_balance - self.bankroll.starting_balance) / self.bankroll.starting_balance * 100, 2
            ),
        }
    
    def get_risk_analysis(self) -> Dict:
        """Analyze risk management"""
        closed = self.get_closed_trades()
        
        if not closed:
            return {"avg_risk_pct": 0, "max_risk_pct": 0, "trades_over_2pct": 0}
        
        risk_pcts = [t.risk_pct for t in closed if t.risk_pct]
        
        return {
            "avg_risk_pct": round(sum(risk_pcts) / len(risk_pcts), 2) if risk_pcts else 0,
            "max_risk_pct": max(risk_pcts) if risk_pcts else 0,
            "trades_over_2pct": len([r for r in risk_pcts if r > 2]),
            "recommendation": self._get_risk_recommendation(risk_pcts),
        }
    
    def _get_risk_recommendation(self, risk_pcts: List[float]) -> str:
        """Get risk management recommendation"""
        if not risk_pcts:
            return "Set your bankroll to get risk recommendations"
        
        avg = sum(risk_pcts) / len(risk_pcts)
        
        if avg > 2:
            return "⚠️ You're risking too much per trade. Max should be 1-2%."
        elif avg < 0.5:
            return "💡 You're being very conservative. Could increase position size slightly."
        else:
            return "✅ Your risk per trade looks appropriate (1-2%)"
    
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
        
        # Bankroll at start of month
        bankroll_at_start = self._get_bankroll_at_date(date(year, month, 1))
        
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
            "bankroll_at_start": bankroll_at_start,
            "bankroll_now": self.bankroll.current_balance,
        }
    
    def _get_bankroll_at_date(self, target_date: date) -> float:
        """Estimate bankroll at a specific date"""
        # For simplicity, assume bankroll grows with P/L
        trades_before = [t for t in self.get_closed_trades() 
                       if datetime.fromisoformat(t.exit_time).date() < target_date]
        pnl_before = sum(t.pnl for t in trades_before if t.pnl)
        return self.bankroll.starting_balance + pnl_before
    
    def get_improvement_report(self) -> str:
        """Generate improvement recommendations"""
        stats = self.get_all_time_stats()
        risk = self.get_risk_analysis()
        bankroll = self.get_bankroll_stats()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    TRADING IMPROVEMENT REPORT                  ║
╚══════════════════════════════════════════════════════════════════════╝

💰 BANKROLL
──────────────────────────────────────────────────────────────────
Starting: ${bankroll['starting_balance']:,.2f}
Current:  ${bankroll['current_balance']:,.2f}
Change:   ${bankroll['bankroll_change']:+.2f} ({bankroll['bankroll_change_pct']:+.2f}%)

📊 PERFORMANCE
──────────────────────────────────────────────────────────────────
Total Trades: {stats['total_trades']}
Win Rate: {stats['win_rate']}%
Total P/L: ${stats['total_pnl']:+.2f}

⚠️ RISK ANALYSIS
──────────────────────────────────────────────────────────────────
Avg Risk/Trade: {risk['avg_risk_pct']}%
Max Risk/Trade: {risk['max_risk_pct']}%
Trades >2% Risk: {risk['trades_over_2pct']}

{risk['recommendation']}

📈 IMPROVEMENT TIPS
──────────────────────────────────────────────────────────────────
"""
        
        # Analyze mistakes
        closed = self.get_closed_trades()
        losses = [t for t in closed if t.pnl and t.pnl < 0]
        
        if losses:
            report += f"\n❌ LOSS ANALYSIS ({len(losses)} losing trades):\n"
            
            # Check for common mistakes
            all_otm = all(
                (t.option_type.upper() == "CALL" and t.entry_price < t.stop_loss) or
                (t.option_type.upper() == "PUT" and t.entry_price < t.stop_loss)
                for t in losses
            )
            
            if all_otm:
                report += "• All losses were OTM calls - check trend before buying\n"
            
            report += f"• Avg loss: ${sum(t.pnl for t in losses)/len(losses):.2f}\n"
        
        wins = [t for t in closed if t.pnl and t.pnl > 0]
        if wins:
            avg_win_time = sum(
                (datetime.fromisoformat(t.exit_time) - datetime.fromisoformat(t.entry_time)).total_seconds()
                for t in wins
            ) / len(wins) / 3600  # hours
            report += f"\n✅ WINNING TRADES ({len(wins)}):\n"
            report += f"• Avg win: ${sum(t.pnl for t in wins)/len(wins):.2f}\n"
            report += f"• Avg hold time: {avg_win_time:.1f} hours\n"
        
        report += f"""

🎯 TOP 5 IMPROVEMENTS
──────────────────────────────────────────────────────────────────
1. Check trend before entering (RSI, MACD, 5-day direction)
2. Use the monitor - don't panic sell
3. Risk max 1-2% per trade
4. Only trade with catalysts (earnings, news)
5. Set stops BEFORE entering, don't move them

📚 NEXT STEPS
──────────────────────────────────────────────────────────────────
• Set your bankroll: journal.set_bankroll(10000)
• Review this report before every trade
• Use the monitor for every 0DTE trade
• Track mistakes and learn from them
"""
        
        return report
    
    def get_all_time_stats(self) -> Dict:
        """Get all-time statistics"""
        closed = [t for t in self.trades if t.status == TradeStatus.CLOSED.value]
        
        total_pnl = sum(t.pnl for t in closed if t.pnl)
        win_trades = [t for t in closed if t.pnl and t.pnl > 0]
        loss_trades = [t for t in closed if t.pnl and t.pnl <= 0]
        
        win_rate = len(win_trades) / len(closed) * 100 if closed else 0
        
        monthly_stats = {}
        for t in closed:
            if t.exit_time:
                month_key = datetime.fromisoformat(t.exit_time).strftime("%Y-%m")
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


# Quick setup for CLI
def setup_bankroll(amount: float):
    """Set initial bankroll"""
    journal = TradeJournal()
    journal.set_bankroll(starting=amount, current=amount)
    print(f"✅ Bankroll set to ${amount:,.2f}")
    return journal


# CLI interface
if __name__ == "__main__":
    import sys
    
    journal = TradeJournal()
    
    commands = {
        "bankroll": lambda: print(f"Bankroll: ${journal.get_bankroll_stats()['current_balance']:,.2f}"),
        "stats": lambda: print(f"Total P/L: ${journal.get_all_time_stats()['total_pnl']:+.2f}"),
        "report": lambda: print(journal.get_improvement_report()),
        "monthly": lambda: journal._print_monthly(),
        "risk": lambda: print(f"Avg Risk: {journal.get_risk_analysis()['recommendation']}"),
    }
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "set-bankroll":
            amount = float(sys.argv[2]) if len(sys.argv) > 2 else 10000
            setup_bankroll(amount)
        
        elif cmd in commands:
            commands[cmd]()
        
        else:
            print(f"Commands: {list(commands.keys())}")
    else:
        print("Commands: bankroll, stats, report, monthly, risk")
        print("Usage: python trade_journal.py set-bankroll 10000")
