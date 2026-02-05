# LLM Integration Guide

## Overview

The trade analyzer now includes **LLM-enhanced natural language analysis** that transforms technical indicators into actionable insights, market narratives, and specific recommendations.

**What It Does:**
- ✅ **Rule-based scoring remains unchanged** - Fast, deterministic, reliable
- ✅ **LLM adds natural language explanations** - Why scores are what they are
- ✅ **Market narratives** - What the technicals are telling us
- ✅ **Actionable recommendations** - Specific next steps and price levels to watch

**Hybrid Approach = Best of Both Worlds:**
- Deterministic technical analysis for scoring
- AI-powered natural language for understanding

---

## Setup

### 1. Install Anthropic SDK

```bash
pip install anthropic
```

### 2. Set API Key

**For Anthropic Claude:**
```bash
# Windows
set ANTHROPIC_API_KEY=your_api_key_here

# Linux/Mac
export ANTHROPIC_API_KEY=your_api_key_here
```

**For MiniMax (alternative provider):**
```bash
# Windows
set ANTHROPIC_API_KEY=your_minimax_key
set ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic

# Linux/Mac
export ANTHROPIC_API_KEY=your_minimax_key
export ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
```

### 3. Configure Model

Edit `config/config.yaml`:
```yaml
analysis:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-5  # or MiniMax-M2.1
  llm_enabled: true  # Set to false to disable LLM
```

---

## What Gets Enhanced

### Before LLM (Rule-Based Only)

```
Setup Score: 81/100
Red Flags: 2
  [HIGH] Counter-trend trade: call entry in downtrend (strength: 80)
  [MEDIUM] Bearish bearish_pinbar pattern conflicts with call entry
Green Flags: 3
  [OK] Healthy premium for position sizing
  [OK] Passes all rule-based checks
  [OK] Bullish morning_star pattern detected (strength: 93/100)
```

**Problem:** You know there are issues, but what do you DO about it?

### After LLM (Enhanced)

```
ENHANCED SUMMARY:
AAPL presents a challenging setup with mixed signals. While a bullish morning
star reversal pattern has formed (93/100 strength), the stock remains in a
strong downtrend. This call entry constitutes a counter-trend trade, which
historically reduces win probability from 70% to approximately 35-40%.

MARKET CONTEXT:
The technical analysis reveals AAPL is in a confirmed downtrend with strength
of 80/100, characterized by lower highs and lower lows over the past 50 days.
Price is trading near VWAP at $275.69, indicating fair value but not
overextended. The nearest resistance at $277.84 provides limited upside (only
1.3%), while the absence of support zones below current price suggests a weak
base. Volume has been stable with an 18.5% increase, but not showing the
dramatic spike typically needed for trend reversals.

TRADE REASONING:
The 81/100 score (down from a naive 89/100) accurately reflects elevated risk:
- The HIGH severity counter-trend flag (-12 points) is warranted. Buying calls
  in a downtrend means fighting established momentum.
- The bearish pin bar pattern directly conflicts with the bullish thesis
- The bullish morning star (+10 points) is the ONE bright spot - it suggests
  possible exhaustion
- However, one reversal pattern in isolation is insufficient evidence

This isn't a bad trade, but it's a TIMING trade - you're trying to catch the
bottom. Most traders lose money attempting this.

RECOMMENDATIONS:
1. WAIT FOR CONFIRMATION
   - Don't enter now. Wait for price to break and close above $277.84 resistance
   - Confirmation would be: break above resistance + volume spike + bullish close

2. IF YOU MUST TRADE NOW (Not recommended):
   - Size DOWN to 0.5x normal position (high risk)
   - Set tight stop at $273 (current support approximation)
   - Take profit aggressively at $277.50 (near resistance)

3. BETTER APPROACH:
   - Add to watchlist, don't trade yet
   - Wait for one of these:
     a) Break above $277.84 on volume (trend change confirmed)
     b) Second bullish reversal pattern forms (added conviction)
     c) Higher low forms above $270 (structure improving)

4. PRICE LEVELS TO MONITOR:
   - $277.84: Key resistance - breakout level
   - $270: Potential support if more downside
   - $280: If breaks resistance, next target

5. INVALIDATION:
   - If price breaks below $270, downtrend continuation confirmed
   - Exit immediately, don't hold hoping for recovery

BOTTOM LINE: This is a 35% win probability trade disguised as 81/100 because
of the counter-trend nature. The morning star is interesting but not enough.
Wait for trend evidence before risking capital.
```

**Solution:** Now you know exactly what to do, what to watch, and why.

---

## Output Structure

The LLM analysis adds these fields to `AnalysisResult`:

### 1. `enhanced_summary`
- 2-3 sentence overview
- Big picture assessment
- Key takeaway

### 2. `market_narrative`
- What technical analysis reveals
- Current market conditions
- Price action context
- Volume and trend implications

### 3. `trade_reasoning`
- Why the score is what it is
- Analysis of red/green flags
- Risk assessment
- Probability discussion
- Counter-trend warnings with explanation

### 4. `recommendations`
- Specific, actionable steps
- Entry strategy (now vs wait)
- Position sizing guidance
- Specific price levels to monitor
- Invalidation criteria
- What would change your mind

### 5. `full_llm_analysis`
- Complete raw response
- For debugging or archival

---

## Usage Examples

### Basic Usage

```python
from analysis.trade_analyzer import TradeAnalyzer

analyzer = TradeAnalyzer('config/config.yaml')

# market_context from your technical analysis modules
analysis = analyzer.analyze(
    trade=trade,
    trade_plan=trade_plan,
    current_price=current_price,
    market_context=market_context  # Include all technical data
)

# Access LLM-enhanced outputs
print(analysis.enhanced_summary)
print(analysis.market_narrative)
print(analysis.trade_reasoning)
print(analysis.recommendations)
```

### Display in Application

```python
# Display results
print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

print(f"\nSetup Score: {analysis.setup_score}/100")
print(f"Quality: {analysis.setup_quality}")

# Show LLM analysis if available
if analysis.enhanced_summary:
    print("\n" + "-"*80)
    print("ENHANCED SUMMARY")
    print("-"*80)
    print(analysis.enhanced_summary)

    print("\n" + "-"*80)
    print("MARKET CONTEXT")
    print("-"*80)
    print(analysis.market_narrative)

    print("\n" + "-"*80)
    print("REASONING")
    print("-"*80)
    print(analysis.trade_reasoning)

    print("\n" + "-"*80)
    print("RECOMMENDATIONS")
    print("-"*80)
    print(analysis.recommendations)
```

### Disable LLM (Fallback)

```yaml
# config/config.yaml
analysis:
  llm_enabled: false  # Disables LLM, keeps rule-based scoring
```

Or don't set ANTHROPIC_API_KEY - system will gracefully fall back.

---

## Cost Considerations

### API Usage

**Per Trade Analysis:**
- Input tokens: ~1,000-1,500 (technical data)
- Output tokens: ~500-1,000 (analysis)
- **Total: ~2,000-2,500 tokens per trade**

**Costs (Anthropic Claude Sonnet 4.5):**
- Input: $3 per million tokens
- Output: $15 per million tokens
- **Per trade: ~$0.02-0.03**

**For 100 trades:**
- Cost: ~$2-3
- Value if prevents ONE bad trade: $100+
- **ROI: Massive**

### When to Use LLM

**Always Use:**
- Analyzing new trades before entry
- Complex setups with conflicting signals
- Counter-trend trades (need explanation)
- Learning/educational purposes

**Optional:**
- Backtesting (use rule-based only)
- Paper trading validation
- High-frequency scanning

### Optimization

**Batch Analysis:**
```python
# Analyze multiple trades in one call
# (Implementation would combine prompts)
```

**Cache Results:**
```python
# Cache analysis for same setup within timeframe
# Avoid re-analyzing identical conditions
```

---

## Customization

### Modify Prompt

Edit `_build_analysis_prompt()` in `trade_analyzer.py`:

```python
def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
    # Add your custom sections
    prompt = f"""You are an expert trader...

    [Add your custom instructions here]

    Consider:
    - Risk tolerance: {your_risk_tolerance}
    - Trading style: {your_style}
    - Time horizon: {your_horizon}
    """
    return prompt
```

### Change Model

**Use GPT-4 instead:**
```python
# Switch to OpenAI
from openai import OpenAI
self.llm = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
```

**Use local model:**
```python
# Use Ollama or similar
# Point ANTHROPIC_BASE_URL to local endpoint
```

---

## Troubleshooting

### "LLM analysis not available"

**Causes:**
1. ANTHROPIC_API_KEY not set
2. `anthropic` package not installed
3. `llm_enabled: false` in config

**Solution:**
```bash
pip install anthropic
set ANTHROPIC_API_KEY=your_key
# Edit config.yaml: llm_enabled: true
```

### "API Error" / Request Failed

**Causes:**
1. Invalid API key
2. Rate limiting
3. Network issues
4. Model not available

**Solution:**
- Check API key validity
- Add retry logic
- Check Anthropic status page
- Verify model name in config

### Slow Response Times

**Normal:** 2-5 seconds for comprehensive analysis

**If slower:**
- Network latency
- Model overload (rare)
- Token count too high

**Optimize:**
- Reduce prompt verbosity
- Use faster model (Claude Haiku)
- Implement caching

### Output Quality Issues

**Problem:** Generic or unhelpful responses

**Solutions:**
1. Provide more context in prompt
2. Add specific examples of good analysis
3. Include your trading rules/preferences
4. Request specific format/structure

---

## Testing

### Test Without Real Trades

```bash
cd tests
python test_llm_enhanced.py AAPL CALL
```

This will:
1. Fetch real market data
2. Run all technical analysis
3. Generate LLM-enhanced output
4. Display formatted results

### Validate Output Quality

Check that LLM provides:
- ✅ Specific price levels
- ✅ Clear action items
- ✅ Risk assessment
- ✅ Invalidation criteria
- ✅ Reasoning backed by technical data

### Compare Old vs New

Run both:
```bash
python tests/test_simple.py  # Rule-based only
python tests/test_llm_enhanced.py  # With LLM
```

Compare clarity and actionability.

---

## Best Practices

### 1. Use LLM for Decision Support, Not Decisions

- LLM explains, YOU decide
- Don't blindly follow LLM recommendations
- Cross-reference with your strategy

### 2. Validate LLM Reasoning

- Check that LLM correctly interpreted technical data
- Ensure recommendations align with shown analysis
- Flag hallucinations or contradictions

### 3. Combine with Rule-Based Scoring

- Trust the 0-100 score (deterministic)
- Use LLM to understand WHY that score
- LLM adds context, not accuracy

### 4. Customize for Your Style

- Modify prompts to match your risk tolerance
- Add your trading rules to prompt
- Request format that matches your workflow

### 5. Monitor API Usage

- Track costs if analyzing many trades
- Implement caching for repeated analyses
- Consider rate limits

---

## Examples of Good LLM Output

### Example 1: Clear Warning

```
RECOMMENDATION: AVOID
This is a classic counter-trend trap. The downtrend has 80/100 strength with
multiple confirmations. The morning star pattern is interesting but isolated.
You need at least TWO of the following before entry:
1. Break above $277.84 resistance
2. Second bullish pattern
3. Volume spike >2x average
Wait for confirmation. Missing this trade is better than catching a falling knife.
```

### Example 2: Conditional Entry

```
RECOMMENDATION: WAIT THEN PLAY
Setup has 85/100 score WITH a critical condition: wait for break above $280.
If price breaks above $280 on volume >1.5x average:
- Enter at $280.50 (confirmation)
- Stop at $277.50 (below resistance-turned-support)
- Target $285 (next resistance)
- Size: 1.0x normal
Current entry at $278 = premature, only 70% win probability.
```

### Example 3: Strong Setup

```
RECOMMENDATION: STRONG PLAY (1.5x size)
Everything aligned:
✓ Uptrend (85/100 strength)
✓ Price at support $215 (3 touches, strong)
✓ Bullish engulfing on volume
✓ Multi-timeframe alignment
✓ VWAP support
This is a textbook setup. Expected win rate: 75-80%.
Entry: Now at $215-216
Stop: $213 (below support)
Target: $220 (resistance, 2.5R)
```

---

## Future Enhancements

### Potential Additions

1. **Trade Journal Analysis**
   - LLM reviews your past trades
   - Identifies patterns in wins/losses
   - Personalized recommendations

2. **News Integration**
   - Fetch relevant news for ticker
   - LLM synthesizes with technical analysis
   - Context-aware recommendations

3. **Sentiment Analysis**
   - Social media sentiment
   - Options flow data
   - Institutional positioning

4. **Multi-Trade Portfolio Analysis**
   - Analyze correlations
   - Portfolio-level recommendations
   - Risk concentration warnings

5. **Learning Mode**
   - LLM explains WHY certain setups work
   - Educational commentary
   - Pattern recognition training

---

## Summary

**LLM Integration Benefits:**
- ✅ Natural language understanding
- ✅ Actionable, specific recommendations
- ✅ Market context and narrative
- ✅ Educational value
- ✅ Better decision-making

**Key Points:**
- Rule-based scoring remains foundation (fast, reliable)
- LLM adds interpretation and guidance
- ~$0.02-0.03 per analysis
- Graceful fallback if LLM unavailable
- Fully customizable

**Next Steps:**
1. Set ANTHROPIC_API_KEY
2. Run `python tests/test_llm_enhanced.py`
3. Review output quality
4. Integrate into your workflow
5. Customize prompts as needed

**Result: More informed, confident trading decisions backed by both technical analysis and AI-powered insights.**
