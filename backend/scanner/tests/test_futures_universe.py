"""Unit tests for the futures universe screen.

Covers the pure filtering behaviour of ``screen_futures_symbols`` with the
network fetch (``_load_tickers``) and threshold source (``_thresholds``)
patched, plus the fail-open contract on fetch errors.
"""
from unittest.mock import patch

from scanner.services import futures_universe as fu


TICKERS = [
    {'symbol': 'GOODUSDT', 'quoteVolume': '20000000', 'lastPrice': '100', 'highPrice': '103', 'lowPrice': '99'},
    {'symbol': 'LOWVOLUSDT', 'quoteVolume': '1000000', 'lastPrice': '100', 'highPrice': '103', 'lowPrice': '99'},
    {'symbol': 'FLATUSDT', 'quoteVolume': '50000000', 'lastPrice': '100', 'highPrice': '100.5', 'lowPrice': '99.8'},
    {'symbol': 'WILDUSDT', 'quoteVolume': '50000000', 'lastPrice': '100', 'highPrice': '200', 'lowPrice': '90'},
]

THRESHOLDS = (10_000_000, 2.0, 40.0)


def test_range_pct_basic():
    assert fu._range_pct({'lastPrice': '100', 'highPrice': '110', 'lowPrice': '90'}) == 20.0


def test_range_pct_invalid_returns_none():
    assert fu._range_pct({'lastPrice': '0', 'highPrice': '1', 'lowPrice': '1'}) is None


def test_screen_keeps_only_liquid_in_band():
    wanted = {'GOODUSDT', 'LOWVOLUSDT', 'FLATUSDT', 'WILDUSDT', 'MISSINGUSDT'}
    with patch.object(fu, '_load_tickers', return_value=TICKERS), \
         patch.object(fu, '_thresholds', return_value=THRESHOLDS):
        passing = fu.screen_futures_symbols(wanted)
    assert passing == {'GOODUSDT'}


def test_screen_empty_input():
    assert fu.screen_futures_symbols(set()) == set()


def test_screen_fails_open_on_fetch_error():
    with patch.object(fu, '_load_tickers', side_effect=RuntimeError('boom')):
        assert fu.screen_futures_symbols({'AUSDT', 'BUSDT'}) == {'AUSDT', 'BUSDT'}


def test_screen_fails_open_on_empty_tickers():
    with patch.object(fu, '_load_tickers', return_value=None):
        assert fu.screen_futures_symbols({'AUSDT'}) == {'AUSDT'}
