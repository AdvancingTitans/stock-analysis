from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from typing import Any

import requests

from . import market_core
from .models import QuoteData
from .normalize import normalize_code

A_INDEX_HISTORY = {
    "sh000001": ("000001", "上证指数"),
    "sz399001": ("399001", "深证成指"),
    "sz399006": ("399006", "创业板指"),
    "sh000300": ("000300", "沪深300"),
}
HK_INDEX_HISTORY = {
    "hkHSI": ("^HSI", "恒生指数"),
    "hkHSCEI": ("^HSCE", "国企指数"),
    "hkHSTECH": ("HSTECH.HK", "恒生科技指数"),
}
US_INDEX_HISTORY = {
    ".INX": ("^GSPC", "标普500"),
    ".IXIC": ("^IXIC", "纳斯达克"),
    ".DJI": ("^DJI", "道琼斯"),
}


def _direct_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def is_historical_date(trade_date: str) -> bool:
    return trade_date < datetime.now().strftime("%Y%m%d")


def _valid_index_row(row: dict[str, Any]) -> bool:
    try:
        price = float(row.get("f2"))
    except (TypeError, ValueError):
        return False
    change = row.get("f4")
    change_pct = row.get("f3")
    if price <= 0:
        return False
    return not (change in (None, 0, 0.0) and change_pct in (None, 0, 0.0))


def _tencent_history(code: str, trade_date: str, limit: int = 60) -> tuple[list[list[Any]], dict[str, Any]]:
    iso_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    response = _direct_session().get(
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        params={"param": f"{code},day,,{iso_date},{limit},qfq"},
        headers={"Referer": "https://gu.qq.com/", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    payload = (response.json().get("data") or {}).get(code) or {}
    rows = payload.get("qfqday") or payload.get("day") or []
    return rows, payload


def _quote_from_history_rows(
    rows: list[list[Any]],
    *,
    symbol: str,
    name: str,
    market: str,
    currency: str,
    trade_date: str,
    source: str,
    turnover_from_last: bool = False,
) -> QuoteData | None:
    target = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    eligible = [row for row in rows if row and str(row[0]) <= target]
    if not eligible or str(eligible[-1][0]) != target:
        return None
    last = eligible[-1]
    previous_close = float(eligible[-2][2]) if len(eligible) >= 2 else None
    price = float(last[2])
    change = price - previous_close if previous_close not in (None, 0) else None
    change_pct = change / previous_close * 100 if change is not None and previous_close else None
    return QuoteData(
        symbol=symbol,
        name=name,
        market=market,
        price=price,
        previous_close=previous_close,
        change=change,
        change_pct=change_pct,
        open_price=float(last[1]),
        high=float(last[3]),
        low=float(last[4]),
        volume=None if turnover_from_last else float(last[5]),
        turnover=float(last[5]) if turnover_from_last else None,
        currency=currency,
        trade_date=trade_date,
        source=source,
        source_chain=[source],
    )


def _fetch_tencent_historical_quote(
    code: str,
    *,
    symbol: str,
    name: str,
    market: str,
    currency: str,
    trade_date: str,
    turnover_from_last: bool = False,
) -> QuoteData | None:
    try:
        rows, payload = _tencent_history(code, trade_date)
    except Exception:
        return None
    current_name = ((payload.get("qt") or {}).get(code) or [None, None])[1]
    return _quote_from_history_rows(
        rows,
        symbol=symbol,
        name=str(current_name or name),
        market=market,
        currency=currency,
        trade_date=trade_date,
        source="tencent-kline",
        turnover_from_last=turnover_from_last,
    )


def _fetch_sina_us_history(symbol: str, trade_date: str) -> QuoteData | None:
    response = _direct_session().get(
        "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var/US_MinKService.getDailyK",
        params={"symbol": symbol, "num": 90},
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    match = re.search(r"var\((\[.*\])\);?", response.text, re.DOTALL)
    if not match:
        return None
    rows = json.loads(match.group(1))
    target = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    eligible = [row for row in rows if row.get("d") and row["d"] <= target]
    if not eligible or eligible[-1]["d"] != target:
        return None
    last = eligible[-1]
    previous_close = float(eligible[-2]["c"]) if len(eligible) >= 2 else None
    price = float(last["c"])
    change = price - previous_close if previous_close not in (None, 0) else None
    change_pct = change / previous_close * 100 if change is not None and previous_close else None
    return QuoteData(
        symbol=symbol,
        market="us",
        price=price,
        previous_close=previous_close,
        change=change,
        change_pct=change_pct,
        open_price=float(last["o"]),
        high=float(last["h"]),
        low=float(last["l"]),
        volume=float(last["v"]) if last.get("v") else None,
        currency="USD",
        trade_date=trade_date,
        source="sina-kline",
        source_chain=["sina-kline"],
    )


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
        symbol=normalize_code(str(data.get("symbol") or ""), source=str(data.get("source") or "generic")),
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
        source_chain=list(data.get("source_chain") or []),
        fallback_reason=data.get("fallback_reason"),
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
    if is_historical_date(trade_date):
        normalized = normalize_code(symbol)
        if normalized.endswith(".HK"):
            raw = normalized.replace(".HK", "").lstrip("0") or "0"
            return _fetch_tencent_historical_quote(
                f"hk{raw.zfill(5)}",
                symbol=normalized,
                name=normalized,
                market="hk",
                currency="HKD",
                trade_date=trade_date,
            )
        if normalized.isdigit():
            prefix = "sh" if normalized.startswith(("5", "6", "9")) else "bj" if normalized.startswith(("4", "8")) else "sz"
            return _fetch_tencent_historical_quote(
                f"{prefix}{normalized}",
                symbol=normalized,
                name=normalized,
                market="a",
                currency="CNY",
                trade_date=trade_date,
            )
        return _fetch_sina_us_history(normalized, trade_date)
    core = market_core
    return adapt_quote(core.get_single_stock_quote(symbol, trade_date))


def fetch_a_indices(trade_date: str) -> list[dict[str, Any]]:
    if is_historical_date(trade_date):
        result = []
        for code, (symbol, name) in A_INDEX_HISTORY.items():
            quote = _fetch_tencent_historical_quote(
                code,
                symbol=symbol,
                name=name,
                market="a",
                currency="CNY",
                trade_date=trade_date,
            )
            if quote:
                result.append(
                    {
                        "f12": quote.symbol,
                        "f14": quote.name,
                        "f2": quote.price,
                        "f4": quote.change,
                        "f3": quote.change_pct,
                        "f6": quote.turnover,
                        "_source": quote.source,
                        "_source_date": trade_date,
                    }
                )
        return result
    core = market_core
    rows = core._fetch_a_indices_tencent()
    source = "tencent"
    if not all(_valid_index_row(row) for row in rows) or len(rows) < 4:
        rows = core._fetch_a_indices_sina()
        source = "sina"
    if not all(_valid_index_row(row) for row in rows) or len(rows) < 4:
        rows = core.get_index(trade_date)
        source = "eastmoney"
    valid_rows = [row for row in rows if _valid_index_row(row)]
    for row in valid_rows:
        row["_source"] = source
    return valid_rows


def fetch_hk_indices(trade_date: str) -> list[QuoteData]:
    if is_historical_date(trade_date):
        return [
            quote
            for code, (symbol, name) in HK_INDEX_HISTORY.items()
            if (
                quote := _fetch_tencent_historical_quote(
                    code,
                    symbol=symbol,
                    name=name,
                    market="hk",
                    currency="HKD",
                    trade_date=trade_date,
                    turnover_from_last=True,
                )
            )
        ]
    core = market_core
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
    if is_historical_date(trade_date):
        rows = []
        for code, (symbol, name) in US_INDEX_HISTORY.items():
            quote = _fetch_sina_us_history(code, trade_date)
            if quote:
                quote.symbol = symbol
                quote.name = name
                rows.append(quote)
        return rows
    core = market_core
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
    if is_historical_date(trade_date):
        return {
            "board_type": board_type,
            "rows": [],
            "_unavailable": "板块榜接口不支持历史日期，已禁止混用实时数据",
        }
    core = market_core
    result = core.fetch_eastmoney_board_list(board_type, trade_date, limit=limit)
    if not result.get("rows"):
        result = core.camofox_board_list(board_type)
        if result.get("rows"):
            result["_fallback"] = "API 失败，已启用浏览器降级抓取"
    return result


def fetch_fund_flow(trade_date: str) -> dict[str, Any]:
    return market_core.get_fund_flow(trade_date, strict_date=True)


def fetch_northbound_flow(trade_date: str) -> dict[str, Any]:
    result = market_core.fetch_northbound_flow_snapshot(trade_date)
    source_date = str(result.get("date") or "").replace("-", "")
    latest_time = str(result.get("latest_time") or "")
    points = int(result.get("points") or 0)
    if source_date != trade_date:
        return {"date": trade_date, "_unavailable": "北向资金日期不匹配"}
    if is_historical_date(trade_date) and (latest_time < "14:55" or points < 100):
        return {"date": trade_date, "_unavailable": "北向资金历史序列不完整"}
    return result


def fetch_limit_pools(trade_date: str) -> dict[str, Any]:
    core = market_core
    return {
        "zt": core.get_zt_pool(trade_date),
        "dt": core.get_dt_pool(trade_date),
        "zb": core.get_zb_pool(trade_date),
    }


def fetch_fund_estimate(code: str, trade_date: str) -> dict[str, Any]:
    return market_core.fetch_fund_estimate(code, trade_date)


def fetch_fund_holdings(code: str, trade_date: str, limit: int = 10) -> dict[str, Any]:
    return market_core.fetch_fund_holdings(code, trade_date, limit=limit)


def fetch_fund_holding_quotes(holdings: list[dict[str, Any]], trade_date: str) -> dict[str, QuoteData]:
    core = market_core
    raw = core.fetch_fund_holding_quotes(holdings, trade_date)
    return {symbol: adapt_quote(q) for symbol, q in raw.items() if adapt_quote(q)}


def fetch_stock_buy_reference(symbol: str, buy_date: str) -> dict[str, Any]:
    return market_core.fetch_stock_close_on_or_after(symbol, buy_date)


def fetch_fund_buy_reference(code: str, buy_date: str) -> dict[str, Any]:
    return market_core.fetch_fund_nav_on_or_after(code, buy_date)
