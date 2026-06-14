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

from scanner.services.binance_futures_client import BinanceFuturesClient
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
        # One trade per signal — the signal stays ACTIVE (like the v1 engine),
        # so it is not re-traded after its trade closes.
        if DayTradePaperTrade.objects.filter(signal=signal).exists():
            continue
        if DayTradePaperTrade.objects.filter(symbol=signal.symbol, status__in=OPEN_STATUSES).exists():
            continue
        trade = _open_trade_from_signal(signal, db_config)
        if trade:
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
    """Close the trade in one exit when price hits the stop or take-profit.

    v1-style: a single fixed-percentage SL and TP, no scale-out or trailing.
    Returns True if the trade closed (and was saved).
    """
    if _stop_hit(trade, price, trade.stop_loss):
        _close_remaining(trade, 'SL', trade.stop_loss, now)
        trade.save()
        return True
    if _target_hit(trade, price, trade.tp1_price):
        _close_remaining(trade, 'TP', trade.tp1_price, now)
        trade.save()
        return True
    return False


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
    async with BinanceFuturesClient() as client:
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
