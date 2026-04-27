"""
Validate a UserBinanceConnection by hitting GET /fapi/v2/account.

This is the only place we exercise a user-supplied key in slice 1.
Trading fan-out is intentionally deferred. The validator returns a
small structured result keyed off Binance error codes / HTTP statuses
so the UI and the health-check task can render specific, actionable
messages without re-parsing Binance text strings.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone as dj_timezone

from .credential_crypto import decrypt
from .futures_trader import BinanceFuturesTrader
from ..models_user_connection import UserBinanceConnection

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    ok: bool
    code: str             # 'healthy' | 'withdraw_enabled' | 'invalid_key' | 'bad_secret' | 'ip_blocked' | 'no_futures' | 'unknown'
    message: str          # short, user-facing (already localised-ready)
    permissions: dict     # {'canTrade': bool, 'canWithdraw': bool, ...} as reported by Binance, empty on hard failures


def _classify_binance_error(exc: Exception) -> ValidationResult:
    """
    Map a Binance API error string to a stable ValidationResult code.

    Binance error format: ``Binance API error: <msg>`` from ``_request``.
    We match on the message body / known error codes rather than HTTP
    status because the trader wraps everything in a single Exception.
    """
    text = str(exc).lower()

    if '-2014' in text or 'api-key format invalid' in text or 'invalid api-key' in text or 'api key' in text and 'invalid' in text:
        return ValidationResult(False, 'invalid_key',
                                'API key is invalid or has been revoked. Re-create it on Binance and reconnect.',
                                {})
    if '-2015' in text or 'invalid signature' in text or 'rejected mbx ip' in text:
        # -2015 covers both bad secret AND IP not whitelisted; the message text disambiguates.
        if 'ip' in text:
            return ValidationResult(False, 'ip_blocked',
                                    'Your Binance API key does not allow our server IP. Add it to the IP allowlist and try again.',
                                    {})
        return ValidationResult(False, 'bad_secret',
                                'API secret is wrong. Re-paste both key and secret carefully — secret is shown only once on Binance.',
                                {})
    if '-2008' in text or 'invalid api-key, ip' in text:
        return ValidationResult(False, 'ip_blocked',
                                'Your Binance API key does not allow our server IP. Add it to the IP allowlist and try again.',
                                {})
    if 'futures' in text and ('not enabled' in text or 'permission' in text):
        return ValidationResult(False, 'no_futures',
                                'Futures trading is not enabled on this API key. Enable Futures permission on Binance and reconnect.',
                                {})
    return ValidationResult(False, 'unknown',
                            f'Unexpected Binance response: {exc}',
                            {})


def _interpret_account_response(payload: dict) -> ValidationResult:
    """Account fetch succeeded — extract permissions and judge the result."""
    permissions = {
        'canTrade': bool(payload.get('canTrade', False)),
        'canDeposit': bool(payload.get('canDeposit', False)),
        'canWithdraw': bool(payload.get('canWithdraw', False)),
        'totalWalletBalance': str(payload.get('totalWalletBalance', '0')),
    }
    if not permissions['canTrade']:
        return ValidationResult(False, 'no_futures',
                                'API key has no trading permission. Enable Futures trading on the key and reconnect.',
                                permissions)
    if permissions['canWithdraw']:
        return ValidationResult(True, 'withdraw_enabled',
                                'Connected, but withdrawals are enabled on this key. We strongly recommend revoking and re-creating it with withdrawals disabled.',
                                permissions)
    return ValidationResult(True, 'healthy',
                            'Your Binance account is connected.',
                            permissions)


def _run_async(coro):
    """Run an async coroutine from sync code on its own loop in a thread.

    Django views are sync; the trader is async. We deliberately do not use
    asgiref.sync.async_to_sync here because the trader uses aiohttp which
    binds to the event loop in its constructor, and we want a clean loop
    per call.
    """
    container = {'res': None, 'err': None}

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            container['res'] = loop.run_until_complete(coro)
        except Exception as exc:
            container['err'] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=30)

    if container['err']:
        raise container['err']
    return container['res']


async def _fetch_account(api_key: str, api_secret: str) -> dict:
    trader = BinanceFuturesTrader(api_key=api_key, api_secret=api_secret)
    try:
        return await trader._request('GET', '/fapi/v2/account', signed=True)
    finally:
        await trader.close()


def validate_connection(connection: UserBinanceConnection) -> ValidationResult:
    """
    Hit Binance with the connection's credentials, return structured result,
    persist the resulting status/permissions/last_check_at on the row.
    """
    try:
        api_key = decrypt(connection.api_key_enc)
        api_secret = decrypt(connection.api_secret_enc)
    except Exception as exc:
        logger.exception("Failed to decrypt connection %s", connection.pk)
        result = ValidationResult(False, 'unknown',
                                  'Stored credentials could not be decrypted; please reconnect.',
                                  {})
        _persist(connection, result, target_status_on_ok=connection.status)
        return result

    try:
        payload = _run_async(_fetch_account(api_key, api_secret))
        result = _interpret_account_response(payload)
    except Exception as exc:
        result = _classify_binance_error(exc)

    _persist(connection, result, target_status_on_ok=connection.status)
    return result


def _persist(connection: UserBinanceConnection, result: ValidationResult,
             target_status_on_ok: str) -> None:
    """
    Apply the validation result to the row.

    On failure the row is moved to BROKEN/REVOKED so the UI / next
    health-check cycle can pick it up. On success we keep whatever the
    user's intended status was (PAUSED on first connect, ACTIVE if they
    later enabled trading via slice 2 — slice 1 always lands at PAUSED).
    """
    connection.last_check_at = dj_timezone.now()
    connection.permissions = result.permissions
    connection.last_error = '' if result.ok else f'{result.code}: {result.message}'

    if result.ok:
        connection.ip_check_passed = True
        if connection.status in (UserBinanceConnection.STATUS_BROKEN,
                                  UserBinanceConnection.STATUS_REVOKED):
            connection.status = UserBinanceConnection.STATUS_PAUSED
        else:
            connection.status = target_status_on_ok or UserBinanceConnection.STATUS_PAUSED
    elif result.code == 'invalid_key':
        connection.status = UserBinanceConnection.STATUS_REVOKED
        connection.ip_check_passed = False
    else:
        connection.status = UserBinanceConnection.STATUS_BROKEN
        if result.code == 'ip_blocked':
            connection.ip_check_passed = False

    connection.save(update_fields=[
        'status', 'permissions', 'ip_check_passed',
        'last_check_at', 'last_error', 'updated_at',
    ])
