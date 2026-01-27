# Trade Analyzer

Automated option trade analyzer for Discord. Listens for trade alerts, parses them, applies rule-based risk management, and outputs a complete execution plan.

## Philosophy

- **Rule-driven core**: Position sizing, stops, and risk management are deterministic formulas
- **AI for analysis only**: AI provides explanations, context, and red-flag checks—not money decisions
- **Go/No-Go as pass/fail**: Trades either pass predefined rules or they don't

## Architecture

```
trade-analyzer/
├── config/
│   └── config.yaml          # All risk parameters and format definitions
├── src/
│   ├── parser/
│   │   └── trade_parser.py  # Extract structured data from Discord alerts
│   ├── market_data/         # (placeholder) Real-time price/IV data
│   ├── risk_engine/
│   │   └── risk_engine.py   # Position sizing, stops, targets
│   ├── analysis/
│   │   └── trade_analyzer.py # AI analysis, red flags, explanations
│   ├── discord_output/
│   │   └── discord_output.py # Format responses for Discord
│   └── main.py              # Discord bot entry point
├── tests/
├── requirements.txt
└── README.md
```

## Setup

```bash
# Clone and install
git clone https://github.com/yourusername/trade-analyzer.git
cd trade-analyzer
pip install -r requirements.txt

# Configure
cp config/config.yaml config/config.yaml
# Edit config.yaml with your settings
```

## Configuration

All parameters are in `config/config.yaml`:

```yaml
# Account
account:
  total_capital: 100000    # Total portfolio value
  max_risk_per_trade: 0.02 # 2% max risk per trade

# Position sizing
sizing:
  default_contracts: 1
  min_premium_to_consider: 0.50

# Stop losses
stops:
  default_pct: 0.50        # 50% of premium
  max_loss_per_contract: 500

# Targets & runner
targets:
  profit_target_r: 2.0
  runner_activation_r: 3.0
  runner_remaining_pct: 0.50
```

## Alert Formats

Supports multiple Discord alert formats:

```yaml
alert_formats:
  - name: "demon_standard"
    pattern: "(?i)(?:BUY|SELL|SIGNAL)\\s+([A-Z]+)\\s+(\\d+)\\s*([CP])\\s*(\\d+)[^\\d]*(\\d+\\.?\\d*)"
    example: "BUY AAPL 01/31 215 CALL @ 3.50"
    
  - name: "simplified"
    pattern: "(?i)([A-Z]+)\\s+([CP])\\s*(\\d+).*?@\\s*(\\d+\\.?\\d*)"
    example: "AAPL CALL 215 @ 3.50"
```

## Running

```bash
export DISCORD_BOT_TOKEN=your_token
export DISCORD_CHANNEL_ID=your_channel_id
python src/main.py
```

## Example Output

```
✅ GO | 5 contracts | Stop $2.75 | T1 $5.25 (2R) | Runner 2 @ $8.25
```

Or in detailed mode:

```
✅ AAPL CALL $215
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Decision: GO | Contracts: 5 | Risk: $1,250 (1.25%)
Entry: $3.50-$3.60 | Stop: $2.75 (21.4%) | Target 1: $5.25 (2R)
Runner: 2 contracts @ $8.25 | Max Loss: $1,125 | Max Gain: $3,500
Setup Quality: HIGH | Confidence: 85%
```

## Risk Engine Rules

1. **Position Sizing**: Risk ÷ Premium = Contracts (floored, min 1)
2. **Stop Loss**: 50% of premium OR $500 max loss per contract (whichever is tighter)
3. **Target 1**: 2R (2× risk)
4. **Runner**: Sell half at 3R, max target at 5R
5. **Go/No-Go**: Pass/fail against all rules

## AI Analysis

The AI module provides:
- Trade summary and explanation
- Red flag detection (high IV, too many days OTM, etc.)
- Green flag identification
- Setup quality assessment
- Confidence score

AI does **not** make money decisions—it only analyzes and explains.

## License

MIT
