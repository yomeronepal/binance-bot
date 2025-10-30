#!/usr/bin/env python
"""
Test volatility classifier integration
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.services.volatility_classifier import get_volatility_classifier
from scanner.strategies.signal_engine import SignalDetectionEngine

def test_volatility_classification():
    """Test volatility classification for different coin types"""

    print("=" * 80)
    print("VOLATILITY CLASSIFIER TEST")
    print("=" * 80)
    print()

    # Get classifier instance
    classifier = get_volatility_classifier()

    # Test symbols from different volatility categories
    test_symbols = {
        'HIGH': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT', 'WIFUSDT', 'FLOKIUSDT'],
        'MEDIUM': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT'],
        'LOW': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'USDTUSDT']
    }

    print("Testing symbol classification...")
    print()

    for expected_vol, symbols in test_symbols.items():
        print(f"\n{expected_vol} Volatility Symbols:")
        print("-" * 80)

        for symbol in symbols:
            try:
                # Classify symbol (quick classification first)
                profile = classifier.classify_symbol(symbol)

                # Check if classification matches expectation
                match = "✅" if profile.volatility_level == expected_vol else "❌"

                print(f"{match} {symbol:15s} -> {profile.volatility_level:6s} "
                      f"(Conf: {profile.confidence:.0%}) | "
                      f"SL={profile.sl_atr_multiplier}x, "
                      f"TP={profile.tp_atr_multiplier}x, "
                      f"ADX={profile.adx_threshold}, "
                      f"MinConf={profile.min_confidence:.0%}")

            except Exception as e:
                print(f"❌ {symbol:15s} -> ERROR: {e}")

    print()
    print("=" * 80)
    print("SIGNAL ENGINE INTEGRATION TEST")
    print("=" * 80)
    print()

    # Test signal engine with volatility-aware mode
    print("Testing SignalDetectionEngine initialization...")
    print()

    # Test WITHOUT volatility-aware mode
    engine_default = SignalDetectionEngine(use_volatility_aware=False)
    print(f"✅ Default engine initialized (volatility_aware={engine_default.use_volatility_aware})")

    # Test WITH volatility-aware mode
    engine_vaware = SignalDetectionEngine(use_volatility_aware=True)
    print(f"✅ Volatility-aware engine initialized (volatility_aware={engine_vaware.use_volatility_aware})")

    print()
    print("Testing config retrieval for different symbols...")
    print()

    # Test config retrieval for different volatility levels
    test_configs = {
        'PEPEUSDT': 'HIGH',
        'SOLUSDT': 'MEDIUM',
        'BTCUSDT': 'LOW'
    }

    for symbol, expected_vol in test_configs.items():
        # Get config for symbol
        config = engine_vaware.get_config_for_symbol(symbol)

        print(f"{symbol} ({expected_vol}):")
        print(f"  SL ATR Multiplier: {config.sl_atr_multiplier}x")
        print(f"  TP ATR Multiplier: {config.tp_atr_multiplier}x")
        print(f"  ADX Threshold:     {config.long_adx_min}")
        print(f"  Min Confidence:    {config.min_confidence:.0%}")
        print()

    print("=" * 80)
    print("EXPECTED PARAMETERS BY VOLATILITY")
    print("=" * 80)
    print()

    print("HIGH Volatility (PEPE, SHIB, DOGE):")
    print("  SL: 2.0x  |  TP: 3.5x  |  ADX: 18  |  Conf: 70%")
    print()

    print("MEDIUM Volatility (SOL, ADA, MATIC):")
    print("  SL: 1.5x  |  TP: 2.5x  |  ADX: 22  |  Conf: 75%")
    print()

    print("LOW Volatility (BTC, ETH, BNB):")
    print("  SL: 1.0x  |  TP: 2.0x  |  ADX: 20  |  Conf: 80%")
    print()

    print("=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)

if __name__ == '__main__':
    try:
        test_volatility_classification()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
