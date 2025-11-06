"""
Management command to validate all universal configurations.

Usage:
    python manage.py validate_configs
"""
import logging
from django.core.management.base import BaseCommand
from scanner.config import get_config_manager, MarketType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Validate all universal configurations for Forex and Binance markets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed configuration information',
        )

    def handle(self, *args, **options):
        """Validate all configurations"""
        verbose = options.get('verbose', False)

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🔍 Universal Configuration Validation'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        # Get config manager
        manager = get_config_manager()

        # Get all configurations
        all_configs = manager.get_all_configs()

        self.stdout.write(self.style.SUCCESS(f"📋 Total Configurations: {len(all_configs)}"))
        self.stdout.write('')

        # Validate each configuration
        validation_results = manager.validate_all_configs()

        all_valid = True
        for market_type, (is_valid, errors) in validation_results.items():
            config = all_configs[market_type]

            self.stdout.write(self.style.WARNING(f"{'─' * 80}"))
            self.stdout.write(self.style.WARNING(f"📊 Market Type: {market_type.value.upper()}"))
            self.stdout.write(self.style.WARNING(f"{'─' * 80}"))

            if is_valid:
                self.stdout.write(self.style.SUCCESS(f"✅ {config.name}: VALID"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ {config.name}: INVALID"))
                for error in errors:
                    self.stdout.write(self.style.ERROR(f"   - {error}"))
                all_valid = False

            # Show configuration details if verbose
            if verbose or not is_valid:
                self.stdout.write('')
                self.stdout.write(f"   Name: {config.name}")
                self.stdout.write(f"   Description: {config.description}")
                self.stdout.write('')
                self.stdout.write(f"   LONG Thresholds:")
                self.stdout.write(f"      RSI Range: {config.long_rsi_min} - {config.long_rsi_max}")
                self.stdout.write(f"      ADX Minimum: {config.long_adx_min}")
                self.stdout.write('')
                self.stdout.write(f"   SHORT Thresholds:")
                self.stdout.write(f"      RSI Range: {config.short_rsi_min} - {config.short_rsi_max}")
                self.stdout.write(f"      ADX Minimum: {config.short_adx_min}")
                self.stdout.write('')
                self.stdout.write(f"   Risk Management:")
                self.stdout.write(f"      SL ATR Multiplier: {config.sl_atr_multiplier}")
                self.stdout.write(f"      TP ATR Multiplier: {config.tp_atr_multiplier}")
                risk_reward = config.tp_atr_multiplier / config.sl_atr_multiplier
                self.stdout.write(f"      Risk/Reward Ratio: 1:{risk_reward:.2f}")
                self.stdout.write('')
                self.stdout.write(f"   Signal Quality:")
                self.stdout.write(f"      Min Confidence: {config.min_confidence * 100:.1f}%")
                self.stdout.write(f"      Preferred Timeframes: {', '.join(config.preferred_timeframes)}")
                self.stdout.write('')

        # Show summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))

        if all_valid:
            self.stdout.write(self.style.SUCCESS('✅ ALL CONFIGURATIONS VALID'))
        else:
            self.stdout.write(self.style.ERROR('❌ SOME CONFIGURATIONS INVALID - PLEASE FIX'))

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        # Test market detection
        self.stdout.write(self.style.WARNING('🔍 Testing Market Detection...'))
        self.stdout.write('')

        test_symbols = [
            ('BTCUSDT', MarketType.BINANCE),
            ('ETHUSDT', MarketType.BINANCE),
            ('EURUSD', MarketType.FOREX),
            ('GBPJPY', MarketType.FOREX),
            ('XAUUSD', MarketType.FOREX),
            ('SOLUSDT', MarketType.BINANCE),
        ]

        detection_correct = 0
        for symbol, expected_type in test_symbols:
            detected_type = manager.detect_market_type(symbol)
            is_correct = detected_type == expected_type

            if is_correct:
                self.stdout.write(self.style.SUCCESS(
                    f"   ✅ {symbol:12s} → {detected_type.value:8s} (expected: {expected_type.value})"
                ))
                detection_correct += 1
            else:
                self.stdout.write(self.style.ERROR(
                    f"   ❌ {symbol:12s} → {detected_type.value:8s} (expected: {expected_type.value})"
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"   Detection Accuracy: {detection_correct}/{len(test_symbols)} "
            f"({detection_correct / len(test_symbols) * 100:.1f}%)"
        ))
        self.stdout.write('')

        # Show configuration summary
        self.stdout.write(self.style.WARNING('📊 Configuration Summary:'))
        self.stdout.write('')

        summary = manager.get_config_summary()
        for market_type_str, config_info in summary['configs'].items():
            self.stdout.write(self.style.WARNING(f"   {market_type_str.upper()}:"))
            self.stdout.write(f"      Name: {config_info['name']}")
            self.stdout.write(f"      LONG RSI: {config_info['rsi_range_long']}")
            self.stdout.write(f"      SHORT RSI: {config_info['rsi_range_short']}")
            self.stdout.write(f"      ADX Min: {config_info['adx_min']}")
            self.stdout.write(f"      Risk/Reward: {config_info['risk_reward_ratio']}")
            self.stdout.write(f"      Min Confidence: {config_info['min_confidence'] * 100:.0f}%")
            self.stdout.write(f"      Timeframes: {', '.join(config_info['preferred_timeframes'])}")
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('✅ Configuration validation complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
