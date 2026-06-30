"""
Monthly balance-based auto-rebalance of futures trading settings.

Formula (per spec):

    per_trade        = balance / 5
    max_concurrent   = 4
    backup_reserve   = balance - (max_concurrent * per_trade)
                     = balance / 5

So if the futures USDT balance is $50:
    per_trade        = $10
    max_concurrent   = 4
    deployable       = $40   (4 x $10)
    backup_reserve   = $10

The divisor (5) is written to ``max_active_gw_trades`` so the engines' sizing
(``per_trade_amount = total_trading_capital / max_active_gw_trades``) yields
balance / 5, while ``max_concurrent_trades`` (4) caps how many trade slots run
at once -- so the 5th unit is never deployed and stays as the reserve.

Only the futures wallet (``/fapi/v2/balance``) is consulted — spot
balance is intentionally ignored. The USDT line item is the source
of truth; cross-wallet PnL and other assets are not added in.

The service is the synchronous boundary between the Celery task,
the manual management command, and any future admin UI button —
each entry point calls ``rebalance_from_futures_balance`` and gets
a summary dict back.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, ROUND_DOWN
from typing import Optional

from signals.models.futures import FuturesTradingSettings, BalanceRebalanceLog

logger = logging.getLogger(__name__)


MAX_CONCURRENT_TRADES = 4
PER_TRADE_DIVISOR = Decimal('5')
MIN_TRADE_AMOUNT = Decimal('1.00')


def _fetch_futures_usdt_balance() -> Optional[Decimal]:
    """
    Pull the USDT line from ``/fapi/v2/balance``. Returns the wallet
    balance for USDT or ``None`` if the call fails or USDT isn't
    listed (e.g. a brand-new sub-account with zero history).
    """
    from signals.services.futures_trader import BinanceFuturesTrader

    async def _go() -> Optional[Decimal]:
        trader = BinanceFuturesTrader(use_testnet=False)
        try:
            rows = await trader.get_account_balance()
        finally:
            await trader.close()

        if not rows:
            return None
        for row in rows:
            if row.get('asset') == 'USDT':
                return Decimal(str(row.get('balance', '0')))
        return None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_go())
    finally:
        loop.close()


def _compute_per_trade(balance: Decimal) -> Decimal:
    """
    Floor balance / 3 to 2 decimals so we never end up with a fractional
    cent value that the Decimal(max_digits=10, decimal_places=2) column
    would silently round.
    """
    return (balance / PER_TRADE_DIVISOR).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN,
    )


def refresh_balance_only() -> dict:
    """
    Pull the live futures USDT balance and update
    ``total_trading_capital`` + ``last_balance_updated_at`` ONLY.

    Per-trade sizing fields (``trade_amount``,
    ``max_concurrent_trades``) are intentionally left untouched —
    those are set by the monthly rebalance and should not move
    intraday on every trade close, otherwise wins/losses compound
    sizing immediately and per-trade risk drifts off-plan.

    Fail-safe: any error returns a summary with ``ok=False`` and
    skips the write. Caller (a post_save signal) should not raise
    on failure.

    Returns:
        ``{ok, balance, previous_balance, reason}``.
    """
    from django.utils import timezone

    out = {
        'ok': False,
        'balance': None,
        'previous_balance': None,
        'reason': '',
    }

    try:
        balance = _fetch_futures_usdt_balance()
    except Exception as exc:
        out['reason'] = f'balance fetch failed: {exc}'
        logger.warning("refresh_balance_only fetch failed: %s", exc)
        return out

    if balance is None:
        out['reason'] = 'no USDT row in futures balance'
        return out

    try:
        settings_obj = FuturesTradingSettings.get_settings()
        out['previous_balance'] = float(settings_obj.total_trading_capital)
        settings_obj.total_trading_capital = balance
        settings_obj.last_balance_updated_at = timezone.now()
        settings_obj.save(update_fields=[
            'total_trading_capital', 'last_balance_updated_at',
        ])
    except Exception as exc:
        out['reason'] = f'settings write failed: {exc}'
        logger.warning("refresh_balance_only write failed: %s", exc)
        return out

    out['ok'] = True
    out['balance'] = float(balance)
    out['reason'] = 'balance refreshed'
    logger.info(
        "Balance refreshed from %.2f -> %.2f",
        out['previous_balance'], out['balance'],
    )
    return out


def _record_log(summary: dict, dry_run: bool) -> None:
    """
    Persist a BalanceRebalanceLog row for the run.

    Dry-runs are recorded too — the history is meant to capture every
    attempt (including failures), not just successful writes. A logging
    failure must not bubble up and break the actual rebalance.
    """
    try:
        BalanceRebalanceLog.objects.create(
            balance=Decimal(str(summary['balance'])) if summary['balance'] is not None else None,
            per_trade_amount=(
                Decimal(str(summary['per_trade'])) if summary['per_trade'] is not None else None
            ),
            max_concurrent_trades=(
                summary['max_concurrent'] if summary['applied'] else None
            ),
            backup_reserve=(
                Decimal(str(summary['backup_reserve']))
                if summary['backup_reserve'] is not None else None
            ),
            previous_trade_amount=(
                Decimal(str(summary['previous']['trade_amount']))
                if summary.get('previous') else None
            ),
            previous_max_concurrent_trades=(
                summary['previous']['max_concurrent_trades']
                if summary.get('previous') else None
            ),
            applied=summary['applied'],
            reason=summary['reason'][:255],
        )
    except Exception as exc:
        logger.warning("Failed to persist BalanceRebalanceLog row: %s", exc)


def rebalance_from_futures_balance(dry_run: bool = False) -> dict:
    """
    Fetch the live futures USDT balance and write back the per-trade
    amount and max-concurrent-trades values to FuturesTradingSettings.

    Every run (success, dry-run, or failure) writes one
    BalanceRebalanceLog row so the history is auditable.

    Args:
        dry_run: If True, compute the new values but don't persist
            FuturesTradingSettings. The log row is still written.

    Returns:
        Summary dict with keys: ok, balance, per_trade, max_concurrent,
        backup_reserve, previous, applied, reason.
    """
    summary: dict = {
        'ok': False,
        'balance': None,
        'per_trade': None,
        'max_concurrent': MAX_CONCURRENT_TRADES,
        'backup_reserve': None,
        'previous': None,
        'applied': False,
        'reason': '',
    }

    try:
        balance = _fetch_futures_usdt_balance()
    except Exception as exc:
        summary['reason'] = f'balance fetch failed: {exc}'
        logger.warning("Balance fetch failed: %s", exc)
        _record_log(summary, dry_run)
        return summary

    if balance is None:
        summary['reason'] = 'no USDT row in futures balance'
        logger.warning("No USDT entry in futures balance response")
        _record_log(summary, dry_run)
        return summary

    summary['balance'] = float(balance)
    per_trade = _compute_per_trade(balance)

    if per_trade < MIN_TRADE_AMOUNT:
        summary['reason'] = (
            f'computed per-trade ${per_trade} is below '
            f'minimum ${MIN_TRADE_AMOUNT}; not rebalancing'
        )
        summary['per_trade'] = float(per_trade)
        logger.warning(summary['reason'])
        _record_log(summary, dry_run)
        return summary

    backup_reserve = balance - (per_trade * MAX_CONCURRENT_TRADES)
    summary['per_trade'] = float(per_trade)
    summary['backup_reserve'] = float(backup_reserve)

    settings_obj = FuturesTradingSettings.get_settings()
    summary['previous'] = {
        'trade_amount': float(settings_obj.trade_amount),
        'max_concurrent_trades': settings_obj.max_concurrent_trades,
    }

    if dry_run:
        summary['ok'] = True
        summary['reason'] = 'dry-run; no write'
        _record_log(summary, dry_run)
        return summary

    from django.utils import timezone
    settings_obj.trade_amount = per_trade
    settings_obj.max_concurrent_trades = MAX_CONCURRENT_TRADES
    settings_obj.max_active_gw_trades = int(PER_TRADE_DIVISOR)
    settings_obj.total_trading_capital = balance
    settings_obj.last_balance_updated_at = timezone.now()
    settings_obj.save(update_fields=[
        'trade_amount', 'max_concurrent_trades', 'max_active_gw_trades',
        'total_trading_capital', 'last_balance_updated_at',
    ])

    summary['ok'] = True
    summary['applied'] = True
    summary['reason'] = 'rebalanced'
    logger.info(
        "Rebalanced from futures balance: balance=%.2f per_trade=%.2f "
        "max_concurrent=%d backup=%.2f (was trade=%.2f, max=%d)",
        balance, per_trade, MAX_CONCURRENT_TRADES, backup_reserve,
        summary['previous']['trade_amount'],
        summary['previous']['max_concurrent_trades'],
    )
    _record_log(summary, dry_run)
    return summary
