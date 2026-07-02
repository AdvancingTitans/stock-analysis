from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .market_time import MarketSession
from .models import Holding
from .normalize import normalize_code
from .profile import infer_market, load_holdings_from_profile, save_holdings_to_profile


@dataclass
class HoldingResolution:
    holdings: list[Holding]
    source: str
    missing_by_symbol: dict[str, list[str]]

    @property
    def include_holdings(self) -> bool:
        return bool(self.holdings)


@dataclass
class TradingPlan:
    market: str
    session_label: str
    report_format: str
    mode: str
    holdings: list[Holding]
    holdings_source: str
    include_holdings: bool


class IncompleteHoldingsError(ValueError):
    def __init__(self, missing_by_symbol: dict[str, list[str]]) -> None:
        self.missing_by_symbol = missing_by_symbol
        self.message = _missing_holdings_message(missing_by_symbol)
        super().__init__(self.message)


def parse_user_holdings_json(raw: str) -> list[Holding]:
    """Parse structured holdings supplied by an upper LLM layer or CLI."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("--holdings-json must be valid JSON") from exc
    rows = _holding_rows(payload)
    return [_holding_from_row(row, index) for index, row in enumerate(rows, start=1)]


def resolve_holdings(
    *,
    user_holdings: list[Holding] | None,
    load_memory: Callable[[], list[Holding]] | None = None,
    save_memory: Callable[[list[Holding]], object] | None = None,
) -> HoldingResolution:
    load_memory = load_memory or load_holdings_from_profile
    save_memory = save_memory or save_holdings_to_profile
    if user_holdings is not None:
        missing = _missing_fields_by_symbol(user_holdings)
        if missing:
            raise IncompleteHoldingsError(missing)
        save_memory(user_holdings)
        return HoldingResolution(holdings=user_holdings, source="user", missing_by_symbol={})

    memory_holdings = _complete_holdings(load_memory())
    if memory_holdings:
        return HoldingResolution(holdings=memory_holdings, source="memory", missing_by_symbol={})
    return HoldingResolution(holdings=[], source="none", missing_by_symbol={})


def plan_trading_task(
    *,
    cli_market: str,
    session: MarketSession,
    requested_format: str,
    user_holdings: list[Holding] | None,
    lens: str | None,
    lenses: tuple[str, ...] | None,
    mode: str | None,
) -> TradingPlan:
    market = "a" if cli_market in {"daily", "a", "global"} else cli_market
    report_format = requested_format
    if report_format == "auto":
        report_format = {"light": "summary", "medium": "key-points", "full": "full"}[session.depth]
    resolution = resolve_holdings(user_holdings=user_holdings)
    return TradingPlan(
        market=market,
        session_label=session.label,
        report_format=report_format,
        mode=_resolve_lens_mode(lens=lens, lenses=lenses, mode=mode),
        holdings=resolution.holdings,
        holdings_source=resolution.source,
        include_holdings=resolution.include_holdings,
    )


def _holding_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("holdings"), list):
        rows = payload["holdings"]
    elif isinstance(payload, dict) and isinstance(payload.get("positions"), dict):
        rows = []
        positions = payload["positions"]
        for bucket, asset_type in (("stocks", "stock"), ("funds", "fund")):
            for symbol, value in (positions.get(bucket) or {}).items():
                row = dict(value) if isinstance(value, dict) else {}
                row.setdefault("symbol", symbol)
                row.setdefault("asset_type", asset_type)
                rows.append(row)
    else:
        raise ValueError("--holdings-json must be a list, {'holdings': [...]}, or stock-analysis profile JSON")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("--holdings-json entries must be objects")
    return rows


def _holding_from_row(row: dict[str, Any], index: int) -> Holding:
    raw_symbol = str(row.get("symbol") or row.get("code") or "").strip()
    symbol = normalize_code(raw_symbol, source="user_holding") if raw_symbol else f"<missing:{index}>"
    asset_type = str(row.get("asset_type") or row.get("type") or ("fund" if row.get("market") == "fund" else "stock"))
    market = str(row.get("market") or infer_market(symbol, asset_type))
    buy_price = _optional_float(row.get("buy_price") or row.get("cost_price"))
    quantity = _holding_quantity(row, buy_price)
    return Holding(
        symbol=symbol,
        asset_type=asset_type,
        market=market,
        quantity=quantity,
        buy_date=str(row.get("buy_date") or row.get("date") or ""),
        buy_price=buy_price,
        currency=str(row.get("currency") or "CNY"),
        name=str(row.get("name") or ""),
    )


def _missing_fields_by_symbol(holdings: list[Holding]) -> dict[str, list[str]]:
    missing_by_symbol: dict[str, list[str]] = {}
    for holding in holdings:
        missing = []
        if not holding.symbol or holding.symbol.startswith("<missing:"):
            missing.append("symbol")
        if holding.quantity <= 0:
            missing.append("quantity")
        if not holding.buy_date:
            missing.append("buy_date")
        if missing:
            missing_by_symbol[holding.symbol or "<missing>"] = missing
    return missing_by_symbol


def _complete_holdings(holdings: list[Holding]) -> list[Holding]:
    return [holding for holding in holdings if not _missing_fields_by_symbol([holding])]


def _missing_holdings_message(missing_by_symbol: dict[str, list[str]]) -> str:
    parts = [f"{symbol}: {', '.join(fields)}" for symbol, fields in missing_by_symbol.items()]
    return "持仓信息不完整，请补充后再进行持仓分析：" + "；".join(parts)


def _resolve_lens_mode(
    *,
    lens: str | None,
    lenses: tuple[str, ...] | None,
    mode: str | None,
) -> str:
    if mode:
        return mode
    if lens:
        return "single"
    return "committee"


def _holding_quantity(row: dict[str, Any], buy_price: float | None) -> float:
    quantity = _optional_float(row.get("quantity") or row.get("shares") or row.get("units"))
    if quantity is not None:
        return quantity
    amount = _optional_float(row.get("amount") or row.get("buy_amount"))
    if amount is not None and buy_price is not None:
        return amount / buy_price
    return 0.0


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
