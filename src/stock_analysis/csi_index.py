"""Official CSI index constituents, weights, and aggregate valuation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests
import xlrd

from .time_series import build_price_series_pack

CSI_BASE = "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile"
FUND_INDEX_CODES = {"512480": "H30184"}


def _download_xls(url: str) -> list[list[Any]]:
    response = requests.get(url, timeout=20, headers={"User-Agent": "stock-analysis/4.13.0"})
    response.raise_for_status()
    workbook = xlrd.open_workbook(file_contents=response.content)
    sheet = workbook.sheet_by_index(0)
    return [sheet.row_values(row) for row in range(sheet.nrows)]


def _download_performance(index_code: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    url = (
        "https://www.csindex.com.cn/csindex-home/perf/index-perf"
        f"?indexCode={index_code}&startDate={start_date}&endDate={end_date}"
    )
    response = requests.get(url, timeout=20, headers={"User-Agent": "stock-analysis/4.13.0"})
    response.raise_for_status()
    payload = response.json()
    return payload.get("data") or []


def _records(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if len(rows) < 2:
        return []
    headers = [str(value).strip() for value in rows[0]]
    return [dict(zip(headers, row)) for row in rows[1:]]


def _text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value or "").strip()


def _latest_on_or_before(records: list[dict[str, Any]], trade_date: str, date_key: str) -> list[dict[str, Any]]:
    eligible = [row for row in records if _text(row.get(date_key)).replace("-", "") <= trade_date]
    if not eligible:
        return []
    latest = max(_text(row.get(date_key)).replace("-", "") for row in eligible)
    return [row for row in eligible if _text(row.get(date_key)).replace("-", "") == latest]


def build_csi_index_snapshot(
    index_code: str,
    trade_date: str,
    *,
    downloader: Any = _download_xls,
    performance_loader: Any = _download_performance,
) -> dict[str, Any]:
    """Build one official index snapshot without estimating missing constituents."""

    compact = trade_date.replace("-", "")
    urls = {
        "constituents": f"{CSI_BASE}/cons/{index_code}cons.xls",
        "weights": f"{CSI_BASE}/closeweight/{index_code}closeweight.xls",
        "valuation": f"{CSI_BASE}/indicator/{index_code}indicator.xls",
    }
    download_errors: dict[str, str] = {}

    def load_xls(name: str) -> list[dict[str, Any]]:
        try:
            return _records(downloader(urls[name]))
        except Exception as exc:
            download_errors[name] = str(exc)
            return []

    constituents_raw = load_xls("constituents")
    weights_raw = load_xls("weights")
    valuation_raw = load_xls("valuation")

    constituents_rows = _latest_on_or_before(constituents_raw, compact, "日期Date")
    weight_rows = _latest_on_or_before(weights_raw, compact, "日期Date")
    valuation_rows = _latest_on_or_before(valuation_raw, compact, "日期Date")
    weights = {
        _text(row.get("成份券代码Constituent Code")): float(row.get("权重(%)weight") or 0)
        for row in weight_rows
    }
    constituents = [
        {
            "code": _text(row.get("成份券代码Constituent Code")).zfill(6),
            "name": _text(row.get("成份券名称Constituent Name")),
            "exchange": _text(row.get("交易所Exchange")),
            "weight_pct": weights.get(_text(row.get("成份券代码Constituent Code"))),
        }
        for row in constituents_rows
        if _text(row.get("成份券代码Constituent Code"))
    ]
    constituents.sort(key=lambda row: -(row.get("weight_pct") or 0))
    valuation_row = valuation_rows[0] if valuation_rows else {}
    valuation = {
        "asof": _text(valuation_row.get("日期Date")),
        "pe_total_share": valuation_row.get("市盈率1（总股本）P/E1"),
        "pe_calculation_share": valuation_row.get("市盈率2（计算用股本）P/E2"),
        "dividend_yield_total_share_pct": valuation_row.get("股息率1（总股本）D/P1"),
        "dividend_yield_calculation_share_pct": valuation_row.get("股息率2（计算用股本）D/P2"),
    }
    end = datetime.strptime(compact, "%Y%m%d")
    start = (end - timedelta(days=220)).strftime("%Y%m%d")
    try:
        raw_history = performance_loader(index_code, start, compact)
    except Exception:
        raw_history = []
    unique_history: dict[str, dict[str, Any]] = {}
    for row in raw_history:
        date = _text(row.get("tradeDate")).replace("-", "")
        try:
            parsed_date = datetime.strptime(date, "%Y%m%d")
            values = {
                key: float(row[key])
                for key in ("open", "high", "low", "close")
                if row.get(key) is not None
            }
        except (TypeError, ValueError):
            continue
        if parsed_date.weekday() >= 5 or date > compact or len(values) != 4 or values["close"] <= 0:
            continue
        trading_value = row.get("tradingValue")
        unique_history[date] = {
            "date": date,
            **values,
            "volume": float(row["tradingVol"]) if row.get("tradingVol") is not None else None,
            "turnover_cny": float(trading_value) * 100_000_000 if trading_value is not None else None,
        }
    history = build_price_series_pack(list(unique_history.values()))
    history["available"] = history["sample_size"] >= 61
    history["source"] = "中证指数有限公司官方指数日线"
    weight_sum = sum(float(row.get("weight_pct") or 0) for row in constituents)
    return {
        "available": bool(constituents and valuation.get("pe_calculation_share") is not None),
        "index_code": index_code,
        "constituent_asof": _text(constituents_rows[0].get("日期Date")) if constituents_rows else None,
        "weight_asof": _text(weight_rows[0].get("日期Date")) if weight_rows else None,
        "constituent_count": len(constituents),
        "weighted_constituent_count": sum(row.get("weight_pct") is not None for row in constituents),
        "weight_sum_pct": weight_sum,
        "constituents": constituents,
        "valuation": valuation,
        "history": history,
        "download_errors": download_errors,
        "urls": urls,
        "source": "中证指数有限公司官方样本、权重与估值文件",
    }
