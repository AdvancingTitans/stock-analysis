from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import requests

from .global_markets import fetch_fred_fx_rate
from .http import force_cn_encoding


def fetch_cny_rates() -> dict[str, float]:
    url = "https://hq.sinajs.cn/list=fx_susdcny,fx_shkdcny,fx_sjpycny,fx_skrwcny"
    response = requests.get(
        url,
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    force_cn_encoding(response)
    rates = {"CNY": 1.0}
    for line in response.text.splitlines():
        m = re.search(r'var hq_str_([^=]+)="([^"]*)"', line)
        if not m:
            continue
        code, payload = m.group(1), m.group(2)
        fields = payload.split(",")
        if len(fields) < 2:
            continue
        try:
            price = float(fields[1])
        except ValueError:
            continue
        if code == "fx_susdcny":
            rates["USD"] = price
        elif code == "fx_shkdcny":
            rates["HKD"] = price
        elif code == "fx_sjpycny":
            rates["JPY"] = price
        elif code == "fx_skrwcny":
            rates["KRW"] = price
    return rates


def fetch_global_fx_snapshot(trade_date: str) -> dict[str, dict[str, float | str | bool]]:
    """Fetch loginless USD/JPY and USD/KRW history without hiding date gaps."""
    result: dict[str, dict[str, float | str | bool]] = {}
    for currency in ("JPY", "KRW"):
        try:
            result[currency] = fetch_fred_fx_rate(currency, trade_date)
        except requests.RequestException as exc:
            result[currency] = {"available": False, "currency": currency, "reason": str(exc)}
    return result


def fetch_cny_rate_history(currency: str, trade_date: str, *, days: int = 180) -> dict[str, Any]:
    """Daily CNY value of one currency from loginless FRED reference series."""

    currency = currency.upper()
    if currency == "CNY":
        return {"available": True, "currency": currency, "rows": [], "source": "identity"}
    target = datetime.strptime(trade_date, "%Y%m%d")
    start = (target - timedelta(days=days)).strftime("%Y-%m-%d")
    end = target.strftime("%Y-%m-%d")

    def series(series_id: str) -> dict[str, float]:
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv",
            params={"id": series_id, "cosd": start, "coed": end},
            headers={"User-Agent": "stock-analysis public-data adapter"},
            timeout=20,
        )
        response.raise_for_status()
        result = {}
        for line in response.text.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) == 2 and parts[1] not in {"", "."}:
                result[parts[0].replace("-", "")] = float(parts[1])
        return result

    usd_cny = series("DEXCHUS")
    if currency == "USD":
        rows = [{"date": date, "cny_per_unit": value} for date, value in sorted(usd_cny.items())]
        return {"available": bool(rows), "currency": currency, "rows": rows, "source": "FRED:DEXCHUS"}
    units_per_usd_id = {"HKD": "DEXHKUS", "JPY": "DEXJPUS", "KRW": "DEXKOUS"}.get(currency)
    if not units_per_usd_id:
        return {"available": False, "currency": currency, "rows": [], "reason": "unsupported currency"}
    units_per_usd = series(units_per_usd_id)
    dates = sorted(set(usd_cny) & set(units_per_usd))
    rows = [
        {"date": date, "cny_per_unit": usd_cny[date] / units_per_usd[date]}
        for date in dates
        if units_per_usd[date] > 0
    ]
    return {
        "available": bool(rows),
        "currency": currency,
        "rows": rows,
        "source": f"FRED:DEXCHUS/{units_per_usd_id}",
    }


def attribute_price_and_fx(price_rows: list[dict[str, Any]], fx_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prices = {str(row.get("date") or "").replace("-", ""): float(row["close"]) for row in price_rows if row.get("close")}
    rates = {str(row.get("date") or "").replace("-", ""): float(row["cny_per_unit"]) for row in fx_rows if row.get("cny_per_unit")}
    dates = sorted(set(prices) & set(rates))
    attributed = []
    for previous, current in zip(dates, dates[1:]):
        local_return = prices[current] / prices[previous] - 1
        fx_return = rates[current] / rates[previous] - 1
        attributed.append({
            "date": current,
            "local_return_pct": local_return * 100,
            "fx_return_pct": fx_return * 100,
            "interaction_pct": local_return * fx_return * 100,
            "cny_return_pct": ((1 + local_return) * (1 + fx_return) - 1) * 100,
        })
    return {
        "available": len(attributed) >= 20,
        "aligned_days": len(attributed),
        "rows": attributed[-60:],
        "identity": "cny_return=(1+local_return)*(1+fx_return)-1",
        "reason": None if len(attributed) >= 20 else "aligned price/FX returns fewer than 20",
    }
