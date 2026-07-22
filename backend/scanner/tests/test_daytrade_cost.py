"""Unit tests for the day-trade paper-executor cost model."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from scanner.tasks.daytrade_executor import _trade_cost


ENTRY_TIME = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def _trade():
    return SimpleNamespace(
        quantity=Decimal("10"),
        entry_price=Decimal("100"),
        entry_time=ENTRY_TIME,
    )


def test_cost_fees_and_slippage_no_funding():
    # entry+exit notional = 1000 + 1000 = 2000; (0.0004 + 0.0002) * 2000 = 1.20
    cost = _trade_cost(_trade(), Decimal("100"), ENTRY_TIME)
    assert cost == Decimal("1.2000")


def test_cost_adds_one_funding_interval_after_8h():
    # +9h -> 1 funding interval: entry_notional 1000 * 0.0001 = 0.10 on top of 1.20
    cost = _trade_cost(_trade(), Decimal("100"), ENTRY_TIME + timedelta(hours=9))
    assert cost == Decimal("1.3000")


def test_cost_no_funding_before_8h():
    cost = _trade_cost(_trade(), Decimal("100"), ENTRY_TIME + timedelta(hours=7))
    assert cost == Decimal("1.2000")


def test_cost_scales_with_exit_price():
    # exit at 110 -> exit_notional 1100; turnover 2100; * 0.0006 = 1.26
    cost = _trade_cost(_trade(), Decimal("110"), ENTRY_TIME)
    assert cost == Decimal("1.2600")
