import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models import PaperTrade, Signal
from django.db.models import Avg
from datetime import datetime

# Analyze open trades
open_trades = list(PaperTrade.objects.filter(status='OPEN').order_by('-entry_time')[:10])

print('=' * 80)
print('OPEN TRADES ANALYSIS')
print('=' * 80)
print(f"Total open trades: {PaperTrade.objects.filter(status='OPEN').count()}")
print(f"Total closed trades: {PaperTrade.objects.filter(status='CLOSED').count()}")
print()

if open_trades:
    print('Sample of 10 recent open trades:')
    print(f"{'Symbol':<10} {'Dir':<5} {'Entry':>12} {'TP':>12} {'SL':>12} {'TP%':>8} {'SL%':>8}")
    print('-' * 80)

    for trade in open_trades:
        entry = float(trade.entry_price)
        tp = float(trade.take_profit)
        sl = float(trade.stop_loss)

        tp_pct = abs((tp - entry) / entry * 100)
        sl_pct = abs((sl - entry) / entry * 100)

        print(f"{trade.symbol:<10} {trade.direction:<5} ${entry:>11.2f} ${tp:>11.2f} ${sl:>11.2f} {tp_pct:>7.2f}% {sl_pct:>7.2f}%")

# Calculate averages
stats = PaperTrade.objects.filter(status='OPEN').aggregate(
    avg_entry=Avg('entry_price'),
    avg_tp=Avg('take_profit'),
    avg_sl=Avg('stop_loss')
)

if stats['avg_entry']:
    avg_entry = float(stats['avg_entry'])
    avg_tp = float(stats['avg_tp'])
    avg_sl = float(stats['avg_sl'])

    avg_tp_pct = abs((avg_tp - avg_entry) / avg_entry * 100)
    avg_sl_pct = abs((avg_sl - avg_entry) / avg_entry * 100)

    print()
    print('AVERAGES:')
    print(f"  Average TP distance: {avg_tp_pct:.2f}%")
    print(f"  Average SL distance: {avg_sl_pct:.2f}%")
    print(f"  Risk/Reward Ratio: 1:{avg_tp_pct/avg_sl_pct:.2f}")
    print()

    print('DIAGNOSIS:')
    if avg_tp_pct > 5:
        print(f"  ⚠️  PROBLEM: TP targets are TOO FAR ({avg_tp_pct:.1f}%)")
        print("     No trades are hitting TP because targets are unrealistic")
        print("     Recommendation: Reduce tp_atr_multiplier from current to 1.5-2.5")
    elif avg_tp_pct > 3:
        print(f"  ⚠️  TP targets are somewhat far ({avg_tp_pct:.1f}%)")
        print("     Consider reducing slightly for faster wins")
    else:
        print(f"  ✅ TP targets look reasonable ({avg_tp_pct:.1f}%)")

    print()

    if avg_sl_pct > 4:
        print(f"  ⚠️  PROBLEM: SL targets are TOO FAR ({avg_sl_pct:.1f}%)")
        print("     Giving market too much room, risking large losses")
        print("     Recommendation: Reduce sl_atr_multiplier to 1.0-1.5")
    elif avg_sl_pct > 2.5:
        print(f"  ⚠️  SL targets are somewhat wide ({avg_sl_pct:.1f}%)")
        print("     Consider tightening for better risk management")
    else:
        print(f"  ✅ SL targets look reasonable ({avg_sl_pct:.1f}%)")

# Check signal engine parameters
print()
print('=' * 80)
print('CURRENT SIGNAL ENGINE PARAMETERS')
print('=' * 80)

try:
    from scanner.strategies.signal_engine import SignalEngine
    import inspect

    # Read the source file
    source_file = inspect.getsourcefile(SignalEngine)
    with open(source_file, 'r') as f:
        lines = f.readlines()

    # Find parameter definitions
    print("Key parameters found in signal_engine.py:")
    for i, line in enumerate(lines):
        if any(param in line for param in ['self.tp_atr_multiplier', 'self.sl_atr_multiplier',
                                           'self.rsi_oversold', 'self.rsi_overbought',
                                           'self.adx_threshold']):
            print(f"  Line {i+1}: {line.strip()}")
except Exception as e:
    print(f"Could not read signal engine: {e}")

print()
print('=' * 80)
print('RECOMMENDED ACTIONS')
print('=' * 80)
print()
print("1. IMMEDIATE FIX - Adjust TP/SL in signal_engine.py:")
print("   • Reduce tp_atr_multiplier to 1.5-2.5 (currently seems too high)")
print("   • Reduce sl_atr_multiplier to 1.0-1.5 (currently seems too high)")
print("   • This will allow trades to close and generate performance data")
print()
print("2. RESTART SERVICES:")
print("   docker-compose restart backend celery-worker")
print()
print("3. WAIT FOR TRADES TO CLOSE:")
print("   • Let 50-100 trades close with new parameters")
print("   • Then run this analysis again")
print()
print("4. USE ML TUNING FOR OPTIMIZATION:")
print("   • Once you have 50+ closed trades")
print("   • Run: ./test_mltuning.sh")
print("   • ML will find optimal TP/SL and other parameters")
print()
