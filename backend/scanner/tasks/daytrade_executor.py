"""Execution + monitoring for the day-trade paper-trading system.

Two tasks, both on the dedicated ``daytrade`` queue:

- open_daytrade_positions: opens a DayTradePaperTrade from each ACTIVE
  DayTradeSignal, sized so the initial stop risks ``risk_per_trade_pct`` of
  the account balance.
- monitor_daytrade_positions: walks open trades against the live price,
  filling TP1 (50%) and TP2 (30%), trailing the 20% runner at the configured
  ATR multiple, honouring the stop, recording each leg as a DayTradeTradeExit,
  and rolling up account metrics.
"""
import asyncio
import logging
from decimal import Decimal

from asgiref.sync import sync_to_async
from celery import shared_task
from django.utils import timezone

from scanner.services.binance_client import BinanceClient
from scanner.strategies.daytrade_signal_engine import DayTradeSignalConfig

logger = logging.getLogger(__name__)

OPEN_STATUSES = ['PENDING', 'OPEN', 'PARTIAL']
CLOSE_STATUS = {
    'SL': 'CLOSED_SL',
    'TRAIL': 'CLOSED_TRAIL',
    'TP': 'CLOSED_TP',
    'MANUAL': 'CLOSED_MANUAL',
}


def _get_or_create_account():
    """Return the system-wide day-trade account, creating it if needed."""
    from signals.models.daytrade import DayTradePaperAccount
    account, _created = DayTradePaperAccount.objects.get_or_create(user=None)
    return account


def _active_config():
    """Load the active DayTradeStrategyConfig as an engine config."""
    from signals.models.daytrade import DayTradeStrategyConfig
    return DayTradeSignalConfig.from_db(DayTradeStrategyConfig.get_active()), DayTradeStrategyConfig.get_active()


def _position_size(db_config, entry, stop_loss):
    """Size a trade with fixed margin and leverage.

    notional = margin x leverage; quantity = notional / entry. P/L is then
    (price move) x quantity, so it already reflects leverage.
    """
    if entry <= 0:
        return None
    margin = db_config.margin_per_trade
    leverage = db_config.leverage
    notional = margin * leverage
    quantity = notional / entry
    return {
        'quantity': quantity,
        'margin': margin,
        'leverage': leverage,
        'stop_distance': abs(entry - stop_loss),
    }


def _open_trade_from_signal(signal, db_config):
    """Create a DayTradePaperTrade sized to a fixed margin x leverage."""
    from signals.models.daytrade import DayTradePaperTrade

    sizing = _position_size(db_config, signal.entry, signal.stop_loss)
    if not sizing or sizing['quantity'] <= 0:
        return None

    now = timezone.now()
    return DayTradePaperTrade.objects.create(
        signal=signal,
        symbol=signal.symbol,
        direction=signal.direction,
        market_type=signal.market_type,
        timeframe=signal.entry_timeframe,
        confidence=signal.confidence,
        entry_price=signal.entry,
        entry_time=now,
        position_size=sizing['margin'],
        quantity=sizing['quantity'],
        remaining_quantity=sizing['quantity'],
        initial_stop_loss=signal.stop_loss,
        stop_loss=signal.stop_loss,
        tp1_price=signal.tp1,
        tp2_price=signal.tp2,
        atr_at_entry=signal.atr,
        account_risk_pct=db_config.risk_per_trade_pct,
        stop_distance=sizing['stop_distance'],
        leverage=sizing['leverage'],
        status='OPEN',
    )


@shared_task(name='scanner.tasks.daytrade_executor.open_daytrade_positions', bind=True, max_retries=0)
def open_daytrade_positions(self):
    """Open paper trades from ACTIVE day-trade signals."""
    from signals.models.daytrade import DayTradeSignal, DayTradePaperTrade

    _, db_config = _active_config()
    account = _get_or_create_account()
    opened = 0

    for signal in DayTradeSignal.objects.filter(status='ACTIVE').order_by('created_at'):
        if signal.confidence is not None and signal.confidence < db_config.min_confidence:
            continue
        if DayTradePaperTrade.objects.filter(symbol=signal.symbol, status__in=OPEN_STATUSES).exists():
            continue
        open_count = DayTradePaperTrade.objects.filter(status__in=OPEN_STATUSES).count()
        if open_count >= account.max_open_trades:
            break
        trade = _open_trade_from_signal(signal, db_config)
        if trade:
            signal.status = 'EXECUTED'
            signal.save(update_fields=['status', 'updated_at'])
            opened += 1
            logger.info("DayTrade opened %s %s @ %s", trade.direction, trade.symbol, trade.entry_price)

    if opened:
        account.last_trade_at = timezone.now()
        account.save(update_fields=['last_trade_at'])
    return {'opened': opened}


def _is_long(trade):
    return trade.direction == 'LONG'


def _target_hit(trade, price, target) -> bool:
    """True if price reached a take-profit target."""
    return price >= target if _is_long(trade) else price <= target


def _stop_hit(trade, price, stop) -> bool:
    """True if price reached a stop level."""
    return price <= stop if _is_long(trade) else price >= stop


def _leg_pnl(trade, price, quantity) -> Decimal:
    """Realized P/L for closing ``quantity`` at ``price``."""
    if _is_long(trade):
        return (price - trade.entry_price) * quantity
    return (trade.entry_price - price) * quantity


def _record_exit(trade, exit_type, price, quantity, now):
    """Create a DayTradeTradeExit leg and accrue realized P/L."""
    from signals.models.daytrade import DayTradeTradeExit
    pnl = _leg_pnl(trade, price, quantity)
    DayTradeTradeExit.objects.create(
        trade=trade, exit_type=exit_type, price=price,
        quantity=quantity, pnl=pnl, exit_time=now,
    )
    trade.remaining_quantity -= quantity
    trade.realized_pnl += pnl


def _partial_exit(trade, exit_type, price, close_pct, now):
    """Close ``close_pct`` of the original quantity as one leg."""
    leg_qty = trade.quantity * (Decimal(str(close_pct)) / Decimal('100'))
    leg_qty = min(leg_qty, trade.remaining_quantity)
    if leg_qty > 0:
        _record_exit(trade, exit_type, price, leg_qty, now)


def _finalize(trade, status, price, now):
    """Mark a trade fully closed and finalise its P/L."""
    trade.profit_loss = trade.realized_pnl
    if trade.position_size:
        trade.profit_loss_percentage = (trade.profit_loss / trade.position_size) * Decimal('100')
    trade.exit_price = price
    trade.exit_time = now
    trade.status = status


def _close_remaining(trade, exit_type, price, now):
    """Close all remaining quantity at ``price`` and finalise the trade."""
    if trade.remaining_quantity > 0:
        _record_exit(trade, exit_type, price, trade.remaining_quantity, now)
    _finalize(trade, CLOSE_STATUS[exit_type], price, now)


def _update_trailing(trade, price, cfg):
    """Ratchet the runner's trailing stop in the trade's favour."""
    distance = trade.atr_at_entry * Decimal(str(cfg.trail_atr_mult))
    if _is_long(trade):
        candidate = price - distance
        if trade.trailing_stop is None or candidate > trade.trailing_stop:
            trade.trailing_stop = candidate
    else:
        candidate = price + distance
        if trade.trailing_stop is None or candidate < trade.trailing_stop:
            trade.trailing_stop = candidate


def apply_price(trade, price, cfg, now) -> bool:
    """Advance a trade's exit state machine for the current price.

    Returns True if the trade changed (and was saved).
    """
    effective_stop = trade.trailing_stop if trade.trailing_stop is not None else trade.stop_loss
    if _stop_hit(trade, price, effective_stop):
        exit_type = 'TRAIL' if trade.trailing_stop is not None else 'SL'
        _close_remaining(trade, exit_type, effective_stop, now)
        trade.save()
        return True

    changed = False
    if not trade.tp1_filled and _target_hit(trade, price, trade.tp1_price):
        _partial_exit(trade, 'TP1', trade.tp1_price, cfg.tp1_close_pct, now)
        trade.tp1_filled = True
        trade.status = 'PARTIAL'
        changed = True

    if trade.tp1_filled and not trade.tp2_filled and _target_hit(trade, price, trade.tp2_price):
        _partial_exit(trade, 'TP2', trade.tp2_price, cfg.tp2_close_pct, now)
        trade.tp2_filled = True
        changed = True

    if trade.tp2_filled and trade.remaining_quantity > 0:
        _update_trailing(trade, price, cfg)
        changed = True
        if _stop_hit(trade, price, trade.trailing_stop):
            _close_remaining(trade, 'TRAIL', trade.trailing_stop, now)
            trade.save()
            return True

    if changed and trade.remaining_quantity <= Decimal('0.00000001'):
        _finalize(trade, 'CLOSED_TP', trade.tp2_price, now)

    if changed:
        if trade.status not in CLOSE_STATUS.values():
            trade.profit_loss = trade.realized_pnl
        trade.save()
    return changed


async def _fetch_prices(client, symbols):
    """Fetch the latest price for each symbol; missing prices are skipped."""
    prices = {}
    for symbol in symbols:
        try:
            data = await client.get_price(symbol)
            prices[symbol] = Decimal(str(data['price']))
        except Exception as exc:
            logger.error("DayTrade price fetch failed for %s: %s", symbol, exc)
    return prices


async def _monitor_async():
    """Fetch prices for open trades and advance each trade's state machine."""
    from signals.models.daytrade import DayTradePaperTrade

    cfg, _db = await sync_to_async(_active_config)()
    open_trades = await sync_to_async(list)(
        DayTradePaperTrade.objects.filter(status__in=OPEN_STATUSES)
    )
    if not open_trades:
        return {'monitored': 0, 'closed': 0}

    symbols = sorted({t.symbol for t in open_trades})
    async with BinanceClient() as client:
        prices = await _fetch_prices(client, symbols)

    closed = 0
    now = timezone.now()
    for trade in open_trades:
        price = prices.get(trade.symbol)
        if price is None:
            continue
        changed = await sync_to_async(apply_price)(trade, price, cfg, now)
        if changed and trade.status in CLOSE_STATUS.values():
            closed += 1

    account = await sync_to_async(_get_or_create_account)()
    await sync_to_async(account.update_metrics)()
    return {'monitored': len(open_trades), 'closed': closed}


@shared_task(name='scanner.tasks.daytrade_executor.monitor_daytrade_positions', bind=True, max_retries=0)
def monitor_daytrade_positions(self):
    """Monitor open day-trades against live prices and manage exits."""
    result = asyncio.run(_monitor_async())
    logger.info("DayTrade monitor: %s", result)
    return result
