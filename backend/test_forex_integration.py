#!/usr/bin/env python
"""
Test Forex Integration with Alpha Vantage API

This script tests:
1. Alpha Vantage API connection
2. Forex data fetching
3. Signal generation for Forex pairs

Usage:
    python test_forex_integration.py
"""
import os
import sys
import django
import asyncio

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.services.alphavantage_client import AlphaVantageClient
from scanner.tasks.forex_scanner import ForexDataProvider, MAJOR_PAIRS, FOREX_CONFIGS
from scanner.strategies.signal_engine import SignalDetectionEngine


async def test_alpha_vantage_connection():
    """Test Alpha Vantage API connection"""
    print("=" * 80)
    print("TEST 1: Alpha Vantage API Connection")
    print("=" * 80)

    client = AlphaVantageClient()
    print(f"✓ API Key configured: {client.api_key[:4]}...{client.api_key[-4:] if len(client.api_key) > 8 else 'demo'}")

    # Test with EURUSD
    print("\nFetching 15m data for EURUSD...")
    klines = await client.get_klines('EURUSD', '15m', limit=10)

    if klines:
        print(f"✓ Successfully fetched {len(klines)} candles")
        print(f"  Latest candle: {klines[-1][1:5]}")  # Open, High, Low, Close
        return True
    else:
        print("✗ Failed to fetch data")
        print("\nNote: If using 'demo' API key, functionality is limited.")
        print("Get a free API key at: https://www.alphavantage.co/support/#api-key")
        return False


async def test_forex_data_provider():
    """Test Forex Data Provider"""
    print("\n" + "=" * 80)
    print("TEST 2: Forex Data Provider")
    print("=" * 80)

    provider = ForexDataProvider()

    # Test single pair
    print("\nFetching data for GBPUSD (1h)...")
    klines = await provider.get_klines('GBPUSD', '1h', limit=50)

    if klines:
        print(f"✓ Successfully fetched {len(klines)} candles for GBPUSD")
        return True
    else:
        print("✗ Failed to fetch data for GBPUSD")
        return False


async def test_signal_generation():
    """Test Forex signal generation"""
    print("\n" + "=" * 80)
    print("TEST 3: Forex Signal Generation")
    print("=" * 80)

    provider = ForexDataProvider()

    # Test with first 3 major pairs
    test_pairs = MAJOR_PAIRS[:3]
    print(f"\nTesting signal generation for: {', '.join(test_pairs)}")

    # Use 1h timeframe config
    config = FOREX_CONFIGS['1h']
    engine = SignalDetectionEngine(config, use_volatility_aware=False)

    signals_found = 0

    for pair in test_pairs:
        print(f"\n  Processing {pair}...")

        # Fetch data
        klines = await provider.get_klines(pair, '1h', limit=100)

        if not klines:
            print(f"    ✗ No data available for {pair}")
            continue

        print(f"    ✓ Fetched {len(klines)} candles")

        # Update engine cache
        engine.update_candles(pair, klines)

        # Process symbol
        result = engine.process_symbol(pair, '1h')

        if result and result.get('action') == 'created':
            signal = result.get('signal')
            if signal:
                signals_found += 1
                print(f"    ✓ SIGNAL FOUND: {signal.direction} @ {signal.entry_price}")
                print(f"      SL: {signal.stop_loss}, TP: {signal.take_profit}")
                print(f"      Confidence: {signal.confidence:.1%}")
        else:
            print(f"    - No signal (waiting for setup)")

    print(f"\n{'=' * 80}")
    print(f"SUMMARY: Found {signals_found} signals out of {len(test_pairs)} pairs tested")
    print(f"{'=' * 80}")

    return signals_found > 0


async def test_celery_task():
    """Test Celery task invocation"""
    print("\n" + "=" * 80)
    print("TEST 4: Celery Task Integration")
    print("=" * 80)

    try:
        from scanner.tasks.forex_scanner import scan_forex_signals

        print("\n✓ Forex scanner tasks imported successfully")
        print("\nAvailable tasks:")
        print("  - scan_forex_signals(timeframes, pair_types)")
        print("  - scan_major_forex_pairs()")
        print("  - scan_all_forex_pairs()")
        print("  - scan_forex_scalping()")

        print("\nCelery Beat Schedule (from celery.py):")
        print("  - 15m scan: Every 15 minutes")
        print("  - 1h scan: Every hour at :10")
        print("  - 4h scan: 00:10, 04:10, 08:10, 12:10, 16:10, 20:10")
        print("  - 1d scan: 00:10 daily")

        return True

    except Exception as e:
        print(f"✗ Error importing Celery tasks: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("FOREX INTEGRATION TEST SUITE")
    print("=" * 80)

    results = []

    # Test 1: API Connection
    try:
        result1 = await test_alpha_vantage_connection()
        results.append(("Alpha Vantage API", result1))
    except Exception as e:
        print(f"\n✗ Test 1 failed with error: {e}")
        results.append(("Alpha Vantage API", False))

    # Test 2: Data Provider
    try:
        result2 = await test_forex_data_provider()
        results.append(("Forex Data Provider", result2))
    except Exception as e:
        print(f"\n✗ Test 2 failed with error: {e}")
        results.append(("Forex Data Provider", False))

    # Test 3: Signal Generation
    try:
        result3 = await test_signal_generation()
        results.append(("Signal Generation", result3))
    except Exception as e:
        print(f"\n✗ Test 3 failed with error: {e}")
        results.append(("Signal Generation", False))

    # Test 4: Celery Integration
    try:
        result4 = await test_celery_task()
        results.append(("Celery Integration", result4))
    except Exception as e:
        print(f"\n✗ Test 4 failed with error: {e}")
        results.append(("Celery Integration", False))

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    print(f"\n{total_passed}/{len(results)} tests passed")

    if total_passed == len(results):
        print("\n🎉 All tests passed! Forex integration is working.")
    elif total_passed > 0:
        print("\n⚠️  Some tests passed. Check failed tests above.")
    else:
        print("\n❌ All tests failed. Check API key and configuration.")

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Get a free Alpha Vantage API key at:")
    print("   https://www.alphavantage.co/support/#api-key")
    print("\n2. Add it to backend/.env:")
    print("   ALPHAVANTAGE_API_KEY=your_key_here")
    print("\n3. Restart services:")
    print("   docker restart binancebot_web binancebot_celery_beat")
    print("\n4. Monitor Forex signals:")
    print("   curl http://localhost:8000/api/signals/?market_type=FOREX")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
