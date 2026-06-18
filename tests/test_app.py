from datetime import datetime

from stock_analysis.app import _market_breadth, _normalize_trade_date, _pool_statistics, build_parser
from stock_analysis.market_time import detect_market_session


def test_report_format_defaults_to_session_aware_auto():
    args = build_parser().parse_args([])
    assert args.report_format == "auto"
    session = detect_market_session(datetime(2026, 6, 18, 9, 10), market="a")
    assert {"light": "summary", "medium": "key-points", "full": "full"}[session.depth] == "summary"


def test_explicit_date_option_is_supported():
    args = build_parser().parse_args(["--date", "20260618"])
    assert args.date == "20260618"


def test_trade_date_and_market_breadth_are_normalized():
    assert _normalize_trade_date("2026-06-18 12:05:41") == "20260618"
    breadth = _market_breadth(
        {
            "rows": [
                {"up_count": 10, "down_count": 5},
                {"up_count": 8, "down_count": 7},
            ]
        }
    )
    assert breadth == {
        "available": True,
        "up": 18,
        "down": 12,
        "ratio": 1.5,
        "scope": "行业板块成分汇总",
    }


def test_pool_statistics_use_actual_board_count_and_standard_blowup_rate():
    stats = _pool_statistics(
        {
            "zt": {
                "data": {
                    "pool": [
                        {"n": "A", "c": "1", "zttj": {"days": 7, "ct": 4}},
                        {"n": "B", "c": "2", "zttj": {"days": 1, "ct": 1}},
                    ]
                }
            },
            "dt": {"data": {"tc": 1, "pool": []}},
            "zb": {"data": {"pool": [{"n": "C", "c": "3"}]}},
        }
    )
    assert stats["first_board_count"] == 1
    assert stats["multi_board_count"] == 1
    assert stats["dt_count"] == 1
    assert stats["leaders"][0]["board_days"] == 4
    assert stats["blowup_ratio"] == 1 / 3
