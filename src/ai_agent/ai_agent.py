"""
AI Agent Module
Calls Anthropic/MiniMax to produce detailed: Go/No-Go, comprehensive reasoning, 
stop loss, take-profit levels, support/resistance, and ODE risks.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RecommendationResult:
    """Structured AI recommendation for an option play."""
    recommendation: str  # "PLAY" or "DON'T PLAY"
    reasoning: str  # Detailed why
    risk_assessment: str  # Max loss/gain scenarios
    entry_criteria: str  # Entry zone and confirmation
    exit_strategy: str  # Stop, targets, time exit
    support_resistance: List[str]
    market_context: str  # Trend, volatility, sentiment
    ode_risks: List[str]  # ODE-specific risks
    raw_response: str = ""


class OptionAIAgent:
    """
    AI agent that analyzes an option play and returns a detailed recommendation
    with stop loss, targets, and levels. Uses Anthropic Claude or MiniMax.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.analysis_config = self.config.get("analysis", {})
        self.model = self.analysis_config.get("model", "claude-sonnet-4-5")
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not set. Set it in your environment to use AI recommendations."
                )
            # MiniMax uses OpenAI-compatible API format
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            try:
                from openai import OpenAI
                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                # Fallback to requests if openai not available
                self._client = {"api_key": api_key, "base_url": base_url}
        return self._client

    def _call_api(self, prompt: str) -> str:
        """Call the API with the prompt and return the response text."""
        client = self._get_client()
        base_url = os.getenv("ANTHROPIC_BASE_URL", "")
        
        # Check if using OpenAI client
        if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            # OpenAI or compatible SDK
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
        else:
            # Fallback to direct HTTP request (MiniMax/OpenAI-compatible)
            import requests
            headers = {
                "Authorization": f"Bearer {client['api_key']}",
                "Content-Type": "application/json",
            }
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
            }
            url = f"{client['base_url']}/chat/completions"
            if not client['base_url'].endswith('/chat/completions'):
                url = f"{client['base_url']}/chat/completions"
            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if result.get("choices") and result["choices"][0].get("message", {}).get("content"):
                    return result["choices"][0]["message"]["content"]
            else:
                raise Exception(f"API call failed: {response.status_code} - {response.text}")
        
        return ""

    def get_recommendation(
        self,
        trade: Any,
        trade_plan: Any,
        analysis: Any,
        current_price: Optional[float] = None,
        market_context: Optional[Dict[str, Any]] = None,
        news_context: Optional[List[Dict[str, str]]] = None,
    ) -> RecommendationResult:
        """
        Call Claude/MiniMax to produce detailed recommendation.
        """
        market_context = market_context or {}
        news_context = news_context or []
        price_str = f"{current_price:.2f}" if current_price is not None else "unknown"

        prompt = self._build_prompt(
            trade=trade,
            trade_plan=trade_plan,
            current_price=price_str,
            market_context=market_context,
            news_context=news_context,
        )

        try:
            text = self._call_api(prompt)
            return self._parse_response(text, trade, trade_plan)
        except Exception as e:
            # Fallback to rule-based
            return self._rule_based_fallback(trade, trade_plan, market_context, str(e))

    def _build_prompt(
        self,
        trade: Any,
        trade_plan: Any,
        current_price: str,
        market_context: Dict[str, Any],
        news_context: List[Dict[str, str]],
    ) -> str:
        is_ode = getattr(trade, "is_ode", False)
        ode_note = " This is a SAME-DAY expiration (0DTE/ODE) play - very volatile; theta and gamma matter a lot." if is_ode else ""

        # Get rule-based info from analysis
        red_flags = []
        green_flags = []
        if hasattr(trade_plan, 'go_no_go_reasons'):
            red_flags = trade_plan.go_no_go_reasons or []
        if hasattr(trade_plan, 'go_no_go'):
            rule_decision = trade_plan.go_no_go

        # Build comprehensive market context
        mc_lines = []
        
        # Core pricing
        if market_context.get("current_price") is not None:
            p = market_context["current_price"]
            mc_lines.append(f"UNDERLYING PRICE: ${p:.2f}")
            if market_context.get("high") is not None and market_context.get("low") is not None:
                mc_lines.append(f"DAY RANGE: ${market_context['low']:.2f} - ${market_context['high']:.2f}")
        
        if market_context.get("option_live") is not None:
            mc_lines.append(f"LIVE OPTION PRICE: ${market_context['option_live']:.2f}")
        
        if market_context.get("pasted_vs_live_premium_diff_pct") is not None:
            diff = market_context["pasted_vs_live_premium_diff_pct"]
            mc_lines.append(f"PREMIUM CHANGE: {diff:+.1f}% (pasted vs live)")
        
        if market_context.get("moneyness_label"):
            mc_lines.append(f"STRIKE STATUS: {market_context['moneyness_label']}")
        
        if market_context.get("five_d_return_pct") is not None:
            mc_lines.append(f"5-DAY RETURN: {market_context['five_d_return_pct']:+.1f}%")
        
        if is_ode and market_context.get("minutes_to_close_et") is not None:
            m = market_context["minutes_to_close_et"]
            mc_lines.append(f"TIME TO CLOSE: {m // 60}h {m % 60}m")

        # Greeks
        g = market_context.get("greeks") or {}
        if g:
            greek_parts = []
            for key in ["delta", "gamma", "theta", "vega"]:
                if g.get(key) is not None:
                    greek_parts.append(f"{key}={g[key]:.3f}")
            if greek_parts:
                mc_lines.append(f"GREEKS: {', '.join(greek_parts)}")

        # Volatility
        if market_context.get("implied_volatility") is not None:
            iv = market_context["implied_volatility"]
            mc_lines.append(f"IV: {iv * 100:.1f}%" if iv <= 2 else f"IV: {iv:.1f}%")
        
        if market_context.get("probability_of_profit") is not None:
            mc_lines.append(f"PROBABILITY OF PROFIT: {market_context['probability_of_profit']:.1%}")
        
        if market_context.get("break_even_price") is not None:
            mc_lines.append(f"BREAK-EVEN: ${market_context['break_even_price']:.2f}")
        
        if market_context.get("iv_rank") is not None:
            mc_lines.append(f"IV RANK: {market_context['iv_rank']:.0f}%")
        
        if market_context.get("realized_vol_30d") is not None:
            mc_lines.append(f"30D REALIZED VOL: {market_context['realized_vol_30d']:.1f}%")

        # Technicals
        tech = market_context.get("technical") or {}
        if tech and isinstance(tech, dict):
            daily = tech.get("daily") or {}
            if daily:
                parts = []
                if daily.get("rsi") is not None:
                    parts.append(f"RSI(14)={daily['rsi']:.0f}")
                if daily.get("price_above_sma_20") is not None:
                    parts.append(f"price {'>' if daily['price_above_sma_20'] else '<'} SMA-20")
                if daily.get("macd_bullish") is not None:
                    parts.append(f"MACD={'BULLISH' if daily['macd_bullish'] else 'BEARISH'}")
                if parts:
                    mc_lines.append(f"TECHNICALS: {' | '.join(parts)}")

        # Stress test
        stress = market_context.get("stress_test")
        if stress:
            for pct, pl, _ in stress:
                if abs(pct - (-0.01)) < 0.001:
                    mc_lines.append(f"STRESS -1%: ${pl:+.0f}")

        # ATR levels
        if market_context.get("atr_stop") is not None:
            mc_lines.append(f"ATR STOP: ${market_context['atr_stop']:.2f}")

        mc_str = "\n".join(mc_lines)

        # News
        news_block = ""
        if news_context:
            lines = []
            for n in news_context[:5]:
                title = n.get("title", "")
                if title:
                    lines.append(f"- {title}")
            if lines:
                news_block = "\nRECENT NEWS:\n" + "\n".join(lines)

        # Stale alert warning
        stale_warning = ""
        if market_context.get("premium_diff_pct") is not None:
            diff = abs(market_context["premium_diff_pct"])
            if diff > 50:
                stale_warning = "\n⚠️ PASTED PREMIUM DIFFERS >50% FROM LIVE - ALERT LIKELY STALE"

        return f"""You are an expert options trader and analyst. Your job is to provide a DEEP, COMPREHENSIVE analysis of this option trade.

{stale_warning}

═══════════════════════════════════════════════════════════════
THE TRADE
═══════════════════════════════════════════════════════════════
TICKER: {trade.ticker}
TYPE: {trade.option_type}
STRIKE: ${trade.strike}
PREMIUM: ${trade.premium}
EXPIRATION: {'TODAY (0DTE)' if is_ode else 'Standard'}
{ode_note}

═══════════════════════════════════════════════════════════════
MARKET DATA
═══════════════════════════════════════════════════════════════
{mc_str}
{news_block}

═══════════════════════════════════════════════════════════════
RULE-BASED PLAN
═══════════════════════════════════════════════════════════════
DECISION: {getattr(trade_plan, 'go_no_go', 'N/A')}
STOP: ${getattr(trade_plan, 'stop_loss', 'N/A')} ({getattr(trade_plan, 'stop_risk_pct', 'N/A')}% of premium)
TARGET 1: ${getattr(trade_plan, 'target_1', 'N/A')} ({getattr(trade_plan, 'target_1_r', 'N/A')}R)
RUNNER: {getattr(trade_plan, 'runner_contracts', 'N/A')} @ ${getattr(trade_plan, 'runner_target', 'N/A')}
CONTRACTS: {getattr(trade_plan.position, 'contracts', 'N/A') if hasattr(trade_plan, 'position') else 'N/A'}
MAX RISK: ${getattr(trade_plan.position, 'max_risk_dollars', 'N/A') if hasattr(trade_plan, 'position') else 'N/A'}

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT - BE VERY DETAILED
═══════════════════════════════════════════════════════════════

RECOMMENDATION: [PLAY or DON'T PLAY - choose ONE]

WHY - DETAILED REASONING:
[Write 4-6 thorough sentences covering:
1. Primary reason for recommendation - what makes this trade work or fail
2. Risk/reward assessment - is the R:R achievable given current conditions?
3. Technical context - how do price, trend, and indicators align?
4. Volatility outlook - IV rank, expected moves, crush risk
5. Time decay impact - especially for 0DTE
6. What specific price action would invalidate the thesis?]

RISK ASSESSMENT:
- Max Loss Scenario: [What happens at max loss and likelihood]
- Max Gain Scenario: [What conditions needed for max gain]
- Risk/Reward Reality: [Is {getattr(trade_plan, 'target_1_r', 'N/A')}R achievable given volatility and time?]
- Probability Estimate: [Your best guess of success probability based on all factors]

ENTRY CRITERIA:
- Entry Zone: [Specific price range to enter]
- Confirmation Needed: [What candle pattern, indicator, or condition confirms entry]
- Best Entry Timing: [Open, mid-morning, lunch, close - be specific]

EXIT STRATEGY:
- Primary Stop: [Exact stop level and when to pull it]
- Trailing Approach: [If price moves favorably, how do you protect profits?]
- Target 1 Exit: [Exact level and how much to close]
- Runner Management: [Size, target, and trailing approach for runner]
- Time Exit: [If not profitable by [time], exit regardless]

SUPPORT & RESISTANCE:
[List 4-6 key levels - 2-3 below, 2-3 above. For each, explain WHY it's significant]

MARKET CONTEXT:
- Trend Direction: [Bullish/Bearish/Neutral - and why]
- Volatility Regime: [High IV/low IV, expected direction]
- Sentiment: [Fear/greed levels, positioning]
- Key Catalysts: [Earnings, CPI, Fed, etc. in next 24-48h]

ODE RISKS (if 0DTE):
- Theta Impact: [How much premium lost per hour?]
- Gamma Exposure: [How much does price move for $1 underlying move?]
- Best Trading Hours: [When to trade, when to avoid]
- Liquidity Concerns: [Slippage risk at current levels]
"""

    def _parse_response(self, text: str, trade: Any, trade_plan: Any) -> RecommendationResult:
        """Parse detailed AI response."""
        recommendation = "DON'T PLAY"  # Default to conservative
        
        # Extract sections with flexible parsing
        sections = {}
        current_section = None
        current_content = []
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Check for section headers
            header_match = re.match(r'^(RECOMMENDATION|RISK ASSESSMENT|ENTRY CRITERIA|EXIT STRATEGY|SUPPORT|RESISTANCE|MARKET CONTEXT|ODE RISKS|WHY)', 
                                    line, re.IGNORECASE)
            if header_match:
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = header_match.group(1).upper()
                current_content = []
                # Get content after colon
                after_colon = line.split(':', 1)
                if len(after_colon) > 1:
                    current_content.append(after_colon[1].strip())
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        # Parse recommendation
        rec_line = sections.get('RECOMMENDEMENT', sections.get('RECOMMENDATION', ''))
        if rec_line:
            if 'PLAY' in rec_line.upper() and 'DON\'T' not in rec_line.upper():
                recommendation = "PLAY"
            elif 'DON\'T PLAY' in rec_line.upper() or 'NO PLAY' in rec_line.upper():
                recommendation = "DON'T PLAY"
        
        # Build support/resistance list
        sr_lines = []
        sr_content = sections.get('SUPPORT', sections.get('SUPPORT & RESISTANCE', ''))
        if sr_content:
            for line in sr_content.split('\n'):
                line = line.strip().lstrip('-*•')
                if line and len(line) > 3:
                    sr_lines.append(line)
        
        # Build ODE risks
        ode_lines = []
        ode_content = sections.get('ODE RISKS', '')
        if ode_content:
            for line in ode_content.split('\n'):
                line = line.strip().lstrip('-*•')
                if line and len(line) > 3:
                    ode_lines.append(line)
        
        return RecommendationResult(
            recommendation=recommendation,
            reasoning=sections.get('WHY', sections.get('WHY - DETAILED REASONING', 'See analysis above.')),
            risk_assessment=sections.get('RISK ASSESSMENT', 'See rule-based plan for risk parameters.'),
            entry_criteria=sections.get('ENTRY CRITERIA', 'Enter at or below pasted premium.'),
            exit_strategy=sections.get('EXIT STRATEGY', f"Stop: ${trade_plan.stop_loss}, Target: ${trade_plan.target_1}"),
            support_resistance=sr_lines if sr_lines else [f"Support: ${trade.strike * 0.98}", f"Resistance: ${trade.strike * 1.02}"],
            market_context=sections.get('MARKET CONTEXT', 'Market conditions as noted above.'),
            ode_risks=ode_lines if ode_lines else (["N/A - not 0DTE"] if not getattr(trade, 'is_ode', False) else ["Standard ODE risks apply."]),
            raw_response=text,
        )

    def _rule_based_fallback(self, trade: Any, trade_plan: Any, market_context: Dict, error: str) -> RecommendationResult:
        """Generate detailed fallback when AI is unavailable."""
        is_ode = getattr(trade, 'is_ode', False)
        
        # Calculate premium diff
        premium_diff = market_context.get('premium_diff_pct', 0)
        stale_warning = "⚠️ ALERT LIKELY STALE" if abs(premium_diff) > 50 else ""
        
        # Technical summary
        tech = market_context.get('technical') or {}
        daily = tech.get('daily', {}) if isinstance(tech, dict) else {}
        rsi = daily.get('rsi', 'N/A')
        
        return RecommendationResult(
            recommendation=getattr(trade_plan, 'go_no_go', 'GO'),
            reasoning=f"""Rule-based analysis with {stale_warning}. 
            
Primary factors: Position size ({getattr(trade_plan.position, 'contracts', 'N/A')} contracts) and max risk (${getattr(trade_plan.position, 'max_risk_dollars', 'N/A')}).
Technicals: RSI {rsi}, underlying 5d return {market_context.get('five_d_return_pct', 'N/A'):+.1f}%.
IV Rank: {market_context.get('iv_rank', 'N/A')}% - {'low IV = favorable for buys' if market_context.get('iv_rank', 100) < 30 else 'high IV = caution on longs' if market_context.get('iv_rank', 0) > 70 else 'moderate IV'}.

{stale_warning}""",
            risk_assessment=f"""MAX LOSS: ${getattr(trade_plan.position, 'max_risk_dollars', 'N/A')} if stop at ${trade_plan.stop_loss} is hit.
MAX GAIN: ~${getattr(trade_plan, 'max_gain_dollars', 'N/A')} if target at ${trade_plan.target_1} is hit ({trade_plan.target_1_r}R).
PROBABILITY: Based on {'low IV' if market_context.get('iv_rank', 50) < 30 else 'high IV' if market_context.get('iv_rank', 50) > 70 else 'moderate'} volatility environment.""",
            entry_criteria=f"""ENTRY ZONE: ${trade.premium - 0.05:.2f} - ${trade.premium + 0.05:.2f}
CONFIRMATION: Wait for price to stabilize at or below entry zone before entering.
TIMING: {'Trade early in day for 0DTE' if is_ode else 'Best during market hours'}.""",
            exit_strategy=f"""PRIMARY STOP: ${trade_plan.stop_loss} ({trade_plan.stop_risk_pct}% of premium) - {'sooner for 0DTE' if is_ode else 'standard stop'}.
TARGET 1: ${trade_plan.target_1} ({trade_plan.target_1_r}R) - take 50% off here.
RUNNER: {trade_plan.runner_contracts} contracts @ ${trade_plan.runner_target} - trail to breakeven after taking partial.
TIME EXIT: {'Exit 1 hour before close if not profitable' if is_ode else 'Exit at 50% DTE if not near targets'}.""",
            support_resistance=[
                f"Support: ${trade.strike * 0.97:.0f} ({'major' if market_context.get('five_d_return_pct', 0) < -2 else 'minor'} level)",
                f"Support: ${trade.strike * 0.95:.0f}",
                f"Resistance: ${trade.strike * 1.02:.0f}",
                f"Resistance: ${trade.strike * 1.05:.0f}",
            ],
            market_context=f"""TREND: {'Bearish' if market_context.get('five_d_return_pct', 0) < -2 else 'Bullish' if market_context.get('five_d_return_pct', 0) > 2 else 'Neutral'} based on 5d return of {market_context.get('five_d_return_pct', 0):+.1f}%.
VOLATILITY: IV Rank {market_context.get('iv_rank', 'N/A')}% - {'favorable for long options' if market_context.get('iv_rank', 50) < 40 else 'caution - IV crush risk'}.
SENTIMENT: {'Fear' if market_context.get('iv_rank', 50) > 60 else 'Greed' if market_context.get('iv_rank', 50) < 40 else 'Neutral'} in {trade.ticker}.""",
            ode_risks=["Theta decay accelerates near close - monitor time remaining.", "Gamma risk - price moves faster near expiration.", "Liquidity may thin in final hours."] if is_ode else ["N/A - not 0DTE"],
        )
