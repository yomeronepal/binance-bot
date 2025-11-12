"""
Multi-Timeframe Futures Signal Scanner

Generates FUTURES-ONLY signals from multiple timeframes (15m, 1h, 4h, 1d) using:
- Dedicated Binance Futures API client
- Market-specific configurations optimized for futures trading
- Timeframe-specific SL/TP ratios
- Default 10x leverage with adjustable parameters
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone

from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
from signals.models import Signal, Symbol

logger = logging.getLogger(__name__)


# SAME UNIVERSAL CONFIG as SPOT - Breathing Room Parameters
# These configs are identical to multi_timeframe_scanner.py for consistency
FUTURES_TIMEFRAME_CONFIGS = {
    '1d': SignalConfig(
        # Daily timeframe - Conservative approach (swing trading)
        min_confidence=0.72,
        long_adx_min=30.0,
        short_adx_min=30.0,
        long_rsi_min=23.0,
        long_rsi_max=33.0,
        short_rsi_min=67.0,
        short_rsi_max=77.0,
        sl_atr_multiplier=3.5,   # Wide stop for breathing room
        tp_atr_multiplier=9.0    # 1:2.67 R/R
    ),
    '4h': SignalConfig(
        # 4-hour timeframe - Balanced approach (day trading)
        min_confidence=0.70,
        long_adx_min=28.0,
        short_adx_min=28.0,
        long_rsi_min=23.0,
        long_rsi_max=33.0,
        short_rsi_min=67.0,
        short_rsi_max=77.0,
        sl_atr_multiplier=3.0,   # Good breathing room
        tp_atr_multiplier=9.0    # 1:2.8 R/R
    ),
    '1h': SignalConfig(
        # 1-hour timeframe - More active (intraday)
        min_confidence=0.73,
        long_adx_min=26.0,
        short_adx_min=26.0,
        long_rsi_min=23.0,
        long_rsi_max=33.0,
        short_rsi_min=67.0,
        short_rsi_max=77.0,
        sl_atr_multiplier=3.0,   # Moderate breathing room
        tp_atr_multiplier=9.0    # 1:2.6 R/R
    ),
    '15m': SignalConfig(
        # 15-minute timeframe - Active trading (scalping)
        min_confidence=0.75,  # Higher confidence for short timeframe
        long_adx_min=25.0,    # Stronger trend required
        short_adx_min=25.0,
        long_rsi_min=25.0,    # Slightly wider RSI ranges
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=75.0,
        sl_atr_multiplier=2.5,   # Tighter stop for scalping
        tp_atr_multiplier=7.0    # 1:2.5 R/R
    ),
    '5m': SignalConfig(
        # 5-minute timeframe - Ultra-scalping (optional, add 5m config)
        min_confidence=0.78,
        long_adx_min=25.0,
        short_adx_min=25.0,
        long_rsi_min=25.0,
        long_rsi_max=35.0,
        short_rsi_min=65.0,
        short_rsi_max=75.0,
        sl_atr_multiplier=1.8,   # Very tight for 5m
        tp_atr_multiplier=4.5    # 1:2.5 R/R
    )
}


# Timeframe priority ranking (higher value = higher priority)
TIMEFRAME_PRIORITY = {
    '1d': 5,    # Highest priority
    '4h': 4,
    '1h': 3,
    '15m': 2,
    '5m': 1     # Lowest priority
}


async def _get_top_futures_pairs_by_volume(
    client: BinanceFuturesClient,
    pairs: List[str],
    top_n: int = 200
) -> List[str]:
    """Get top N futures pairs by 24h volume"""
    try:
        volume_data = []

        # Fetch 24h tickers in batches to avoid rate limits
        for i in range(0, min(len(pairs), 200), 50):
            batch = pairs[i:i+50]
            tasks = [client.get_24h_ticker(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, results):
                if isinstance(result, dict):
                    try:
                        volume = float(result.get('quoteVolume', 0))
                        volume_data.append((symbol, volume))
                    except (ValueError, TypeError):
                        pass

            await asyncio.sleep(0.5)  # Rate limiting

        # Sort by volume descending
        volume_data.sort(key=lambda x: x[1], reverse=True)

        top_pairs = [symbol for symbol, _ in volume_data[:top_n]]
        logger.info(f"Selected top {len(top_pairs)} futures pairs by 24h volume")
        return top_pairs

    except Exception as e:
        logger.error(f"Error getting top futures pairs: {e}")
        return pairs[:top_n]


async def _save_futures_signal_with_dedup(signal_data: Dict, timeframe: str) -> Optional[Signal]:
    """
    Save futures signal with timeframe-aware deduplication and priority.

    Priority system:
    - Higher timeframe signals replace lower timeframe signals
    - Lower timeframe signals are skipped if higher timeframe exists
    """
    try:
        from asgiref.sync import sync_to_async

        @sync_to_async
        def save_signal():
            from django.db import transaction

            symbol_str = signal_data['symbol']
            direction = signal_data.get('direction', signal_data.get('signal_type'))
            entry_price = Decimal(str(signal_data.get('entry', signal_data.get('entry_price'))))
            new_priority = TIMEFRAME_PRIORITY.get(timeframe, 0)

            with transaction.atomic():
                # Get or create Symbol object
                symbol_obj, _ = Symbol.objects.get_or_create(
                    symbol=symbol_str,
                    defaults={
                        'exchange': 'BINANCE',
                        'active': True,
                        'market_type': 'FUTURES'
                    }
                )

                # Check for existing ACTIVE futures signals for this symbol+direction
                existing_signal = Signal.objects.select_for_update().filter(
                    symbol=symbol_obj,
                    direction=direction,
                    status='ACTIVE',
                    market_type='FUTURES'
                ).first()

                if existing_signal:
                    existing_timeframe = existing_signal.timeframe
                    existing_priority = TIMEFRAME_PRIORITY.get(existing_timeframe, 0)

                    # Case 1: Same timeframe - check time-based deduplication
                    if timeframe == existing_timeframe:
                        # Timeframe-aware deduplication window
                        if timeframe == '1h':
                            dedup_window_minutes = 55
                        elif timeframe == '4h':
                            dedup_window_minutes = 230
                        elif timeframe == '1d':
                            dedup_window_minutes = 1400
                        elif timeframe == '15m':
                            dedup_window_minutes = 13
                        elif timeframe == '5m':
                            dedup_window_minutes = 4
                        else:
                            dedup_window_minutes = 15

                        recent_time = timezone.now() - timedelta(minutes=dedup_window_minutes)

                        if existing_signal.created_at >= recent_time:
                            # Check price tolerance (1%)
                            price_tolerance = entry_price * Decimal('0.01')
                            if (existing_signal.entry >= entry_price - price_tolerance and
                                existing_signal.entry <= entry_price + price_tolerance):
                                logger.debug(
                                    f"⏭️ Skipping duplicate futures {direction} signal for {symbol_str} "
                                    f"({timeframe}) - already exists"
                                )
                                return None

                    # Case 2: New signal is LOWER priority - skip it
                    if new_priority < existing_priority:
                        logger.info(
                            f"⏭️ Skipping futures {direction} signal for {symbol_str} ({timeframe}) - "
                            f"higher timeframe signal exists ({existing_timeframe})"
                        )
                        return None

                    # Case 3: New signal is HIGHER priority - replace existing
                    if new_priority > existing_priority:
                        logger.info(
                            f"⬆️ UPGRADING futures {direction} signal for {symbol_str}: "
                            f"{existing_timeframe} → {timeframe} "
                            f"(Conf: {existing_signal.confidence:.0%} → {signal_data['confidence']:.0%})"
                        )

                        # Delete lower timeframe signal
                        Signal.objects.filter(
                            symbol=symbol_obj,
                            direction=direction,
                            timeframe=existing_timeframe,
                            status='ACTIVE',
                            market_type='FUTURES'
                        ).delete()

                # Determine trading type and duration
                trading_type, estimated_duration, target_rr = _determine_trading_type(
                    timeframe,
                    signal_data['confidence']
                )

                # Create new futures signal
                signal = Signal.objects.create(
                    symbol=symbol_obj,
                    direction=direction,
                    entry=entry_price,
                    sl=Decimal(str(signal_data.get('sl', signal_data.get('stop_loss')))),
                    tp=Decimal(str(signal_data.get('tp', signal_data.get('take_profit')))),
                    confidence=signal_data['confidence'],
                    timeframe=timeframe,
                    market_type='FUTURES',
                    leverage=signal_data.get('leverage', 10),  # Default 10x
                    status='ACTIVE',
                    trading_type=trading_type,
                    estimated_duration=estimated_duration,
                    risk_reward_ratio=target_rr
                )

                logger.info(
                    f"✅ New FUTURES {direction} signal: {symbol_str} @ ${signal.entry} "
                    f"({timeframe}, {signal.leverage}x, Conf: {signal.confidence:.0%})"
                )

                return signal

        return await save_signal()

    except Exception as e:
        logger.error(f"Error saving futures signal: {e}", exc_info=True)
        return None


def _determine_trading_type(timeframe: str, confidence: float) -> tuple:
    """Determine trading type, duration, and target R/R based on timeframe"""
    if timeframe == '1d':
        return ('SWING', '3-7 days', 3.0)
    elif timeframe == '4h':
        return ('DAY', '1-2 days', 3.0)
    elif timeframe == '1h':
        return ('INTRADAY', '4-12 hours', 3.0)
    elif timeframe == '15m':
        return ('SCALP', '30-90 min', 3.0)
    elif timeframe == '5m':
        return ('ULTRA_SCALP', '10-30 min', 3.0)
    else:
        return ('INTRADAY', '4-12 hours', 3.0)


async def scan_futures_timeframe(
    client: BinanceFuturesClient,
    timeframe: str,
    top_pairs: List[str],
    limit: int = 200
) -> Dict[str, int]:
    """
    Scan a specific timeframe for FUTURES signals.

    Args:
        client: Binance Futures API client
        timeframe: Timeframe to scan ('5m', '15m', '1h', '4h', '1d')
        top_pairs: List of futures symbols to scan
        limit: Number of candles to fetch

    Returns:
        Dict with counts: {'created': N, 'skipped': N, 'errors': N}
    """
    counts = {'created': 0, 'skipped': 0, 'errors': 0}

    logger.info(f"🔍 Scanning {len(top_pairs)} futures pairs on {timeframe} timeframe...")

    try:
        # Get configuration for this timeframe
        config = FUTURES_TIMEFRAME_CONFIGS.get(timeframe)
        if not config:
            logger.error(f"No config for futures timeframe: {timeframe}")
            return counts

        # Fetch klines for all pairs with rate limiting
        klines_data = await client.batch_get_klines(
            top_pairs,
            interval=timeframe,
            limit=limit,
            batch_size=5  # Conservative batch size
        )

        # Create engine with futures-specific config
        engine = SignalDetectionEngine(
            config=config,
            use_volatility_aware=True  # Enable volatility-aware SL/TP
        )

        # Process each symbol
        for symbol, klines in klines_data.items():
            try:
                # Update engine cache
                engine.update_candles(symbol, klines)

                # Process symbol
                result = engine.process_symbol(symbol, timeframe)

                if result:
                    action = result.get('action')

                    if action == 'created':
                        signal_data = result['signal']
                        signal_data['timeframe'] = timeframe
                        signal_data['market_type'] = 'FUTURES'
                        signal_data['leverage'] = 10  # Default leverage

                        # Save with deduplication
                        saved_signal = await _save_futures_signal_with_dedup(signal_data, timeframe)

                        if saved_signal:
                            counts['created'] += 1

                            # Broadcast signal
                            from scanner.services.dispatcher import signal_dispatcher
                            signal_dispatcher.broadcast_signal({
                                'symbol': symbol,
                                'direction': signal_data.get('direction'),
                                'entry': float(saved_signal.entry),
                                'sl': float(saved_signal.sl),
                                'tp': float(saved_signal.tp),
                                'confidence': saved_signal.confidence,
                                'timeframe': timeframe,
                                'market_type': 'FUTURES',
                                'leverage': saved_signal.leverage
                            })
                        else:
                            counts['skipped'] += 1

            except Exception as e:
                logger.error(f"Error processing futures {symbol} on {timeframe}: {e}")
                counts['errors'] += 1
                continue

        logger.info(
            f"✅ Futures {timeframe} scan complete: "
            f"{counts['created']} created, "
            f"{counts['skipped']} skipped, "
            f"{counts['errors']} errors"
        )

    except Exception as e:
        logger.error(f"Error scanning futures {timeframe}: {e}", exc_info=True)

    return counts


# ============================================================================
# CELERY TASKS - Individual Timeframe Scanners
# ============================================================================

@shared_task(
    name='scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1d',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_futures_1d(self):
    """
    Scan Binance Futures 1-day timeframe.
    Best for swing trading signals with leverage.
    """
    logger.info("🔍 Starting Futures 1-day timeframe scan...")

    try:
        result = asyncio.run(_scan_futures_single_timeframe('1d'))
        logger.info(f"✅ Futures 1d scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Futures 1d scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.futures_multi_timeframe_scanner.scan_futures_4h',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_futures_4h(self):
    """
    Scan Binance Futures 4-hour timeframe.
    Good balance between signal quality and frequency.
    """
    logger.info("🔍 Starting Futures 4-hour timeframe scan...")

    try:
        result = asyncio.run(_scan_futures_single_timeframe('4h'))
        logger.info(f"✅ Futures 4h scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Futures 4h scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1h',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_futures_1h(self):
    """
    Scan Binance Futures 1-hour timeframe.
    Active intraday trading signals with leverage.
    """
    logger.info("🔍 Starting Futures 1-hour timeframe scan...")

    try:
        result = asyncio.run(_scan_futures_single_timeframe('1h'))
        logger.info(f"✅ Futures 1h scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Futures 1h scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.futures_multi_timeframe_scanner.scan_futures_15m',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_futures_15m(self):
    """
    Scan Binance Futures 15-minute timeframe.
    Scalping signals with leverage.
    """
    logger.info("🔍 Starting Futures 15-minute timeframe scan...")

    try:
        result = asyncio.run(_scan_futures_single_timeframe('15m'))
        logger.info(f"✅ Futures 15m scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Futures 15m scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.futures_multi_timeframe_scanner.scan_futures_5m',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_futures_5m(self):
    """
    Scan Binance Futures 5-minute timeframe.
    Ultra-scalping signals with leverage (optional - high frequency).
    """
    logger.info("🔍 Starting Futures 5-minute timeframe scan...")

    try:
        result = asyncio.run(_scan_futures_single_timeframe('5m'))
        logger.info(f"✅ Futures 5m scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Futures 5m scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _scan_futures_single_timeframe(timeframe: str) -> Dict:
    """
    Async implementation of single futures timeframe scan.

    Args:
        timeframe: Timeframe to scan ('5m', '15m', '1h', '4h', '1d')

    Returns:
        Dict with scan results
    """
    async with BinanceFuturesClient() as client:
        # Get all USDT perpetual futures pairs
        futures_pairs = await client.get_usdt_futures_pairs()

        # Get top pairs by volume (all pairs, sorted)
        top_pairs = await _get_top_futures_pairs_by_volume(
            client,
            futures_pairs,
            top_n=len(futures_pairs)  # Scan all available pairs
        )

        logger.info(f"📊 Scanning {len(top_pairs)} futures pairs on {timeframe}")

        # Determine candle limit based on timeframe
        if timeframe == '5m':
            limit = 300  # ~25 hours of 5m data
        elif timeframe == '15m':
            limit = 200  # ~2 days of 15m data
        elif timeframe == '1h':
            limit = 200  # ~8 days of 1h data
        elif timeframe == '4h':
            limit = 150  # ~25 days of 4h data
        elif timeframe == '1d':
            limit = 100  # ~3 months of daily data
        else:
            limit = 200

        # Run scan
        counts = await scan_futures_timeframe(client, timeframe, top_pairs, limit)

        return {
            'timeframe': timeframe,
            'pairs_scanned': len(top_pairs),
            'signals_created': counts['created'],
            'signals_skipped': counts['skipped'],
            'errors': counts['errors'],
            'timestamp': timezone.now().isoformat()
        }
