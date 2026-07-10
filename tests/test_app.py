import json
from datetime import datetime
from unittest.mock import patch

import pytest

from stock_analysis.app import (
    _append_fund_profile_tables,
    _build_market_facts,
    _flow_snapshot,
    _market_breadth,
    _normalize_trade_date,
    _pool_statistics,
    _should_include_holdings,
    build_evidence,
    build_parser,
    run,
)
from stock_analysis.market_time import detect_market_session
from stock_analysis.models import Holding, QuoteData


@pytest.fixture(autouse=True)
def _keep_build_evidence_tests_offline(monkeypatch):
    monkeypatch.setattr(
        "stock_analysis.app.fetch_a_share_market_breadth",
        lambda _: {"available": False, "scope": "A股全市场个股", "reason": "test fixture"},
    )
    monkeypatch.setattr(
        "stock_analysis.app.fetch_a_index_price_volume",
        lambda _: {"available": False, "source": "tencent-kline", "missing": ["returns_60d"]},
    )


def test_report_format_defaults_to_session_aware_auto():
    args = build_parser().parse_args([])
    assert args.report_format == "auto"
    session = detect_market_session(datetime(2026, 6, 18, 9, 10), market="a")
    assert {"light": "summary", "medium": "key-points", "full": "full"}[session.depth] == "summary"


def test_explicit_date_option_is_supported():
    args = build_parser().parse_args(["--date", "20260618"])
    assert args.date == "20260618"


def test_screen_help_is_renderable():
    assert "roe_weighted:gt:8%" in build_parser().format_help()


def test_screen_cli_writes_one_evidence_file(monkeypatch, tmp_path, capsys):
    annual_rows = [
        {
            "SECURITY_CODE": "600000",
            "SECURITY_NAME_ABBR": "浦发银行",
            "DATATYPE": "2025年 年报",
            "SECURITY_TYPE": "A股",
            "QDATE": "2025Q4",
            "REPORTDATE": "2025-12-31 00:00:00",
            "NOTICE_DATE": "2026-03-01 00:00:00",
            "WEIGHTAVG_ROE": 9.15,
            "YSTZ": 9.2,
        }
    ]
    universe = {
        "complete": True,
        "reported_total": 1,
        "pages_fetched": 1,
        "unique_symbols": 1,
        "universe_as_of": "2026-07-10",
        "records": [{"symbol": "600000"}],
    }
    universe_file = tmp_path / "universe.json"
    universe_file.write_text(json.dumps(universe), encoding="utf-8")
    monkeypatch.setattr(
        "stock_analysis.app.fetch_a_share_annual_report_slice",
        lambda _: {"rows": annual_rows, "complete": True, "reported_total": 1, "expected_pages": 1, "pages_fetched": 1},
    )
    monkeypatch.chdir(tmp_path)

    assert run([
        "--market", "screen", "--fiscal-year", "2025", "--universe-file", str(universe_file),
        "--filter", "roe_weighted:gt:8", "--sort", "roe_weighted:desc", "--emit-evidence",
    ]) == 0

    assert "条件命中股票" in capsys.readouterr().out
    evidence = list(tmp_path.glob("screen_evidence_*.json"))
    assert len(evidence) == 1


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


def test_fund_profiles_are_added_to_market_evidence(monkeypatch):
    monkeypatch.setattr(
        "stock_analysis.app.fetch_fund_profile",
        lambda symbol, _: {
            "fundcode": symbol,
            "returns": {"近1年": 3.2},
            "scale": {"latest_size_yi": 10.0},
            "fees": {"front_end_rate_pct": 0.15},
            "managers": [{"name": "样本经理"}],
        },
    )

    from stock_analysis.app import _fund_profiles

    profiles = _fund_profiles({"details": [{"symbol": "512480", "market": "fund"}]}, "20260710")

    assert profiles["512480"]["returns"]["近1年"] == 3.2


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


def test_market_loads_memory_holdings_when_user_input_is_absent():
    with patch(
        "stock_analysis.trading.load_holdings_from_profile",
        return_value=[Holding(symbol="600519", asset_type="stock", market="a", quantity=10, buy_date="20260601")],
    ):
        assert _should_include_holdings("a", explicitly_requested=False) is True
    assert _should_include_holdings("hk", explicitly_requested=True) is True


def test_build_evidence_records_portfolio_exposure_when_holdings_exist():
    holding = Holding(symbol="600519", asset_type="stock", market="a", quantity=10, buy_date="20260601")
    quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        market="a",
        price=1200.0,
        change_pct=1.2,
        currency="CNY",
        trade_date="20260701",
        source="tencent",
    )
    with (
        patch("stock_analysis.portfolio.fetch_single_quote", return_value=quote),
        patch("stock_analysis.portfolio.fetch_stock_buy_reference", return_value={"close": 1000.0}),
        patch("stock_analysis.portfolio.moving_average_summary", return_value={"trend": "多头"}),
        patch("stock_analysis.portfolio.em_get", side_effect=Exception("skip boards")),
        patch("stock_analysis.app.fetch_a_indices", return_value=[]),
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch("stock_analysis.app.fetch_board_list", return_value={"rows": []}),
        patch("stock_analysis.app.fetch_limit_pools", return_value={"zt": {}, "dt": {}, "zb": {}}),
        patch("stock_analysis.app.fetch_a_share_financial_snapshot", return_value={}),
    ):
        evidence, _ = build_evidence(
            trade_date="20260701",
            market="a",
            session_label="盘中",
            include_holdings=True,
            holdings=[holding],
        )

    assert evidence.meta["portfolio_exposure"]["available"] is True
    assert evidence.meta["portfolio_exposure"]["holding_count"] == 1
    assert evidence.meta["portfolio_exposure"]["top3_ratio"] == 1.0


def test_flow_snapshot_preserves_market_and_board_flow_scopes():
    snapshot = _flow_snapshot(
        {
            "date": "2026-07-03",
            "主力净流入": "120000000",
            "_concept_in": '[{"name":"机器人","net":226.22,"leader":"丰光精密"}]',
            "_concept_out": '[{"name":"白酒","net":-41.22,"leader":"贵州茅台"}]',
            "_sector_in": '[["电机", 99.5]]',
            "_sector_out": '[["银行", -88.2]]',
            "_fallback_indicator": "concept_money_flow",
            "_indicator_note": "概念板块资金流，不等同于全市场主力资金净流入。",
            "_sector_note": "行业资金流为新浪行业流向参考。",
        }
    )

    assert snapshot["market_main_net"] == 120000000.0
    assert snapshot["scope_note"] == "概念板块资金流，不等同于全市场主力资金净流入。"
    assert snapshot["sector_note"] == "行业资金流为新浪行业流向参考。"
    assert snapshot["concept_in"][0]["name"] == "机器人"
    assert snapshot["concept_out"][0]["name"] == "白酒"
    assert snapshot["sector_in"][0]["name"] == "电机"
    assert snapshot["sector_out"][0]["name"] == "银行"


def test_build_market_facts_joins_boards_hotspots_flow_lhb_and_announcements():
    facts = _build_market_facts(
        trade_date="20260703",
        industry={
            "rows": [
                {"name": "电机", "change_pct": 5.6, "leader": "江苏雷利", "leader_change_pct": 14.3},
                {"name": "银行", "change_pct": -1.5, "leader": "样本银行", "leader_change_pct": -3.2},
            ]
        },
        concept={
            "rows": [
                {"name": "AI芯片", "change_pct": 4.2, "leader": "寒武纪", "leader_change_pct": 20.0},
                {"name": "白酒", "change_pct": -2.0, "leader": "贵州茅台", "leader_change_pct": -1.2},
            ]
        },
        fund_flow={
            "_concept_in": '[{"name":"AI芯片","net":12.3,"leader":"寒武纪"}]',
            "_concept_out": '[{"name":"白酒","net":-8.1,"leader":"贵州茅台"}]',
        },
        pools={
            "zt": {
                "data": {
                    "pool": [
                        {"n": "寒武纪", "c": "688256", "hybk": "AI芯片", "zttj": {"ct": 1}, "fund": 100000000},
                        {"n": "样本科技", "c": "000001", "hybk": "AI芯片", "zttj": {"ct": 1}, "fund": 10000000},
                    ]
                }
            }
        },
        sentiment={
            "chinese_news_items": [
                {
                    "title": "AI芯片概念多股涨停，海外新品发布刺激需求预期",
                    "source": "东方财富",
                    "publish_date": "20260703",
                    "url": "https://example.com/ai",
                }
            ],
        },
        lhb={"available": True, "rows": [{"name": "寒武纪", "buy_amount_wan": 5200}]},
        announcements={"available": True, "rows": [{"title": "样本股份中标50亿元新能源项目"}]},
    )

    assert facts["board_rankings"]["industry_top5"][0]["name"] == "电机"
    assert facts["board_rankings"]["concept_bottom5"][0]["name"] == "白酒"
    assert facts["hotspots_24h"][0]["topic"] == "AI芯片"
    assert facts["hotspots_24h"][0]["limit_up_count"] == 2
    assert facts["money_flow"]["concept_in"][0]["name"] == "AI芯片"
    assert facts["lhb_aftermarket"]["rows"][0]["name"] == "寒武纪"
    assert facts["announcements"]["rows"][0]["title"].startswith("样本股份")


def test_board_rankings_do_not_label_positive_rows_as_decliners():
    facts = _build_market_facts(
        trade_date="20260703",
        industry={
            "rows": [
                {"name": "电机", "change_pct": 5.6},
                {"name": "银行", "change_pct": 1.5},
            ]
        },
        concept={
            "rows": [
                {"name": "AI芯片", "change_pct": 4.2},
                {"name": "白酒", "change_pct": 0.2},
            ]
        },
        fund_flow={},
        pools={},
        sentiment={},
        lhb={"available": False, "rows": []},
        announcements={"available": False, "rows": []},
    )

    assert facts["board_rankings"]["industry_bottom5"] == []
    assert facts["board_rankings"]["concept_bottom5"] == []


def test_stock_market_renders_deterministic_single_symbol_view(capsys):
    with patch(
        "stock_analysis.app.fetch_single_quote",
        return_value=QuoteData(
            symbol="600519",
            name="贵州茅台",
            market="a",
            price=1240.5,
            change_pct=-1.25,
            previous_close=1256.2,
            open_price=1250.0,
            high=1260.0,
            low=1238.0,
            volume=1200000,
            turnover=1488600000,
            currency="CNY",
            trade_date="20260618",
            source="tencent",
        ),
    ), patch(
        "stock_analysis.app.fetch_a_share_order_book_snapshot",
        return_value={
            "available": True,
            "source": "sina",
            "trade_date": "20260618",
            "quote_time": "15:34:59",
            "best_bid": 1240.49,
            "best_ask": 1240.50,
            "spread": 0.01,
            "spread_bps": 0.0806,
            "bid1_lots": 120.0,
            "ask1_lots": 80.0,
            "limitations": ["仅为盘口快照，非逐笔成交。"],
        },
    ), patch(
        "stock_analysis.app.fetch_a_share_financial_snapshot",
        return_value={"available": False, "periods": [], "gaps": []},
    ):
        assert run(["--market", "stock", "--symbol", "600519", "--date", "20260618"]) == 0

    output = capsys.readouterr().out
    assert "# 单股速览（20260618）" in output
    assert "| 600519 | 贵州茅台 | A股 | 1,240.50 CNY | -1.25% | 20260618 |" in output
    assert "## A股盘口与交易成本快照" in output
    assert "| 1,240.49 | 1,240.50 | 0.01 | 0.0806 | 20260618 15:34:59 |" in output
    assert "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。" in output


def test_build_evidence_records_stock_microstructure_and_cost_proxy_for_a_share_holdings():
    quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        market="a",
        price=1182.19,
        change_pct=-1.43,
        turnover=None,
        turnover_rate=0.27,
        currency="CNY",
        trade_date="20260709",
        source="tencent",
    )
    holding = Holding(symbol="600519", asset_type="stock", market="a", quantity=100, buy_date="20260601")
    with (
        patch("stock_analysis.portfolio.fetch_single_quote", return_value=quote),
        patch("stock_analysis.portfolio.fetch_stock_buy_reference", return_value={"price": 1200.0, "date": "20260601"}),
        patch("stock_analysis.app.fetch_a_indices", return_value=[]),
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch("stock_analysis.app.fetch_board_list", return_value={"rows": []}),
        patch("stock_analysis.app.fetch_limit_pools", return_value={"zt": {}, "dt": {}, "zb": {}}),
        patch("stock_analysis.app.fetch_a_share_financial_snapshot", return_value={}),
        patch(
            "stock_analysis.app.fetch_a_share_order_book_snapshot",
            return_value={
                "available": True,
                "source": "sina",
                "trade_date": "20260709",
                "best_bid": 1182.19,
                "best_ask": 1182.2,
                "spread": 0.01,
                "spread_bps": 0.0846,
                "turnover_cny": 4_035_216_946,
            },
        ),
    ):
        evidence, _ = build_evidence("20260709", "daily", "盘后", include_holdings=True, holdings=[holding])

    assert evidence.meta["stock_microstructure"]["600519"]["spread_bps"] == 0.0846
    assert evidence.meta["stock_trading_costs"]["600519"]["liquidity_bucket"] == "very_deep"
    assert evidence.meta["stock_trading_costs"]["600519"]["slippage_model"] == "daily_rebalance_proxy"
    assert evidence.meta["stock_trading_costs"]["600519"]["daily_turnover_cny"] == 4_035_216_946
    assert "ETF/指数期货对冲成本未建模" in evidence.meta["stock_trading_costs"]["600519"]["limitations"]


def test_stock_market_renders_a_share_financial_snapshot(capsys):
    with patch(
        "stock_analysis.app.fetch_single_quote",
        return_value=QuoteData(
            symbol="600519",
            name="贵州茅台",
            market="a",
            price=1240.5,
            currency="CNY",
            trade_date="20260618",
            source="tencent",
        ),
    ), patch(
        "stock_analysis.app.fetch_a_share_financial_snapshot",
        return_value={
            "available": True,
            "periods": [
                {
                    "period_label": "2026Q1",
                    "report_date": "2026-03-31",
                    "notice_date": "2026-04-29",
                    "roe_weighted": 10.57,
                    "gross_margin": 91.2,
                    "debt_asset_ratio": 12.12,
                    "operating_cash_flow": 26_910_000_000,
                    "free_cash_flow_lite": 26_305_000_000,
                }
            ],
            "forecasts": {"available": False, "rows": []},
            "earnings_flash": {"available": False, "rows": []},
            "limitations": ["业绩预告/快报仅在公司披露时存在；无返回不代表公司没有业绩变化。"],
            "gaps": ["业绩预告/快报仅在公司披露时存在"],
        },
    ), patch(
        "stock_analysis.app.fetch_a_share_order_book_snapshot",
        return_value={"available": False},
    ):
        assert run(["--market", "stock", "--symbol", "600519", "--date", "20260618"]) == 0

    output = capsys.readouterr().out
    assert "## A股财务证据快照" in output
    assert "| 2026Q1 | 2026-03-31 | +10.57% | +91.20% | +12.12% | 269.10亿 | 263.05亿 |" in output
    assert "业绩预告/快报仅在公司披露时存在" in output


def test_fund_market_renders_deterministic_fund_view(capsys):
    with (
        patch(
            "stock_analysis.app.fetch_fund_estimate",
            return_value={
                "name": "招商中证白酒指数",
                "estimate_nav": 1.2345,
                "estimate_change_pct": 0.56,
                "date": "2026-06-18",
                "_source": "天天基金实时估值",
            },
        ),
        patch(
            "stock_analysis.app.fetch_fund_holdings",
            return_value={
                "holdings": [
                    {"code": "600519", "name": "贵州茅台", "weight_pct": 14.2},
                ]
            },
        ),
        patch(
            "stock_analysis.app.fetch_fund_holding_quotes",
            return_value={"600519": QuoteData(symbol="600519", price=1240.5, change_pct=-1.25)},
        ),
        patch("stock_analysis.app.fetch_fund_profile", return_value={}),
        patch("stock_analysis.app.is_historical_date", return_value=False),
    ):
        assert run(["--market", "fund", "--fund", "161725", "--date", "20260618"]) == 0

    output = capsys.readouterr().out
    assert "# 基金速览（20260618）" in output
    assert "| 161725 | 招商中证白酒指数 | 1.23 CNY | +0.56% | 20260618 |" in output
    assert "| 600519 | 贵州茅台 | 14.20% | 1,240.50 | -1.25% |" in output


def test_fund_market_renders_public_profile_enrichment(capsys):
    with (
        patch(
            "stock_analysis.app.fetch_fund_estimate",
            return_value={
                "name": "易方达优质精选混合(QDII)",
                "nav": 1.2345,
                "date": "2026-06-18",
                "_source": "天天基金实时估值",
            },
        ),
        patch("stock_analysis.app.fetch_fund_holdings", return_value={"holdings": []}),
        patch("stock_analysis.app.fetch_fund_holding_quotes", return_value={}),
        patch(
            "stock_analysis.app.fetch_fund_profile",
            return_value={
                "returns": {"近1月": -12.79, "近3月": -20.24, "近6月": -25.77, "近1年": -19.87},
                "fees": {"front_end_source_rate_pct": 1.5, "front_end_rate_pct": 0.15},
                "scale": {"latest_size_yi": 95.44, "asof": "2026-03-31", "mom": "-16.17%"},
                "performance_evaluation": {"average_score": 77.75, "metrics": {"收益率": 80.0}},
                "managers": [
                    {
                        "name": "张坤",
                        "work_time": "13年又280天",
                        "fund_size": "416.72亿(4只基金)",
                        "score": 65.62,
                        "tenure_return_pct": 295.6454,
                    }
                ],
            },
        ),
    ):
        assert run(["--market", "fund", "--fund", "110011", "--date", "20260618"]) == 0

    output = capsys.readouterr().out
    assert "## 长期业绩与费率" in output
    assert "| 近1年 | -19.87% |" in output
    assert "| 前端申购费 | 1.50% | 0.15% |" in output
    assert "| 最新规模 | 95.44亿 | 2026-03-31 | -16.17% |" in output
    assert "## 基金经理" in output
    assert "| 张坤 | 13年又280天 | 416.72亿(4只基金) | 65.62 | +295.65% |" in output


def test_historical_fund_market_prefers_requested_date_nav(capsys):
    with (
        patch(
            "stock_analysis.app.fetch_fund_estimate",
            return_value={
                "name": "半导体ETF国联安",
                "estimate_nav": 1.3742,
                "estimate_change_pct": 1.0,
                "date": "2026-07-09",
                "_source": "天天基金实时估值",
            },
        ),
        patch(
            "stock_analysis.app.fetch_fund_nav_quote",
            return_value={
                "fundcode": "512480",
                "date": "2026-07-08",
                "nav": 1.3447,
                "change_pct": 3.06,
                "_source": "东方财富历史净值",
            },
            create=True,
        ),
        patch("stock_analysis.app.fetch_fund_holdings", return_value={"holdings": []}),
        patch("stock_analysis.app.fetch_fund_holding_quotes", return_value={}),
        patch("stock_analysis.app.fetch_fund_profile", return_value={}),
    ):
        assert run(["--market", "fund", "--fund", "512480", "--date", "20260708"]) == 0

    output = capsys.readouterr().out
    assert "| 512480 | 半导体ETF国联安 | 1.34 CNY | +3.06% | 20260708 |" in output
    assert "20260709" not in output


def test_fund_profile_tables_skip_empty_public_profile():
    lines = []

    _append_fund_profile_tables(
        lines,
        {
            "returns": {},
            "fees": {
                "front_end_source_rate_pct": None,
                "front_end_rate_pct": None,
                "min_purchase_cny": None,
            },
            "scale": {},
            "performance_evaluation": {"average_score": None, "metrics": {}},
            "managers": [],
        },
    )

    assert lines == []


def test_m1_remains_available_when_indices_exist_but_breadth_is_missing():
    with (
        patch("stock_analysis.app.fetch_a_indices") as fetch_a_indices,
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch(
            "stock_analysis.app.fetch_board_list",
            side_effect=[{"rows": []}, {"rows": []}],
        ) as fetch_board_list,
        patch(
            "stock_analysis.app.fetch_limit_pools",
            return_value={"zt": {}, "dt": {}, "zb": {}},
        ),
    ):
        fetch_a_indices.return_value = [
            {
                "f12": "000001",
                "f14": "上证指数",
                "f2": 3000,
                "f3": 1.0,
                "f4": 30,
                "f6": 1,
                "_source_date": "20260618",
                "_source": "test",
            }
        ]

        evidence, _ = build_evidence("20260618", "a", "午间", False)

    assert evidence.modules["M1"]["available"] is True
    assert evidence.modules["M1"]["breadth"]["available"] is False
    assert evidence.modules["M2"]["available"] is False
    assert fetch_board_list.call_count == 2


def test_a_index_payload_preserves_volume_when_turnover_is_missing():
    with (
        patch(
            "stock_analysis.app.fetch_a_indices",
            return_value=[
                {
                    "f12": "000300",
                    "f14": "沪深300",
                    "f2": 4842.17,
                    "f3": 0.62,
                    "f4": 29.87,
                    "f5": 301067568.0,
                    "f6": None,
                    "_source_date": "20260703",
                    "_source": "tencent-kline",
                }
            ],
        ),
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch("stock_analysis.app.fetch_board_list", side_effect=[{"rows": []}, {"rows": []}]),
        patch("stock_analysis.app.fetch_limit_pools", return_value={"zt": {}, "dt": {}, "zb": {}}),
    ):
        evidence, _ = build_evidence("20260703", "a", "盘后", False)

    row = evidence.modules["M1"]["a_indices"][0]
    assert row["symbol"] == "000300"
    assert row["turnover"] is None
    assert row["volume"] == 301067568.0


def test_m4_remains_available_when_risk_pool_returns_counts_without_rows():
    with (
        patch("stock_analysis.app.fetch_a_indices", return_value=[]),
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch("stock_analysis.app.fetch_board_list", side_effect=[{"rows": []}, {"rows": []}]),
        patch(
            "stock_analysis.app.fetch_limit_pools",
            return_value={
                "zt": {"data": {"tc": 0, "pool": []}},
                "dt": {"data": {"tc": 2, "pool": []}},
                "zb": {"data": {"tc": 0, "pool": []}},
            },
        ),
    ):
        evidence, _ = build_evidence("20260618", "a", "午间", False)

    assert evidence.modules["M4"]["available"] is True
    assert evidence.modules["M4"]["dt_count"] == 2
    assert "market_public_pulse" not in evidence.meta
    assert "chinese_community_items" not in evidence.meta


def test_m3_remains_available_when_limit_pool_returns_counts_without_rows():
    with (
        patch("stock_analysis.app.fetch_a_indices", return_value=[]),
        patch("stock_analysis.app.fetch_hk_indices", return_value=[]),
        patch("stock_analysis.app.fetch_us_indices", return_value=[]),
        patch("stock_analysis.app.fetch_northbound_flow", return_value={}),
        patch("stock_analysis.app.fetch_fund_flow", return_value={}),
        patch(
            "stock_analysis.app.fetch_board_list",
            side_effect=[
                {"rows": [{"name": "电机", "change_pct": 5.6, "up_count": 24, "down_count": 2}]},
                {"rows": []},
            ],
        ),
        patch(
            "stock_analysis.app.fetch_limit_pools",
            return_value={
                "zt": {"data": {"tc": 108, "pool": []}},
                "dt": {"data": {"tc": 19, "pool": []}},
                "zb": {"data": {"tc": 52, "pool": []}},
            },
        ),
    ):
        evidence, _ = build_evidence("20260703", "a", "盘后", False)

    assert evidence.modules["M3"]["available"] is True
    assert evidence.modules["M3"]["zt_count"] == 108
    assert "涨停池 108 家" in evidence.modules["M3"]["summary"]
    assert evidence.modules["M6"]["available"] is True
