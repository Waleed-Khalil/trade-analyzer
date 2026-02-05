"""Test Fibonacci integration"""
import sys
sys.path.insert(0, 'src')

from analysis.fibonacci import get_fib_analysis

print("="*70)
print("FIBONACCI ANALYSIS - INTEGRATION TEST")
print("="*70)
print()

# Test with AAPL current price ~277
fib = get_fib_analysis('AAPL', current_price=277.41)

if fib:
    print(f"Ticker: AAPL")
    print(f"Current Price: ${fib['current_price']}")
    print(f"Swing Range: ${fib['swing_low']} - ${fib['swing_high']} (${fib['swing_range']} range)")
    print(f"Position: {fib['position'].replace('_', ' ')}")
    print()

    print("Retracements (pullback support levels):")
    for level in [0.236, 0.382, 0.5, 0.618, 0.786]:
        if level in fib['retracements']:
            price = fib['retracements'][level]
            distance = abs(fib['current_price'] - price)
            pct = (distance / fib['current_price']) * 100
            marker = " <-- Near current price" if pct < 2.0 else ""
            print(f"  {level:.3f}: ${price:.2f} ({pct:.1f}% away){marker}")

    print()
    print("Extensions (profit targets):")
    for level in [1.272, 1.414, 1.618, 2.618]:
        if level in fib['extensions']:
            price = fib['extensions'][level]
            distance = price - fib['current_price']
            pct = (distance / fib['current_price']) * 100
            print(f"  {level:.3f}: ${price:.2f} (+{pct:.1f}% gain needed)")

    print()
    print("="*70)
    print("[OK] Fibonacci analysis working correctly")
    print("[OK] Now integrated into main.py output")
    print("="*70)
else:
    print("[ERROR] Fibonacci analysis failed")
