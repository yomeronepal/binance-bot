"""Celery scanner for the day-trade (15m Market Structure Pullback) engine.

Runs every minute: resolves the symbol universe (``*`` means all Binance
USDT pairs, otherwise the configured list), fetches 15m + 1h candles, and
runs DayTradeSignalEngine.generate() per symbol. 1h candles are cached
(they only change hourly) to keep the per-minute request load down, and a
Redis lock prevents overlapping runs.
"""
import asyncio
import logging

from asgiref.sync import sync_to_async
from celery import shared_task
from django.core.cache import cache

from scanner.indicators.indicator_utils import klines_to_dataframe
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.strategies.daytrade_signal_engine import (
    DayTradeSignalEngine,
    DayTradeSignalConfig,
)

logger = logging.getLogger(__name__)

MAJOR_PAIRS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'LTCUSDT',
]

SCAN_LOCK_KEY = 'daytrade_scan_lock'
SCAN_LOCK_TTL = 290
KLINES_1H_TTL = 300
ENTRY_KLINES_LIMIT = 150
BATCH_SIZE = 10


async def _top_by_volume(client, pairs, top_n):
    """Return the ``top_n`` pairs ranked by 24h quote volume."""
    valid = set(pairs)
    tickers = await client._request('GET', '/fapi/v1/ticker/24hr')
    ranked = sorted(
        (t for t in tickers if t['symbol'] in valid),
        key=lambda t: float(t.get('quoteVolume') or 0),
        reverse=True,
    )
    return [t['symbol'] for t in ranked[:top_n]]


async def _resolve_symbols(client, configured, top_n):
    """Resolve the scan universe.

    For ``*`` (or empty): all USDT perpetuals, optionally trimmed to the
    top_n most-liquid by 24h volume. Otherwise the configured list.
    """
    if not configured or '*' in configured:
        pairs = await client.get_usdt_futures_pairs()
        valid = set(pairs)
        if top_n and top_n > 0:
            top = await _top_by_volume(client, pairs, top_n)
            majors = [m for m in MAJOR_PAIRS if m in valid]
            universe = list(dict.fromkeys(top + majors))
            logger.info(
                "DayTrade universe: top %d by volume + %d majors -> %d pairs",
                top_n, len(majors), len(universe)
            )
            return universe
        logger.info("DayTrade universe: ALL (%d USDT futures pairs)", len(pairs))
        return pairs
    symbols = [s.upper() for s in configured]
    logger.info("DayTrade universe: %d configured symbols", len(symbols))
    return symbols


async def _fetch_1h_cached(client, symbols, limit):
    """Fetch 1h klines, serving cached symbols and fetching only the misses."""
    result = {}
    missing = []
    for symbol in symbols:
        cached = cache.get(f'daytrade:1h:{symbol}')
        if cached is not None:
            result[symbol] = cached
        else:
            missing.append(symbol)

    if missing:
        fetched = await client.batch_get_klines(
            missing, interval='1h', limit=limit, batch_size=BATCH_SIZE
        )
        for symbol, klines in fetched.items():
            if klines:
                cache.set(f'daytrade:1h:{symbol}', klines, KLINES_1H_TTL)
                result[symbol] = klines
    return result


def _generate_for_symbol(engine, symbol, klines_15m, klines_1h):
    """Build frames and run the engine for one symbol (sync, ORM-safe)."""
    if not klines_15m or not klines_1h:
        return None
    df_15m = klines_to_dataframe(klines_15m)
    df_1h = klines_to_dataframe(klines_1h)
    return engine.generate(symbol, df_15m, df_1h)


async def _scan_daytrade_async():
    """Resolve the universe, fetch candles, and run the engine per symbol."""
    from signals.models.daytrade import DayTradeStrategyConfig

    db_config = await sync_to_async(DayTradeStrategyConfig.get_active)()
    cfg = DayTradeSignalConfig.from_db(db_config)
    engine = DayTradeSignalEngine(cfg)
    trend_limit = cfg.trend_ema_slow + 15

    counts = {'symbols': 0, 'created': 0, 'errors': 0}

    async with BinanceFuturesClient() as client:
        symbols = await _resolve_symbols(client, cfg.symbols, cfg.universe_top_n)
        counts['symbols'] = len(symbols)

        klines_1h = await _fetch_1h_cached(client, symbols, trend_limit)
        klines_15m = await client.batch_get_klines(
            symbols, interval=cfg.entry_timeframe,
            limit=ENTRY_KLINES_LIMIT, batch_size=BATCH_SIZE
        )

        for symbol in symbols:
            try:
                signal = await sync_to_async(_generate_for_symbol)(
                    engine, symbol, klines_15m.get(symbol), klines_1h.get(symbol)
                )
                if signal:
                    counts['created'] += 1
            except Exception as exc:
                counts['errors'] += 1
                logger.error("DayTrade scan error for %s: %s", symbol, exc)

    logger.info(
        "DayTrade scan complete: %d symbols, %d signals, %d errors",
        counts['symbols'], counts['created'], counts['errors']
    )
    return counts


@shared_task(
    name='scanner.tasks.daytrade_scanner.scan_daytrade',
    bind=True,
    max_retries=0,
)
def scan_daytrade(self):
    """Run the day-trade scan once, guarded by a lock to avoid overlap."""
    if not cache.add(SCAN_LOCK_KEY, '1', timeout=SCAN_LOCK_TTL):
        logger.info("DayTrade scan already running, skipping this tick")
        return {'skipped': True}
    try:
        return asyncio.run(_scan_daytrade_async())
    finally:
        cache.delete(SCAN_LOCK_KEY)
