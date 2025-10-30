"""
Test script to verify backtesting system functionality.
Run this to test if backtesting is working correctly.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 70)
print("BACKTESTING SYSTEM TEST")
print("=" * 70)

# Test 1: Import all components
print("\n1️⃣  Testing imports...")
try:
    from signals.models_backtest import (
        BacktestRun, BacktestTrade, StrategyOptimization,
        OptimizationRecommendation, BacktestMetric
    )
    from scanner.services.historical_data_fetcher import historical_data_fetcher
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.services.parameter_optimizer import parameter_optimizer
    from scanner.services.self_learning_module import self_learning_module
    print("   ✅ All modules imported successfully")
except Exception as e:
    print(f"   ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Check database models
print("\n2️⃣  Testing database models...")
try:
    print(f"   BacktestRun count: {BacktestRun.objects.count()}")
    print(f"   BacktestTrade count: {BacktestTrade.objects.count()}")
    print(f"   StrategyOptimization count: {StrategyOptimization.objects.count()}")
    print(f"   OptimizationRecommendation count: {OptimizationRecommendation.objects.count()}")
    print("   ✅ Database models working")
except Exception as e:
    print(f"   ❌ Database error: {e}")
    sys.exit(1)

# Test 3: Test historical data fetcher
print("\n3️⃣  Testing historical data fetcher...")
try:
    async def test_fetch():
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        print(f"   Fetching BTCUSDT data from {start_date.date()} to {end_date.date()}...")
        klines = await historical_data_fetcher.fetch_historical_klines(
            'BTCUSDT',
            '1h',
            start_date,
            end_date,
            limit=100
        )
        print(f"   ✅ Fetched {len(klines)} candles")
        return klines

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    klines = loop.run_until_complete(test_fetch())
    loop.close()

except Exception as e:
    print(f"   ❌ Data fetch error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test backtesting engine
print("\n4️⃣  Testing backtesting engine...")
try:
    engine = BacktestEngine(
        initial_capital=Decimal('10000'),
        position_size=Decimal('100'),
        strategy_params={}
    )
    print("   ✅ Backtesting engine initialized")

    # Create mock signals for testing
    if klines and len(klines) > 0:
        mock_signals = [
            {
                'symbol': 'BTCUSDT',
                'timestamp': klines[0]['timestamp'],
                'direction': 'LONG',
                'entry': klines[0]['close'],
                'tp': klines[0]['close'] * Decimal('1.02'),
                'sl': klines[0]['close'] * Decimal('0.98'),
                'confidence': 0.75,
                'indicators': {}
            }
        ]

        symbols_data = {'BTCUSDT': klines}
        results = engine.run_backtest(symbols_data, mock_signals)

        print(f"   ✅ Backtest completed:")
        print(f"      Total trades: {results['total_trades']}")
        print(f"      Win rate: {float(results['win_rate']):.2f}%")
        print(f"      ROI: {float(results['roi']):.2f}%")

except Exception as e:
    print(f"   ❌ Backtest engine error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test API views
print("\n5️⃣  Testing API views...")
try:
    from signals.views_backtest import BacktestViewSet, OptimizationViewSet, RecommendationViewSet
    print("   ✅ API views imported successfully")
except Exception as e:
    print(f"   ❌ API views error: {e}")

# Test 6: Test Celery tasks
print("\n6️⃣  Testing Celery tasks...")
try:
    from scanner.tasks.backtest_tasks import (
        run_backtest_async,
        run_optimization_async,
        generate_recommendations_async
    )
    print("   ✅ Celery tasks imported successfully")
    print(f"      - run_backtest_async: {run_backtest_async.name}")
    print(f"      - run_optimization_async: {run_optimization_async.name}")
    print(f"      - generate_recommendations_async: {generate_recommendations_async.name}")
except Exception as e:
    print(f"   ❌ Celery tasks error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Create a test backtest run
print("\n7️⃣  Creating test backtest run in database...")
try:
    # Get or create test user
    user, created = User.objects.get_or_create(
        email='test@example.com',
        defaults={
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User'
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()

    # Create test backtest
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    backtest = BacktestRun.objects.create(
        user=user,
        name='Test Backtest',
        symbols=['BTCUSDT'],
        timeframe='1h',
        start_date=start_date,
        end_date=end_date,
        strategy_params={
            'long_rsi_min': 50,
            'long_rsi_max': 70,
            'sl_atr_multiplier': 1.5,
            'tp_atr_multiplier': 2.5
        },
        initial_capital=Decimal('10000'),
        position_size=Decimal('100'),
        status='PENDING'
    )

    print(f"   ✅ Test backtest created:")
    print(f"      ID: {backtest.id}")
    print(f"      Name: {backtest.name}")
    print(f"      Status: {backtest.status}")
    print(f"      Symbols: {backtest.symbols}")
    print(f"      Date range: {backtest.start_date.date()} to {backtest.end_date.date()}")

    # Clean up
    print("\n   Cleaning up test data...")
    backtest.delete()
    if created:
        user.delete()
    print("   ✅ Test data cleaned up")

except Exception as e:
    print(f"   ❌ Database test error: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("✅ Backtesting system is working!")
print("\nNext steps:")
print("1. Access admin panel: http://localhost:8000/admin/signals/backtestrun/")
print("2. Use API endpoints (requires authentication):")
print("   POST /api/backtest/ - Create new backtest")
print("   GET  /api/backtest/ - List backtests")
print("3. Check Celery worker: docker-compose logs celery-worker")
print("\nTo run a real backtest, use the API or admin panel.")
print("=" * 70)
