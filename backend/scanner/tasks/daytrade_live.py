"""Live Binance execution for day-trade signals.

When a day-trade signal fires inside an active optimized Day-Trade Session, place
a REAL Binance futures order, sized from the shared futures pool
(FuturesTradingSettings.total_trading_capital / max_active_gw_trades x leverage).

The resulting position is recorded as a FuturesTrade so the existing 30s sync
(sync_futures_trades_with_binance) manages mark price, SL/TP detection and the
SL/TP push notification. Gated hard by FuturesTradingSettings.is_enabled (global
live master switch) AND daytrade_live_enabled; deduped per signal and per symbol.
"""
import asyncio
import logging
import threading
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone as dj_timezone

from signals.services.futures_trader import BinanceFuturesTrader

logger = logging.getLogger(__name__)

NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def _now_in_active_session():
    """True if the current Nepal time falls inside any active Day-Trade Session."""
    from signals.models.daytrade import DayTradeSession

    npt = dj_timezone.now() + NEPAL_OFFSET
    hour, weekday = npt.hour, npt.weekday()
    for session in DayTradeSession.objects.filter(is_active=True):
        if session.covers(hour, weekday):
            return True
    return False


def _place_orders(symbol, direction, leverage, margin, stop_loss, take_profit):
    """Place entry + SL/TP orders on Binance in a worker thread.

    Returns (result, exception); result is None on failure.
    """
    result = [None]
    error = [None]

    def run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _execute():
                    trader = BinanceFuturesTrader(use_testnet=False)
                    try:
                        symbol_info = await trader.get_symbol_info(symbol)
                        if not symbol_info:
                            raise Exception(f"No symbol info for {symbol}")
                        price = await trader.get_current_price(symbol)
                        if not price:
                            raise Exception(f"No current price for {symbol}")
                        return await trader.place_trade_orders(
                            symbol, direction, leverage, margin,
                            stop_loss, take_profit, symbol_info, price,
                        )
                    finally:
                        await trader.close()
                result[0] = loop.run_until_complete(_execute())
            finally:
                loop.close()
        except Exception as exc:
            error[0] = exc

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=60)
    return result[0], error[0]


def _live_gates_open(signal):
    """Return (settings, reason). settings is None when execution must be skipped."""
    from signals.models.futures import FuturesTradingSettings, FuturesTrade

    settings = FuturesTradingSettings.get_settings()
    if not settings.is_enabled:
        return None, 'futures_master_disabled'
    if not settings.daytrade_live_enabled:
        return None, 'daytrade_live_disabled'
    if signal.meta and signal.meta.get('live_order_id'):
        return None, 'already_executed'
    if not _now_in_active_session():
        return None, 'not_in_session'
    if settings.get_available_gw_trade_slots() <= 0:
        return None, 'no_slots'
    if FuturesTrade.objects.filter(
        symbol=signal.symbol, direction=signal.direction, status__in=['OPEN', 'PENDING']
    ).exists():
        return None, 'existing_position'
    return settings, 'ok'


def _record_live_trade(signal, settings, result):
    """Persist the filled order as an OPEN FuturesTrade and tag the signal."""
    from signals.models.futures import FuturesTrade

    trade = FuturesTrade.objects.create(
        signal=None,
        symbol=signal.symbol,
        direction=signal.direction,
        leverage=settings.leverage,
        quantity=result['quantity'],
        entry_price=result['entry_price'],
        entry_time=dj_timezone.now(),
        stop_loss=signal.stop_loss,
        take_profit=signal.tp1,
        position_size_usdt=settings.per_trade_amount,
        status='OPEN',
        binance_order_id=result['order_id'],
        error_message='Day-trade live entry (in-session)',
    )
    signal.meta = {**(signal.meta or {}), 'live_order_id': str(result['order_id']),
                   'live_futures_trade_id': trade.id}
    signal.save(update_fields=['meta', 'updated_at'])
    return trade


def maybe_execute_live_daytrade(signal):
    """Execute a real Binance order for a day-trade signal if all live gates pass.

    Failure-isolated and idempotent: returns the FuturesTrade on success, else None.
    """
    settings, reason = _live_gates_open(signal)
    if settings is None:
        logger.debug("DayTrade live skip %s: %s", signal.symbol, reason)
        return None

    result, error = _place_orders(
        signal.symbol, signal.direction, settings.leverage,
        settings.per_trade_amount, signal.stop_loss, signal.tp1,
    )
    if error or not result:
        logger.error("DayTrade live order failed for %s: %s", signal.symbol, error or 'no result')
        return None

    trade = _record_live_trade(signal, settings, result)
    logger.info(
        "DayTrade LIVE opened: %s %s qty=%s @ %s (FuturesTrade %s)",
        signal.direction, signal.symbol, result['quantity'], result['entry_price'], trade.id,
    )
    return trade
