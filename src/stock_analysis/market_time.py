from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

A_SHARE_HOLIDAYS_2026 = {
    "20260101",
    "20260216", "20260217", "20260218", "20260219", "20260220", "20260221", "20260222",
    "20260404", "20260405", "20260406",
    "20260501", "20260502", "20260503", "20260504", "20260505",
    "20260619", "20260620", "20260621",
    "20260925", "20260926", "20260927",
    "20261001", "20261002", "20261003", "20261004", "20261005", "20261006", "20261007", "20261008",
}


@dataclass
class MarketSession:
    market: str
    label: str
    depth: str


def _is_trade_day(dt: datetime, market: str) -> bool:
    if market != "a":
        return dt.weekday() < 5
    return dt.weekday() < 5 and dt.strftime("%Y%m%d") not in A_SHARE_HOLIDAYS_2026


def resolve_trade_date(now: datetime, market: str = "a") -> str:
    dt = now
    while not _is_trade_day(dt, market):
        dt -= timedelta(days=1)
    if market == "a" and (dt.hour, dt.minute) < (9, 0):
        prev = dt - timedelta(days=1)
        while not _is_trade_day(prev, market):
            prev -= timedelta(days=1)
        return prev.strftime("%Y%m%d")
    return dt.strftime("%Y%m%d")


def detect_market_session(now: datetime, market: str = "a") -> MarketSession:
    hm = (now.hour, now.minute)
    if market in {"a", "hk"}:
        if (9, 0) <= hm < (9, 30):
            return MarketSession(market=market, label="早盘", depth="light")
        if (9, 30) <= hm < (11, 30):
            return MarketSession(market=market, label="盘中", depth="medium")
        if (11, 30) <= hm < (13, 0):
            return MarketSession(market=market, label="午间", depth="medium")
        if (13, 0) <= hm < (15, 0):
            return MarketSession(market=market, label="盘中", depth="medium")
        return MarketSession(market=market, label="盘后", depth="full")
    if (21, 30) <= hm or hm < (4, 0):
        return MarketSession(market=market, label="夜盘", depth="medium")
    return MarketSession(market=market, label="盘后", depth="full")
