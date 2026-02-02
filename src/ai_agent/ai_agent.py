"""
AI Agent Module
Calls Anthropic to produce: Go/No-Go, reasoning, stop loss, take-profit levels, support/resistance, ODE risks.
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
    reasoning: str
    stop_loss_suggestion: str
    take_profit_levels: List[str]
    support_resistance: List[str]
    ode_risks: List[str]
    raw_response: str = ""


class OptionAIAgent:
    """
    AI agent that analyzes an option play and returns a clear recommendation
    with stop loss, targets, and levels. Uses Anthropic Claude.
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
            from anthropic import Anthropic
            # MiniMax and other compatible providers: set ANTHROPIC_BASE_URL (e.g. https://api.minimax.io/anthropic)
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = Anthropic(**kwargs)
        return self._client

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
        Call Claude to produce: PLAY/DON'T PLAY, why, stop, targets, support/resistance, ODE risks.
        """
        market_context = market_context or {}
        news_context = news_context or []
        price_str = f"{current_price:.2f}" if current_price is not None else "unknown"

        # Build context for the prompt
        rule_decision = trade_plan.go_no_go
        rule_reasons = trade_plan.go_no_go_reasons or []
        red_flags = [f["message"] for f in analysis.red_flags] if analysis else []
        green_flags = [f["message"] for f in analysis.green_flags] if analysis else []

        prompt = self._build_prompt(
            trade=trade,
            trade_plan=trade_plan,
            current_price=price_str,
            market_context=market_context,
            news_context=news_context,
            rule_decision=rule_decision,
            rule_reasons=rule_reasons,
            red_flags=red_flags,
            green_flags=green_flags,
        )

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            # Compatible with Anthropic and MiniMax (blocks may have .type and .text)
            text = ""
            if response.content:
                for block in response.content:
                    t = getattr(block, "text", None)
                    if t:
                        text += t
            if not text and response.content:
                text = getattr(response.content[0], "text", "") or ""
            return self._parse_response(text, trade, trade_plan)
        except Exception as e:
            return RecommendationResult(
                recommendation=rule_decision,
                reasoning=f"AI unavailable ({e}). Using rule-based decision: {'; '.join(rule_reasons) or 'No reasons'}.",
                stop_loss_suggestion=f"Rule-based stop: ${trade_plan.stop_loss}",
                take_profit_levels=[
                    f"T1: ${trade_plan.target_1} ({trade_plan.target_1_r}R)",
                    f"Runner: ${trade_plan.runner_target}" if trade_plan.runner_contracts else "",
                ],
                support_resistance=[],
                ode_risks=["AI not available; consider ODE theta/gamma risk and time of day."] if getattr(trade, "is_ode", False) else [],
                raw_response="",
            )

    def _build_prompt(
        self,
        trade: Any,
        trade_plan: Any,
        current_price: str,
        market_context: Dict[str, Any],
        news_context: List[Dict[str, str]],
        rule_decision: str,
        rule_reasons: List[str],
        red_flags: List[str],
        green_flags: List[str],
    ) -> str:
        is_ode = getattr(trade, "is_ode", False)
        ode_note = " This is a SAME-DAY expiration (0DTE/ODE) play - very volatile; theta and gamma matter a lot." if is_ode else ""

        mc = ""
        if market_context.get("current_price") is not None:
            p = market_context["current_price"]
            mc = f" Underlying {trade.ticker} last: ${p:.2f}"
            if market_context.get("high") is not None and market_context.get("low") is not None:
                mc += f", day range ${market_context['low']:.2f}-${market_context['high']:.2f}."
            else:
                mc += "."
        if not mc and current_price != "unknown":
            mc = f" Underlying {trade.ticker} price (if known): ${current_price}."
        if market_context.get("option_live") is not None:
            mc += f" Option (live from Polygon): ${market_context['option_live']:.2f}."
        if market_context.get("moneyness_label"):
            mc += f" Strike: {market_context['moneyness_label']}."
        if market_context.get("five_d_return_pct") is not None:
            pct = market_context["five_d_return_pct"]
            mc += f" Underlying 5d: {pct:+.1f}%."
        if market_context.get("premium_diff_pct") is not None:
            mc += f" Pasted vs live option: {market_context['premium_diff_pct']:+.0f}%."
        if is_ode and market_context.get("minutes_to_close_et") is not None:
            m = market_context["minutes_to_close_et"]
            mc += f" Time to close (ET): {m // 60}h {m % 60}m."
        g = market_context.get("greeks") or {}
        if g:
            mc += f" Greeks: delta={g.get('delta')}, theta={g.get('theta')}, vega={g.get('vega')}."
        if market_context.get("implied_volatility") is not None:
            iv = market_context["implied_volatility"]
            mc += f" IV: {iv * 100:.1f}%." if iv <= 2 else f" IV: {iv:.1f}%."
        if market_context.get("break_even_price") is not None:
            mc += f" Break-even: ${market_context['break_even_price']:.2f}."

        news_block = ""
        if news_context:
            lines = []
            for n in news_context[:5]:
                title = n.get("title", "")
                desc = n.get("description", "")
                if title or desc:
                    lines.append(f"- {title}" + (f": {desc[:120]}..." if desc else ""))
            if lines:
                news_block = "\nRECENT NEWS (Brave Search):\n" + "\n".join(lines) + "\n"

        stale_rule = ""
        if market_context.get("premium_diff_pct") is not None:
            diff = abs(market_context["premium_diff_pct"])
            if diff > 50:
                stale_rule = "\nIMPORTANT: Pasted premium and live option price differ significantly. If the difference is over 50%, recommend DON'T PLAY and explain that the alert is likely stale; the trader should verify current price before acting."
        return f"""You are an expert options analyst. A trader pasted an option play and received a rule-based analysis. Your job is to give a clear, actionable recommendation: whether to PLAY or DON'T PLAY, and exactly what stop loss and take-profit levels to use.
{stale_rule}

OPTION PLAY:
- Ticker: {trade.ticker} | Type: {trade.option_type} | Strike: ${trade.strike} | Premium: ${trade.premium}
- Same-day expiration (0DTE/ODE): {is_ode}{ode_note}
{mc}
{news_block}

RULE-BASED PLAN:
- Decision: {rule_decision}. Reasons: {"; ".join(rule_reasons) or "None"}
- Position: {trade_plan.position.contracts} contracts | Stop: ${trade_plan.stop_loss} | Target 1: ${trade_plan.target_1} ({trade_plan.target_1_r}R) | Runner: {trade_plan.runner_contracts} @ ${trade_plan.runner_target}
- Red flags: {", ".join(red_flags) or "None"}
- Green flags: {", ".join(green_flags) or "None"}

Respond in this exact structure (use these section headers so the parser can read them):

RECOMMENDATION: [PLAY or DON'T PLAY]

WHY: [2-4 sentences: main reason to take or skip the trade, and how it fits the rules and flags.]

STOP LOSS: [Exact level, e.g. "$2.25" or "50% of premium at $1.75", and brief note if you disagree with the rule-based stop.]

TAKE PROFIT LEVELS:
- [First target, e.g. "T1: $4.50 (1.5R) — take 50% off"]
- [Second target / runner if applicable]
- [Any additional level]

SUPPORT / RESISTANCE: [List 2-4 key price levels on the underlying to watch, e.g. "Support: $214, $210. Resistance: $220, $225."]

ODE RISKS: [If same-day expiration: list 2-3 specific risks like theta decay, gamma, time of day. If not ODE, write "N/A."]
"""

    def _parse_response(self, text: str, trade: Any, trade_plan: Any) -> RecommendationResult:
        """Parse Claude/MiniMax response into RecommendationResult. Robust WHY extraction."""
        recommendation = "GO"
        reasoning = ""
        stop_loss_suggestion = f"${trade_plan.stop_loss}"
        take_profit_levels: List[str] = []
        support_resistance: List[str] = []
        ode_risks: List[str] = []

        # Split by section headers (flexible: WHY, Why, RECOMMENDATION, STOP LOSS, etc.)
        section_pattern = re.compile(
            r"\n\s*(?=RECOMMENDATION:|WHY:|Why:|STOP LOSS:|TAKE PROFIT:|SUPPORT|RESISTANCE:|ODE RISKS:)",
            re.IGNORECASE,
        )
        sections = section_pattern.split(text)
        for section in sections:
            section = section.strip()
            if not section:
                continue
            head = section.split("\n")[0].strip()
            rest = "\n".join(section.split("\n")[1:]).strip()
            if re.match(r"RECOMMENDATION\s*:", head, re.I):
                if "DON'T PLAY" in head.upper() or "NO" in head.upper():
                    recommendation = "DON'T PLAY"
                else:
                    recommendation = "PLAY"
            elif re.match(r"WHY\s*:", head, re.I):
                first_line_content = re.sub(r"^WHY\s*:\s*", "", head, flags=re.I).strip()
                reasoning = (first_line_content + "\n" + rest).strip() if rest else first_line_content
            elif re.match(r"STOP LOSS\s*:", head, re.I):
                stop_loss_suggestion = rest or stop_loss_suggestion
            elif re.match(r"TAKE PROFIT", head, re.I):
                lines = [l.strip().lstrip("- ").strip() for l in section.split("\n")[1:] if l.strip()]
                take_profit_levels = [l for l in lines if l] if lines else [f"T1: ${trade_plan.target_1}", f"Runner: ${trade_plan.runner_target}"]
            elif "SUPPORT" in head.upper() or "RESISTANCE" in head.upper():
                if rest:
                    support_resistance = [s.strip() for s in re.split(r"[.;]", rest) if s.strip()]
            elif re.match(r"ODE RISKS\s*:", head, re.I):
                if rest and "N/A" not in rest.upper():
                    ode_risks = [s.strip() for s in re.split(r"[.;]", rest) if s.strip()]

        # Fallback: extract reasoning from text between RECOMMENDATION and next section
        if not reasoning and text:
            fallback = self._extract_reasoning_fallback(text)
            if fallback:
                reasoning = fallback

        if not take_profit_levels:
            take_profit_levels = [f"T1: ${trade_plan.target_1} ({trade_plan.target_1_r}R)", f"Runner: ${trade_plan.runner_target}"]

        return RecommendationResult(
            recommendation=recommendation,
            reasoning=reasoning or "See rule-based plan above.",
            stop_loss_suggestion=stop_loss_suggestion,
            take_profit_levels=take_profit_levels,
            support_resistance=support_resistance,
            ode_risks=ode_risks,
            raw_response=text,
        )

    def _extract_reasoning_fallback(self, text: str) -> str:
        """Extract WHY/reasoning from raw text when section parsing missed it."""
        lines = text.split("\n")
        start = None
        end = None
        next_headers = ("STOP LOSS", "TAKE PROFIT", "SUPPORT", "RESISTANCE", "ODE RISKS")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if stripped.startswith("RECOMMENDATION"):
                start = i + 1
            if start is not None and end is None:
                for h in next_headers:
                    if stripped.startswith(h):
                        end = i
                        break
            if end is not None:
                break
        if start is not None:
            block = lines[start:end] if end is not None else lines[start:]
            candidate = "\n".join(l.rstrip() for l in block if l.strip()).strip()
            if len(candidate) > 20 and "RECOMMENDATION" not in candidate.upper():
                return candidate
        return ""
