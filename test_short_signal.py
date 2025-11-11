#!/usr/bin/env python
"""Test script to verify SHORT signal saving works."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import asyncio
from decimal import Decimal
from django.utils import timezone
from signals.models import Signal, Symbol

async def test_short_signal_save():
    """Test saving a SHORT FUTURES signal."""
    from scanner.tasks.celery_tasks import _save_futures_signal_async

    # Create test signal data
    test_signal = {
        'symbol': 'TESTUSDT',
        'direction': 'SHORT',
        'entry': '100.50',
        'sl': '105.00',
        'tp': '90.00',
        'confidence': 0.75,
        'timeframe': '1h',
        'description': 'Test SHORT signal',
        'market_type': 'FUTURES',
        'leverage': 10
    }

    print(f"📝 Testing SHORT signal save for {test_signal['symbol']}...")
    print(f"   Direction: {test_signal['direction']}")
    print(f"   Entry: ${test_signal['entry']}, SL: ${test_signal['sl']}, TP: ${test_signal['tp']}")

    try:
        saved_signal = await _save_futures_signal_async(test_signal)

        if saved_signal:
            print(f"✅ SUCCESS: Signal saved to database!")
            print(f"   ID: {saved_signal.id}")
            print(f"   Symbol: {saved_signal.symbol.symbol}")
            print(f"   Direction: {saved_signal.direction}")
            print(f"   Market Type: {saved_signal.market_type}")
            print(f"   Entry: ${saved_signal.entry}")
            print(f"   Leverage: {saved_signal.leverage}x")

            # Verify it's in the database
            db_signal = Signal.objects.filter(
                id=saved_signal.id,
                direction='SHORT',
                market_type='FUTURES'
            ).first()

            if db_signal:
                print(f"✅ VERIFIED: Signal found in database with ID {db_signal.id}")

                # Clean up test signal
                db_signal.delete()
                print(f"🧹 Cleaned up test signal")
            else:
                print(f"❌ ERROR: Signal not found in database!")
        else:
            print(f"⚠️  Signal was filtered (likely duplicate)")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("="*60)
    print("SHORT FUTURES Signal Save Test")
    print("="*60)
    asyncio.run(test_short_signal_save())
    print("="*60)
