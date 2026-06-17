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
    holdings: list[Holding] = []
    for kind, asset_type in (("stocks", "stock"), ("funds", "fund")):
        for raw_symbol, raw in positions.get(kind, {}).items():
            if not isinstance(raw, dict):
                continue
            symbol = normalize_code(str(raw_symbol), source="profile")
            market = infer_market(symbol, asset_type)
            holdings.append(
                Holding(
                    symbol=symbol,
                    asset_type=asset_type,
                    market=market,
                    quantity=float(raw.get("quantity", 0) or 0),
                    buy_date=str(raw.get("buy_date") or ""),
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
