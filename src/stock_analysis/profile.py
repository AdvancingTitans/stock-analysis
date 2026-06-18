from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Holding
from .normalize import normalize_code


def profile_path() -> Path:
    override = os.environ.get("YOUNG_STOCK_PROFILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".young_stock" / "profile.json"


def load_holdings_from_profile() -> list[Holding]:
    path = profile_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    positions = data.get("positions", {})
    legacy_buy_prices = data.get("buy_price", {})
    holdings: list[Holding] = []
    for kind, asset_type in (("stocks", "stock"), ("funds", "fund")):
        for raw_symbol, raw in positions.get(kind, {}).items():
            if not isinstance(raw, dict):
                continue
            symbol = normalize_code(str(raw_symbol), source="profile")
            market = infer_market(symbol, asset_type)
            buy_price = raw.get("buy_price")
            if buy_price is None and isinstance(legacy_buy_prices, dict):
                buy_price = legacy_buy_prices.get(raw_symbol, legacy_buy_prices.get(symbol))
            holdings.append(
                Holding(
                    symbol=symbol,
                    asset_type=asset_type,
                    market=market,
                    quantity=float(raw.get("quantity", 0) or 0),
                    buy_date=str(raw.get("buy_date") or ""),
                    buy_price=_optional_float(buy_price),
                )
            )
    return holdings


def infer_market(symbol: str, asset_type: str) -> str:
    if asset_type == "fund":
        return "fund"
    if symbol.endswith(".HK"):
        return "hk"
    if symbol.isdigit():
        return "a"
    return "us"


def _optional_float(value: object) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
