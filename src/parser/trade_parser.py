"""
Parser Module
Extract structured trade data from Discord alert messages.
Supports optional EXP YYYY-MM-DD or EXP MM/DD/YYYY for explicit expiration.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
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
    is_ode: bool = False  # Same-day expiration (0DTE)
    days_to_expiration: Optional[int] = None  # 0 = today

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "option_type": self.option_type,
            "strike": self.strike,
            "premium": self.premium,
            "contracts": self.contracts,
            "expiration": self.expiration,
            "direction": self.direction,
            "raw_message": self.raw_message,
            "is_ode": self.is_ode,
            "days_to_expiration": self.days_to_expiration,
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
        Optional: EXP YYYY-MM-DD or EXP MM/DD/YYYY sets expiration and DTE.
        Optional: DTE N or N DTE sets days-to-expiration explicitly (single source of truth).
        """
        message = message.strip()
        for fmt in self.formats:
            try:
                trade = self._try_format(message, fmt)
                if trade:
                    # 1) Explicit DTE in message (e.g. "DTE 2" or "2 DTE") — universal source
                    explicit_dte = self._parse_explicit_dte(message)
                    if explicit_dte is not None:
                        exp_date = (date.today() + timedelta(days=explicit_dte)).strftime("%Y-%m-%d")
                        trade = OptionTrade(
                            ticker=trade.ticker,
                            option_type=trade.option_type,
                            strike=trade.strike,
                            premium=trade.premium,
                            contracts=trade.contracts,
                            expiration=exp_date,
                            entry_price=trade.entry_price,
                            direction=trade.direction,
                            raw_message=trade.raw_message,
                            parsed_at=trade.parsed_at,
                            is_ode=(explicit_dte == 0),
                            days_to_expiration=explicit_dte,
                        )
                        return trade
                    # 2) EXP date in message — DTE computed from (exp - today)
                    exp_date, dte = self._parse_expiration(message)
                    if exp_date is not None:
                        trade = OptionTrade(
                            ticker=trade.ticker,
                            option_type=trade.option_type,
                            strike=trade.strike,
                            premium=trade.premium,
                            contracts=trade.contracts,
                            expiration=exp_date,
                            entry_price=trade.entry_price,
                            direction=trade.direction,
                            raw_message=trade.raw_message,
                            parsed_at=trade.parsed_at,
                            is_ode=(dte is not None and dte == 0),
                            days_to_expiration=dte,
                        )
                    return trade
            except Exception:
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

        is_ode, days_to_exp = self._detect_ode(message)
        return OptionTrade(
            ticker=ticker,
            option_type=option_type,
            strike=strike,
            premium=premium,
            expiration=data.get('expiration'),
            direction=self._detect_direction(message),
            raw_message=message,
            parsed_at=datetime.utcnow(),
            is_ode=is_ode,
            days_to_expiration=days_to_exp,
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

    def _parse_explicit_dte(self, message: str) -> Optional[int]:
        """
        Parse explicit DTE from message. Returns days (0 = today) or None.
        Supports: DTE N, N DTE (e.g. DTE 2, 2 DTE). Case-insensitive.
        """
        msg = message.strip()
        m = re.search(r"\bdte\s*(\d+)\b", msg, re.I)
        if m:
            return max(0, int(m.group(1)))
        m = re.search(r"\b(\d+)\s*dte\b", msg, re.I)
        if m:
            return max(0, int(m.group(1)))
        return None

    def _detect_ode(self, message: str) -> tuple:
        """Detect same-day expiration (0DTE/ODE). Returns (is_ode, days_to_expiration)."""
        msg_lower = message.lower().strip()
        ode_patterns = [
            r"0\s*dte", r"0dte", r"zero\s*dte",
            r"same\s*day", r"same-day", r"sameday",
            r"today\s*exp", r"exp\s*today", r"ode\b",
        ]
        for pat in ode_patterns:
            if re.search(pat, msg_lower):
                return True, 0
        return False, None

    def _parse_expiration(self, message: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Parse optional EXP date from message. Returns (exp_date_YYYY_MM_DD, days_to_expiration).
        Supports: EXP 2026-02-06, EXP 02/06/2026, EXP 2/6/26.
        """
        msg = message.strip()
        # EXP YYYY-MM-DD
        m = re.search(r"\bexp\s+(\d{4})-(\d{1,2})-(\d{1,2})\b", msg, re.I)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                exp = date(y, mo, d)
                exp_str = exp.strftime("%Y-%m-%d")
                today = date.today()
                dte = max(0, (exp - today).days)
                return exp_str, dte
            except ValueError:
                pass
        # EXP MM/DD/YYYY or MM/DD/YY
        m = re.search(r"\bexp\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\b", msg, re.I)
        if m:
            mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                exp = date(y, mo, d)
                exp_str = exp.strftime("%Y-%m-%d")
                today = date.today()
                dte = max(0, (exp - today).days)
                return exp_str, dte
            except ValueError:
                pass
        return None, None
    
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
            
        # Check minimum premium (ODE allows lower min)
        sizing = self.config.get("sizing", {})
        ode = self.config.get("ode", {})
        min_prem = sizing.get("min_premium_to_consider", 0.50)
        if getattr(trade, "is_ode", False) and ode.get("enabled", True):
            min_prem = ode.get("min_premium", 0.30)
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
