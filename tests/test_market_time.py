from datetime import datetime

from stock_analysis.market_time import detect_market_session, resolve_trade_date


def test_detect_market_session_for_a_share_morning():
    session = detect_market_session(datetime(2026, 6, 18, 9, 10), market="a")
    assert session.market == "a"
    assert session.label == "早盘"
    assert session.depth == "light"


def test_detect_market_session_for_a_share_aftermarket():
    session = detect_market_session(datetime(2026, 6, 18, 15, 30), market="a")
    assert session.label == "盘后"
    assert session.depth == "full"


def test_resolve_trade_date_rolls_back_non_trade_day():
    trade_date = resolve_trade_date(datetime(2026, 6, 21, 10, 0), market="a")
    assert trade_date == "20260618"


def test_detect_market_session_for_us_night_session():
    session = detect_market_session(datetime(2026, 6, 18, 22, 0), market="us")
    assert session.label == "夜盘"
    assert session.depth == "medium"
