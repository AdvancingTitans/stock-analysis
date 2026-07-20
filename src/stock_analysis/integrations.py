from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any

import requests

from . import market_core
from .global_markets import (
    detect_jp_kr_market,
    detect_public_global_market,
    fetch_jp_kr_financials,
    fetch_jp_kr_quote,
    fetch_naver_history,
    fetch_tdnet_disclosures,
    fetch_yahoo_history,
)
from .models import QuoteData
from .normalize import normalize_code
from .time_series import build_price_series_pack

A_INDEX_HISTORY = {
    "sh000001": ("000001", "上证指数"),
    "sz399001": ("399001", "深证成指"),
    "sz399006": ("399006", "创业板指"),
    "sh000300": ("000300", "沪深300"),
}
A_INDEX_EM_SECIDS = {
    "000001": "1.000001",
    "399001": "0.399001",
    "399006": "0.399006",
    "000300": "1.000300",
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


def _days_from_today(trade_date: str) -> int:
    requested = datetime.strptime(trade_date, "%Y%m%d")
    return (datetime.now() - requested).days


def _is_recent_historical(trade_date: str, max_days: int = 7) -> bool:
    return is_historical_date(trade_date) and _days_from_today(trade_date) <= max_days


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
    allow_nearest: bool = False,
    max_gap_days: int = 5,
) -> QuoteData | None:
    target = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    eligible = [row for row in rows if row and str(row[0]) <= target]
    if not eligible:
        return None
    if str(eligible[-1][0]) != target:
        if not allow_nearest:
            return None
        from datetime import datetime

        actual = datetime.strptime(str(eligible[-1][0]), "%Y-%m-%d")
        requested = datetime.strptime(target, "%Y-%m-%d")
        if (requested - actual).days > max_gap_days:
            return None
    last = eligible[-1]
    previous_close = float(eligible[-2][2]) if len(eligible) >= 2 else None
    price = float(last[2])
    change = price - previous_close if previous_close not in (None, 0) else None
    change_pct = change / previous_close * 100 if change is not None and previous_close else None
    quote = QuoteData(
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
    if str(last[0]) != target:
        quote.quality_flags.append("nearest_available_kline")
        quote.fallback_reason = f"kline_date={last[0]}"
    return quote


def _fetch_tencent_historical_quote(
    code: str,
    *,
    symbol: str,
    name: str,
    market: str,
    currency: str,
    trade_date: str,
    turnover_from_last: bool = False,
    allow_nearest: bool = False,
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
        turnover_from_last=turnover_from_last or code.startswith("hk"),
        allow_nearest=allow_nearest,
    )


def _fetch_sina_us_history(symbol: str, trade_date: str, *, allow_nearest: bool = False) -> QuoteData | None:
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
    if not eligible:
        return None
    if eligible[-1]["d"] != target:
        if not allow_nearest:
            return None
        actual = datetime.strptime(str(eligible[-1]["d"]), "%Y-%m-%d")
        requested = datetime.strptime(target, "%Y-%m-%d")
        if (requested - actual).days > 5:
            return None
    last = eligible[-1]
    previous_close = float(eligible[-2]["c"]) if len(eligible) >= 2 else None
    price = float(last["c"])
    change = price - previous_close if previous_close not in (None, 0) else None
    change_pct = change / previous_close * 100 if change is not None and previous_close else None
    quote = QuoteData(
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
        trade_date=str(last["d"]).replace("-", ""),
        source="sina-kline",
        source_chain=["sina-kline"],
    )
    if str(last["d"]) != target:
        quote.quality_flags.append("nearest_available_kline")
        quote.fallback_reason = f"requested={trade_date}; kline_date={last['d']}"
    return quote


def _enrich_historical_quote(quote: QuoteData | None, symbol: str, trade_date: str) -> QuoteData | None:
    try:
        supplemental = adapt_quote(market_core.fetch_stock_history_quote(symbol, trade_date))
    except Exception:
        supplemental = None
    if quote is None:
        return supplemental
    if supplemental is None:
        return quote
    if str(supplemental.trade_date or "").replace("-", "") != str(quote.trade_date or "").replace("-", ""):
        return quote
    enrich_fields = (
        "volume",
        "turnover",
        "turnover_rate",
        "total_market_cap",
        "float_market_cap",
        "pe",
        "pb",
        "high",
        "low",
    )
    for field_name in enrich_fields:
        if getattr(quote, field_name, None) is None and getattr(supplemental, field_name, None) is not None:
            setattr(quote, field_name, getattr(supplemental, field_name))
    source_chain = list(quote.source_chain or ([quote.source] if quote.source else []))
    for source in supplemental.source_chain or ([supplemental.source] if supplemental.source else []):
        if source and source not in source_chain:
            source_chain.append(source)
    quote.source_chain = source_chain
    return quote


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
    normalized = normalize_code(symbol)
    if detect_jp_kr_market(normalized):
        return fetch_jp_kr_quote(normalized, trade_date)
    if is_historical_date(trade_date):
        if normalized.endswith(".HK"):
            raw = normalized.replace(".HK", "").lstrip("0") or "0"
            quote = _fetch_tencent_historical_quote(
                f"hk{raw.zfill(5)}",
                symbol=normalized,
                name=normalized,
                market="hk",
                currency="HKD",
                trade_date=trade_date,
            )
            return _enrich_historical_quote(quote, normalized, trade_date)
        if normalized.isdigit():
            prefix = "sh" if normalized.startswith(("5", "6", "9")) else "bj" if normalized.startswith(("4", "8")) else "sz"
            quote = _fetch_tencent_historical_quote(
                f"{prefix}{normalized}",
                symbol=normalized,
                name=normalized,
                market="a",
                currency="CNY",
                trade_date=trade_date,
            )
            return _enrich_historical_quote(quote, normalized, trade_date)
        quote = _fetch_sina_us_history(normalized, trade_date, allow_nearest=True)
        return _enrich_historical_quote(quote, normalized, trade_date)
    core = market_core
    return adapt_quote(core.get_single_stock_quote(symbol, trade_date))


def fetch_jp_kr_financial_snapshot(symbol: str, trade_date: str) -> dict[str, Any]:
    return fetch_jp_kr_financials(normalize_code(symbol), trade_date)


def fetch_jp_kr_price_volume(symbol: str, trade_date: str) -> dict[str, Any]:
    return fetch_global_price_volume(symbol, trade_date)


def fetch_global_price_volume(symbol: str, trade_date: str) -> dict[str, Any]:
    normalized = normalize_code(symbol)
    market = detect_public_global_market(normalized)
    if not market:
        return {}
    try:
        history = (
            fetch_yahoo_history(normalized, trade_date, days=180)
            if market != "kr"
            else fetch_naver_history(normalized, trade_date, days=180)
        )
    except Exception as exc:
        return {"available": False, "symbol": normalized, "reason": str(exc), "rows": []}
    rows = [row for row in history.get("rows") or [] if row["date"] <= trade_date]
    payload = build_price_series_pack(
        [
            {
                "date": row["date"],
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
                "turnover_cny": None,
                "turnover_local": float(row["close"]) * float(row["volume"]),
            }
            for row in rows
            if None not in (row.get("close"), row.get("high"), row.get("low"), row.get("volume"))
        ]
    )
    required = {"returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"}
    metrics = payload.get("metrics") or {}
    local_turnovers = [
        float(row["turnover_local"])
        for row in payload.get("rows") or []
        if row.get("turnover_local") is not None
    ][-20:]
    liquidity = payload.get("liquidity") or {}
    liquidity.update(
        {
            "average_turnover_20d_local": sum(local_turnovers) / len(local_turnovers) if local_turnovers else None,
            "turnover_currency": history.get("currency"),
            "turnover_sample_size": len(local_turnovers),
        }
    )
    return {
        "available": required <= set(metrics),
        "symbol": normalized,
        "source": history.get("source"),
        "sample_size": payload.get("sample_size", 0),
        "metrics": metrics,
        "currency": history.get("currency"),
        "market": market,
        "liquidity": liquidity,
        "rows": payload.get("rows") or [],
        "available_fields": sorted(required & set(metrics)),
        "missing": sorted(required - set(metrics)),
        "conditions": [] if required <= set(metrics) else ["个股日 K 线需提供至少 61 个有效交易日"],
    }


def fetch_jp_kr_disclosures(symbol: str, trade_date: str, limit: int = 20) -> dict[str, Any]:
    normalized = normalize_code(symbol)
    if normalized.endswith(".T"):
        try:
            return fetch_tdnet_disclosures(normalized, trade_date, limit=limit)
        except Exception as exc:
            return {"available": False, "rows": [], "_source": "tdnet-public-html", "reason": str(exc)}
    return {
        "available": False,
        "rows": [],
        "_source": "kr-primary-disclosure-gap",
        "reason": "DART/OpenDART structured API requires a key; Agent primary-evidence fallback may inspect public filings",
    }


def fetch_a_share_financial_snapshot(symbol: str, trade_date: str, limit: int = 8) -> dict[str, Any]:
    return market_core.fetch_a_share_financial_snapshot(symbol, trade_date, limit=limit)


def fetch_company_disclosures(symbol: str, name: str, trade_date: str, limit: int = 20) -> dict[str, Any]:
    return market_core.fetch_company_disclosures(symbol, name, trade_date, limit=limit)


def fetch_a_share_annual_report_slice(fiscal_year: int) -> dict[str, Any]:
    """Stable facade for the auditable whole-market annual-report slice."""
    return market_core.fetch_a_share_annual_report_slice(fiscal_year)


def fetch_a_share_market_breadth(trade_date: str) -> dict[str, Any]:
    """Return strict current-day A-share breadth, never board-component totals."""
    return market_core.fetch_a_share_market_breadth(trade_date)


def fetch_a_index_price_volume(trade_date: str) -> dict[str, Any]:
    """Build auditable 5d/20d/60d index metrics from Tencent daily K lines."""
    indices: dict[str, dict[str, Any]] = {}
    for code, (symbol, name) in A_INDEX_HISTORY.items():
        try:
            rows, _ = _tencent_history(code, trade_date, limit=90)
        except Exception as exc:
            indices[symbol] = {"name": name, "available": False, "reason": str(exc)}
            continue
        metrics = _price_volume_metrics(rows, trade_date)
        metrics.update({"name": name, "symbol": symbol, "source": "tencent-kline"})
        indices[symbol] = metrics

    required = {"returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"}
    complete = next((row for row in indices.values() if required <= set(row.get("metrics") or {})), None)
    return {
        "available": complete is not None,
        "source": "tencent-kline",
        "indices": indices,
        "available_fields": sorted(required & set((complete or {}).get("metrics") or {})),
        "missing": [] if complete is not None else sorted(required),
        "conditions": [] if complete is not None else ["Tencent 指数日 K 线需提供至少 61 个有效交易日"],
    }


def fetch_a_share_price_volume(symbol: str, trade_date: str) -> dict[str, Any]:
    """Build a single listed A-share/ETF multi-period price-volume pack."""
    normalized = normalize_code(symbol)
    if not normalized.isdigit() or len(normalized) != 6:
        return {
            "available": False,
            "symbol": normalized,
            "missing": ["returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"],
            "conditions": ["个股多周期量价包当前只覆盖 6 位 A股/场内基金代码"],
        }
    prefix = "sh" if normalized.startswith(("5", "6", "9")) else "bj" if normalized.startswith(("4", "8")) else "sz"
    try:
        rows, _ = _tencent_history(f"{prefix}{normalized}", trade_date, limit=90)
    except Exception as exc:
        return {
            "available": False,
            "symbol": normalized,
            "source": "tencent-kline",
            "missing": ["returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"],
            "conditions": [f"腾讯个股日 K 线不可用：{exc}"],
        }
    payload = _price_volume_metrics(rows, trade_date)
    required = {"returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"}
    metrics = payload.get("metrics") or {}
    return {
        "available": required <= set(metrics),
        "symbol": normalized,
        "source": "tencent-kline",
        "sample_size": payload.get("sample_size", 0),
        "metrics": metrics,
        "liquidity": payload.get("liquidity") or {},
        "rows": payload.get("rows") or [],
        "available_fields": sorted(required & set(metrics)),
        "missing": sorted(required - set(metrics)),
        "conditions": [] if required <= set(metrics) else ["腾讯个股日 K 线需提供至少 61 个有效交易日"],
    }


def fetch_listed_fund_premium_discount(code: str, trade_date: str) -> dict[str, Any]:
    """Build a split-normalized listed-fund premium/discount series from public sources."""
    normalized = normalize_code(code)
    if not normalized.isdigit() or len(normalized) != 6:
        return {
            "available": False,
            "fundcode": normalized,
            "_error": "场内基金折溢价仅支持 6 位代码",
        }
    nav_history = market_core.fetch_fund_nav_history(normalized, trade_date)
    metadata = market_core.fetch_fund_tracking_metadata(normalized)
    if not nav_history.get("complete"):
        return {
            "available": False,
            "fundcode": normalized,
            "nav_history": nav_history,
            "tracking_metadata": metadata,
            "_error": nav_history.get("_error") or "official NAV history unavailable",
        }
    prefix = "sh" if normalized.startswith(("5", "6", "9")) else "bj" if normalized.startswith(("4", "8")) else "sz"
    try:
        kline_rows, _ = _tencent_history(f"{prefix}{normalized}", trade_date, limit=90)
    except Exception as exc:
        return {
            "available": False,
            "fundcode": normalized,
            "nav_history": nav_history,
            "tracking_metadata": metadata,
            "_error": f"腾讯场内基金日 K 线不可用：{exc}",
        }
    prices = {
        str(row[0]): close
        for row in kline_rows
        if row and len(row) >= 3 and (close := _safe_float(row[2])) is not None and close > 0
    }
    nav_by_date = {str(row["date"]): row for row in nav_history["rows"]}
    split_events, unparsed_actions = _fund_split_events(nav_history["rows"])
    matched: list[dict[str, Any]] = []
    for date in sorted(set(prices) & set(nav_by_date)):
        nav = _safe_float(nav_by_date[date].get("nav"))
        factor = _qfq_nav_factor(date, split_events)
        if nav is None or nav <= 0 or factor is None:
            continue
        adjusted_nav = nav * factor
        matched.append(
            {
                "date": date,
                "close": prices[date],
                "official_nav": nav,
                "qfq_nav": adjusted_nav,
                "premium_discount_pct": (prices[date] / adjusted_nav - 1) * 100,
            }
        )
    if unparsed_actions:
        return {
            "available": False,
            "fundcode": normalized,
            "rows": matched,
            "nav_history": nav_history,
            "tracking_metadata": metadata,
            "split_events": split_events,
            "_error": "存在无法解析的分红/拆分事件，不能将前复权场内价与原始净值混算",
            "unparsed_actions": unparsed_actions,
        }
    if len(matched) < 20:
        return {
            "available": False,
            "fundcode": normalized,
            "rows": matched,
            "nav_history": nav_history,
            "tracking_metadata": metadata,
            "split_events": split_events,
            "_error": "场内价与官方净值重合样本少于 20 个交易日",
        }
    recent = matched[-20:]
    values = [row["premium_discount_pct"] for row in recent]
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    return {
        "available": True,
        "fundcode": normalized,
        "source": "腾讯前复权日K线 + 东方财富官方历史净值",
        "rows": matched,
        "matched_days": len(matched),
        "latest": matched[-1],
        "premium_discount_20d_mean_pct": average,
        "premium_discount_20d_std_pct": math.sqrt(variance),
        "premium_discount_20d_min_pct": min(values),
        "premium_discount_20d_max_pct": max(values),
        "split_events": split_events,
        "tracking_metadata": metadata,
        "limitations": [
            "场内价格使用腾讯前复权日K线；官方净值在份额拆分日前按公开拆分比例归一。",
            "基金页面的年化跟踪误差为披露值；重算需与标的指数日线按相同交易日严格对齐。",
        ],
    }


def _fund_split_events(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    split_events: list[dict[str, Any]] = []
    unparsed_actions: list[dict[str, Any]] = []
    for row in rows:
        action = str(row.get("corporate_action") or "").strip()
        if not action:
            continue
        matched = re.search(r"分拆\s*(\d+(?:\.\d+)?)\s*份", action)
        if not matched:
            unparsed_actions.append({"date": row.get("date"), "corporate_action": action})
            continue
        ratio = _safe_float(matched.group(1))
        if ratio is None or ratio <= 0:
            unparsed_actions.append({"date": row.get("date"), "corporate_action": action})
            continue
        split_events.append({"date": str(row["date"]), "ratio": ratio, "corporate_action": action})
    return sorted(split_events, key=lambda row: row["date"]), unparsed_actions


def _qfq_nav_factor(date: str, split_events: list[dict[str, Any]]) -> float | None:
    factor = 1.0
    for event in split_events:
        if date < event["date"]:
            ratio = _safe_float(event.get("ratio"))
            if ratio is None or ratio <= 0:
                return None
            factor /= ratio
    return factor


def _price_volume_metrics(rows: list[list[Any]], trade_date: str) -> dict[str, Any]:
    target = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    samples = []
    for row in rows:
        if not row or len(row) < 6 or str(row[0]) > target:
            continue
        close = _safe_float(row[2])
        high = _safe_float(row[3])
        low = _safe_float(row[4])
        volume = _safe_float(row[5])
        if None in (close, high, low, volume) or close <= 0 or volume < 0:
            continue
        samples.append({
            "date": str(row[0]).replace("-", ""),
            "close": close,
            "high": high,
            "low": low,
            "volume": volume,
            "turnover_cny": close * volume * 100,
        })
    return build_price_series_pack(samples)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _eastmoney_index_history_amounts(trade_date: str) -> dict[str, float]:
    amounts: dict[str, float] = {}
    for symbol, secid in A_INDEX_EM_SECIDS.items():
        data = market_core.fetch_json(
            market_core.EM_KLINE_URL.format(
                secid=secid,
                beg=trade_date,
                end=trade_date,
                ts=int(time.time() * 1000),
            ),
            {"Referer": "https://quote.eastmoney.com/"},
        )
        rows = (data.get("data") or {}).get("klines") or []
        if not rows:
            continue
        fields = str(rows[-1]).split(",")
        if len(fields) < 7:
            continue
        amount = _safe_float(fields[6])
        if amount is not None and amount > 0:
            amounts[symbol] = amount
    return amounts


def _merge_index_turnover(rows: list[dict[str, Any]], trade_date: str) -> list[dict[str, Any]]:
    if not rows:
        return rows
    try:
        history_amounts = _eastmoney_index_history_amounts(trade_date)
    except Exception:
        history_amounts = {}
    for row in rows:
        amount = history_amounts.get(str(row.get("f12") or ""))
        if amount is not None:
            row["f6"] = amount
            row["_turnover_source"] = "eastmoney-kline"
    if all((_safe_float(row.get("f6")) or 0) > 0 for row in rows):
        return rows
    try:
        em_rows = market_core.get_index(trade_date)
    except Exception:
        return rows
    turnover_by_symbol = {
        str(item.get("f12") or ""): item.get("f6")
        for item in em_rows
        if item.get("f12") and item.get("f6") is not None
    }
    for row in rows:
        if (_safe_float(row.get("f6")) or 0) > 0:
            continue
        em_turnover = turnover_by_symbol.get(str(row.get("f12") or ""))
        if em_turnover is not None:
            row["f6"] = em_turnover
            row["_turnover_source"] = "eastmoney"
    return rows


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
                        "f5": quote.volume,
                        "f6": quote.turnover,
                        "_source": quote.source,
                        "_source_date": trade_date,
                        "_quality_flags": list(quote.quality_flags),
                        "_fallback_reason": quote.fallback_reason,
                    }
                )
        return _merge_index_turnover(result, trade_date)
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
        rows = [
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
                    allow_nearest=True,
                )
            )
        ]
        if rows:
            return rows
        # 腾讯 K 线滞后时，回退到实时港股指数并标注最近可用。
        live_rows = fetch_hk_indices(datetime.now().strftime("%Y%m%d"))
        for quote in live_rows:
            quote.quality_flags.append("nearest_available_live")
            quote.fallback_reason = f"requested={trade_date}"
        return live_rows
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
            quote = _fetch_sina_us_history(code, trade_date, allow_nearest=True)
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
    normalized_type = "concept" if board_type == "concept" else "industry"
    if is_historical_date(trade_date):
        cached = market_core.cache_load("board_list", f"{trade_date}_{normalized_type}", "eastmoney_clist")
        if cached and cached.get("rows"):
            cached = dict(cached)
            cached["_source_note"] = "历史板块榜来自本地缓存"
            return cached
    if is_historical_date(trade_date) and not _is_recent_historical(trade_date):
        return {
            "board_type": normalized_type,
            "rows": [],
            "_unavailable": "远期历史板块榜无缓存，禁止混用实时数据",
        }
    result = market_core.get_board_list(board_type, trade_date, limit=limit)
    if is_historical_date(trade_date) and _is_recent_historical(trade_date) and not result.get("rows"):
        ths = market_core.fetch_ths_board_list(board_type, limit=limit)
        if ths.get("rows"):
            ths = dict(ths)
            ths["_fallback"] = "近期历史板块榜无缓存，已使用同花顺公开页补全"
            ths["_source_note"] = "近期历史复盘使用当前公开板块页补全，需结合交易日核验。"
            return ths
    if is_historical_date(trade_date) and not result.get("rows"):
        result = dict(result or {"board_type": normalized_type, "rows": []})
        result.setdefault(
            "_unavailable",
            "历史板块榜无缓存；请在交易日收盘后运行一次以写入缓存，或启用 STOCK_ANALYSIS_BROWSER_FALLBACK=1",
        )
    return result


def fetch_fund_flow(trade_date: str) -> dict[str, Any]:
    return market_core.get_fund_flow(trade_date, strict_date=True)


def fetch_lhb_aftermarket(trade_date: str, limit: int = 5) -> dict[str, Any]:
    return market_core.fetch_lhb_aftermarket(trade_date, limit=limit)


def fetch_important_announcements(
    trade_date: str,
    candidates: list[dict[str, Any]] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    return market_core.fetch_important_announcements(trade_date, candidates=candidates, limit=limit)


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


def fetch_fund_nav_quote(code: str, trade_date: str) -> dict[str, Any]:
    return market_core.fetch_fund_nav_quote(code, trade_date)


def fetch_fund_profile(code: str, trade_date: str) -> dict[str, Any]:
    return market_core.fetch_fund_profile(code, trade_date)


def fetch_fund_holdings(code: str, trade_date: str, limit: int = 10) -> dict[str, Any]:
    return market_core.fetch_fund_holdings(code, trade_date, limit=limit)


def fetch_fund_holding_quotes(holdings: list[dict[str, Any]], trade_date: str) -> dict[str, QuoteData]:
    core = market_core
    raw = core.fetch_fund_holding_quotes(holdings, trade_date)
    return {symbol: adapt_quote(q) for symbol, q in raw.items() if adapt_quote(q)}


def fetch_a_share_order_book_snapshot(symbol: str, trade_date: str) -> dict[str, Any]:
    return market_core.fetch_a_share_order_book_snapshot(symbol, trade_date)


def fetch_stock_buy_reference(symbol: str, buy_date: str) -> dict[str, Any]:
    return market_core.fetch_stock_close_on_or_after(symbol, buy_date)


def fetch_fund_buy_reference(code: str, buy_date: str) -> dict[str, Any]:
    return market_core.fetch_fund_nav_on_or_after(code, buy_date)
