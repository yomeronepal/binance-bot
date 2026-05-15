"""
Classify a Binance symbol as CRYPTO, STOCK, or COMMODITY.

Source of truth ordering:

1. ``contract_type`` from Binance ``/fapi/v1/exchangeInfo`` when
   available. ``'PERPETUAL'`` is always CRYPTO; ``'TRADIFI_PERPETUAL'``
   is the tokenized-traditional-finance lane (US equities + commodity
   ETFs/futures) that needs the further split below.

2. If contract_type is unknown (None / spot / legacy data), fall back to
   matching against ``COMMODITY_TICKERS``. Anything still unmatched
   defaults to CRYPTO — the bot's universe is mostly crypto, so a
   conservative default keeps existing reporting stable.

Pure function: no DB access, safe to call from migrations, Celery
tasks, and management commands.
"""
from __future__ import annotations

from typing import Optional


CRYPTO = 'CRYPTO'
STOCK = 'STOCK'
COMMODITY = 'COMMODITY'

ASSET_CLASS_CHOICES = [
    (CRYPTO, 'Crypto'),
    (STOCK, 'Stock'),
    (COMMODITY, 'Commodity'),
]

BINANCE_CRYPTO_CONTRACT_TYPES = {'PERPETUAL'}
BINANCE_TRADIFI_CONTRACT_TYPES = {'TRADIFI_PERPETUAL'}


COMMODITY_TICKERS = {
    'XAU', 'XAG', 'XPT', 'XPD',
    'GOLD', 'SILVER', 'PLATINUM', 'PALLADIUM',
    'GLD', 'SLV', 'IAU', 'PPLT', 'PALL',
    'GC', 'SI', 'PL', 'PA',

    'CL', 'WTI', 'BZ', 'BRENTOIL', 'BRENT',
    'NG', 'NATGAS',
    'RB', 'HO',
    'USO', 'UNG', 'BNO', 'XLE',

    'HG', 'COPPER', 'ALU', 'ALUMINUM', 'ZINC', 'NI', 'NICKEL',
    'LIT', 'COP',

    'WHEAT', 'CORN', 'SOYBEAN', 'SUGAR', 'COFFEE', 'COTTON',
    'ZW', 'ZC', 'ZS', 'SB', 'KC', 'CT', 'CC',
    'DBA', 'DBC', 'CORN_ETF',
}


def _strip_quote_currency(symbol: str) -> str:
    """
    Strip the common USDT/USDC/BUSD quote suffix so 'GLDUSDT' -> 'GLD'.
    Returns the bare base ticker upper-cased; leaves symbol untouched if
    no known quote is found.
    """
    s = (symbol or '').upper().strip()
    for quote in ('USDT', 'USDC', 'BUSD', 'FDUSD', 'TUSD'):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)]
    return s


def classify_symbol(
    symbol: str,
    contract_type: Optional[str] = None,
) -> str:
    """
    Return one of ``CRYPTO``, ``STOCK``, ``COMMODITY``.

    Args:
        symbol: Trading-pair string (e.g. 'BTCUSDT', 'NVDAUSDT', 'GLDUSDT').
        contract_type: Optional Binance ``contractType`` ('PERPETUAL' or
            'TRADIFI_PERPETUAL'). Pass it when available — it's the
            most reliable signal.

    Returns:
        Asset-class string.
    """
    ct = (contract_type or '').upper().strip() or None
    base = _strip_quote_currency(symbol)

    if ct in BINANCE_CRYPTO_CONTRACT_TYPES:
        return CRYPTO

    if ct in BINANCE_TRADIFI_CONTRACT_TYPES:
        return COMMODITY if base in COMMODITY_TICKERS else STOCK

    if base in COMMODITY_TICKERS:
        return COMMODITY

    return CRYPTO
