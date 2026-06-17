from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import QuoteData


def load_young_core():
    try:
        from young_stock import _core  # type: ignore
    except ModuleNotFoundError:
        import sys
        from pathlib import Path

        candidate = Path("/Users/yjw/agent/young-stock-cli/src")
        if candidate.exists():
            sys.path.insert(0, str(candidate))
        from young_stock import _core  # type: ignore

    return _core


def adapt_quote(raw: Any) -> QuoteData | None:
    if raw is None:
        return None
    if isinstance(raw, QuoteData):
        return raw
    data = asdict(raw) if hasattr(raw, "__dataclass_fields__") else dict(raw)
    market = {
        "cn_market": "a",
        "hk_market": "hk",
        "us_market": "us",
    }.get(data.get("market", ""), data.get("market", ""))
    return QuoteData(
        symbol=str(data.get("symbol") or ""),
        name=str(data.get("name") or ""),
        market=market,
        price=data.get("price"),
        change=data.get("change"),
        change_pct=data.get("change_pct"),
        previous_close=data.get("prev_close"),
        open_price=data.get("open_price"),
        volume=data.get("volume"),
        turnover=data.get("turnover"),
        turnover_rate=data.get("turnover_rate"),
        total_market_cap=data.get("market_cap"),
        float_market_cap=data.get("float_market_cap"),
        pe=data.get("pe"),
        pb=data.get("pb"),
        high=data.get("high"),
        low=data.get("low"),
        currency=data.get("currency") or "CNY",
        trade_date=str(data.get("date") or ""),
        source=str(data.get("source") or ""),
        quality_flags=list(data.get("quality_flags") or []),
        extra={
            "high_52w": data.get("high_52w"),
            "low_52w": data.get("low_52w"),
            "amplitude_pct": data.get("amplitude_pct"),
            "notes": list(data.get("notes") or []),
            "completeness": data.get("completeness"),
        },
    )


def fetch_single_quote(symbol: str, trade_date: str) -> QuoteData | None:
    core = load_young_core()
    return adapt_quote(core.get_single_stock_quote(symbol, trade_date))


def fetch_a_indices(trade_date: str) -> list[dict[str, Any]]:
    core = load_young_core()
    return core.get_index(trade_date)


def fetch_hk_indices(trade_date: str) -> list[QuoteData]:
    core = load_young_core()
    mapping = {
        "^HSI": "恒生指数",
        "^HSCE": "国企指数",
        "HSTECH.HK": "恒生科技指数",
    }
    order = list(mapping)
    rows = core.fetch_hk_indices_tencent(mapping, trade_date)
    if not core._has_all_quotes(rows, order):
        rows = core.merge_quotes_by_symbol(rows, core.fetch_hk_indices_sina(mapping, trade_date), order)
    if not core._has_all_quotes(rows, order):
        rows = core.merge_quotes_by_symbol(rows, core.fetch_indices_direct(mapping, trade_date, core.EM_HK_INDEX_SECID), order)
    return [adapt_quote(row) for row in rows if adapt_quote(row)]


def fetch_us_indices(trade_date: str) -> list[QuoteData]:
    core = load_young_core()
    mapping = {
        "^GSPC": "标普500",
        "^IXIC": "纳斯达克",
        "^DJI": "道琼斯",
    }
    order = list(mapping)
    rows = core.fetch_us_indices_sina(mapping, trade_date)
    if not core._has_all_quotes(rows, order):
        rows = core.merge_quotes_by_symbol(rows, core.fetch_us_indices_tencent(mapping, trade_date), order)
    if not core._has_all_quotes(rows, order):
        rows = core.merge_quotes_by_symbol(rows, core.fetch_indices_direct(mapping, trade_date, core.EM_US_INDEX_SECID), order)
    return [adapt_quote(row) for row in rows if adapt_quote(row)]


def fetch_board_list(board_type: str, trade_date: str, limit: int = 20) -> dict[str, Any]:
    core = load_young_core()
    result = core.fetch_eastmoney_board_list(board_type, trade_date, limit=limit)
    if not result.get("rows"):
        result = core.camofox_board_list(board_type)
        if result.get("rows"):
            result["_fallback"] = "API 失败，已启用浏览器降级抓取"
    return result


def fetch_fund_flow(trade_date: str) -> dict[str, Any]:
    return load_young_core().get_fund_flow(trade_date, strict_date=False)


def fetch_northbound_flow(trade_date: str) -> dict[str, Any]:
    return load_young_core().fetch_northbound_flow_snapshot(trade_date)


def fetch_limit_pools(trade_date: str) -> dict[str, Any]:
    core = load_young_core()
    return {
        "zt": core.get_zt_pool(trade_date),
        "dt": core.get_dt_pool(trade_date),
        "zb": core.get_zb_pool(trade_date),
    }


def fetch_fund_estimate(code: str, trade_date: str) -> dict[str, Any]:
    return load_young_core().fetch_fund_estimate(code, trade_date)


def fetch_fund_holdings(code: str, trade_date: str, limit: int = 10) -> dict[str, Any]:
    return load_young_core().fetch_fund_holdings(code, trade_date, limit=limit)


def fetch_fund_holding_quotes(holdings: list[dict[str, Any]], trade_date: str) -> dict[str, QuoteData]:
    core = load_young_core()
    raw = core.fetch_fund_holding_quotes(holdings, trade_date)
    return {symbol: adapt_quote(q) for symbol, q in raw.items() if adapt_quote(q)}


def fetch_stock_buy_reference(symbol: str, buy_date: str) -> dict[str, Any]:
    return load_young_core().fetch_stock_close_on_or_after(symbol, buy_date)


def fetch_fund_buy_reference(code: str, buy_date: str) -> dict[str, Any]:
    return load_young_core().fetch_fund_nav_on_or_after(code, buy_date)
