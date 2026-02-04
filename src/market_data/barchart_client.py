#!/usr/bin/env python3
"""
Barchart Integration - Simplified
Provides structure for Barchart data even without direct API access.
Use this when you manually check Barchart or copy data.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class BarchartIVData:
    """IV data from Barchart"""
    ticker: str
    iv_rank: float  # 0-100
    iv_percentile: float  # 0-100
    implied_volatility: float  # as decimal or percentage
    iv_rank_change: Optional[float] = None  # daily change
    historical_iv: Optional[float] = None  # historical average
    fetch_time: str = None
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "iv_rank": self.iv_rank,
            "iv_percentile": self.iv_percentile,
            "implied_volatility": self.implied_volatility,
            "iv_rank_change": self.iv_rank_change,
            "historical_iv": self.historical_iv,
            "fetch_time": self.fetch_time or datetime.now().isoformat(),
        }


@dataclass
class BarchartUnusualActivity:
    """Unusual options activity from Barchart"""
    ticker: str
    option_type: str  # CALL/PUT
    strike: float
    expiration: str
    volume: int
    open_interest: int
    volume_oi_ratio: float
    sentiment: str  # bullish/bearish
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    fetch_time: str = None
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiration": self.expiration,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "volume_oi_ratio": self.volume_oi_ratio,
            "sentiment": self.sentiment,
            "last_price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "fetch_time": self.fetch_time or datetime.now().isoformat(),
        }


@dataclass
class BarchartOptionsFlow:
    """Options flow data from Barchart"""
    ticker: str
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    call_put_ratio: float
    sentiment: str  # bullish/bearish/neutral
    flow_score: Optional[int] = None  # -100 to 100
    fetch_time: str = None
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "call_volume": self.call_volume,
            "put_volume": self.put_volume,
            "call_oi": self.call_oi,
            "put_oi": self.put_oi,
            "call_put_ratio": self.call_put_ratio,
            "sentiment": self.sentiment,
            "flow_score": self.flow_score,
            "fetch_time": self.fetch_time or datetime.now().isoformat(),
        }


class BarchartData:
    """
    Store and manage Barchart data manually entered or from other sources.
    This provides structure for when you check Barchart manually.
    """
    
    def __init__(self):
        self.iv_data: Dict[str, BarchartIVData] = {}
        self.unusual_activity: List[BarchartUnusualActivity] = []
        self.options_flow: Dict[str, BarchartOptionsFlow] = {}
    
    def add_iv_data(self, data: BarchartIVData):
        """Add IV data for a ticker"""
        self.iv_data[data.ticker.upper()] = data
    
    def add_unusual_activity(self, activities: List[BarchartUnusualActivity]):
        """Add unusual activity list"""
        self.unusual_activity.extend(activities)
    
    def add_options_flow(self, data: BarchartOptionsFlow):
        """Add options flow for a ticker"""
        self.options_flow[data.ticker.upper()] = data
    
    def get_iv_for_ticker(self, ticker: str) -> Optional[BarchartIVData]:
        """Get IV data for a ticker"""
        return self.iv_data.get(ticker.upper())
    
    def get_sentiment(self, ticker: str) -> Optional[str]:
        """Get market sentiment for a ticker"""
        flow = self.options_flow.get(ticker.upper())
        return flow.sentiment if flow else None
    
    def should_trade_call(self, ticker: str) -> Optional[bool]:
        """
        Determine if we should consider buying calls based on Barchart data.
        Returns: True (bullish), False (bearish), or None (neutral/unclear)
        """
        flow = self.options_flow.get(ticker.upper())
        iv = self.iv_data.get(ticker.upper())
        
        # Check options flow sentiment
        if flow:
            if flow.sentiment == "bullish" and flow.call_put_ratio > 1.2:
                return True
            elif flow.sentiment == "bearish" and flow.call_put_ratio < 0.8:
                return False
        
        # Check IV conditions
        if iv:
            # Low IV is favorable for buying options
            if iv.iv_rank < 30:
                return True
            # High IV is unfavorable
            elif iv.iv_rank > 70:
                return False
        
        return None
    
    def get_trading_recommendation(self, ticker: str, option_type: str = "CALL") -> Dict:
        """
        Get trading recommendation based on Barchart data.
        
        Returns:
        {
            "recommendation": "BUY" / "SELL" / "AVOID" / "WATCH",
            "confidence": 0-100,
            "reasons": [...],
            "iv_status": "low" / "medium" / "high",
            "sentiment": "bullish" / "bearish" / "neutral",
        }
        """
        result = {
            "recommendation": "WATCH",
            "confidence": 0,
            "reasons": [],
            "iv_status": "unknown",
            "sentiment": "neutral",
            "ticker": ticker,
            "option_type": option_type,
            "timestamp": datetime.now().isoformat(),
        }
        
        flow = self.options_flow.get(ticker.upper())
        iv = self.iv_data.get(ticker.upper())
        
        # Check sentiment
        if flow:
            result["sentiment"] = flow.sentiment
            if option_type == "CALL" and flow.sentiment == "bullish":
                result["reasons"].append(f"Bullish options flow ({flow.call_put_ratio:.2f} C/P ratio)")
                result["confidence"] += 20
            elif option_type == "PUT" and flow.sentiment == "bearish":
                result["reasons"].append(f"Bearish options flow ({flow.call_put_ratio:.2f} C/P ratio)")
                result["confidence"] += 20
        
        # Check IV
        if iv:
            if iv.iv_rank < 30:
                result["iv_status"] = "low"
                result["reasons"].append(f"Low IV Rank ({iv.iv_rank:.0f}%) - favorable for buying")
                result["confidence"] += 30
            elif iv.iv_rank > 70:
                result["iv_status"] = "high"
                result["reasons"].append(f"High IV Rank ({iv.iv_rank:.0f}%) - IV crush risk")
                result["confidence"] -= 10
            else:
                result["iv_status"] = "medium"
                result["reasons"].append(f"Medium IV Rank ({iv.iv_rank:.0f}%)")
                result["confidence"] += 10
        
        # Generate recommendation
        confidence = result["confidence"]
        
        if confidence >= 60:
            if option_type == "CALL" and result["sentiment"] in ["bullish", "neutral"] and iv and iv.iv_rank < 50:
                result["recommendation"] = "BUY"
            elif option_type == "PUT" and result["sentiment"] in ["bearish", "neutral"] and iv and iv.iv_rank < 50:
                result["recommendation"] = "BUY"
            else:
                result["recommendation"] = "WATCH"
        elif confidence >= 30:
            result["recommendation"] = "WATCH"
        else:
            result["recommendation"] = "AVOID"
        
        return result
    
    def export_json(self, filepath: str = "barchart_data.json"):
        """Export all data to JSON"""
        data = {
            "iv_data": {k: v.to_dict() for k, v in self.iv_data.items()},
            "unusual_activity": [a.to_dict() for a in self.unusual_activity],
            "options_flow": {k: v.to_dict() for k, v in self.options_flow.items()},
            "exported_at": datetime.now().isoformat(),
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return filepath


def manual_entry_example():
    """
    Example: How to manually enter Barchart data
    (When you check Barchart.com manually and enter the data)
    """
    data = BarchartData()
    
    # Example: You checked Barchart and found these IV ranks
    data.add_iv_data(BarchartIVData(
        ticker="MSFT",
        iv_rank=25,
        iv_percentile=28,
        implied_volatility=0.38,
        historical_iv=0.45,
    ))
    
    data.add_iv_data(BarchartIVData(
        ticker="QQQ",
        iv_rank=15,
        iv_percentile=18,
        implied_volatility=0.32,
        historical_iv=0.40,
    ))
    
    # Example: Unusual activity you saw on Barchart
    data.add_unusual_activity([
        BarchartUnusualActivity(
            ticker="NVDA",
            option_type="CALL",
            strike=1000,
            expiration="2/21",
            volume=15000,
            open_interest=5000,
            volume_oi_ratio=3.0,
            sentiment="bullish",
            last_price=15.50,
        ),
        BarchartUnusualActivity(
            ticker="AAPL",
            option_type="PUT",
            strike=220,
            expiration="2/14",
            volume=25000,
            open_interest=8000,
            volume_oi_ratio=3.1,
            sentiment="bearish",
            last_price=8.25,
        ),
    ])
    
    # Get recommendation for MSFT calls
    rec = data.get_trading_recommendation("MSFT", "CALL")
    print(f"MSFT CALL Recommendation:")
    print(f"  {rec['recommendation']} (confidence: {rec['confidence']}%)")
    print(f"  Reasons: {rec['reasons']}")
    
    return data


if __name__ == "__main__":
    print("="*70)
    print("Barchart Data Integration")
    print("="*70)
    print()
    print("Use this module to store Barchart data manually or from API.")
    print()
    print("Example: Manual entry workflow")
    print("-"*70)
    data = manual_entry_example()
    print()
    print("Data exported to barchart_data.json")
    data.export_json()
