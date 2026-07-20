"""Dependency-free JPX/KRX session calendar snapshots.

The holiday sets are generated from exchange_calendars 4.13.2 and are bounded
on purpose.  A date outside the verified window is unavailable rather than a
weekday guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

CALENDAR_SOURCE = "exchange_calendars@4.13.2"
CALENDAR_VALID_FROM = "20240101"
CALENDAR_VALID_THROUGH = "20271231"

_JP_CLOSED = {
    "20240101", "20240102", "20240103", "20240108", "20240212", "20240223",
    "20240320", "20240429", "20240503", "20240506", "20240715", "20240812",
    "20240916", "20240923", "20241014", "20241104", "20241231", "20250101",
    "20250102", "20250103", "20250113", "20250211", "20250224", "20250320",
    "20250429", "20250505", "20250506", "20250721", "20250811", "20250915",
    "20250923", "20251013", "20251103", "20251124", "20251231", "20260101",
    "20260102", "20260112", "20260211", "20260223", "20260320", "20260429",
    "20260504", "20260505", "20260506", "20260720", "20260811", "20260921",
    "20260922", "20260923", "20261012", "20261103", "20261123", "20261231",
    "20270101", "20270111", "20270211", "20270223", "20270322", "20270429",
    "20270503", "20270504", "20270505", "20270719", "20270811", "20270920",
    "20270923", "20271011", "20271103", "20271123", "20271231",
}

_KR_CLOSED = {
    "20240101", "20240209", "20240212", "20240301", "20240410", "20240501",
    "20240506", "20240515", "20240606", "20240815", "20240916", "20240917",
    "20240918", "20241001", "20241003", "20241009", "20241225", "20241231",
    "20250101", "20250127", "20250128", "20250129", "20250130", "20250303",
    "20250501", "20250505", "20250506", "20250603", "20250606", "20250815",
    "20251003", "20251006", "20251007", "20251008", "20251009", "20251225",
    "20251231", "20260101", "20260216", "20260217", "20260218", "20260302",
    "20260501", "20260505", "20260525", "20260817", "20260924", "20260925",
    "20261005", "20261009", "20261225", "20261231", "20270101", "20270208",
    "20270209", "20270301", "20270505", "20270513", "20270816", "20270914",
    "20270915", "20270916", "20271004", "20271011", "20271227", "20271231",
}


@dataclass(frozen=True)
class SessionHours:
    open: time
    close: time
    break_start: time | None = None
    break_end: time | None = None


def _normalized_market(market: str) -> str:
    value = market.lower().replace("_market", "")
    if value not in {"jp", "kr"}:
        raise ValueError(f"unsupported calendar market: {market}")
    return value


def is_session_day(value: date | datetime | str, market: str) -> bool:
    market = _normalized_market(market)
    if isinstance(value, str):
        key = value.replace("-", "")
        day = datetime.strptime(key, "%Y%m%d").date()
    else:
        day = value.date() if isinstance(value, datetime) else value
        key = day.strftime("%Y%m%d")
    if not CALENDAR_VALID_FROM <= key <= CALENDAR_VALID_THROUGH:
        raise ValueError(
            f"{market} calendar only verified for {CALENDAR_VALID_FROM}-{CALENDAR_VALID_THROUGH}"
        )
    closed = _JP_CLOSED if market == "jp" else _KR_CLOSED
    return day.weekday() < 5 and key not in closed


def previous_or_same_session(value: date | datetime | str, market: str) -> date:
    if isinstance(value, str):
        day = datetime.strptime(value.replace("-", ""), "%Y%m%d").date()
    else:
        day = value.date() if isinstance(value, datetime) else value
    for _ in range(14):
        if is_session_day(day, market):
            return day
        day -= timedelta(days=1)
    raise ValueError(f"cannot resolve {market} session near {value}")


def session_hours(value: date | datetime | str, market: str) -> SessionHours:
    market = _normalized_market(market)
    if not is_session_day(value, market):
        raise ValueError(f"not a {market} trading session: {value}")
    if market == "kr":
        return SessionHours(open=time(9), close=time(15, 30))
    key = value.replace("-", "") if isinstance(value, str) else (
        value.date() if isinstance(value, datetime) else value
    ).strftime("%Y%m%d")
    close = time(15, 30) if key >= "20241105" else time(15)
    return SessionHours(open=time(9), close=close, break_start=time(11, 30), break_end=time(12, 30))


def calendar_metadata(market: str) -> dict[str, str]:
    return {
        "market": _normalized_market(market),
        "source": CALENDAR_SOURCE,
        "valid_from": CALENDAR_VALID_FROM,
        "valid_through": CALENDAR_VALID_THROUGH,
    }
