"""Free, loginless JP/KR public-market adapters.

These adapters keep transport, provenance and as-of limitations visible.  They
do not promote aggregator financials to issuer-primary evidence.
"""

from __future__ import annotations

import calendar
import html
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .models import QuoteData

_UA = "Mozilla/5.0 (stock-analysis public-data adapter)"
_MARKET_SUFFIXES = {".T": "jp", ".KS": "kr", ".KQ": "kr"}
_YAHOO_TIMEZONES = {
    "jp": "Asia/Tokyo",
    "kr": "Asia/Seoul",
    "hk": "Asia/Hong_Kong",
    "us": "America/New_York",
}


def detect_jp_kr_market(symbol: str) -> str | None:
    upper = str(symbol).strip().upper()
    return next((market for suffix, market in _MARKET_SUFFIXES.items() if upper.endswith(suffix)), None)


def detect_public_global_market(symbol: str) -> str | None:
    upper = str(symbol).strip().upper()
    regional = detect_jp_kr_market(upper)
    if regional:
        return regional
    if upper.endswith(".HK"):
        return "hk"
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", upper):
        return "us"
    return None


def canonical_global_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if re.fullmatch(r"JP:\d{4}", value):
        return f"{value[3:]}.T"
    if re.fullmatch(r"KR:\d{6}", value):
        return f"{value[3:]}.KS"
    if detect_jp_kr_market(value):
        return value
    return value


def _direct_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    return session


def _epoch(day: date, timezone: str) -> int:
    return int(datetime.combine(day, time(), tzinfo=ZoneInfo(timezone)).timestamp())


def _requested_day(trade_date: str) -> date:
    return datetime.strptime(trade_date, "%Y%m%d").date()


def fetch_yahoo_history(symbol: str, trade_date: str, *, days: int = 120) -> dict[str, Any]:
    symbol = canonical_global_symbol(symbol)
    market = detect_public_global_market(symbol)
    if not market:
        return {"available": False, "rows": [], "reason": "not a supported Yahoo symbol"}
    target = _requested_day(trade_date)
    timezone = _YAHOO_TIMEZONES[market]
    response = _direct_session().get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={
            "period1": _epoch(target - timedelta(days=days), timezone),
            "period2": _epoch(target + timedelta(days=1), timezone),
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        },
        timeout=15,
    )
    response.raise_for_status()
    result = ((response.json().get("chart") or {}).get("result") or [None])[0]
    if not result:
        return {"available": False, "rows": [], "reason": "Yahoo returned no chart result"}
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    adjusted = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    rows = []
    for index, timestamp in enumerate(result.get("timestamp") or []):
        values = {key: (quote.get(key) or [None] * (index + 1))[index] for key in ("open", "high", "low", "close", "volume")}
        if values["close"] in (None, 0):
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp, ZoneInfo(timezone)).strftime("%Y%m%d"),
                **values,
                "adj_close": adjusted[index] if index < len(adjusted) else None,
            }
        )
    meta = result.get("meta") or {}
    return {
        "available": bool(rows),
        "symbol": symbol,
        "market": market,
        "currency": meta.get("currency") or ("JPY" if market == "jp" else "KRW"),
        "timezone": meta.get("exchangeTimezoneName") or timezone,
        "exchange": meta.get("exchangeName"),
        "rows": rows,
        "events": result.get("events") or {},
        "source": "yahoo-chart",
    }


def fetch_naver_history(symbol: str, trade_date: str, *, days: int = 120) -> dict[str, Any]:
    canonical = canonical_global_symbol(symbol)
    if not canonical.endswith((".KS", ".KQ")):
        return {"available": False, "rows": [], "reason": "not a Korean symbol"}
    code = canonical.split(".", 1)[0]
    target = _requested_day(trade_date)
    response = _direct_session().get(
        "https://api.finance.naver.com/siseJson.naver",
        params={
            "symbol": code,
            "requestType": 1,
            "startTime": (target - timedelta(days=days)).strftime("%Y%m%d"),
            "endTime": trade_date,
            "timeframe": "day",
        },
        headers={"Referer": "https://finance.naver.com/"},
        timeout=15,
    )
    response.raise_for_status()
    rows = []
    for match in re.findall(
        r'\[\s*"(\d{8})"\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)',
        response.text,
    ):
        day, open_price, high, low, close, volume = match
        rows.append(
            {
                "date": day,
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
                "adj_close": None,
            }
        )
    return {
        "available": bool(rows),
        "symbol": canonical,
        "market": "kr",
        "currency": "KRW",
        "timezone": "Asia/Seoul",
        "exchange": "KOSDAQ" if canonical.endswith(".KQ") else "KOSPI",
        "rows": rows,
        "source": "naver-chart",
    }


def _quote_from_history(history: dict[str, Any], requested_date: str) -> QuoteData | None:
    rows = [row for row in history.get("rows") or [] if row["date"] <= requested_date]
    if not rows:
        return None
    latest = rows[-1]
    prior_close = rows[-2]["close"] if len(rows) > 1 else None
    change = latest["close"] - prior_close if prior_close not in (None, 0) else None
    quote = QuoteData(
        symbol=history.get("symbol") or "",
        name=history.get("symbol") or "",
        market=history.get("market") or "",
        price=latest["close"],
        previous_close=prior_close,
        change=change,
        change_pct=change / prior_close * 100 if change is not None and prior_close else None,
        open_price=latest["open"],
        high=latest["high"],
        low=latest["low"],
        volume=latest["volume"],
        currency=history.get("currency") or "",
        trade_date=latest["date"],
        source=history.get("source") or "",
        source_chain=[history.get("source") or ""],
        extra={
            "timezone": history.get("timezone"),
            "exchange": history.get("exchange"),
            "requested_date": requested_date,
            "adjustment": "raw",
        },
    )
    if latest["date"] != requested_date:
        quote.quality_flags.append("nearest_available_kline")
        quote.fallback_reason = f"requested={requested_date}; effective={latest['date']}"
    return quote


def fetch_jp_kr_quote(symbol: str, trade_date: str) -> QuoteData | None:
    canonical = canonical_global_symbol(symbol)
    market = detect_jp_kr_market(canonical)
    if market == "jp":
        try:
            return _quote_from_history(fetch_yahoo_history(canonical, trade_date), trade_date)
        except (requests.RequestException, ValueError, KeyError):
            return None
    if market != "kr":
        return None
    naver = yahoo = None
    try:
        naver = fetch_naver_history(canonical, trade_date)
    except (requests.RequestException, ValueError):
        pass
    try:
        yahoo = fetch_yahoo_history(canonical, trade_date)
    except (requests.RequestException, ValueError, KeyError):
        pass
    primary = _quote_from_history(naver or {}, trade_date) or _quote_from_history(yahoo or {}, trade_date)
    if primary is None:
        return None
    secondary = _quote_from_history(yahoo or {}, trade_date) if primary.source == "naver-chart" else None
    if secondary:
        primary.source_chain.append("yahoo-chart")
        comparable = ("price", "open_price", "high", "low", "volume")
        matched = all(getattr(primary, key) == getattr(secondary, key) for key in comparable)
        primary.extra["cross_check_status"] = "matched" if matched else "conflict"
        if not matched:
            primary.quality_flags.append("cross_source_conflict")
            primary.extra["cross_check_quote"] = {
                key: getattr(secondary, key) for key in comparable
            }
    return primary


_YAHOO_FINANCIAL_TYPES = {
    "annualTotalRevenue": "revenue",
    "annualGrossProfit": "gross_profit",
    "annualOperatingIncome": "operating_profit",
    "annualNetIncome": "parent_net_profit",
    "annualTotalAssets": "total_assets",
    "annualTotalLiabilitiesNetMinorityInterest": "total_liabilities",
    "annualStockholdersEquity": "stockholders_equity",
    "annualTotalDebt": "total_debt",
    "annualOperatingCashFlow": "operating_cash_flow",
    "annualCapitalExpenditure": "capital_expenditure",
    "annualCashDividendsPaid": "cash_dividends_paid",
    "annualRepurchaseOfCapitalStock": "share_repurchases",
    "annualDilutedEPS": "basic_eps",
    "quarterlyTotalRevenue": "revenue",
    "quarterlyGrossProfit": "gross_profit",
    "quarterlyOperatingIncome": "operating_profit",
    "quarterlyNetIncome": "parent_net_profit",
    "quarterlyTotalAssets": "total_assets",
    "quarterlyTotalLiabilitiesNetMinorityInterest": "total_liabilities",
    "quarterlyStockholdersEquity": "stockholders_equity",
    "quarterlyTotalDebt": "total_debt",
    "quarterlyOperatingCashFlow": "operating_cash_flow",
    "quarterlyCapitalExpenditure": "capital_expenditure",
    "quarterlyCashDividendsPaid": "cash_dividends_paid",
    "quarterlyRepurchaseOfCapitalStock": "share_repurchases",
    "quarterlyDilutedEPS": "basic_eps",
}


def fetch_yahoo_financials(symbol: str, trade_date: str) -> dict[str, Any]:
    canonical = canonical_global_symbol(symbol)
    market = detect_public_global_market(canonical)
    if market not in {"jp", "kr", "hk", "us"}:
        return {}
    if trade_date < datetime.now().strftime("%Y%m%d"):
        return {
            "periods": [],
            "_source": "yahoo-fundamentals",
            "_limitations": ["aggregator rows have no publication date and are unsafe for historical as-of research"],
        }
    response = _direct_session().get(
        f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{canonical}",
        params={
            "symbol": canonical,
            "type": ",".join(_YAHOO_FINANCIAL_TYPES),
            "period1": 1262304000,
            "period2": int(datetime.now().timestamp()) + 86400,
        },
        timeout=15,
    )
    response.raise_for_status()
    timeseries = response.json().get("timeseries") or {}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for series in timeseries.get("result") or []:
        kinds = (series.get("meta") or {}).get("type") or []
        kind = kinds[0] if isinstance(kinds, list) and kinds else kinds
        metric = _YAHOO_FINANCIAL_TYPES.get(kind)
        if not metric:
            continue
        frequency = "quarter" if str(kind).startswith("quarterly") else "annual"
        for item in series.get(kind) or []:
            period = str(item.get("asOfDate") or "")
            if not period or period.replace("-", "") > trade_date:
                continue
            value = (item.get("reportedValue") or {}).get("raw")
            if value is None:
                continue
            row = grouped.setdefault(
                (period, frequency),
                {
                    "report_date": period,
                    "period_label": f"{period[:4]}FY" if frequency == "annual" else period,
                    "notice_date": None,
                    "publication_date_status": "missing",
                    "accounting_basis": "reported_by_aggregator",
                    "scope": "consolidated_or_provider_default",
                },
            )
            row[metric] = value
    periods = sorted(grouped.values(), key=lambda row: row["report_date"], reverse=True)
    for row in periods:
        currency = {"jp": "JPY", "kr": "KRW", "hk": "HKD", "us": "USD"}[market]
        capex = row.get("capital_expenditure")
        operating_cash = row.get("operating_cash_flow")
        if operating_cash is not None and capex is not None:
            row["free_cash_flow_lite"] = float(operating_cash) + float(capex)
        revenue = row.get("revenue")
        gross_profit = row.get("gross_profit")
        if revenue not in (None, 0) and gross_profit is not None:
            row["gross_margin"] = float(gross_profit) / float(revenue) * 100
        liabilities = row.get("total_liabilities")
        assets = row.get("total_assets")
        if assets not in (None, 0) and liabilities is not None:
            row["debt_asset_ratio"] = float(liabilities) / float(assets) * 100
        row.update({"_source": "yahoo-fundamentals", "_currency": currency, "_source_type": "secondary_aggregated_financial"})
    return {
        "periods": periods,
        "_source": "yahoo-fundamentals",
        "_source_type": "secondary_aggregated_financial",
        "_limitations": ["publication date unavailable", "field coverage varies by issuer"],
    }


def _plain(value: str) -> str:
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", value)))


def _number(value: str) -> float | None:
    text = _plain(value).replace(",", "")
    if text in {"", "-", "--", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_naver_financials(symbol: str, trade_date: str) -> dict[str, Any]:
    canonical = canonical_global_symbol(symbol)
    if not canonical.endswith((".KS", ".KQ")):
        return {}
    if trade_date < datetime.now().strftime("%Y%m%d"):
        return {
            "periods": [],
            "_source": "naver-finance",
            "_limitations": ["public page has no publication date and is unsafe for historical as-of research"],
        }
    code = canonical.split(".", 1)[0]
    response = _direct_session().get(
        "https://finance.naver.com/item/main.naver",
        params={"code": code},
        headers={"Referer": "https://finance.naver.com/"},
        timeout=15,
    )
    response.raise_for_status()
    match = re.search(r'<div class="section cop_analysis">(.*?)</table>', response.text, re.DOTALL)
    if not match:
        return {"periods": [], "_source": "naver-finance", "_limitations": ["financial table not found"]}
    table = match.group(1)
    columns = []
    for cell in re.findall(r'<th scope="col"[^>]*>(.*?)</th>', table, re.DOTALL):
        label = _plain(cell)
        period = re.search(r"(\d{4})\.(\d{2})", label)
        if period:
            columns.append((f"{period.group(1)}-{period.group(2)}", "(E)" in label))
    field_map = {
        "매출액": "revenue",
        "영업이익": "operating_profit",
        "당기순이익": "parent_net_profit",
        "영업활동현금흐름": "operating_cash_flow",
        "ROE(지배주주)": "roe_weighted",
        "부채비율": "debt_asset_ratio",
        "EPS(원)": "basic_eps",
        "BPS(원)": "bps",
    }
    grouped = []
    for index, (period, estimate) in enumerate(columns):
        year, month = (int(part) for part in period.split("-"))
        grouped.append(
            {
            "report_date": f"{period}-{calendar.monthrange(year, month)[1]:02d}",
            "period_label": f"{period[:4]}FY" if index < 4 else period,
            "notice_date": None,
            "publication_date_status": "missing",
            "accounting_basis": "reported_by_aggregator",
            "scope": "IFRS_consolidated_or_provider_default",
            "is_estimate": estimate,
            }
        )
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL):
        heading = re.search(r'<th scope="row"[^>]*>.*?<strong>(.*?)</strong>.*?</th>', row_html, re.DOTALL)
        if not heading:
            continue
        metric = field_map.get(_plain(heading.group(1)))
        if not metric:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        for target, cell in zip(grouped, cells):
            value = _number(cell)
            if value is not None:
                target[metric] = value * 100_000_000 if metric in {
                    "revenue", "operating_profit", "parent_net_profit", "operating_cash_flow"
                } else value
    periods = [row for row in grouped if not row.pop("is_estimate") and len(row) > 6]
    periods.sort(key=lambda row: row["report_date"], reverse=True)
    for row in periods:
        row.update({"_source": "naver-finance", "_currency": "KRW", "_source_type": "secondary_aggregated_financial"})
    return {
        "periods": periods,
        "_source": "naver-finance",
        "_source_type": "secondary_aggregated_financial",
        "_limitations": ["publication date unavailable", "forecast columns discarded", "monetary unit is KRW 100m"],
        "_unit_scale": 100_000_000,
    }


def fetch_jp_kr_financials(symbol: str, trade_date: str) -> dict[str, Any]:
    market = detect_jp_kr_market(canonical_global_symbol(symbol))
    if market == "kr":
        try:
            naver = fetch_naver_financials(symbol, trade_date)
            if naver.get("periods"):
                return naver
        except requests.RequestException:
            pass
    try:
        return fetch_yahoo_financials(symbol, trade_date)
    except (requests.RequestException, ValueError, KeyError):
        return {"periods": [], "_source": "jp_kr_financials", "_limitations": ["all public financial adapters failed"]}


def fetch_tdnet_disclosures(symbol: str, trade_date: str, limit: int = 20) -> dict[str, Any]:
    canonical = canonical_global_symbol(symbol)
    if not canonical.endswith(".T"):
        return {"available": False, "rows": [], "_source": "tdnet-public-html"}
    response = _direct_session().get(
        f"https://www.release.tdnet.info/inbs/I_list_001_{trade_date}.html",
        headers={"Referer": "https://www.release.tdnet.info/inbs/I_main_00.html"},
        timeout=15,
    )
    if response.status_code == 404:
        return {"available": False, "rows": [], "_source": "tdnet-public-html", "reason": "date outside public retention"}
    response.raise_for_status()
    wanted = canonical.split(".", 1)[0]
    rows = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", response.text, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 4 or _plain(cells[1]).rstrip("0") != wanted.rstrip("0"):
            continue
        link = re.search(r'href="([^"]+\.pdf)"[^>]*>(.*?)</a>', cells[3], re.DOTALL)
        if not link:
            continue
        rows.append(
            {
                "title": _plain(link.group(2)),
                "published_at": trade_date,
                "time": _plain(cells[0]),
                "issuer": _plain(cells[2]),
                "url": f"https://www.release.tdnet.info/inbs/{link.group(1)}",
                "source": "TDnet",
                "source_type": "issuer_primary_disclosure_index",
                "category": "company_disclosure",
                "validation_status": "conditional",
            }
        )
    return {"available": bool(rows), "rows": rows[:limit], "_source": "tdnet-public-html"}


def fetch_fred_fx_rate(currency: str, trade_date: str) -> dict[str, Any]:
    series = {"JPY": "DEXJPUS", "KRW": "DEXKOUS"}.get(currency.upper())
    if not series:
        return {"available": False, "currency": currency}
    target = _requested_day(trade_date)
    response = _direct_session().get(
        "https://fred.stlouisfed.org/graph/fredgraph.csv",
        params={
            "id": series,
            "cosd": (target - timedelta(days=14)).isoformat(),
            "coed": target.isoformat(),
        },
        timeout=15,
    )
    response.raise_for_status()
    values = []
    for line in response.text.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) != 2 or parts[1] in {"", "."}:
            continue
        values.append((parts[0].replace("-", ""), float(parts[1])))
    if not values:
        return {"available": False, "currency": currency, "source": f"FRED:{series}"}
    effective_date, units_per_usd = values[-1]
    return {
        "available": True,
        "currency": currency.upper(),
        "requested_date": trade_date,
        "effective_date": effective_date,
        "units_per_usd": units_per_usd,
        "source": f"FRED:{series}",
    }
