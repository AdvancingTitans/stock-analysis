from stock_analysis import market_core


def test_northbound_rejects_incomplete_or_abnormal_series(monkeypatch):
    monkeypatch.setattr(market_core, "nearest_trade_date", lambda: "20260710")
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        market_core,
        "_fetch_raw",
        lambda *args, **kwargs: '{"time":["09:10","09:11"],"hgt":[0.0,0.1],"sgt":[364.0,365.0]}',
    )

    result = market_core.fetch_northbound_flow_snapshot("20260710")

    assert result["available"] is False
    assert result["_quality_status"] == "unavailable"
    assert "total_yi" not in result
    assert "points=2" in result["_error"]


def test_northbound_requires_current_day_and_validated_cache(monkeypatch):
    monkeypatch.setattr(market_core, "nearest_trade_date", lambda: "20260710")
    stale_cache = {"total_yi": 999.0, "_validation_version": 1}
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: stale_cache)
    monkeypatch.setattr(
        market_core,
        "_fetch_raw",
        lambda *args, **kwargs: '{"time":[],"hgt":[],"sgt":[]}',
    )

    historical = market_core.fetch_northbound_flow_snapshot("20260709")
    current = market_core.fetch_northbound_flow_snapshot("20260710")

    assert historical["available"] is False
    assert "历史日期" in historical["_error"]
    assert current["available"] is False
    assert "total_yi" not in current


def test_stock_fund_flow_retries_error_payload_before_marking_gap(monkeypatch):
    responses = iter(
        [
            {"_error": "connection reset"},
            {"data": {"name": "样本股", "klines": ["2026-07-10,1,2,3,4,5,6"]}},
        ]
    )
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "fetch_json", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(market_core.time, "sleep", lambda _: None)

    result = market_core.fetch_stock_fund_flow_daily("600519", "20260710", limit=1)

    assert result["rows"][0]["date"] == "2026-07-10"
    assert "重试" in result["_source_note"]


def test_fund_flow_merges_sector_fallback_when_ths_concept_flow_is_available(monkeypatch):
    monkeypatch.setattr(
        market_core,
        "fetch_ths_concept_money_flow_snapshot",
        lambda _date: {
            "date": "2026-07-03",
            "_source": "同花顺概念资金流",
            "_concept_in": '[{"name":"机器人概念","net":183.96,"leader":"丰光精密"}]',
            "_concept_out": '[{"name":"长安汽车概念","net":-41.22,"leader":"迈赫股份"}]',
        },
    )
    monkeypatch.setattr(
        market_core,
        "fetch_sina_sector_money_flow_snapshot",
        lambda _date: {
            "date": "2026-07-03",
            "_source": "新浪财经资金流页面行业流向",
            "_sector_in": '[["电机", 99.5], ["贵金属", 88.2]]',
            "_sector_out": '[["银行", -77.1]]',
        },
    )

    result = market_core.get_fund_flow("20260703")

    assert result["_concept_in"]
    assert result["_concept_out"]
    assert result["_sector_in"]
    assert result["_sector_out"]
    assert "同花顺概念资金流" in result["_source"]
    assert "新浪财经资金流页面行业流向" in result["_source"]


def test_lhb_aftermarket_ignores_legacy_empty_cache_and_uses_datacenter_rows(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: {"available": False, "rows": []})
    saved = {}
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: saved.setdefault("payload", args[-1]))
    monkeypatch.setattr(
        market_core,
        "eastmoney_datacenter",
        lambda *args, **kwargs: [
            {
                "TRADE_DATE": "2026-07-03 00:00:00",
                "SECURITY_CODE": "002056",
                "SECURITY_NAME_ABBR": "横店东磁",
                "CLOSE_PRICE": 32.82,
                "CHANGE_RATE": 7.045,
                "TOTAL_BUY": 1018191968.29,
                "TOTAL_SELL": 468170764.44,
                "TOTAL_NET": 550021203.85,
            }
        ],
    )

    result = market_core.fetch_lhb_aftermarket("20260703", limit=5)

    assert result["available"] is True
    assert result["_cache_version"] >= 2
    assert result["rows"][0]["name"] == "横店东磁"
    assert result["rows"][0]["buy_amount_wan"] == 101819.196829
    assert saved["payload"]["available"] is True


def test_lhb_aftermarket_falls_back_to_recent_trade_date(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)

    def fake_datacenter(_report_name, *, filter_str="", **_kwargs):
        if "2026-07-04" in filter_str:
            return []
        if "2026-07-03" in filter_str:
            return [
                {
                    "TRADE_DATE": "2026-07-03 00:00:00",
                    "SECURITY_CODE": "600000",
                    "SECURITY_NAME_ABBR": "样本股份",
                    "CLOSE_PRICE": 10.5,
                    "CHANGE_RATE": 10.0,
                    "BILLBOARD_BUY_AMT": 200000000.0,
                    "BILLBOARD_SELL_AMT": 100000000.0,
                    "BILLBOARD_NET_AMT": 100000000.0,
                }
            ]
        return []

    monkeypatch.setattr(market_core, "eastmoney_datacenter", fake_datacenter)

    result = market_core.fetch_lhb_aftermarket("20260704", limit=5)

    assert result["available"] is True
    assert result["date"] == "2026-07-03"
    assert result["requested_date"] == "2026-07-04"
    assert result["fallback_reason"] == "requested=2026-07-04; lhb_date=2026-07-03"


def test_important_announcements_fallback_to_market_keywords(monkeypatch):
    calls = []

    def fake_news(keyword, size=10, lang="zh-CN", news_type=2):
        calls.append(keyword)
        if keyword == "重大合同":
            return {
                "data": [
                    {
                        "title": "样本股份：中标50亿元新能源项目",
                        "publish_time": "2026-07-03 09:30:00",
                        "url": "https://example.com/notice",
                    }
                ]
            }
        return {"data": []}

    monkeypatch.setattr(market_core, "futu_news_search", fake_news)

    result = market_core.fetch_important_announcements("20260703", candidates=[], limit=8)

    assert "重大合同" in calls
    assert result["available"] is True
    assert result["rows"][0]["title"] == "样本股份：中标50亿元新能源项目"


def test_company_disclosures_classify_governance_and_capital_allocation(monkeypatch):
    monkeypatch.setattr(
        market_core,
        "futu_news_search",
        lambda *args, **kwargs: {
            "data": [
                {"title": "贵州茅台：2025年度分红实施公告", "publish_time": "2026-07-01 09:30:00", "url": "https://example.com/dividend"},
                {"title": "贵州茅台关于董事会换届的公告", "publish_time": "2026-06-20 09:30:00", "url": "https://example.com/board"},
                {"title": "贵州茅台产品市场新闻", "publish_time": "2026-06-18 09:30:00", "url": "https://example.com/news"},
                {"title": "其他公司年度分红公告", "publish_time": "2026-06-18 09:30:00", "url": "https://example.com/other"},
            ]
        },
    )

    result = market_core.fetch_company_disclosures("600519", "贵州茅台", "20260710", limit=10)

    assert result["available"] is True
    assert {row["category"] for row in result["rows"]} == {"capital_allocation", "governance"}
    assert all(row["source_type"] == "public_announcement_index" for row in result["rows"])
    assert all(row["url"] for row in result["rows"])


def test_limit_pool_ignores_legacy_empty_cache_and_saves_versioned_payload(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: {"data": {"pool": []}})
    saved = {}
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: saved.setdefault("payload", args[-1]))
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda *args, **kwargs: {"data": {"qdate": "20260703", "tc": 1, "pool": [{"n": "样本股份"}]}},
    )

    result = market_core.get_zt_pool("20260703")

    assert result["data"]["tc"] == 1
    assert result["_cache_version"] >= 2
    assert saved["payload"]["_cache_version"] >= 2


def test_combined_news_search_includes_eastmoney_fast_source(monkeypatch):
    monkeypatch.setattr(market_core, "futu_news_search", lambda *args, **kwargs: {"source": "futu_news", "data": []})
    monkeypatch.setattr(market_core, "futu_stock_feed", lambda *args, **kwargs: {"source": "futu_feed", "data": []})
    monkeypatch.setattr(market_core, "_normalize_futu_feed", lambda *args, **kwargs: {"source": "futu_feed", "data": []})
    monkeypatch.setattr(market_core, "sina_roll_news", lambda *args, **kwargs: {"source": "sina_roll", "data": []})
    monkeypatch.setattr(
        market_core,
        "eastmoney_fast_news",
        lambda *args, **kwargs: {
            "source": "eastmoney_fast",
            "data": [
                {
                    "title": "AI芯片概念多股涨停",
                    "publish_time": "2026-07-03 14:30:00",
                    "source": "东方财富",
                }
            ],
        },
    )

    result = market_core.combined_news_search("AI芯片", size=3, lang="zh-CN", date_str="20260703")

    assert result["source"] == "eastmoney_fast"
    assert result["all_count"] == 1
    assert result["source_counts"] == {"eastmoney_fast": 1}
    assert result["data"][0]["title"] == "AI芯片概念多股涨停"
