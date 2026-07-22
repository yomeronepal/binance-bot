"""Celery tasks for the 4h order-block (ICT) engine — paper-first harness.

scan_order_block: at each 4h close, evaluate the order-block rule on closed
candles and open a cost-aware paper trade per new signal, sized fixed-fractional
(risk a % of current equity) and capped at a max number of concurrent positions
to bound correlated drawdown. monitor_order_block_positions: every few minutes,
close open trades at SL/TP net of fee + slippage. Gated by
OrderBlockStrategyConfig.enabled; paper only.
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
from scanner.strategies.order_block_engine import evaluate_order_block

logger = logging.getLogger(__name__)

SCAN_LOCK_KEY = 'order_block_scan_lock'
SCAN_LOCK_TTL = 280
KLINES_LIMIT = 250


async def _fetch_entry_frames(symbols, entry_tf):
    """Fetch entry klines per symbol as dataframes."""
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            k_entry = await client.get_klines(symbol, interval=entry_tf, limit=KLINES_LIMIT)
            if k_entry:
                out[symbol] = klines_to_dataframe(k_entry)
    return out


async def _fetch_prices(symbols):
    """Current mark price per symbol."""
    out = {}
    async with BinanceFuturesClient() as client:
        for symbol in symbols:
            try:
                out[symbol] = Decimal(str(await client.get_current_price(symbol)))
            except Exception as exc:
                logger.warning("OB price fetch failed for %s: %s", symbol, exc)
    return out


def _drop_forming(df):
    """Drop the still-forming last candle so evaluation uses closed data."""
    return df.iloc[:-1] if len(df) > 1 else df


def _current_equity(config):
    """Starting equity plus realized P/L from all closed trades."""
    from django.db.models import Sum
    from signals.models.order_block import OrderBlockPaperTrade
    realized = OrderBlockPaperTrade.objects.filter(
        status__startswith='CLOSED'
    ).aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
    return config.account_equity + realized


def _position_from_risk(sig, equity, config):
    """Fixed-fractional sizing: quantity that risks risk_pct of equity to the stop."""
    entry = Decimal(str(sig['entry']))
    stop = Decimal(str(sig['stop_loss']))
    risk_distance = abs(entry - stop)
    if entry <= 0 or risk_distance <= 0:
        return None
    risk_amount = equity * Decimal(str(config.risk_per_trade_pct)) / Decimal('100')
    quantity = risk_amount / risk_distance
    margin = (quantity * entry) / Decimal(config.leverage)
    return quantity, margin, risk_amount


def _open_trade(symbol, sig, config, equity):
    """Open an OPEN OrderBlockPaperTrade sized fixed-fractional."""
    from signals.models.order_block import OrderBlockPaperTrade
    sized = _position_from_risk(sig, equity, config)
    if sized is None:
        return None
    quantity, margin, risk_amount = sized
    return OrderBlockPaperTrade.objects.create(
        symbol=symbol,
        direction=sig['direction'],
        entry_price=Decimal(str(sig['entry'])),
        stop_loss=Decimal(str(sig['stop_loss'])),
        take_profit=Decimal(str(sig['take_profit'])),
        atr_at_entry=Decimal(str(sig['atr'])),
        quantity=quantity,
        position_size=margin.quantize(Decimal('0.01')),
        risk_amount=risk_amount.quantize(Decimal('0.01')),
        confidence=sig.get('confidence', 0),
        leverage=config.leverage,
        entry_time=timezone.now(),
        status='OPEN',
    )


def _record_signal(symbol, sig, candle_open, entry_tf):
    """Persist the detected order block as an OrderBlockSignal (deduped per candle)."""
    from signals.models.order_block import OrderBlockSignal
    signal, _created = OrderBlockSignal.objects.get_or_create(
        symbol=symbol,
        entry_timeframe=entry_tf,
        candle_open_time=candle_open,
        direction=sig['direction'],
        defaults={
            'entry': Decimal(str(sig['entry'])),
            'stop_loss': Decimal(str(sig['stop_loss'])),
            'take_profit': Decimal(str(sig['take_profit'])),
            'atr': Decimal(str(sig['atr'])),
            'confidence': sig.get('confidence', 0),
            'structure': sig.get('structure', ''),
        },
    )
    return signal


def _mark_signal(signal, status):
    """Update a signal's status if it changed."""
    if signal.status != status:
        signal.status = status
        signal.save(update_fields=['status'])


def _open_count():
    """Number of currently open order-block positions."""
    from signals.models.order_block import OrderBlockPaperTrade
    return OrderBlockPaperTrade.objects.filter(status='OPEN').count()


def _has_open(symbol):
    """True if the symbol already has an open position."""
    from signals.models.order_block import OrderBlockPaperTrade
    return OrderBlockPaperTrade.objects.filter(symbol=symbol, status='OPEN').exists()


def _run_scan():
    """Resolve config + symbols, evaluate each, record signals + open capped trades."""
    from signals.models.order_block import OrderBlockStrategyConfig
    config = OrderBlockStrategyConfig.get_active()
    if not config.enabled:
        return {'skipped': 'disabled'}

    symbols = config.scan_symbols()
    frames = asyncio.run(_fetch_entry_frames(symbols, config.entry_timeframe))
    created = 0
    signals = 0
    for symbol in symbols:
        df_entry = frames.get(symbol)
        if df_entry is None:
            continue
        if _has_open(symbol):
            continue
        df_closed = _drop_forming(df_entry)
        sig = evaluate_order_block(df_closed, config)
        if not sig:
            continue
        opened = _handle_signal(symbol, sig, df_closed, config)
        if opened:
            created += 1
        if opened or sig.get('first_break'):
            signals += 1
    logger.info("OB scan: %d symbols, %d signals, %d opened", len(symbols), signals, created)
    return {'symbols': len(symbols), 'signals': signals, 'created': created}


def _handle_signal(symbol, sig, df_closed, config):
    """Open a trade if the cap allows; record a feed signal on a break or an entry.

    Feed stays clean: continuation bars that neither break structure nor open a
    trade are not logged. Returns the opened trade (or None).
    """
    can_open = _open_count() < config.max_concurrent_positions
    trade = _open_trade(symbol, sig, config, _current_equity(config)) if can_open else None
    if not (trade or sig.get('first_break')):
        return None
    candle_open = df_closed.index[-1].to_pydatetime().replace(tzinfo=dt_timezone.utc)
    signal = _record_signal(symbol, sig, candle_open, config.entry_timeframe)
    if trade:
        _mark_signal(signal, 'EXECUTED')
        logger.info("OB opened %s %s @ %s (risk $%s)", trade.direction, symbol, trade.entry_price, trade.risk_amount)
    else:
        _mark_signal(signal, 'SKIPPED')
    return trade


@shared_task(name='scanner.tasks.order_block_scanner.scan_order_block', bind=True, max_retries=0)
def scan_order_block(self):
    """Run the 4h order-block scan once, guarded by a Redis lock."""
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
    """Close open order-block trades that have reached SL/TP."""
    from signals.models.order_block import OrderBlockStrategyConfig, OrderBlockPaperTrade
    open_trades = list(OrderBlockPaperTrade.objects.filter(status='OPEN'))
    if not open_trades:
        return {'checked': 0, 'closed': 0}
    config = OrderBlockStrategyConfig.get_active()
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
            logger.info("OB closed %s %s at %s (%s)", trade.direction, trade.symbol, hit[0], hit[1])
    return {'checked': len(open_trades), 'closed': closed}


@shared_task(name='scanner.tasks.order_block_scanner.monitor_order_block_positions', bind=True, max_retries=0)
def monitor_order_block_positions(self):
    """Close open order-block paper trades at SL/TP (net of cost)."""
    return _run_monitor()
