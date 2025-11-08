"""
Multi-Timeframe Signal Scanner with Universal Configuration System

Generates signals from multiple timeframes (15m, 1h, 4h, 1d) using:
- Market-specific universal configurations (Forex vs Binance)
- Breathing room parameters for better win rates
- Automatic market type detection per symbol
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from celery import shared_task

from scanner.services.binance_client import BinanceClient
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
from scanner.config import get_signal_config_for_symbol, detect_market_type, MarketType
from signals.models import Signal

logger = logging.getLogger(__name__)


async def _get_top_pairs_by_volume(client: BinanceClient, pairs: List[str], top_n: int = 200) -> List[str]:
    """Get top N pairs by 24h volume"""
    try:
        # Get 24h ticker data for all symbols (no symbol parameter = all tickers)
        response = await client._request('GET', '/api/v3/ticker/24hr')

        # response should be a list of tickers
        if not isinstance(response, list):
            logger.warning("Unexpected ticker response format")
            return pairs[:top_n]

        # Create volume map
        volume_map = {}
        for ticker in response:
            symbol = ticker.get('symbol', '')
            quote_volume = float(ticker.get('quoteVolume', 0))
            if symbol and quote_volume > 0:
                volume_map[symbol] = quote_volume

        # Sort pairs by volume
        volume_data = []
        for pair in pairs:
            volume = volume_map.get(pair, 0)
            if volume > 0:
                volume_data.append((pair, volume))

        # Sort by volume descending
        volume_data.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        top_pairs = [pair for pair, _ in volume_data[:top_n]]

        logger.info(f"Selected top {len(top_pairs)} pairs by 24h volume")
        return top_pairs
    except Exception as e:
        logger.error(f"Error getting top pairs by volume: {e}")
        return pairs[:top_n]


# Optimized breathing room parameters (based on backtest results)
BREATHING_ROOM_CONFIGS = {
    '1d': SignalConfig(
        # Daily timeframe - Conservative approach (swing trading)
        min_confidence=0.70,
        long_adx_min=30.0,
        short_adx_min=30.0,
        long_rsi_min=23.0,
        long_rsi_max=33.0,
        short_rsi_min=67.0,
        short_rsi_max=77.0,
        sl_atr_multiplier=3.0,   # Wide stop for breathing room
        tp_atr_multiplier=8.0    # 1:2.67 R/R
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
        sl_atr_multiplier=2.5,   # Good breathing room
        tp_atr_multiplier=7.0    # 1:2.8 R/R
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
        sl_atr_multiplier=2.5,   # Moderate breathing room
        tp_atr_multiplier=6.5    # 1:2.6 R/R
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
        sl_atr_multiplier=2.0,   # Tighter stop for scalping
        tp_atr_multiplier=5.0    # 1:2.5 R/R
    )
}


# Timeframe priority ranking (higher value = higher priority)
TIMEFRAME_PRIORITY = {
    '1d': 4,   # Highest priority
    '4h': 3,
    '1h': 2,
    '15m': 1   # Lowest priority
}


async def _save_signal_async(signal_data: Dict) -> Optional[Signal]:
    """
    Save signal to database with timeframe prioritization.

    If the same symbol already has a signal on a different timeframe:
    - Higher timeframe (1d > 4h > 1h > 15m) replaces lower timeframe
    - Lower timeframe is skipped if higher timeframe exists
    """
    try:
        from asgiref.sync import sync_to_async

        @sync_to_async
        def save_signal():
            from signals.models import Symbol as SymbolModel

            symbol_str = signal_data['symbol']
            direction = signal_data.get('signal_type', signal_data.get('direction'))  # Support both field names
            new_timeframe = signal_data.get('timeframe', '1h')
            new_priority = TIMEFRAME_PRIORITY.get(new_timeframe, 0)

            # Get or create Symbol object
            symbol_obj, _ = SymbolModel.objects.get_or_create(
                symbol=symbol_str,
                defaults={'exchange': 'BINANCE'}
            )

            # Check for existing ACTIVE signals for this symbol+direction
            existing = Signal.objects.filter(
                symbol=symbol_obj,
                direction=direction,  # Database uses 'direction' not 'signal_type'
                status='ACTIVE'
            ).first()

            if existing:
                existing_timeframe = existing.timeframe
                existing_priority = TIMEFRAME_PRIORITY.get(existing_timeframe, 0)

                # Case 1: Same timeframe - skip duplicate
                if new_timeframe == existing_timeframe:
                    logger.debug(
                        f"⏭️ Skipping duplicate {direction} signal for {symbol_str} ({new_timeframe}) - "
                        f"already exists"
                    )
                    return None

                # Case 2: New signal is LOWER priority - skip it
                if new_priority < existing_priority:
                    logger.info(
                        f"⏭️ Skipping {direction} signal for {symbol_str} ({new_timeframe}) - "
                        f"higher timeframe signal exists ({existing_timeframe})"
                    )
                    return None

                # Case 3: New signal is HIGHER priority - replace existing
                if new_priority > existing_priority:
                    logger.info(
                        f"⬆️ UPGRADING {direction} signal for {symbol_str}: "
                        f"{existing_timeframe} → {new_timeframe} "
                        f"(Conf: {existing.confidence:.0%} → {signal_data['confidence']:.0%})"
                    )

                    # Delete ALL lower timeframe signals (SPOT + FUTURES)
                    Signal.objects.filter(
                        symbol=symbol_obj,
                        direction=direction,
                        timeframe=existing_timeframe,
                        status='ACTIVE'
                    ).delete()

                    # Create new higher timeframe signals (SPOT + FUTURES)
                    spot_signal = Signal.objects.create(
                        symbol=symbol_obj,
                        direction=direction,
                        entry=signal_data.get('entry_price', signal_data.get('entry')),
                        sl=signal_data.get('stop_loss', signal_data.get('sl')),
                        tp=signal_data.get('take_profit', signal_data.get('tp')),
                        confidence=signal_data['confidence'],
                        timeframe=new_timeframe,
                        market_type='SPOT',
                        status='ACTIVE'
                    )

                    futures_signal = Signal.objects.create(
                        symbol=symbol_obj,
                        direction=direction,
                        entry=signal_data.get('entry_price', signal_data.get('entry')),
                        sl=signal_data.get('stop_loss', signal_data.get('sl')),
                        tp=signal_data.get('take_profit', signal_data.get('tp')),
                        confidence=signal_data['confidence'],
                        timeframe=new_timeframe,
                        market_type='FUTURES',
                        leverage=10,  # Default 10x leverage for futures
                        status='ACTIVE'
                    )

                    logger.info(
                        f"✅ Upgraded to {new_timeframe} signals for {symbol_str} "
                        f"@ ${spot_signal.entry} (SPOT + FUTURES, Conf: {spot_signal.confidence:.0%})"
                    )
                    return spot_signal  # Return SPOT signal as primary

            # No existing signal - create new ones (SPOT + FUTURES)
            spot_signal = Signal.objects.create(
                symbol=symbol_obj,
                direction=direction,
                entry=signal_data.get('entry_price', signal_data.get('entry')),
                sl=signal_data.get('stop_loss', signal_data.get('sl')),
                tp=signal_data.get('take_profit', signal_data.get('tp')),
                confidence=signal_data['confidence'],
                timeframe=new_timeframe,
                market_type='SPOT',
                status='ACTIVE'
            )

            futures_signal = Signal.objects.create(
                symbol=symbol_obj,
                direction=direction,
                entry=signal_data.get('entry_price', signal_data.get('entry')),
                sl=signal_data.get('stop_loss', signal_data.get('sl')),
                tp=signal_data.get('take_profit', signal_data.get('tp')),
                confidence=signal_data['confidence'],
                timeframe=new_timeframe,
                market_type='FUTURES',
                leverage=10,  # Default 10x leverage for futures
                status='ACTIVE'
            )

            logger.info(
                f"✅ New {direction} signals: {symbol_str} @ ${spot_signal.entry} "
                f"(SPOT + FUTURES, {new_timeframe}, Conf: {spot_signal.confidence:.0%})"
            )
            return spot_signal  # Return SPOT signal as primary

        return await save_signal()
    except Exception as e:
        logger.error(f"Error saving signal: {e}", exc_info=True)
        return None


async def scan_timeframe(
    client: BinanceClient,
    timeframe: str,
    top_pairs: List[str],
    limit: int = 200,
    use_universal_config: bool = True
) -> Dict[str, int]:
    """
    Scan a specific timeframe for signals with market-specific configuration.

    Args:
        client: Binance API client
        timeframe: Timeframe to scan ('15m', '1h', '4h', '1d')
        top_pairs: List of symbols to scan
        limit: Number of candles to fetch
        use_universal_config: If True, use market-specific universal configs

    Returns:
        Dict with counts: {'created': N, 'updated': N, 'invalidated': N}
    """
    counts = {'created': 0, 'updated': 0, 'invalidated': 0, 'skipped_no_config': 0}

    logger.info(f"🔍 Scanning {len(top_pairs)} symbols on {timeframe} timeframe "
                f"(Universal Config: {'ON' if use_universal_config else 'OFF'})...")

    try:
        # Fetch klines for all pairs
        klines_data = await client.batch_get_klines(
            top_pairs,
            interval=timeframe,
            limit=limit,
            batch_size=20
        )

        # Process each symbol
        for symbol, klines in klines_data.items():
            try:
                # Get market-specific configuration
                if use_universal_config:
                    config = get_signal_config_for_symbol(symbol)
                    if config is None:
                        logger.warning(f"⚠️ No config for {symbol}, skipping")
                        counts['skipped_no_config'] += 1
                        continue

                    market_type = detect_market_type(symbol)
                    logger.debug(f"📋 Using {market_type.value} config for {symbol}")
                else:
                    # Fallback to breathing room config
                    config = BREATHING_ROOM_CONFIGS.get(timeframe)
                    if not config:
                        logger.warning(f"⚠️ No breathing room config for {timeframe}")
                        continue

                # Create engine with symbol-specific config
                engine = SignalDetectionEngine(
                    config=config,
                    use_volatility_aware=False  # Use fixed universal params
                )

                # Update engine cache
                engine.update_candles(symbol, klines)

                # Process symbol
                result = engine.process_symbol(symbol, timeframe)

                if result:
                    action = result.get('action')

                    if action == 'created':
                        signal_data = result['signal']
                        signal_data['timeframe'] = timeframe  # Add timeframe
                        saved_signal = await _save_signal_async(signal_data)
                        if saved_signal:
                            counts['created'] += 1
                            direction = signal_data.get('signal_type', signal_data.get('direction'))
                            entry = signal_data.get('entry_price', signal_data.get('entry'))
                            market_type = detect_market_type(symbol)
                            logger.info(f"✅ New {direction} signal [{market_type.value.upper()}]: "
                                       f"{signal_data['symbol']} @ ${entry} ({timeframe})")

                    elif action == 'updated':
                        counts['updated'] += 1

                    elif action == 'invalidated':
                        counts['invalidated'] += 1

            except Exception as e:
                logger.error(f"Error processing {symbol} on {timeframe}: {e}")
                continue

        logger.info(
            f"✅ {timeframe} scan complete: "
            f"{counts['created']} created, "
            f"{counts['updated']} updated, "
            f"{counts['invalidated']} invalidated, "
            f"{counts.get('skipped_no_config', 0)} skipped (no config)"
        )

    except Exception as e:
        logger.error(f"Error scanning {timeframe}: {e}", exc_info=True)

    return counts


@shared_task(
    name='scanner.tasks.multi_timeframe_scanner.scan_multi_timeframe',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def scan_multi_timeframe(self):
    """
    Scan multiple timeframes (4h and 1d) for trading signals
    Celery task that runs periodically
    """
    logger.info("🚀 Starting multi-timeframe market scan (4h + 1d)...")

    try:
        # Run async scan
        result = asyncio.run(_scan_multi_timeframe_async())
        return result
    except Exception as e:
        logger.error(f"Multi-timeframe scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _scan_multi_timeframe_async():
    """
    Async implementation of multi-timeframe scan with universal configuration.

    Uses market-specific universal configs (Forex vs Binance) for each symbol.
    """

    # Initialize clients
    client = BinanceClient()

    # Get all USDT pairs
    usdt_pairs = await client.get_usdt_pairs()

    # Get all pairs sorted by volume (no limit - scan ALL Binance coins)
    top_pairs = await _get_top_pairs_by_volume(client, usdt_pairs, top_n=len(usdt_pairs))
    logger.info(f"📊 Scanning ALL {len(top_pairs)} Binance USDT pairs with UNIVERSAL CONFIG")

    # Timeframes to scan (in order of priority: longer to shorter)
    timeframes = ['1d', '4h', '1h', '15m']

    total_counts = {'created': 0, 'updated': 0, 'invalidated': 0, 'skipped_no_config': 0}

    for timeframe in timeframes:
        try:
            # Determine candle limit based on timeframe
            if timeframe == '15m':
                limit = 300  # More candles for short timeframe
            elif timeframe == '1h':
                limit = 250
            elif timeframe == '4h':
                limit = 200
            else:  # 1d
                limit = 100

            # Scan this timeframe with universal config
            counts = await scan_timeframe(
                client=client,
                timeframe=timeframe,
                top_pairs=top_pairs,
                limit=limit,
                use_universal_config=True  # Enable universal configuration
            )

            # Aggregate counts
            for key in counts:
                total_counts[key] += counts[key]

        except Exception as e:
            logger.error(f"Error scanning {timeframe}: {e}", exc_info=True)
            continue

    logger.info(
        f"🎯 Multi-timeframe scan complete! "
        f"Total: {total_counts['created']} new signals, "
        f"{total_counts['updated']} updates, "
        f"{total_counts['invalidated']} invalidated, "
        f"{total_counts.get('skipped_no_config', 0)} skipped (no config)"
    )

    return {
        'success': True,
        'timeframes_scanned': timeframes,
        'signals_created': total_counts['created'],
        'signals_updated': total_counts['updated'],
        'signals_invalidated': total_counts['invalidated'],
        'timestamp': datetime.utcnow().isoformat()
    }


@shared_task(
    name='scanner.tasks.multi_timeframe_scanner.scan_1d_timeframe',
    bind=True,
    max_retries=3
)
def scan_1d_timeframe(self):
    """
    Scan 1-day timeframe only (for separate scheduling)
    Best for swing trading signals
    """
    logger.info("🔍 Starting 1-day timeframe scan...")

    try:
        result = asyncio.run(_scan_single_timeframe_async('1d'))
        return result
    except Exception as e:
        logger.error(f"1d scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.multi_timeframe_scanner.scan_4h_timeframe',
    bind=True,
    max_retries=3
)
def scan_4h_timeframe(self):
    """
    Scan 4-hour timeframe only (for separate scheduling)
    Good balance between signal quality and frequency
    """
    logger.info("🔍 Starting 4-hour timeframe scan...")

    try:
        result = asyncio.run(_scan_single_timeframe_async('4h'))
        return result
    except Exception as e:
        logger.error(f"4h scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.multi_timeframe_scanner.scan_1h_timeframe',
    bind=True,
    max_retries=3
)
def scan_1h_timeframe(self):
    """
    Scan 1-hour timeframe only (for separate scheduling)
    Active intraday trading signals
    """
    logger.info("🔍 Starting 1-hour timeframe scan...")

    try:
        result = asyncio.run(_scan_single_timeframe_async('1h'))
        return result
    except Exception as e:
        logger.error(f"1h scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    name='scanner.tasks.multi_timeframe_scanner.scan_15m_timeframe',
    bind=True,
    max_retries=3
)
def scan_15m_timeframe(self):
    """
    Scan 15-minute timeframe only (for separate scheduling)
    Scalping and active trading signals
    """
    logger.info("🔍 Starting 15-minute timeframe scan...")

    try:
        result = asyncio.run(_scan_single_timeframe_async('15m'))
        return result
    except Exception as e:
        logger.error(f"15m scan failed: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _scan_single_timeframe_async(timeframe: str):
    """
    Scan a single timeframe with universal configuration.

    Args:
        timeframe: Timeframe to scan ('15m', '1h', '4h', '1d')

    Returns:
        Dict with scan results
    """
    client = BinanceClient()

    # Get all USDT pairs
    usdt_pairs = await client.get_usdt_pairs()

    # Get all pairs sorted by volume (scan ALL coins)
    top_pairs = await _get_top_pairs_by_volume(client, usdt_pairs, top_n=len(usdt_pairs))

    # Determine candle limit based on timeframe
    if timeframe == '15m':
        limit = 300  # More candles for short timeframe
    elif timeframe == '1h':
        limit = 250
    elif timeframe == '4h':
        limit = 200
    else:  # 1d
        limit = 100

    # Scan with universal configuration
    counts = await scan_timeframe(
        client=client,
        timeframe=timeframe,
        top_pairs=top_pairs,
        limit=limit,
        use_universal_config=True  # Enable market-specific universal configs
    )

    return {
        'success': True,
        'timeframe': timeframe,
        'signals_created': counts['created'],
        'signals_updated': counts['updated'],
        'signals_invalidated': counts['invalidated'],
        'skipped_no_config': counts.get('skipped_no_config', 0),
        'timestamp': datetime.utcnow().isoformat()
    }
