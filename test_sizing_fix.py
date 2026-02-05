"""Quick test of position sizing fix"""
import sys
sys.path.insert(0, 'src')

from risk_engine.position_sizer import PositionSizer
import yaml

# Load config
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

# Create sizer
sizer = PositionSizer(config)

# Test scenario: score 32 (low), IV rank 18 (low)
result = sizer.calculate_position_size(
    account_value=100000,
    entry_price=2.50,
    stop_loss=1.25,
    setup_score=32,
    iv_rank=18,
    trade_history=[],
    current_drawdown_pct=0.0
)

print("="*60)
print("POSITION SIZING TEST")
print("="*60)
print(f"Entry: $2.50")
print(f"Stop: $1.25")
print(f"Risk per contract: ${2.50 - 1.25} = $1.25/share = $125/contract")
print(f"Setup score: 32/100 (LOW)")
print(f"IV Rank: 18% (LOW - favorable)")
print()
print(f"Expected: ~8-16 contracts (2% of $100k = $2k, $2k/$125 = 16 base)")
print()
print("RESULT:")
print(f"  Contracts: {result['contracts']}")
print(f"  Risk: ${result['risk_dollars']:.2f} ({result['risk_pct']:.2f}%)")
print(f"  Position value: ${result['position_value']:.2f}")
print(f"  Reasoning: {result['reasoning']}")
print()
print("MULTIPLIERS:")
print(f"  Setup (32/100): {result.get('setup_multiplier', 'N/A')}x (should be <1.0 for low score)")
print(f"  IV (18%): {result.get('volatility_multiplier', 'N/A')}x (should be 1.5x for low IV)")
print(f"  Equity: {result.get('equity_multiplier', 'N/A')}x")
print(f"  Drawdown: {result.get('drawdown_multiplier', 'N/A')}x")
print()
print(f"✓ PASS" if 4 <= result['contracts'] <= 25 else "✗ FAIL - contracts out of expected range")
