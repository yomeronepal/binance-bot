"""Celery tasks for the 4h swing engine (paper-first validation harness).

scan_swing: at each 4h close, evaluate the breakout-in-trend rule on closed
candles and open a cost-aware paper trade per new signal (one per symbol).
monitor_swing_positions: every few minutes, close open trades at SL/TP net of
fee + slippage. Gated by SwingStrategyConfig.enabled; paper only.
"""
import asyncio
import logging
from datetime import timezone as dt_timezone
from decimal import Decimal

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from scanner.indicators.indicator_utils import klines_to_dataframe
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.strategies.swing_engine import evaluate_swing

logger = logging.getLogger(__name__)

SCAN_LOCK_KEY = 'swing_scan_lock'
SCAN_LOCK_TTL = 280
KLINES_LIMIT = 250


async def _fetch_frames(symbols, entry_tf, trend_tf):
    """Fetch entry + trend klines per symbol as dataframes."""
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            k_entry = await client.get_klines(symbol, interval=entry_tf, limit=KLINES_LIMIT)
            k_trend = await client.get_klines(symbol, interval=trend_tf, limit=KLINES_LIMIT)
            if k_entry and k_trend:
                out[symbol] = (klines_to_dataframe(k_entry), klines_to_dataframe(k_trend))
    return out


async def _fetch_prices(symbols):
    """Current mark price per symbol."""
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            try:
                out[symbol] = Decimal(str(await client.get_current_price(symbol)))
            except Exception as exc:
                logger.warning("Swing price fetch failed for %s: %s", symbol, exc)
    return out


def _drop_forming(df):
    """Drop the still-forming last candle so evaluation uses closed data."""
    return df.iloc[:-1] if len(df) > 1 else df


def _open_trade(symbol, sig, config):
    """Open an OPEN SwingPaperTrade sized margin x leverage."""
    from signals.models.swing import SwingPaperTrade
    entry = Decimal(str(sig['entry']))
    if entry <= 0:
        return None
    quantity = (config.margin_per_trade * Decimal(config.leverage)) / entry
    return SwingPaperTrade.objects.create(
        symbol=symbol,
        direction=sig['direction'],
        entry_price=entry,
        stop_loss=Decimal(str(sig['stop_loss'])),
        take_profit=Decimal(str(sig['take_profit'])),
        atr_at_entry=Decimal(str(sig['atr'])),
        quantity=quantity,
        position_size=config.margin_per_trade,
        leverage=config.leverage,
        entry_time=timezone.now(),
        status='OPEN',
    )


def _record_signal(symbol, sig, candle_open, entry_tf, trend_tf):
    """Persist the detected breakout as a SwingSignal (deduped per candle)."""
    from signals.models.swing import SwingSignal
    signal, _created = SwingSignal.objects.get_or_create(
        symbol=symbol,
        entry_timeframe=entry_tf,
        candle_open_time=candle_open,
        direction=sig['direction'],
        defaults={
            'trend_timeframe': trend_tf,
            'entry': Decimal(str(sig['entry'])),
            'stop_loss': Decimal(str(sig['stop_loss'])),
            'take_profit': Decimal(str(sig['take_profit'])),
            'atr': Decimal(str(sig['atr'])),
        },
    )
    return signal


def _run_scan():
    """Resolve config + symbols, evaluate each, record signals + open trades."""
    from signals.models.swing import SwingStrategyConfig, SwingPaperTrade
    config = SwingStrategyConfig.get_active()
    if not config.enabled:
        return {'skipped': 'disabled'}

    symbols = config.scan_symbols()
    frames = asyncio.run(_fetch_frames(symbols, config.entry_timeframe, config.trend_timeframe))
    created = 0
    signals = 0
    for symbol in symbols:
        pair = frames.get(symbol)
        if not pair:
            continue
        df_entry, df_trend = pair
        df_entry_closed = _drop_forming(df_entry)
        sig = evaluate_swing(df_entry_closed, _drop_forming(df_trend), config)
        if not sig:
            continue
        candle_open = df_entry_closed.index[-1].to_pydatetime().replace(tzinfo=dt_timezone.utc)
        signal = _record_signal(symbol, sig, candle_open, config.entry_timeframe, config.trend_timeframe)
        signals += 1
        if SwingPaperTrade.objects.filter(symbol=symbol, status='OPEN').exists():
            continue
        trade = _open_trade(symbol, sig, config)
        if trade:
            created += 1
            if signal.status != 'EXECUTED':
                signal.status = 'EXECUTED'
                signal.save(update_fields=['status'])
            logger.info("Swing opened %s %s @ %s", trade.direction, symbol, trade.entry_price)
    logger.info("Swing scan: %d symbols, %d signals, %d opened", len(symbols), signals, created)
    return {'symbols': len(symbols), 'signals': signals, 'created': created}


@shared_task(name='scanner.tasks.swing_scanner.scan_swing', bind=True, max_retries=0)
def scan_swing(self):
    """Run the 4h swing scan once, guarded by a Redis lock."""
    if not cache.add(SCAN_LOCK_KEY, '1', timeout=SCAN_LOCK_TTL):
        return {'skipped': 'locked'}
    try:
        return _run_scan()
    finally:
        cache.delete(SCAN_LOCK_KEY)


def _exit_level(trade, price):
    """Return (exit_price, status) if price crossed SL/TP, else None."""
    if trade.direction == 'LONG':
        if price <= trade.stop_loss:
            return trade.stop_loss, 'CLOSED_SL'
        if price >= trade.take_profit:
            return trade.take_profit, 'CLOSED_TP'
    else:
        if price >= trade.stop_loss:
            return trade.stop_loss, 'CLOSED_SL'
        if price <= trade.take_profit:
            return trade.take_profit, 'CLOSED_TP'
    return None


def _close_trade(trade, exit_price, status, config):
    """Close a trade at exit_price, net of round-trip fee + slippage."""
    qty = trade.quantity
    if trade.direction == 'LONG':
        gross = (exit_price - trade.entry_price) * qty
    else:
        gross = (trade.entry_price - exit_price) * qty
    turnover = qty * trade.entry_price + qty * exit_price
    cost = turnover * (config.fee_rate + config.slippage_rate)
    trade.exit_price = exit_price
    trade.exit_time = timezone.now()
    trade.status = status
    trade.fees_paid = cost
    trade.profit_loss = gross - cost
    if trade.position_size:
        trade.profit_loss_percentage = (trade.profit_loss / trade.position_size) * Decimal('100')
    trade.save()


def _run_monitor():
    """Close open swing trades that have reached SL/TP."""
    from signals.models.swing import SwingStrategyConfig, SwingPaperTrade
    open_trades = list(SwingPaperTrade.objects.filter(status='OPEN'))
    if not open_trades:
        return {'checked': 0, 'closed': 0}
    config = SwingStrategyConfig.get_active()
    prices = asyncio.run(_fetch_prices(list({t.symbol for t in open_trades})))
    closed = 0
    for trade in open_trades:
        price = prices.get(trade.symbol)
        if price is None:
            continue
        hit = _exit_level(trade, price)
        if hit:
            _close_trade(trade, hit[0], hit[1], config)
            closed += 1
            logger.info("Swing closed %s %s at %s (%s)", trade.direction, trade.symbol, hit[0], hit[1])
    return {'checked': len(open_trades), 'closed': closed}


@shared_task(name='scanner.tasks.swing_scanner.monitor_swing_positions', bind=True, max_retries=0)
def monitor_swing_positions(self):
    """Close open swing paper trades at SL/TP (net of cost)."""
    return _run_monitor()
