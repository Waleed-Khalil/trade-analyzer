"""
Parser Module
Extract structured trade data from Discord alert messages
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
import yaml


@dataclass
class OptionTrade:
    """Structured representation of an options trade alert"""
    ticker: str
    option_type: str  # 'CALL' or 'PUT'
    strike: float
    premium: float
    contracts: Optional[int] = None
    expiration: Optional[str] = None
    entry_price: Optional[float] = None
    direction: str = "LONG"  # Default to long
    raw_message: str = ""
    parsed_at: datetime = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "option_type": self.option_type,
            "strike": self.strike,
            "premium": self.premium,
            "contracts": self.contracts,
            "expiration": self.expiration,
            "direction": self.direction,
            "raw_message": self.raw_message
        }


class TradeParser:
    """
    Parse Discord option trade alerts into structured JSON.
    Supports multiple alert formats via configurable patterns.
    """
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config.yaml in project root
            import os
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.formats = self.config.get('alert_formats', [])
        
    def parse(self, message: str) -> Optional[OptionTrade]:
        """
        Try to parse a Discord message as an options alert.
        Returns OptionTrade if successful, None if no match.
        """
        message = message.strip()
        
        for fmt in self.formats:
            try:
                trade = self._try_format(message, fmt)
                if trade:
                    return trade
            except Exception as e:
                continue
                
        return None
    
    def _try_format(self, message: str, fmt: Dict) -> Optional[OptionTrade]:
        """Try parsing with a specific format definition"""
        pattern = fmt.get('pattern', '')
        fields = fmt.get('fields', [])
        
        match = re.search(pattern, message)
        if not match:
            return None
            
        # Build dict of field -> value
        data = {}
        for i, field in enumerate(fields):
            if i + 1 <= len(match.groups()):
                data[field] = match.group(i + 1)
        
        # Extract required fields
        ticker = data.get('ticker', '').upper()
        option_type = data.get('type', '').upper()  # Handle 'type' or 'option_type'
        if not option_type:
            option_type = data.get('option_type', '').upper()
        strike = self._parse_number(data.get('strike', '0'))
        premium = self._parse_number(data.get('premium', '0'))
        
        if not all([ticker, option_type, strike > 0, premium > 0]):
            return None
            
        return OptionTrade(
            ticker=ticker,
            option_type=option_type,
            strike=strike,
            premium=premium,
            expiration=data.get('expiration'),
            direction=self._detect_direction(message),
            raw_message=message,
            parsed_at=datetime.utcnow()
        )
    
    def _parse_number(self, value: str) -> float:
        """Safely parse a number string"""
        try:
            # Remove $ and commas
            cleaned = value.replace('$', '').replace(',', '')
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    
    def _detect_direction(self, message: str) -> str:
        """Detect LONG or SHORT from message"""
        msg_lower = message.lower()
        if any(word in msg_lower for word in ['buy', 'long', 'call', 'bull']):
            return "LONG"
        elif any(word in msg_lower for word in ['sell', 'short', 'put', 'bear']):
            return "SHORT"
        return "LONG"  # Default
    
    def validate(self, trade: OptionTrade) -> List[str]:
        """
        Validate parsed trade against business rules.
        Returns list of validation errors (empty = valid).
        """
        errors = []
        
        # Basic field validation
        if not trade.ticker or len(trade.ticker) < 1:
            errors.append("Missing or invalid ticker")
            
        if trade.option_type not in ['CALL', 'PUT']:
            errors.append(f"Invalid option type: {trade.option_type}")
            
        if trade.strike <= 0:
            errors.append(f"Invalid strike price: {trade.strike}")
            
        if trade.premium <= 0:
            errors.append(f"Invalid premium: {trade.premium}")
            
        # Check minimum premium
        min_prem = self.config.get('sizing', {}).get('min_premium_to_consider', 0.50)
        if trade.premium < min_prem:
            errors.append(f"Premium {trade.premium} below minimum {min_prem}")
            
        return errors


# CLI test
if __name__ == "__main__":
    import sys
    
    parser = TradeParser()
    
    test_messages = [
        "BUY AAPL 01/31 215 CALL @ 3.50",
        "AAPL CALL 215 @ 3.50",
        "SELL TSLA PUT 800 @ 12.50"
    ]
    
    for msg in test_messages:
        trade = parser.parse(msg)
        if trade:
            print(f"✓ Parsed: {trade.ticker} {trade.option_type} ${trade.strike} @ ${trade.premium}")
            errors = parser.validate(trade)
            if errors:
                print(f"  ⚠ Warnings: {errors}")
        else:
            print(f"✗ Failed to parse: {msg}")
