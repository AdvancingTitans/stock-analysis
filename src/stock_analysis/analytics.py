from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any

import requests

from .http import safe_float


def secid_for_symbol(symbol: str, market: str) -> str:
    if market == "a":
        exchange = "1" if symbol.startswith(("5", "6", "9")) else "0"
        return f"{exchange}.{symbol}"
    if market == "hk":
        raw = symbol.replace(".HK", "").lstrip("0") or "0"
        return f"116.{raw.zfill(5)}"
    return f"105.{symbol}"


def fetch_recent_closes(symbol: str, market: str, limit: int = 30) -> list[float]:
    if market == "a":
        closes = _fetch_a_closes_baidu(symbol, limit)
        if closes:
            return closes
    elif market == "us":
        closes = _fetch_us_closes_sina(symbol, limit)
        if closes:
            return closes
    elif market == "hk":
        closes = _fetch_global_closes_yahoo(symbol, limit)
        if closes:
            return closes

    secid = secid_for_symbol(symbol, market)
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=1&beg=0&end=20500101&lmt={limit}"
    )
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers={"Referer": "https://quote.eastmoney.com/"}, timeout=10)
    response.raise_for_status()
    data = response.json()
    rows = ((data.get("data") or {}).get("klines") or [])
    closes: list[float] = []
    for row in rows:
        parts = str(row).split(",")
        if len(parts) >= 3:
            close = safe_float(parts[2])
            if close is not None:
                closes.append(close)
    return closes


def _direct_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _fetch_a_closes_baidu(symbol: str, limit: int) -> list[float]:
    response = _direct_session().get(
        "https://finance.pae.baidu.com/selfselect/getstockquotation",
        params={
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": symbol,
            "start_time": "",
            "ktype": "1",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        },
        timeout=10,
    )
    response.raise_for_status()
    market_data = ((response.json().get("Result") or {}).get("newMarketData") or {})
    keys = list(market_data.get("keys") or [])
    try:
        close_index = keys.index("close")
    except ValueError:
        return []
    closes = []
    for row in str(market_data.get("marketData") or "").split(";"):
        fields = row.split(",")
        if close_index < len(fields):
            close = safe_float(fields[close_index])
            if close is not None:
                closes.append(close)
    return closes[-limit:]


def _fetch_us_closes_sina(symbol: str, limit: int) -> list[float]:
    response = _direct_session().get(
        "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var/US_MinKService.getDailyK",
        params={"symbol": symbol.upper(), "num": max(limit, 30)},
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    match = re.search(r"\((\[.+\])\)", response.text)
    if not match:
        return []
    rows = json.loads(match.group(1))
    closes = [safe_float(row.get("c")) for row in rows]
    return [close for close in closes if close is not None][-limit:]


def _fetch_global_closes_yahoo(symbol: str, limit: int) -> list[float]:
    response = _direct_session().get(
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"interval": "1d", "range": "3mo"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = ((response.json().get("chart") or {}).get("result") or [{}])[0]
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [safe_float(value) for value in quotes.get("close") or []]
    return [close for close in closes if close is not None][-limit:]


def moving_average_summary(symbol: str, market: str) -> dict[str, Any]:
    try:
        closes = fetch_recent_closes(symbol, market)
    except Exception:
        return {"ma5": None, "ma10": None, "ma20": None, "trend": None}
    if len(closes) < 20:
        return {"ma5": None, "ma10": None, "ma20": None, "trend": None}
    ma5 = mean(closes[-5:])
    ma10 = mean(closes[-10:])
    ma20 = mean(closes[-20:])
    latest = closes[-1]
    if latest > ma5 > ma10 > ma20:
        trend = "多头"
    elif latest < ma5 < ma10 < ma20:
        trend = "空头"
    else:
        trend = "震荡"
    return {"ma5": ma5, "ma10": ma10, "ma20": ma20, "trend": trend}
