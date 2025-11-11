"""
Celery tasks for Binance scanner.
Handles periodic scanning, notifications, and maintenance.
"""
import logging
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_binance_market(self):
    """
    Periodic task to scan Binance market and generate signals.
    Runs every minute via Celery Beat.
    """
    try:
        logger.info("🔄 Starting Binance market scan...")

        from scanner.services.binance_client import BinanceClient
        from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
        from scanner.services.dispatcher import signal_dispatcher
        from signals.models import Signal, Symbol

        # Initialize components with quality-focused thresholds
        config = SignalConfig(
            min_confidence=0.70,           # 70% confidence for higher quality signals
            long_rsi_min=25.0,             # True oversold conditions (tight range)
            long_rsi_max=35.0,             # Mean reversion buy zone
            short_rsi_min=65.0,            # True overbought conditions (tight range)
            short_rsi_max=75.0,            # Mean reversion sell zone
            long_adx_min=20.0,             # Filter choppy markets (minimum trend strength)
            short_adx_min=20.0             # Avoid low-confidence ranging conditions
        )
        # Enable volatility-aware mode for dynamic SL/TP adjustment per coin
        engine = SignalDetectionEngine(config, use_volatility_aware=True)

        # Run async scanning using asyncio.run() to prevent memory leaks
        # This properly creates, uses, and cleans up the event loop
        result = asyncio.run(_scan_market_async(engine))

        logger.info(
            f"✅ Market scan completed: "
            f"Created={result['created']}, "
            f"Updated={result['updated']}, "
            f"Deleted={result['deleted']}, "
            f"Active={result['active']}"
        )

        return result

    except Exception as exc:
        logger.error(f"❌ Error in market scan: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _scan_market_async(engine):
    """Async helper for market scanning with network error handling."""
    from scanner.services.binance_client import BinanceClient
    from scanner.services.dispatcher import signal_dispatcher

    created_count = 0
    updated_count = 0
    deleted_count = 0

    async with BinanceClient() as client:
        # Pre-flight connectivity check
        logger.info("🔍 Checking Binance API connectivity...")
        is_connected = await client.check_connectivity()

        if not is_connected:
            logger.error(
                "🔴 Cannot connect to Binance API. "
                "Please check:\n"
                "  1. Internet connection is active\n"
                "  2. DNS servers are reachable (try: ping 8.8.8.8)\n"
                "  3. Firewall/VPN not blocking api.binance.com\n"
                "  4. Docker network configuration is correct"
            )
            raise ConnectionError(
                "Failed to connect to Binance API. Check network connectivity."
            )
        # Get all USDT pairs (maximum coverage)
        usdt_pairs = await client.get_usdt_pairs()

        # Get top volume pairs (all available for maximum coverage - ~436 pairs)
        top_pairs = await _get_top_pairs(client, usdt_pairs, top_n=len(usdt_pairs))

        # Save all symbols to database
        await _save_symbols_to_db(top_pairs)

        # Fetch klines for all pairs with optimized rate limiting
        # Using smaller batch_size (5) and longer delay (1.5s) to prevent timeouts
        klines_data_1h = await client.batch_get_klines(
            top_pairs,
            interval='1h',
            limit=200,
            batch_size=5,  # Reduced from 20 to 5 concurrent requests
            delay_between_batches=1.5  # Increased delay to prevent rate limiting
        )

        # Fetch 4h data for multi-timeframe confirmation
        klines_data_4h = await client.batch_get_klines(
            top_pairs,
            interval='4h',
            limit=200,
            batch_size=5,
            delay_between_batches=1.5
        )

        # Process each symbol
        for symbol in top_pairs:
            try:
                klines_1h = klines_data_1h.get(symbol, [])
                klines_4h = klines_data_4h.get(symbol, [])

                if not klines_1h:
                    continue

                # Update engine cache with 1h data
                engine.update_candles(symbol, klines_1h)

                # Update engine cache with 4h data for MTF confirmation
                if klines_4h:
                    engine.update_candles(f"{symbol}_4h", klines_4h)

                # Process symbol
                result = engine.process_symbol(symbol, '1h')

                if result:
                    action = result.get('action')

                    if action == 'created':
                        signal_data = result['signal']
                        saved_signal = await _save_signal_async(signal_data)
                        if saved_signal:  # Only count if not a duplicate
                            created_count += 1
                            signal_dispatcher.broadcast_signal(signal_data)

                    elif action == 'updated':
                        updated_count += 1
                        signal_data = result['signal']
                        _broadcast_signal_update(signal_data)

                    elif action == 'deleted':
                        deleted_count += 1
                        signal_id = result['signal_id']
                        _broadcast_signal_deletion(signal_id)

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

    return {
        'created': created_count,
        'updated': updated_count,
        'deleted': deleted_count,
        'active': len(engine.active_signals)
    }


async def _get_top_pairs(client, pairs: List[str], top_n: int = 50) -> List[str]:
    """Get top N pairs by volume."""
    try:
        volume_data = []

        # Process ALL pairs, not just first 200
        for i in range(0, len(pairs), 50):
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

            await asyncio.sleep(0.5)

        volume_data.sort(key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in volume_data[:top_n]]

    except Exception as e:
        logger.error(f"Error getting top pairs: {e}")
        return pairs[:top_n]


async def _save_symbols_to_db(symbols: List[str]):
    """Save all scanned symbols to database."""
    from asgiref.sync import sync_to_async
    from signals.models import Symbol

    logger.info(f"💾 Saving {len(symbols)} symbols to database...")

    @sync_to_async
    def save_symbols():
        saved_count = 0
        updated_count = 0

        for symbol in symbols:
            try:
                symbol_obj, created = Symbol.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        'exchange': 'BINANCE',
                        'active': True
                    }
                )

                if created:
                    saved_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error saving symbol {symbol}: {e}")
                continue

        logger.info(f"📊 Symbols saved: {saved_count} new, {updated_count} updated")
        return saved_count, updated_count

    await save_symbols()


def _determine_trading_type_and_duration(timeframe: str, confidence: float):
    """
    Determine trading type, estimated duration, and risk-reward ratio based on timeframe and confidence.

    Trading Type Risk Profiles:
    - SCALPING: Higher R/R (2.0-3.0) - Quick exits, tighter stops
    - DAY: Moderate R/R (1.5-2.5) - Balance between risk and reward
    - SWING: Lower R/R (1.2-2.0) - Wider stops, bigger targets

    Returns: (trading_type, estimated_duration_hours, risk_reward_ratio)
    """
    # timeframe: (trading_type, base_duration_hours, base_risk_reward)
    timeframe_map = {
        '1m': ('SCALPING', 0.25, 2.5),   # 15 minutes, 2.5:1 R/R
        '5m': ('SCALPING', 1, 2.0),       # 1 hour, 2.0:1 R/R
        '15m': ('DAY', 3, 2.0),           # 3 hours, 2.0:1 R/R
        '30m': ('DAY', 6, 1.8),           # 6 hours, 1.8:1 R/R
        '1h': ('DAY', 12, 1.5),           # 12 hours, 1.5:1 R/R
        '4h': ('SWING', 48, 1.5),         # 2 days, 1.5:1 R/R
        '1d': ('SWING', 168, 1.3),        # 7 days, 1.3:1 R/R
        '1w': ('SWING', 720, 1.2),        # 30 days, 1.2:1 R/R
    }

    trading_type, base_duration, base_rr = timeframe_map.get(timeframe, ('DAY', 12, 1.8))

    # Adjust duration and R/R based on confidence
    if confidence >= 0.85:
        # High confidence: faster targets, better R/R
        duration = base_duration * 0.7  # 30% faster
        risk_reward = base_rr * 1.2     # 20% better R/R
    elif confidence >= 0.75:
        # Medium confidence: normal parameters
        duration = base_duration
        risk_reward = base_rr
    else:
        # Lower confidence: slower targets, conservative R/R
        duration = base_duration * 1.3  # 30% slower
        risk_reward = base_rr * 0.9     # 10% more conservative

    return trading_type, int(duration), round(risk_reward, 2)


async def _save_signal_async(signal_data: Dict):
    """Save signal to database asynchronously with deduplication."""
    from asgiref.sync import sync_to_async
    from signals.models import Signal, Symbol
    from decimal import Decimal

    @sync_to_async
    def save_signal():
        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=signal_data['symbol'],
            defaults={
                'exchange': 'BINANCE',
                'active': True
            }
        )

        # Check for duplicate signals - timeframe-aware deduplication window
        # For 1h timeframe: check last 55 minutes (allow 1 signal per hour)
        # For other timeframes: check last 15 minutes
        timeframe = signal_data['timeframe']
        if timeframe == '1h':
            dedup_window_minutes = 55  # Allow new signal every hour
        elif timeframe == '4h':
            dedup_window_minutes = 230  # ~3.8 hours - allow 1 per 4h candle
        elif timeframe == '1d':
            dedup_window_minutes = 1400  # ~23 hours - allow 1 per day
        else:
            dedup_window_minutes = 15  # Default for smaller timeframes

        recent_time = timezone.now() - timedelta(minutes=dedup_window_minutes)
        entry_price = Decimal(str(signal_data['entry']))
        price_tolerance = entry_price * Decimal('0.01')  # 1% tolerance (increased from 0.5%)

        existing_signal = Signal.objects.filter(
            symbol=symbol_obj,
            direction=signal_data['direction'],
            timeframe=signal_data['timeframe'],
            status='ACTIVE',
            created_at__gte=recent_time,
            entry__gte=entry_price - price_tolerance,
            entry__lte=entry_price + price_tolerance,
            market_type='SPOT'
        ).first()

        if existing_signal:
            logger.info(
                f"⏭️  Skipping duplicate signal for {signal_data['symbol']} {signal_data['direction']} "
                f"@ ${entry_price} (Existing: ${existing_signal.entry}, "
                f"Created: {existing_signal.created_at.strftime('%H:%M:%S')}, "
                f"Window: {dedup_window_minutes}min)"
            )
            return None

        # Determine trading type, estimated duration, and target risk-reward
        trading_type, estimated_duration, target_rr = _determine_trading_type_and_duration(
            signal_data['timeframe'],
            signal_data['confidence']
        )

        # Adjust TP/SL to match target risk-reward ratio
        entry = Decimal(str(signal_data['entry']))
        sl = Decimal(str(signal_data['sl']))
        tp = Decimal(str(signal_data['tp']))

        # Calculate current risk
        if signal_data['direction'] == 'LONG':
            risk = entry - sl
            # Adjust TP to achieve target R/R
            adjusted_tp = entry + (risk * Decimal(str(target_rr)))
        else:  # SHORT
            risk = sl - entry
            # Adjust TP to achieve target R/R
            adjusted_tp = entry - (risk * Decimal(str(target_rr)))

        # Create new signal with adjusted TP
        signal = Signal.objects.create(
            symbol=symbol_obj,
            direction=signal_data['direction'],
            entry=entry,
            sl=sl,
            tp=adjusted_tp,
            confidence=signal_data['confidence'],
            timeframe=signal_data['timeframe'],
            description=signal_data.get('description', ''),
            status='ACTIVE',
            market_type='SPOT',
            trading_type=trading_type,
            estimated_duration_hours=estimated_duration
        )
        logger.info(
            f"💾 Saved signal to DB: {signal.direction} {signal.symbol.symbol} @ ${signal.entry} "
            f"(ID: {signal.id}, Conf: {signal.confidence:.0%})"
        )
        return signal

    return await save_signal()


def _broadcast_signal_update(signal_data: Dict):
    """Broadcast signal update via WebSocket."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            'signals_global',
            {
                'type': 'signal_updated',
                'signal': signal_data
            }
        )


def _broadcast_signal_deletion(signal_id: str):
    """Broadcast signal deletion via WebSocket."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            'signals_global',
            {
                'type': 'signal_deleted',
                'signal_id': signal_id
            }
        )


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def full_data_refresh(self):
    """
    Full data refresh task.
    Recomputes all indicators for historical data.
    Runs every hour via Celery Beat.
    """
    try:
        logger.info("🔄 Starting full data refresh...")

        from signals.models import Signal, Symbol

        # Mark old signals as expired
        expired_time = timezone.now() - timedelta(hours=1)
        expired_count = Signal.objects.filter(
            status='ACTIVE',
            created_at__lt=expired_time
        ).update(status='EXPIRED')

        logger.info(f"📊 Full refresh: Marked {expired_count} signals as expired")

        # Could add more refresh logic here:
        # - Refresh symbol list
        # - Recompute historical indicators
        # - Clean up old data

        return {
            'expired_signals': expired_count,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"❌ Error in full refresh: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_signal_notifications(self):
    """
    Send notifications for high-confidence signals.
    Runs every 2 minutes via Celery Beat.
    """
    try:
        logger.info("📬 Checking for signal notifications...")

        from signals.models import Signal

        # Get recent high-confidence signals
        recent_time = timezone.now() - timedelta(minutes=2)
        high_conf_signals = Signal.objects.filter(
            status='ACTIVE',
            confidence__gte=0.85,
            created_at__gte=recent_time
        )

        notification_count = 0

        for signal in high_conf_signals:
            # Broadcast via WebSocket
            from scanner.services.dispatcher import signal_dispatcher

            signal_data = {
                'symbol': signal.symbol.symbol,
                'direction': signal.direction,
                'entry': float(signal.entry),
                'sl': float(signal.sl),
                'tp': float(signal.tp),
                'confidence': signal.confidence,
                'timeframe': signal.timeframe,
                'description': signal.description,
            }

            signal_dispatcher.broadcast_signal(signal_data)
            notification_count += 1

            logger.info(
                f"📨 Notification sent: {signal.direction} {signal.symbol.symbol} "
                f"(Conf: {signal.confidence:.0%})"
            )

        logger.info(f"✅ Sent {notification_count} notifications")

        return {
            'notifications_sent': notification_count,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"❌ Error sending notifications: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_signals():
    """
    Cleanup expired signals and remove duplicates from database.
    Runs every 5 minutes via Celery Beat.
    """
    try:
        logger.info("🧹 Cleaning up expired signals...")

        from signals.models import Signal
        from django.db.models import Count, Min

        # 1. Delete old signals (older than 24 hours)
        cutoff_time = timezone.now() - timedelta(hours=24)
        old_deleted, _ = Signal.objects.filter(
            created_at__lt=cutoff_time
        ).delete()

        # 2. Mark signals that hit TP/SL as EXECUTED
        # Check LONG signals that hit TP (current price >= TP)
        executed_long = Signal.objects.filter(
            status='ACTIVE',
            direction='LONG',
            market_type='SPOT'
        ).count()  # Placeholder - would need real-time price data

        # Check SHORT signals that hit TP (current price <= TP)
        executed_short = Signal.objects.filter(
            status='ACTIVE',
            direction='SHORT',
            market_type='SPOT'
        ).count()  # Placeholder - would need real-time price data

        # 3. Mark old active signals as EXPIRED (older than 4 hours)
        expire_time = timezone.now() - timedelta(hours=4)
        expired_count = Signal.objects.filter(
            status='ACTIVE',
            created_at__lt=expire_time
        ).update(status='EXPIRED')

        # 4. Remove duplicate signals (keep the most recent one)
        duplicates_removed = 0
        # Find duplicate groups (same symbol, direction, timeframe, market_type)
        duplicate_groups = Signal.objects.filter(
            status='ACTIVE'
        ).values(
            'symbol', 'direction', 'timeframe', 'market_type'
        ).annotate(
            count=Count('id'),
            first_id=Min('id')
        ).filter(count__gt=1)

        # For each duplicate group, keep only the most recent signal
        for group in duplicate_groups:
            old_duplicates = Signal.objects.filter(
                symbol_id=group['symbol'],
                direction=group['direction'],
                timeframe=group['timeframe'],
                market_type=group['market_type'],
                status='ACTIVE'
            ).order_by('-created_at')[1:]  # Keep first (most recent), delete rest

            for signal in old_duplicates:
                signal.status = 'CANCELLED'
                signal.save()
                duplicates_removed += 1

        logger.info(
            f"✅ Cleanup complete: {old_deleted} old deleted, "
            f"{expired_count} expired, {duplicates_removed} duplicates removed"
        )

        return {
            'old_deleted': old_deleted,
            'expired_count': expired_count,
            'duplicates_removed': duplicates_removed,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error in cleanup: {e}", exc_info=True)
        return {'error': str(e)}


@shared_task
def system_health_check():
    """
    System health check task.
    Runs every 10 minutes via Celery Beat.
    """
    try:
        logger.info("🏥 Running system health check...")

        from signals.models import Signal, Symbol
        from django.db import connection

        health_data = {
            'timestamp': timezone.now().isoformat(),
            'database': 'connected',
            'active_signals': Signal.objects.filter(status='ACTIVE').count(),
            'total_symbols': Symbol.objects.count(),
        }

        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Test Redis connection
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', 60)
            health_data['redis'] = 'connected'
        except Exception:
            health_data['redis'] = 'disconnected'

        logger.info(f"✅ Health check passed: {health_data}")

        return health_data

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}", exc_info=True)
        return {'error': str(e), 'timestamp': timezone.now().isoformat()}


# Manual task for testing
@shared_task
def test_celery_task(message="Hello from Celery!"):
    """Simple test task to verify Celery is working."""
    logger.info(f"🎯 Test task executed: {message}")
    return {
        'message': message,
        'timestamp': timezone.now().isoformat(),
        'status': 'success'
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_futures_market(self):
    """
    Periodic task to scan Binance Futures market and generate signals.
    Runs every minute via Celery Beat.
    """
    try:
        logger.info("🔄 Starting Binance Futures market scan...")

        from scanner.services.binance_futures_client import BinanceFuturesClient
        from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
        from scanner.services.dispatcher import signal_dispatcher
        from signals.models import Signal, Symbol

        # Initialize components with quality-focused thresholds
        config = SignalConfig(
            min_confidence=0.70,           # 70% confidence for higher quality signals
            long_rsi_min=25.0,             # True oversold conditions (tight range)
            long_rsi_max=35.0,             # Mean reversion buy zone
            short_rsi_min=65.0,            # True overbought conditions (tight range)
            short_rsi_max=75.0,            # Mean reversion sell zone
            long_adx_min=20.0,             # Filter choppy markets (minimum trend strength)
            short_adx_min=20.0             # Avoid low-confidence ranging conditions
        )
        # Enable volatility-aware mode for dynamic SL/TP adjustment per coin
        engine = SignalDetectionEngine(config, use_volatility_aware=True)

        # Run async scanning
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_scan_futures_market_async(engine))

            logger.info(
                f"✅ Futures market scan completed: "
                f"Created={result['created']}, "
                f"Updated={result['updated']}, "
                f"Deleted={result['deleted']}, "
                f"Active={result['active']}"
            )

            return result

        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"❌ Error in futures market scan: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _scan_futures_market_async(engine):
    """Async helper for futures market scanning."""
    from scanner.services.binance_futures_client import BinanceFuturesClient
    from scanner.services.dispatcher import signal_dispatcher

    created_count = 0
    updated_count = 0
    deleted_count = 0

    async with BinanceFuturesClient() as client:
        # Get all USDT perpetual futures pairs
        futures_pairs = await client.get_usdt_futures_pairs()

        # Get all futures pairs for maximum coverage (~530 pairs)
        top_pairs = await _get_top_futures_pairs(client, futures_pairs, top_n=len(futures_pairs))

        # Save futures symbols to database
        await _save_futures_symbols_to_db(top_pairs)

        # Fetch klines for all pairs with optimized rate limiting
        # Using smaller batch_size (5) to prevent timeouts
        klines_data = await client.batch_get_klines(
            top_pairs,
            interval='1h',
            limit=200,
            batch_size=5  # Reduced from 20 to 5 concurrent requests
        )

        # Process each symbol
        for symbol, klines in klines_data.items():
            try:
                # Update engine cache
                engine.update_candles(symbol, klines)

                # Process symbol
                result = engine.process_symbol(symbol, '1h')

                if result:
                    action = result.get('action')

                    if action == 'created':
                        signal_data = result['signal']
                        signal_data['market_type'] = 'FUTURES'
                        signal_data['leverage'] = 10  # Default 10x leverage
                        saved_signal = await _save_futures_signal_async(signal_data)
                        if saved_signal:  # Only count if not a duplicate
                            created_count += 1
                            signal_dispatcher.broadcast_signal(signal_data)

                    elif action == 'updated':
                        updated_count += 1
                        signal_data = result['signal']
                        _broadcast_signal_update(signal_data)

                    elif action == 'deleted':
                        deleted_count += 1
                        signal_id = result['signal_id']
                        _broadcast_signal_deletion(signal_id)

            except Exception as e:
                logger.error(f"Error processing futures {symbol}: {e}")
                continue

    return {
        'created': created_count,
        'updated': updated_count,
        'deleted': deleted_count,
        'active': len(engine.active_signals)
    }


async def _get_top_futures_pairs(client, pairs: List[str], top_n: int = 50) -> List[str]:
    """Get top N futures pairs by volume."""
    try:
        volume_data = []

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

            await asyncio.sleep(0.5)

        volume_data.sort(key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in volume_data[:top_n]]

    except Exception as e:
        logger.error(f"Error getting top futures pairs: {e}")
        return pairs[:top_n]


async def _save_futures_symbols_to_db(symbols: List[str]):
    """Save all scanned futures symbols to database."""
    from asgiref.sync import sync_to_async
    from signals.models import Symbol

    logger.info(f"💾 Saving {len(symbols)} futures symbols to database...")

    @sync_to_async
    def save_symbols():
        saved_count = 0
        updated_count = 0

        for symbol in symbols:
            try:
                symbol_obj, created = Symbol.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        'exchange': 'BINANCE',
                        'active': True,
                        'market_type': 'FUTURES'
                    }
                )

                if created:
                    saved_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error saving futures symbol {symbol}: {e}")
                continue

        logger.info(f"📊 Futures symbols saved: {saved_count} new, {updated_count} updated")
        return saved_count, updated_count

    await save_symbols()


async def _save_futures_signal_async(signal_data: Dict):
    """Save futures signal to database asynchronously with deduplication."""
    from asgiref.sync import sync_to_async
    from signals.models import Signal, Symbol
    from decimal import Decimal

    @sync_to_async
    def save_signal():
        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=signal_data['symbol'],
            defaults={
                'exchange': 'BINANCE',
                'active': True,
                'market_type': 'FUTURES'
            }
        )

        # Check for duplicate signals - timeframe-aware deduplication window
        timeframe = signal_data['timeframe']
        if timeframe == '1h':
            dedup_window_minutes = 55  # Allow new signal every hour
        elif timeframe == '4h':
            dedup_window_minutes = 230  # ~3.8 hours - allow 1 per 4h candle
        elif timeframe == '1d':
            dedup_window_minutes = 1400  # ~23 hours - allow 1 per day
        else:
            dedup_window_minutes = 15  # Default for smaller timeframes

        recent_time = timezone.now() - timedelta(minutes=dedup_window_minutes)
        entry_price = Decimal(str(signal_data['entry']))
        price_tolerance = entry_price * Decimal('0.01')  # 1% tolerance

        existing_signal = Signal.objects.filter(
            symbol=symbol_obj,
            direction=signal_data['direction'],
            timeframe=signal_data['timeframe'],
            status='ACTIVE',
            created_at__gte=recent_time,
            entry__gte=entry_price - price_tolerance,
            entry__lte=entry_price + price_tolerance,
            market_type='FUTURES'
        ).first()

        if existing_signal:
            logger.info(
                f"⏭️  Skipping duplicate futures signal for {signal_data['symbol']} {signal_data['direction']} "
                f"@ ${entry_price} (Existing: ${existing_signal.entry}, "
                f"Created: {existing_signal.created_at.strftime('%H:%M:%S')}, "
                f"Window: {dedup_window_minutes}min)"
            )
            return None

        # Determine trading type, estimated duration, and target risk-reward
        trading_type, estimated_duration, target_rr = _determine_trading_type_and_duration(
            signal_data['timeframe'],
            signal_data['confidence']
        )

        # Adjust TP/SL to match target risk-reward ratio
        entry = Decimal(str(signal_data['entry']))
        sl = Decimal(str(signal_data['sl']))
        tp = Decimal(str(signal_data['tp']))

        # Calculate current risk
        if signal_data['direction'] == 'LONG':
            risk = entry - sl
            # Adjust TP to achieve target R/R
            adjusted_tp = entry + (risk * Decimal(str(target_rr)))
        else:  # SHORT
            risk = sl - entry
            # Adjust TP to achieve target R/R
            adjusted_tp = entry - (risk * Decimal(str(target_rr)))

        # Create new signal with adjusted TP
        signal = Signal.objects.create(
            symbol=symbol_obj,
            direction=signal_data['direction'],
            entry=entry,
            sl=sl,
            tp=adjusted_tp,
            confidence=signal_data['confidence'],
            timeframe=signal_data['timeframe'],
            description=signal_data.get('description', ''),
            status='ACTIVE',
            market_type='FUTURES',
            leverage=signal_data.get('leverage', 10),
            trading_type=trading_type,
            estimated_duration_hours=estimated_duration
        )
        logger.info(
            f"💾 Saved FUTURES signal to DB: {signal.direction} {signal.symbol.symbol} @ ${signal.entry} "
            f"(ID: {signal.id}, Conf: {signal.confidence:.0%}, Leverage: {signal.leverage}x)"
        )
        return signal


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def check_and_close_paper_trades(self):
    """
    Periodic task to check open paper trades and automatically close them
    if Stop Loss or Take Profit is hit.

    This task:
    1. Fetches current prices from Binance
    2. Checks all open paper trades
    3. Closes trades that hit SL or TP
    4. Sends notifications for closed trades

    Runs every 30 seconds via Celery Beat.
    """
    try:
        from decimal import Decimal
        from signals.services.paper_trader import paper_trading_service
        from signals.models import PaperTrade
        from scanner.services.binance_client import BinanceClient
        from scanner.services.dispatcher import signal_dispatcher

        logger.info("🔍 Checking paper trades for auto-close...")

        # Get all open paper trades
        open_trades = PaperTrade.objects.filter(status='OPEN')
        if not open_trades.exists():
            logger.debug("No open paper trades to check")
            return {'checked': 0, 'closed': 0}

        # Get unique symbols from open trades
        symbols = set(trade.symbol for trade in open_trades)
        logger.info(f"📊 Checking {open_trades.count()} open trades across {len(symbols)} symbols")

        # Fetch current prices from Binance
        binance_client = BinanceClient()
        current_prices = {}

        async def fetch_prices():
            prices = {}
            for symbol in symbols:
                try:
                    price_data = await binance_client.get_price(symbol)
                    if price_data and 'price' in price_data:
                        prices[symbol] = Decimal(str(price_data['price']))
                except Exception as e:
                    logger.warning(f"Failed to fetch price for {symbol}: {e}")
                    continue
            return prices

        # Run async price fetching using asyncio.run() to prevent memory leaks
        current_prices = asyncio.run(fetch_prices())

        # Check and close trades
        closed_trades = paper_trading_service.check_and_close_trades(current_prices)

        # Update PaperAccounts for closed trades - optimized to prevent N+1 queries
        if closed_trades:
            from signals.models import PaperAccount
            from signals.services.auto_trader import auto_trading_service

            # Prefetch all user accounts in single query to avoid N+1 problem
            user_ids = [trade.user_id for trade in closed_trades if trade.user_id]
            accounts = {account.user_id: account for account in
                       PaperAccount.objects.filter(user_id__in=user_ids).select_related('user')}

            for trade in closed_trades:
                try:
                    # Update account if this trade belongs to an auto-trading account
                    if trade.user_id and trade.user_id in accounts:
                        account = accounts[trade.user_id]
                        # Remove position from account (already done in close_trade_and_update_account)
                        # but we ensure metrics are updated
                        account.update_metrics()
                        logger.debug(f"Updated account for user {trade.user_id}: Balance=${account.balance}")
                except Exception as e:
                    logger.warning(f"Failed to update account for trade {trade.id}: {e}")

        # Send notifications for closed trades via WebSocket
        for trade in closed_trades:
            try:
                # Dispatch trade closed notification
                asyncio.run(signal_dispatcher.broadcast_paper_trade_update(
                    'paper_trade_closed',
                    {
                        'id': trade.id,
                        'symbol': trade.symbol,
                        'direction': trade.direction,
                        'status': trade.status,
                        'entry_price': str(trade.entry_price),
                        'exit_price': str(trade.exit_price) if trade.exit_price else None,
                        'profit_loss': float(trade.profit_loss),
                        'profit_loss_percentage': float(trade.profit_loss_percentage),
                    }
                ))
            except Exception as e:
                logger.error(f"Failed to send notification for closed trade {trade.id}: {e}")

        result = {
            'checked': open_trades.count(),
            'closed': len(closed_trades),
            'symbols': list(symbols),
            'closed_trades': [
                {
                    'id': t.id,
                    'symbol': t.symbol,
                    'status': t.status,
                    'profit_loss': float(t.profit_loss)
                } for t in closed_trades
            ]
        }

        if closed_trades:
            logger.info(f"✅ Auto-closed {len(closed_trades)} paper trades")

        return result

    except Exception as e:
        logger.error(f"❌ Error in check_and_close_paper_trades: {str(e)}", exc_info=True)
        # Retry on error
        raise self.retry(exc=e)
