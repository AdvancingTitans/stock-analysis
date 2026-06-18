from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..config import SourceConfig
from ..normalize import normalize_code

MOOTDX_CATEGORIES = {
    "deep_kline": 4,
    "minute_kline": 7,
}


def fetch_mootdx_specialized(
    symbol: str,
    request_type: str,
    *,
    config: SourceConfig,
    trade_date: str,
    offset: int = 120,
) -> dict[str, Any]:
    normalized = normalize_code(symbol, source="mootdx")
    if request_type not in {"order_book", "transactions", "minute_kline", "deep_kline", "extended_quote"}:
        raise ValueError(f"unsupported mootdx request type: {request_type}")
    if not config.enable_mootdx:
        return _quote_fallback(normalized, trade_date, "mootdx 默认禁用")

    try:
        from mootdx.quotes import Quotes  # type: ignore

        client = Quotes.factory(market="std")
        if request_type in {"order_book", "extended_quote"}:
            payload = client.quotes(symbol=[normalized])
        elif request_type == "transactions":
            payload = client.transaction(symbol=normalized, date=trade_date)
        else:
            payload = client.bars(
                symbol=normalized,
                category=MOOTDX_CATEGORIES[request_type],
                offset=offset,
            )
        if payload is None or getattr(payload, "empty", False):
            return _quote_fallback(normalized, trade_date, "mootdx 返回空数据")
        records = payload.to_dict(orient="records") if hasattr(payload, "to_dict") else payload
        return {
            "status": "ok",
            "source": "mootdx",
            "symbol": normalized,
            "request_type": request_type,
            "trade_date": trade_date,
            "data": records,
        }
    except Exception as exc:
        return _quote_fallback(normalized, trade_date, f"mootdx 调用失败: {exc}")


def _quote_fallback(symbol: str, trade_date: str, reason: str) -> dict[str, Any]:
    from ..integrations import fetch_single_quote

    quote = fetch_single_quote(symbol, trade_date)
    return {
        "status": "fallback" if quote else "unavailable",
        "source": quote.source if quote else "",
        "symbol": symbol,
        "request_type": "basic_quote",
        "trade_date": trade_date,
        "fallback_reason": reason,
        "data": asdict(quote) if quote else None,
    }
