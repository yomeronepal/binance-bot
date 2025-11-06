"""
Forex Signal Scanner
Generates forex trading signals using technical indicators
Supports major, minor, and exotic currency pairs
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from celery import shared_task
from decimal import Decimal

from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
from signals.models import Signal, Symbol
from django.db import transaction

logger = logging.getLogger(__name__)


# Major Forex Pairs (highest liquidity)
MAJOR_PAIRS = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF',
    'AUDUSD', 'USDCAD', 'NZDUSD'
]

# Minor Forex Pairs (cross pairs)
MINOR_PAIRS = [
    'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURCAD', 'EURNZD',
    'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPCAD', 'GBPNZD',
    'AUDJPY', 'AUDCHF', 'AUDCAD', 'AUDNZD',
    'CADJPY', 'CHFJPY', 'NZDJPY'
]

# Exotic Pairs (lower liquidity, higher spreads)
EXOTIC_PAIRS = [
    'USDTRY', 'USDZAR', 'USDMXN', 'USDSEK', 'USDNOK',
    'EURZAR', 'EURTRY', 'GBPTRY', 'JPYTRY'
]


# Forex-optimized signal configurations
FOREX_CONFIGS = {
    '1d': SignalConfig(
        # Daily timeframe - Position trading
        min_confidence=0.70,
        long_adx_min=25.0,  # Higher ADX for stronger trends
        short_adx_min=25.0,
        long_rsi_min=25.0,
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=75.0,
        sl_atr_multiplier=2.0,   # Tighter stops for forex
        tp_atr_multiplier=6.0,   # 1:3 R/R
        signal_expiry_minutes=1440,  # 24 hours
    ),
    '4h': SignalConfig(
        # 4-hour timeframe - Swing trading
        min_confidence=0.70,
        long_adx_min=22.0,
        short_adx_min=22.0,
        long_rsi_min=25.0,
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=75.0,
        sl_atr_multiplier=1.8,
        tp_atr_multiplier=5.5,   # 1:3.05 R/R
        signal_expiry_minutes=480,  # 8 hours
    ),
    '1h': SignalConfig(
        # 1-hour timeframe - Day trading
        min_confidence=0.72,
        long_adx_min=20.0,
        short_adx_min=20.0,
        long_rsi_min=28.0,
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=72.0,
        sl_atr_multiplier=1.5,
        tp_atr_multiplier=4.5,   # 1:3 R/R
        signal_expiry_minutes=180,  # 3 hours
    ),
    '15m': SignalConfig(
        # 15-minute timeframe - Scalping
        min_confidence=0.75,
        long_adx_min=18.0,
        short_adx_min=18.0,
        long_rsi_min=30.0,
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=70.0,
        sl_atr_multiplier=1.2,
        tp_atr_multiplier=3.6,   # 1:3 R/R
        signal_expiry_minutes=60,  # 1 hour
    ),
}

# Timeframe priority (higher = more important)
TIMEFRAME_PRIORITY = {
    '1d': 4,
    '4h': 3,
    '1h': 2,
    '15m': 1,
}


class ForexDataProvider:
    """
    Provides forex price data from various sources
    Can be extended to use OANDA, FXCM, or other forex data providers
    For now, uses mock data structure - replace with actual API calls
    """

    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[List]:
        """
        Fetch forex candlestick data

        Args:
            symbol: Currency pair (e.g., 'EURUSD')
            interval: Timeframe ('15m', '1h', '4h', '1d')
            limit: Number of candles

        Returns:
            List of klines in Binance-compatible format
        """
        # TODO: Replace with actual forex data provider (OANDA, FXCM, etc.)
        # For now, return empty list - you'll need to integrate a real forex data source
        logger.warning(f"Forex data provider not implemented. Symbol: {symbol}, Interval: {interval}")
        return []

    async def batch_get_klines(self, pairs: List[str], interval: str, limit: int = 200) -> Dict[str, List]:
        """Fetch klines for multiple pairs"""
        result = {}
        for pair in pairs:
            klines = await self.get_klines(pair, interval, limit)
            if klines:
                result[pair] = klines
        return result


async def save_forex_signal(symbol_str: str, signal_data: Dict, timeframe: str) -> Optional[Signal]:
    """
    Save forex signal to database with duplicate prevention

    Args:
        symbol_str: Currency pair symbol
        signal_data: Signal information from engine
        timeframe: Signal timeframe
    """
    try:
        @transaction.atomic
        def save_signal():
            # Get or create forex symbol
            symbol_obj, created = Symbol.objects.get_or_create(
                symbol=symbol_str,
                defaults={
                    'exchange': 'FOREX',
                    'active': True,
                    'market_type': 'FOREX'
                }
            )

            direction = signal_data['direction']
            new_priority = TIMEFRAME_PRIORITY.get(timeframe, 0)

            # Check for existing signals (same direction)
            existing = Signal.objects.filter(
                symbol=symbol_obj,
                direction=direction,
                market_type='FOREX',
                status='ACTIVE'
            ).first()

            if existing:
                existing_timeframe = existing.timeframe
                existing_priority = TIMEFRAME_PRIORITY.get(existing_timeframe, 0)

                # Case 1: Same timeframe - skip duplicate
                if timeframe == existing_timeframe:
                    logger.debug(
                        f"⏭️ Skipping duplicate {direction} forex signal for {symbol_str} ({timeframe})"
                    )
                    return None

                # Case 2: New signal is LOWER priority - skip it
                if new_priority < existing_priority:
                    logger.info(
                        f"⏭️ Skipping {direction} forex signal for {symbol_str} ({timeframe}) - "
                        f"higher timeframe signal exists ({existing_timeframe})"
                    )
                    return None

                # Case 3: New signal is HIGHER priority - replace existing
                if new_priority > existing_priority:
                    logger.info(
                        f"⬆️ UPGRADING {direction} forex signal for {symbol_str}: "
                        f"{existing_timeframe} → {timeframe} "
                        f"(Conf: {existing.confidence:.0%} → {signal_data['confidence']:.0%})"
                    )

                    # Delete lower timeframe signal
                    Signal.objects.filter(
                        symbol=symbol_obj,
                        direction=direction,
                        timeframe=existing_timeframe,
                        market_type='FOREX',
                        status='ACTIVE'
                    ).delete()

                    # Create new higher timeframe signal
                    forex_signal = Signal.objects.create(
                        symbol=symbol_obj,
                        direction=direction,
                        entry=signal_data.get('entry_price', signal_data.get('entry')),
                        sl=signal_data.get('stop_loss', signal_data.get('sl')),
                        tp=signal_data.get('take_profit', signal_data.get('tp')),
                        confidence=signal_data['confidence'],
                        timeframe=timeframe,
                        market_type='FOREX',
                        leverage=100,  # Default forex leverage
                        status='ACTIVE'
                    )

                    logger.info(
                        f"✅ Upgraded to {timeframe} forex signal for {symbol_str} "
                        f"@ {forex_signal.entry} (Conf: {forex_signal.confidence:.0%})"
                    )
                    return forex_signal

            # No existing signal - create new one
            forex_signal = Signal.objects.create(
                symbol=symbol_obj,
                direction=direction,
                entry=signal_data.get('entry_price', signal_data.get('entry')),
                sl=signal_data.get('stop_loss', signal_data.get('sl')),
                tp=signal_data.get('take_profit', signal_data.get('tp')),
                confidence=signal_data['confidence'],
                timeframe=timeframe,
                market_type='FOREX',
                leverage=100,  # Default forex leverage
                status='ACTIVE'
            )

            logger.info(
                f"✅ New {direction} forex signal: {symbol_str} @ {forex_signal.entry} "
                f"({timeframe}, Conf: {forex_signal.confidence:.0%})"
            )
            return forex_signal

        return save_signal()
    except Exception as e:
        logger.error(f"Error saving forex signal: {e}", exc_info=True)
        return None


async def scan_forex_timeframe(
    data_provider: ForexDataProvider,
    engine: SignalDetectionEngine,
    timeframe: str,
    pairs: List[str],
    limit: int = 200
) -> Dict[str, int]:
    """
    Scan forex pairs on a specific timeframe

    Args:
        data_provider: Forex data provider
        engine: Signal detection engine
        timeframe: Timeframe to scan
        pairs: List of currency pairs
        limit: Number of candles to fetch

    Returns:
        Dict with counts: {'created': N, 'updated': N, 'invalidated': N}
    """
    counts = {'created': 0, 'updated': 0, 'invalidated': 0}

    logger.info(f"🔍 Scanning {len(pairs)} forex pairs on {timeframe} timeframe...")

    try:
        # Fetch klines for all pairs
        klines_data = await data_provider.batch_get_klines(pairs, interval=timeframe, limit=limit)

        # Process each pair
        for symbol, klines in klines_data.items():
            try:
                # Update engine cache
                engine.update_candles(symbol, klines)

                # Process symbol
                result = engine.process_symbol(symbol, timeframe)

                if result:
                    action = result.get('action')
                    signal_data = result.get('signal')

                    if action == 'created' and signal_data:
                        # Save forex signal
                        saved_signal = await save_forex_signal(symbol, signal_data.to_dict(), timeframe)
                        if saved_signal:
                            counts['created'] += 1
                    elif action == 'updated':
                        counts['updated'] += 1
                    elif action == 'deleted':
                        counts['invalidated'] += 1

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        logger.info(
            f"✅ {timeframe} forex scan complete: "
            f"{counts['created']} created, {counts['updated']} updated, {counts['invalidated']} invalidated"
        )

    except Exception as e:
        logger.error(f"Error scanning forex {timeframe}: {e}", exc_info=True)

    return counts


@shared_task(bind=True, name='scanner.tasks.scan_forex_signals')
def scan_forex_signals(self, timeframes: Optional[List[str]] = None, pair_types: Optional[List[str]] = None):
    """
    Celery task to scan forex signals across multiple timeframes

    Args:
        timeframes: List of timeframes to scan (default: ['4h', '1d'])
        pair_types: List of pair types to scan: 'major', 'minor', 'exotic' (default: ['major'])

    Returns:
        Dict with scan results and counts
    """
    if timeframes is None:
        timeframes = ['4h', '1d']  # Default: swing trading timeframes

    if pair_types is None:
        pair_types = ['major']  # Default: major pairs only

    # Build pairs list based on types
    pairs = []
    if 'major' in pair_types:
        pairs.extend(MAJOR_PAIRS)
    if 'minor' in pair_types:
        pairs.extend(MINOR_PAIRS)
    if 'exotic' in pair_types:
        pairs.extend(EXOTIC_PAIRS)

    if not pairs:
        logger.warning("No forex pairs selected for scanning")
        return {'error': 'No pairs selected', 'counts': {}}

    logger.info(f"🚀 Starting forex signal scan: {len(pairs)} pairs, {len(timeframes)} timeframes")

    total_counts = {tf: {'created': 0, 'updated': 0, 'invalidated': 0} for tf in timeframes}

    try:
        async def run_scan():
            data_provider = ForexDataProvider()

            for timeframe in timeframes:
                # Get configuration for this timeframe
                config = FOREX_CONFIGS.get(timeframe, FOREX_CONFIGS['4h'])

                # Initialize signal engine
                engine = SignalDetectionEngine(config, use_volatility_aware=False)

                # Scan this timeframe
                counts = await scan_forex_timeframe(
                    data_provider,
                    engine,
                    timeframe,
                    pairs,
                    limit=200
                )

                total_counts[timeframe] = counts

            return total_counts

        # Run async scan
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(run_scan())
        finally:
            loop.close()

        # Calculate totals
        total_created = sum(c['created'] for c in results.values())
        total_updated = sum(c['updated'] for c in results.values())
        total_invalidated = sum(c['invalidated'] for c in results.values())

        logger.info(
            f"✅ Forex scan complete: {total_created} signals created, "
            f"{total_updated} updated, {total_invalidated} invalidated"
        )

        return {
            'success': True,
            'pairs_scanned': len(pairs),
            'timeframes': timeframes,
            'total_created': total_created,
            'total_updated': total_updated,
            'total_invalidated': total_invalidated,
            'details': results
        }

    except Exception as e:
        logger.error(f"Error in forex signal scan: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'counts': total_counts
        }


@shared_task(bind=True, name='scanner.tasks.scan_major_forex_pairs')
def scan_major_forex_pairs(self):
    """Scan major forex pairs (4h and 1d timeframes)"""
    return scan_forex_signals(
        timeframes=['4h', '1d'],
        pair_types=['major']
    )


@shared_task(bind=True, name='scanner.tasks.scan_all_forex_pairs')
def scan_all_forex_pairs(self):
    """Scan all forex pairs (major + minor)"""
    return scan_forex_signals(
        timeframes=['1h', '4h', '1d'],
        pair_types=['major', 'minor']
    )


@shared_task(bind=True, name='scanner.tasks.scan_forex_scalping')
def scan_forex_scalping(self):
    """Scan major forex pairs for scalping (15m and 1h timeframes)"""
    return scan_forex_signals(
        timeframes=['15m', '1h'],
        pair_types=['major']
    )
