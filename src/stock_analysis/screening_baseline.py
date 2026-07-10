"""Contracts established before the A-share fundamental screening MVP."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

PERCENT_POINTS = "percent_points"
ANNUAL_REPORT_TYPE = "A股"
OFFICIAL_SECURITY_MASTER_SOURCES = {
    "SSE": "https://www.sse.com.cn/assortment/stock/list/share/",
    "SZSE": "https://www.szse.cn/market/product/stock/list/index.html",
    "BSE": "https://www.bse.cn/nq/listedcompany.html",
}

FINANCIAL_FIELD_CONTRACT = {
    "roe_weighted_pct": {
        "source_field": "WEIGHTAVG_ROE",
        "unit": PERCENT_POINTS,
        "description": "加权平均净资产收益率；8 表示 8%，不是 0.08。",
    },
    "revenue_growth_yoy_pct": {
        "source_field": "YSTZ",
        "unit": PERCENT_POINTS,
        "description": "营业总收入同比；允许负数和零，不能用行情 safe_float 解析。",
    },
}


def annual_report_filter(fiscal_year: int) -> str:
    """Return the exact Eastmoney filter for the A-share annual-report slice."""
    if fiscal_year < 1990 or fiscal_year > 9999:
        raise ValueError("fiscal_year must be a four-digit year")
    return f'(DATATYPE="{fiscal_year}年 年报")(SECURITY_TYPE="{ANNUAL_REPORT_TYPE}")'


def normalize_annual_financial_row(row: dict[str, Any], *, fiscal_year: int) -> dict[str, Any]:
    """Normalize one disclosed annual-report row without changing its units."""
    _require_annual_a_share_row(row, fiscal_year=fiscal_year)
    fields = {}
    for name, contract in FINANCIAL_FIELD_CONTRACT.items():
        value = _signed_number(row.get(contract["source_field"]))
        fields[name] = {
            "raw_value": row.get(contract["source_field"]),
            "normalized_value": value,
            "unit": contract["unit"],
            "status": "reported" if value is not None else "missing",
        }
    return {
        "symbol": str(row["SECURITY_CODE"]),
        "name": str(row.get("SECURITY_NAME_ABBR") or ""),
        "report_date": _date_only(row["REPORTDATE"]),
        "report_period": f"{fiscal_year}FY",
        "announcement_date": _date_only(row.get("NOTICE_DATE")),
        "source": "eastmoney:RPT_LICO_FN_CPD",
        "fields": fields,
    }


def normalize_sse_security_master_row(row: dict[str, Any], *, universe_as_of: str) -> dict[str, Any]:
    """Normalize a current SSE stock-list record from its official list endpoint."""
    as_of = _parse_iso_date(universe_as_of)
    symbol = str(row.get("SECURITY_CODE_A") or "").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError("official SSE row is missing a six-digit A-share code")
    listed_at = _date_only(row.get("LISTING_DATE"))
    if not listed_at:
        raise ValueError("official SSE row is missing LISTING_DATE")
    return {
        "symbol": symbol,
        "name": str(row.get("SECURITY_ABBR_A") or row.get("COMPANY_ABBR") or ""),
        "exchange": "SSE",
        "board": {"0": "main"}.get(str(row.get("LISTING_BOARD") or ""), "unknown"),
        "listed_at": listed_at,
        "universe_as_of": as_of.isoformat(),
        "source": "sse:stock-list",
    }


def normalize_szse_security_master_row(row: dict[str, Any], *, universe_as_of: str) -> dict[str, Any]:
    """Normalize an official SZSE stock-list row into the shared master shape."""
    return _normalize_security_master_row(
        symbol=row.get("agdm"),
        name=_strip_html(row.get("agjc")),
        exchange="SZSE",
        board=row.get("bk") or "unknown",
        listed_at=row.get("agssrq"),
        universe_as_of=universe_as_of,
        source="szse:stock-list",
    )


def normalize_bse_security_master_row(row: dict[str, Any], *, universe_as_of: str) -> dict[str, Any]:
    """Normalize an official BSE stock-list row into the shared master shape."""
    return _normalize_security_master_row(
        symbol=row.get("xxzqdm"),
        name=row.get("xxzqjc"),
        exchange="BSE",
        board="BSE",
        listed_at=row.get("fxssrq"),
        universe_as_of=universe_as_of,
        source="bse:stock-list",
    )


def _normalize_security_master_row(
    *,
    symbol: Any,
    name: Any,
    exchange: str,
    board: Any,
    listed_at: Any,
    universe_as_of: str,
    source: str,
) -> dict[str, Any]:
    as_of = _parse_iso_date(universe_as_of)
    normalized_symbol = str(symbol or "").strip()
    if len(normalized_symbol) != 6 or not normalized_symbol.isdigit():
        raise ValueError(f"official {exchange} row is missing a six-digit A-share code")
    normalized_listing_date = _canonical_date(listed_at)
    if not normalized_listing_date:
        raise ValueError(f"official {exchange} row is missing a listing date")
    return {
        "symbol": normalized_symbol,
        "name": str(name or "").strip(),
        "exchange": exchange,
        "board": str(board or "unknown"),
        "listed_at": normalized_listing_date,
        "universe_as_of": as_of.isoformat(),
        "source": source,
    }


def _require_annual_a_share_row(row: dict[str, Any], *, fiscal_year: int) -> None:
    expected = {
        "DATATYPE": f"{fiscal_year}年 年报",
        "SECURITY_TYPE": ANNUAL_REPORT_TYPE,
        "QDATE": f"{fiscal_year}Q4",
    }
    mismatched = [field for field, value in expected.items() if row.get(field) != value]
    if mismatched:
        raise ValueError(f"row is not the requested A-share annual report: {', '.join(mismatched)}")
    if _date_only(row.get("REPORTDATE")) != f"{fiscal_year}-12-31":
        raise ValueError("annual-report row must have a fiscal year-end REPORTDATE")
    symbol = str(row.get("SECURITY_CODE") or "")
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError("annual-report row is missing a six-digit SECURITY_CODE")


def _signed_number(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_only(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else ""


def _canonical_date(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return _date_only(text)


def _strip_html(value: Any) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("universe_as_of must use YYYY-MM-DD") from exc
