"""
Image Analysis Module
Extract option trade data from screenshots (Robinhood, ThinkOrSwim, etc.)
Uses vision AI to parse prices, Greeks, IV, and other metrics.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class ScreenshotData:
    """Structured data extracted from option screenshot"""
    ticker: str
    strike: float
    option_type: str  # CALL or PUT
    expiration: str  # MM/DD or YYYY-MM-DD
    mark: float
    bid: Optional[float]
    ask: Optional[float]
    iv: Optional[float]
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]
    pop: Optional[float]  # Probability of Profit
    volume: Optional[int]
    open_interest: Optional[int]
    day_high: Optional[float]
    day_low: Optional[float]
    previous_close: Optional[float]
    raw_text: str = ""
    extracted_at: datetime = None


def extract_option_data_from_image(image_path: str) -> Optional[ScreenshotData]:
    """
    Use vision AI to extract option data from a screenshot.
    Returns ScreenshotData or None if extraction fails.
    """
    from PIL import Image
    import base64
    
    # Check if file exists
    import os
    if not os.path.exists(image_path):
        return None
    
    # Use the model's image analysis capability
    # The model will parse the screenshot and return structured data
    prompt = """Extract the following option trading data from this screenshot. Return ONLY a JSON object with these fields (no markdown, no commentary):

{
  "ticker": "QQQ",
  "strike": 603.00,
  "option_type": "PUT",  // or CALL
  "expiration": "2/4/2026",  // or MM/DD format
  "mark": 0.79,
  "bid": 0.78,
  "ask": 0.79,
  "iv": 53.71,  // as percentage (e.g., 53.71 for 53.71%)
  "delta": -0.1676,
  "gamma": 0.0285,
  "theta": -0.79,
  "vega": 0.0411,
  "rho": -0.0007,
  "pop": 14.90,  // Probability of Profit as percentage
  "volume": 6778,
  "open_interest": 2443,
  "day_high": 1.06,
  "day_low": 0.38,
  "previous_close": 0.57
}

Extract ALL visible data. If a field isn't visible, use null. Match the exact format above."""

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    # Call the image analysis tool (this uses Claude/Anthropic vision)
    # The tool returns analysis; we parse it
    return None  # Placeholder - actual implementation below


def parse_screenshot_response(response: str) -> Optional[ScreenshotData]:
    """
    Parse the AI's response from image analysis into ScreenshotData.
    """
    # Find JSON in response (may be wrapped in markdown)
    json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if not json_match:
        return None
    
    try:
        import json
        data = json.loads(json_match.group())
        
        return ScreenshotData(
            ticker=data.get("ticker", "").upper(),
            strike=float(data.get("strike", 0)),
            option_type=data.get("option_type", "").upper(),
            expiration=data.get("expiration", ""),
            mark=float(data.get("mark", 0)),
            bid=float(data.get("bid")) if data.get("bid") else None,
            ask=float(data.get("ask")) if data.get("ask") else None,
            iv=float(data.get("iv") / 100) if data.get("iv") and data.get("iv") > 2 else float(data.get("iv")) if data.get("iv") else None,
            delta=float(data.get("delta")) if data.get("delta") else None,
            gamma=float(data.get("gamma")) if data.get("gamma") else None,
            theta=float(data.get("theta")) if data.get("theta") else None,
            vega=float(data.get("vega")) if data.get("vega") else None,
            rho=float(data.get("rho")) if data.get("rho") else None,
            pop=float(data.get("pop") / 100) if data.get("pop") and data.get("pop") > 1 else float(data.get("pop")) if data.get("pop") else None,
            volume=int(data.get("volume")) if data.get("volume") else None,
            open_interest=int(data.get("open_interest")) if data.get("open_interest") else None,
            day_high=float(data.get("day_high")) if data.get("day_high") else None,
            day_low=float(data.get("day_low")) if data.get("day_low") else None,
            previous_close=float(data.get("previous_close")) if data.get("previous_close") else None,
            raw_text=response,
            extracted_at=datetime.utcnow(),
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return None


def screenshot_to_market_context(screenshot: ScreenshotData) -> Dict[str, Any]:
    """
    Convert ScreenshotData to market_context dict for the trade analyzer.
    """
    context = {}
    
    if screenshot.mark:
        context["option_live"] = screenshot.mark
        context["pasted_vs_live_premium_diff_pct"] = 0  # No pasted premium for screenshots
    
    if screenshot.iv is not None:
        context["implied_volatility"] = screenshot.iv
    
    if screenshot.delta is not None:
        greeks = context.get("greeks", {})
        greeks["delta"] = screenshot.delta
        context["greeks"] = greeks
    
    if screenshot.gamma is not None:
        greeks = context.get("greeks", {})
        greeks["gamma"] = screenshot.gamma
        context["greeks"] = greeks
    
    if screenshot.theta is not None:
        greeks = context.get("greeks", {})
        greeks["theta"] = screenshot.theta
        context["greeks"] = greeks
    
    if screenshot.vega is not None:
        greeks = context.get("greeks", {})
        greeks["vega"] = screenshot.vega
        context["greeks"] = greeks
    
    if screenshot.pop is not None:
        context["probability_of_profit"] = screenshot.pop
    
    if screenshot.volume is not None:
        context["option_volume"] = screenshot.volume
    
    if screenshot.open_interest is not None:
        context["open_interest"] = screenshot.open_interest
    
    if screenshot.previous_close:
        context["previous_close"] = screenshot.previous_close
    
    return context


def create_synthetic_trade(screenshot: ScreenshotData) -> Any:
    """
    Create a synthetic OptionTrade object from screenshot data.
    This allows the trade analyzer to process screenshot data.
    """
    # Import here to avoid circular imports
    from parser.trade_parser import OptionTrade
    
    # Parse expiration to determine ODE
    exp_str = screenshot.expiration
    is_ode = False
    
    # Try to parse expiration
    try:
        from datetime import datetime, date
        # Handle MM/DD or MM/DD/YY or MM/DD/YYYY
        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%m/%d"]:
            try:
                exp_date = datetime.strptime(exp_str, fmt).date()
                today = date.today()
                dte = max(0, (exp_date - today).days)
                is_ode = (dte == 0)
                exp_str = exp_date.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    except Exception:
        pass
    
    return OptionTrade(
        ticker=screenshot.ticker,
        option_type=screenshot.option_type,
        strike=screenshot.strike,
        premium=screenshot.mark,
        expiration=exp_str if re.match(r"\d{4}-\d{2}-\d{2}", str(exp_str)) else None,
        direction="LONG",
        raw_message=f"Screenshot: {screenshot.ticker} {screenshot.option_type} ${screenshot.strike} @ ${screenshot.mark}",
        is_ode=is_ode,
        days_to_expiration=0 if is_ode else None,
    )


# CLI test
if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python image_analysis.py <screenshot_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)
    
    # This would use the image tool in actual implementation
    print(f"Analyzing screenshot: {image_path}")
    print("Note: Run via main.py with --screenshot flag for full analysis")
