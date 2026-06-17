from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuoteData:
    symbol: str
    name: str = ""
    market: str = ""
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    previous_close: float | None = None
    open_price: float | None = None
    volume: float | None = None
    turnover: float | None = None
    turnover_rate: float | None = None
    pe: float | None = None
    pb: float | None = None
    total_market_cap: float | None = None
    float_market_cap: float | None = None
    high: float | None = None
    low: float | None = None
    currency: str = "CNY"
    trade_date: str = ""
    source: str = ""
    source_chain: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    quality_flags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Holding:
    symbol: str
    asset_type: str
    market: str
    quantity: float
    buy_date: str
    buy_price: float | None = None
    currency: str = "CNY"
    name: str = ""


@dataclass
class HoldingValidation:
    holding: Holding
    quote: QuoteData
    status: str
    note: str = ""
