"""Exact, dependency-free financial calculations for deterministic reports."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def market_cap(price: Any, shares: Any) -> Decimal | None:
    """Return price × shares exactly; missing inputs remain missing."""
    unit_price, share_count = _decimal(price), _decimal(shares)
    return unit_price * share_count if unit_price is not None and share_count is not None else None


def free_cash_flow_yield(free_cash_flow: Any, capitalization: Any) -> Decimal | None:
    cash, cap = _decimal(free_cash_flow), _decimal(capitalization)
    if cash is None or cap is None or cap <= 0:
        return None
    return cash / cap


def scenario_value(base_value: Any, growth: Any, multiple_change: Any = 0) -> Decimal | None:
    """A transparent one-period scenario helper, not a DCF or price target."""
    base, growth_rate, multiple = _decimal(base_value), _decimal(growth), _decimal(multiple_change)
    if base is None or growth_rate is None or multiple is None:
        return None
    return base * (Decimal("1") + growth_rate) * (Decimal("1") + multiple)
