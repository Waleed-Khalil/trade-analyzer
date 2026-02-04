#!/usr/bin/env python3
"""
Traders Cheat Sheet Integration
Store and use Barchart Traders Cheat Sheet data for technical analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class CheatSheetData:
    """Barchart Traders Cheat Sheet data for a ticker"""
    ticker: str
    current_price: float
    previous_close: float
    
    # Pivot Points
    pivot_point: float
    r1: float  # Resistance 1
    r2: float  # Resistance 2
    r3: float  # Resistance 3
    s1: float  # Support 1
    s2: float  # Support 2
    s3: float  # Support 3
    
    # Moving Averages
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    ma_200: Optional[float] = None
    
    # Technical Signals
    rsi: Optional[float] = None
    macd_signal: Optional[str] = None  # bullish/bearish/neutral
    atr: Optional[float] = None
    
    # Barchart Signals
    overall_signal: str = "neutral"  # bullish/bearish/neutral
    short_term: str = "neutral"
    medium_term: str = "neutral"
    long_term: str = "neutral"
    
    # Additional Data
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    
    # Timestamp
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "current_price": self.current_price,
            "previous_close": self.previous_close,
            "pivot_point": self.pivot_point,
            "resistance": {"r1": self.r1, "r2": self.r2, "r3": self.r3},
            "support": {"s1": self.s1, "s2": self.s2, "s3": self.s3},
            "moving_averages": {
                "ma_20": self.ma_20,
                "ma_50": self.ma_50,
                "ma_200": self.ma_200,
            },
            "technical_indicators": {
                "rsi": self.rsi,
                "macd_signal": self.macd_signal,
                "atr": self.atr,
            },
            "signals": {
                "overall": self.overall_signal,
                "short_term": self.short_term,
                "medium_term": self.medium_term,
                "long_term": self.long_term,
            },
            "volume": {
                "day": self.volume,
                "average": self.avg_volume,
            },
            "fetched_at": self.fetched_at,
        }


class CheatSheetStore:
    """Store and query Traders Cheat Sheet data"""
    
    def __init__(self, filepath: str = "logs/cheat_sheets.json"):
        self.filepath = filepath
        self.data: Dict[str, CheatSheetData] = {}
        self._load()
    
    def _load(self):
        """Load data from file"""
        try:
            with open(self.filepath) as f:
                raw = json.load(f)
                for ticker, d in raw.items():
                    self.data[ticker.upper()] = CheatSheetData(**d)
        except FileNotFoundError:
            self.data = {}
    
    def _save(self):
        """Save data to file"""
        with open(self.filepath, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.data.items()}, f, indent=2)
    
    def add(self, data: CheatSheetData):
        """Add or update cheat sheet data"""
        self.data[data.ticker.upper()] = data
        self._save()
    
    def get(self, ticker: str) -> Optional[CheatSheetData]:
        """Get cheat sheet for a ticker"""
        return self.data.get(ticker.upper())
    
    def get_support_levels(self, ticker: str) -> List[float]:
        """Get support levels for a ticker"""
        data = self.get(ticker)
        if data:
            return sorted([data.s1, data.s2, data.s3], reverse=True)
        return []
    
    def get_resistance_levels(self, ticker: str) -> List[float]:
        """Get resistance levels for a ticker"""
        data = self.get(ticker)
        if data:
            return sorted([data.r1, data.r2, data.r3])
        return []
    
    def get_trend(self, ticker: str) -> str:
        """Get overall trend from cheat sheet"""
        data = self.get(ticker)
        if data:
            return data.overall_signal
        return "unknown"
    
    def should_buy_calls(self, ticker: str) -> Optional[bool]:
        """Determine if we should consider buying calls"""
        data = self.get(ticker)
        if not data:
            return None
        
        bullish_signals = 0
        bearish_signals = 0
        
        # Check trend
        if data.overall_signal == "bullish":
            bullish_signals += 2
        elif data.overall_signal == "bearish":
            bearish_signals += 2
        
        # Check price vs moving averages
        if data.current_price and data.ma_50:
            if data.current_price > data.ma_50:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # Check RSI
        if data.rsi:
            if data.rsi > 70:
                bearish_signals += 1  # Overbought
            elif data.rsi < 30:
                bullish_signals += 1  # Oversold
        
        # Check MACD
        if data.macd_signal == "bullish":
            bullish_signals += 1
        elif data.macd_signal == "bearish":
            bearish_signals += 1
        
        if bullish_signals > bearish_signals:
            return True
        elif bearish_signals > bullish_signals:
            return False
        return None
    
    def get_trade_setup(self, ticker: str, option_type: str = "CALL") -> Dict:
        """
        Get trade setup recommendations based on cheat sheet.
        
        Returns:
        {
            "setup": "bullish" / "bearish" / "neutral",
            "confidence": 0-100,
            "entry_zone": "$xxx - $xxx",
            "stop": "$xxx",
            "target": "$xxx",
            "reasons": [...],
        }
        """
        data = self.get(ticker)
        if not data:
            return {"error": "No cheat sheet data for " + ticker}
        
        setup = self.should_buy_calls(ticker)
        
        if option_type == "CALL":
            target_r1 = data.r1
            target_r2 = data.r2
            stop = data.s1
        else:
            target_r1 = data.s1
            target_r2 = data.s2
            stop = data.r1
        
        reasons = []
        
        # Add reasons based on signals
        if data.overall_signal == "bullish":
            reasons.append(f"Overall bullish signal ({data.overall_signal})")
        elif data.overall_signal == "bearish":
            reasons.append(f"Overall bearish signal ({data.overall_signal})")
        
        if data.current_price and data.ma_50:
            if data.current_price > data.ma_50:
                reasons.append(f"Price above 50 MA (${data.ma_50:.2f})")
            else:
                reasons.append(f"Price below 50 MA (${data.ma_50:.2f})")
        
        if data.rsi:
            if data.rsi > 70:
                reasons.append(f"RSI overbought ({data.rsi:.0f})")
            elif data.rsi < 30:
                reasons.append(f"RSI oversold ({data.rsi:.0f})")
            else:
                reasons.append(f"RSI neutral ({data.rsi:.0f})")
        
        if data.macd_signal:
            reasons.append(f"MACD {data.macd_signal}")
        
        # Calculate confidence
        if setup is True:
            confidence = 70 + (10 if data.overall_signal == "strong_bullish" else 0)
        elif setup is False:
            confidence = 30
        else:
            confidence = 50
        
        return {
            "ticker": ticker,
            "option_type": option_type,
            "setup": "bullish" if setup else "bearish" if setup is False else "neutral",
            "confidence": confidence,
            "current_price": data.current_price,
            "entry_zone": f"${data.current_price - 0.50:.2f} - ${data.current_price + 0.50:.2f}",
            "stop": f"${stop:.2f}",
            "target_1": f"${target_r1:.2f}",
            "target_2": f"${target_r2:.2f}",
            "support": self.get_support_levels(ticker),
            "resistance": self.get_resistance_levels(ticker),
            "signals": data.to_dict().get("signals", {}),
            "reasons": reasons,
            "pivot_point": data.pivot_point,
            "fetched_at": data.fetched_at,
        }
    
    def export_json(self, filepath: str = None) -> str:
        """Export all data to JSON"""
        filepath = filepath or self.filepath
        with open(filepath, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.data.items()}, f, indent=2)
        return filepath


def manual_entry_example():
    """
    Example: How to manually enter Traders Cheat Sheet data
    (When you check Barchart.com manually)
    """
    store = CheatSheetStore()
    
    # Example: MSFT Traders Cheat Sheet from Barchart
    store.add(CheatSheetData(
        ticker="MSFT",
        current_price=415.30,
        previous_close=413.50,
        
        # Pivot Points (from Barchart)
        pivot_point=415.00,
        r1=418.00,
        r2=421.00,
        r3=424.00,
        s1=412.00,
        s2=409.00,
        s3=406.00,
        
        # Moving Averages
        ma_20=418.50,
        ma_50=410.00,
        ma_200=395.00,
        
        # Technical Indicators
        rsi=52,
        macd_signal="bullish",
        atr=5.20,
        
        # Barchart Signals
        overall_signal="neutral",
        short_term="neutral",
        medium_term="bullish",
        long_term="bullish",
        
        # Volume
        volume=22000000,
        avg_volume=25000000,
    ))
    
    # Get trade setup for calls
    setup = store.get_trade_setup("MSFT", "CALL")
    print("MSFT CALL Setup:")
    print(f"  Setup: {setup['setup']}")
    print(f"  Confidence: {setup['confidence']}%")
    print(f"  Entry: {setup['entry_zone']}")
    print(f"  Stop: {setup['stop']}")
    print(f"  Target: {setup['target_1']}")
    
    return store


if __name__ == "__main__":
    print("="*70)
    print("Traders Cheat Sheet Integration")
    print("="*70)
    print()
    print("Example: Manual entry from Barchart.com")
    print("-"*70)
    
    store = manual_entry_example()
    
    print()
    print("="*70)
    print("To use:")
    print("1. Check Barchart Traders Cheat Sheet")
    print("2. Enter data manually with store.add()")
    print("3. Get trade setups with store.get_trade_setup()")
    print("="*70)
