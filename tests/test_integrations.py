from datetime import datetime, timedelta

from stock_analysis import integrations, market_core


def test_get_index_ignores_cached_rows_missing_configured_index(monkeypatch):
    monkeypatch.setattr(
        market_core,
        "cache_load",
        lambda *args, **kwargs: {"data": [{"f12": "000001", "f6": 1.0}]},
    )
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda *args, **kwargs: {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "上证指数", "f6": 1.0},
                    {"f12": "000300", "f14": "沪深300", "f6": 2.0},
                ]
            }
        },
    )
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)

    rows = market_core.get_index("20260703")

    assert any(row.get("f12") == "000300" for row in rows)


def test_strict_market_breadth_requires_all_clist_pages(monkeypatch):
    responses = iter(
        [
            {"data": {"total": 3, "diff": [{"f3": 1.2}, {"f3": -0.4}]}},
            {"data": {"total": 3, "diff": [{"f3": 0.0}]}},
        ]
    )
    monkeypatch.setattr(market_core, "nearest_trade_date", lambda: "20260710")
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "fetch_json", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(market_core.time, "sleep", lambda _: None)

    breadth = market_core.fetch_a_share_market_breadth("20260710", page_size=2)

    assert breadth["available"] is True
    assert breadth["up"] == 1
    assert breadth["down"] == 1
    assert breadth["flat"] == 1
    assert breadth["pages_fetched"] == 2
    assert breadth["valid_rows"] == breadth["reported_total"]


def test_market_breadth_falls_back_to_sina_full_pagination(monkeypatch):
    sina_pages = iter(
        [
            '[{"code":"600000","changepercent":1.0},{"code":"000001","changepercent":-1.0}]',
            '[{"code":"920000","changepercent":0.0}]',
        ]
    )
    monkeypatch.setattr(market_core, "nearest_trade_date", lambda: "20260710")
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "fetch_json", lambda *args, **kwargs: {"_error": "Eastmoney unavailable"})
    monkeypatch.setattr(market_core, "_fetch_raw", lambda *args, **kwargs: next(sina_pages))

    breadth = market_core.fetch_a_share_market_breadth("20260710", page_size=2)

    assert breadth["available"] is True
    assert breadth["source"] == "sina:hs_a"
    assert breadth["pagination_termination"] == "short_page"
    assert (breadth["up"], breadth["down"], breadth["flat"]) == (1, 1, 1)


def test_historical_board_list_never_uses_live_endpoint():
    result = integrations.fetch_board_list("industry", "20200102")
    assert result["rows"] == []
    assert "禁止混用实时数据" in result["_unavailable"]


def test_historical_quote_uses_requested_close_only():
    quote = integrations._quote_from_history_rows(
        [
            ["2026-06-16", "10", "11", "12", "9", "100"],
            ["2026-06-17", "11", "12", "13", "10", "120"],
            ["2026-06-18", "12", "15", "16", "11", "150"],
        ],
        symbol="600000",
        name="样本",
        market="a",
        currency="CNY",
        trade_date="20260617",
        source="test-kline",
    )
    assert quote is not None
    assert quote.price == 12
    assert quote.previous_close == 11
    assert quote.trade_date == "20260617"


def test_historical_single_quote_enriches_kline_with_stock_get_fields(monkeypatch):
    kline_quote = integrations.QuoteData(
        symbol="600519",
        name="贵州茅台",
        market="a",
        price=1203.0,
        previous_close=1193.0,
        change=10.0,
        change_pct=0.84,
        open_price=1198.0,
        high=1210.0,
        low=1190.0,
        volume=1000,
        currency="CNY",
        trade_date="20260708",
        source="tencent-kline",
        source_chain=["tencent-kline"],
    )
    supplemental_quote = market_core.QuoteData(
        symbol="600519",
        name="贵州茅台",
        market="cn_market",
        price=1204.0,
        prev_close=1193.0,
        change=11.0,
        change_pct=0.92,
        turnover=12_300_000_000,
        turnover_rate=0.42,
        pe=22.5,
        pb=8.1,
        market_cap=15120.0,
        float_market_cap=15119.0,
        currency="CNY",
        date="20260708",
        source="eastmoney-kline",
    )

    monkeypatch.setattr(integrations, "_fetch_tencent_historical_quote", lambda *args, **kwargs: kline_quote)
    monkeypatch.setattr(market_core, "fetch_stock_history_quote", lambda *args, **kwargs: supplemental_quote)

    quote = integrations.fetch_single_quote("600519", "20260708")

    assert quote is not None
    assert quote.price == 1203.0
    assert quote.turnover == 12_300_000_000
    assert quote.turnover_rate == 0.42
    assert quote.pe == 22.5
    assert quote.pb == 8.1
    assert quote.total_market_cap == 15120.0
    assert quote.source_chain == ["tencent-kline", "eastmoney-kline"]


def test_a_share_order_book_snapshot_parses_sina_best_bid_ask(monkeypatch):
    fields = [
        "贵州茅台",
        "1191.000",
        "1199.300",
        "1182.190",
        "1191.990",
        "1178.000",
        "1182.190",
        "1182.200",
        "3409634",
        "4035216946.000",
        "173",
        "1182.190",
        "100",
        "1182.180",
        "700",
        "1182.170",
        "1400",
        "1182.160",
        "11300",
        "1182.150",
        "3300",
        "1182.200",
        "500",
        "1182.260",
        "100",
        "1182.350",
        "100",
        "1182.360",
        "100",
        "1182.420",
        "2026-07-09",
        "15:34:59",
        "00",
        "",
    ]
    monkeypatch.setattr(market_core, "fetch_sina_batch", lambda codes: {"sh600519": fields})

    snapshot = integrations.fetch_a_share_order_book_snapshot("600519", "20260709")

    assert snapshot["available"] is True
    assert snapshot["source"] == "sina"
    assert snapshot["best_bid"] == 1182.19
    assert snapshot["best_ask"] == 1182.2
    assert snapshot["spread"] == 0.01
    assert snapshot["spread_bps"] == 0.0846
    assert snapshot["volume_shares"] == 3409634.0
    assert snapshot["turnover_cny"] == 4035216946.0
    assert snapshot["bid_depth_lots"] == 13673.0
    assert snapshot["ask_depth_lots"] == 4100.0
    assert snapshot["trade_date"] == "20260709"


def test_board_list_falls_back_to_ths_when_eastmoney_clist_is_empty(monkeypatch):
    html = """
    <table><tbody>
      <tr>
        <td>1</td><td><a href="http://q.10jqka.com.cn/thshy/detail/code/881156/">保险</a></td>
        <td class="c-rise">7.09</td><td>614.03</td><td>186.31</td><td>35.51</td>
        <td class="c-rise">5</td><td class="c-fall">0</td><td>30.34</td>
        <td><a href="http://stockpage.10jqka.com.cn/601628/">中国人寿</a></td>
        <td>38.78</td><td>9.70</td>
      </tr>
    </tbody></table>
    """

    monkeypatch.setattr(market_core, "fetch_eastmoney_board_list", lambda *args, **kwargs: {"rows": []})
    monkeypatch.setattr(market_core, "_fetch_text", lambda *args, **kwargs: html)
    monkeypatch.setattr(market_core, "nearest_trade_date", lambda: "20991231")

    result = market_core.get_board_list("industry", "20991231")

    assert result["rows"][0]["name"] == "保险"
    assert result["rows"][0]["change_pct"] == 7.09
    assert result["_fallback"] == "东财 clist 不可用，已启用同花顺板块页"


def test_recent_historical_board_list_uses_ths_when_clist_is_empty(monkeypatch):
    monkeypatch.setattr(integrations, "_is_recent_historical", lambda *args, **kwargs: True)
    monkeypatch.setattr(integrations, "is_historical_date", lambda *args, **kwargs: True)
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        market_core,
        "get_board_list",
        lambda *args, **kwargs: {"board_type": "industry", "rows": [], "_error": "empty clist"},
    )
    monkeypatch.setattr(
        market_core,
        "fetch_ths_board_list",
        lambda *args, **kwargs: {"board_type": "industry", "rows": [{"name": "电机", "change_pct": 5.6}]},
    )

    result = integrations.fetch_board_list("industry", "20260703", limit=5)

    assert result["rows"][0]["name"] == "电机"
    assert result["_fallback"] == "近期历史板块榜无缓存，已使用同花顺公开页补全"


def test_searchapi_resolves_global_stock_secid_from_eastmoney_payload(monkeypatch):
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda *args, **kwargs: {
            "QuotationCodeTable": {
                "Data": [
                    {"Code": "BABA", "Name": "阿里巴巴", "MktNum": "106"},
                    {"Code": "09988", "Name": "阿里巴巴-W", "MktNum": "116"},
                ]
            }
        },
    )

    assert market_core.resolve_global_stock_secid("BABA", "us_market") == ("106.BABA", "阿里巴巴")
    assert market_core.resolve_global_stock_secid("9988.HK", "hk_market") == ("116.09988", "阿里巴巴-W")


def test_stock_get_quote_preserves_turnover_from_f48():
    quote = market_core._stock_get_to_quote(
        {
            "f43": 123.4,
            "f44": 125,
            "f45": 120,
            "f46": 121,
            "f47": 4567,
            "f48": 890000000,
            "f58": "样本指数",
            "f60": 122,
            "f169": 1.4,
            "f170": 1.15,
        },
        "^SAMPLE",
        "us_market",
        "20260702",
    )

    assert quote.volume == 4567
    assert quote.turnover == 890000000


def test_price_volume_metrics_require_a_full_multiperiod_kline_sample():
    rows = []
    for day in range(61):
        close = 3000 + day
        rows.append([f"2026-05-{day + 1:02d}", close - 1, close, close + 2, close - 2, 1000 + day])

    metrics = integrations._price_volume_metrics(rows, "20260630")

    assert metrics["sample_size"] == 61
    assert set(metrics["metrics"]) == {"returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"}


def test_a_share_price_volume_reuses_strict_multiperiod_contract(monkeypatch):
    rows = [
        [
            f"2026-{1 + day // 28:02d}-{1 + day % 28:02d}",
            "10",
            str(10 + day),
            str(11 + day),
            str(9 + day),
            str(100 + day),
        ]
        for day in range(61)
    ]
    monkeypatch.setattr(integrations, "_tencent_history", lambda *args, **kwargs: (rows, {}))

    pack = integrations.fetch_a_share_price_volume("600519", "20260305")

    assert pack["available"] is True
    assert pack["symbol"] == "600519"
    assert set(pack["metrics"]) == {"returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"}


def test_fund_nav_history_paginates_official_rows(monkeypatch):
    first_page = [
        {"FSRQ": f"2026-06-{day:02d}", "DWJZ": "1.0", "LJJZ": "1.0", "JZZZL": "0", "FHSP": ""}
        for day in range(1, 21)
    ]
    second_page = [
        {"FSRQ": "2026-07-01", "DWJZ": "1.1", "LJJZ": "1.1", "JZZZL": "10", "FHSP": ""}
    ]
    responses = iter([{"Data": {"LSJZList": first_page}}, {"Data": {"LSJZList": second_page}}])
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "fetch_json", lambda *args, **kwargs: next(responses))

    history = market_core.fetch_fund_nav_history("512480", "20260710")

    assert history["complete"] is True
    assert history["pages_fetched"] == 2
    assert history["pagination_termination"] == "short_page"
    assert len(history["rows"]) == 21


def test_listed_fund_premium_discount_normalizes_share_split(monkeypatch):
    start = datetime(2026, 3, 1)
    nav_rows = []
    kline_rows = []
    for offset in range(41):
        date = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        pre_split = offset < 20
        nav_rows.append(
            {
                "date": date,
                "nav": 10.0 if pre_split else 5.0,
                "corporate_action": "每份基金份额分拆2.0份" if offset == 20 else "",
            }
        )
        close = 5.0
        kline_rows.append([date, "5", str(close), "5", "5", "100"])
    monkeypatch.setattr(
        market_core,
        "fetch_fund_nav_history",
        lambda *args, **kwargs: {"complete": True, "rows": nav_rows},
    )
    monkeypatch.setattr(
        market_core,
        "fetch_fund_tracking_metadata",
        lambda *_: {"tracked_index": "样本指数", "reported_annual_tracking_error_pct": 0.2},
    )
    monkeypatch.setattr(integrations, "_tencent_history", lambda *args, **kwargs: (kline_rows, {}))

    pack = integrations.fetch_listed_fund_premium_discount("512480", "20260410")

    assert pack["available"] is True
    assert pack["matched_days"] == 41
    assert pack["latest"]["premium_discount_pct"] == 0.0
    assert pack["premium_discount_20d_mean_pct"] == 0.0
    assert pack["split_events"][0]["ratio"] == 2.0


def test_fund_tracking_metadata_parsers_keep_disclosed_fields_distinct():
    basic = "<th>业绩比较基准</th><td>样本指数收益率</td><th>跟踪标的</th><td>样本指数</td>"
    home = "<a>年化跟踪误差：</a>0.20%"

    assert market_core._fund_basic_table_value(basic, "业绩比较基准") == "样本指数收益率"
    assert market_core._fund_basic_table_value(basic, "跟踪标的") == "样本指数"
    assert market_core._fund_tracking_error_text(home) == 0.2


def test_fund_nav_quote_prefers_official_daily_growth_when_split_happens(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda *args, **kwargs: {
            "Data": {
                "LSJZList": [
                    {"FSRQ": "2026-07-02", "DWJZ": "1.3447", "JZZZL": "-8.27", "FHSP": "每份基金份额分拆2.0份"},
                    {"FSRQ": "2026-07-01", "DWJZ": "2.9318", "JZZZL": "-1.85"},
                ]
            }
        },
    )

    quote = market_core.fetch_fund_nav_quote("512480", "20260702")

    assert quote["nav"] == 1.3447
    assert quote["previous_nav"] == 2.9318
    assert quote["change_pct"] == -8.27
    assert quote["split_note"] == "每份基金份额分拆2.0份"


def test_parse_fund_profile_js_extracts_public_performance_fee_and_manager_fields():
    js = """
    var fS_name = "易方达优质精选混合(QDII)";
    var fS_code = "110011";
    var fund_sourceRate="1.50";
    var fund_Rate="0.15";
    var fund_minsg="10";
    var syl_1y="-12.79";
    var syl_3y="-20.24";
    var syl_6y="-25.77";
    var syl_1n="-19.87";
    var Data_fluctuationScale = {"categories":["2026-03-31"],"series":[{"y":95.44,"mom":"-16.17%"}]};
    var Data_performanceEvaluation = {"avr":"77.75","categories":["选证能力","收益率"],"data":[50.0,80.0]};
    var Data_currentFundManager =[
      {"name":"张坤","star":4,"workTime":"13年又280天","fundSize":"416.72亿(4只基金)",
       "power":{"avr":"65.62"},
       "profit":{"series":[{"data":[{"y":295.6454},{"y":37.91},{"y":116.26}]}]}}
    ] ;
    """

    profile = market_core.parse_fund_profile_js("110011", js)

    assert profile["fundcode"] == "110011"
    assert profile["name"] == "易方达优质精选混合(QDII)"
    assert profile["returns"]["近1月"] == -12.79
    assert profile["returns"]["近1年"] == -19.87
    assert profile["fees"]["front_end_source_rate_pct"] == 1.5
    assert profile["fees"]["front_end_rate_pct"] == 0.15
    assert profile["scale"]["latest_size_yi"] == 95.44
    assert profile["performance_evaluation"]["average_score"] == 77.75
    assert profile["performance_evaluation"]["metrics"]["收益率"] == 80.0
    assert profile["managers"][0]["name"] == "张坤"
    assert profile["managers"][0]["tenure_return_pct"] == 295.6454


def test_parse_fund_profile_js_ignores_null_manager_rows():
    js = """
    var fS_name = "样本基金";
    var Data_currentFundManager =[null] ;
    """

    profile = market_core.parse_fund_profile_js("110011", js)

    assert profile["managers"] == []


def test_fetch_fund_profile_falls_back_to_fundmob_f10_when_pingzhongdata_is_sparse(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "_fetch_raw", lambda *args, **kwargs: 'var fS_name = "半导体ETF国联安";')
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda url, headers=None: {
            "Datas": {
                "FCODE": "512480",
                "SHORTNAME": "半导体ETF国联安",
                "ENDNAV": "354.21",
                "FSRQ": "2026-03-31",
                "RZDF": "-7.50",
                "SGZT": "开放申购",
                "SHZT": "开放赎回",
                "JJJL": [
                    {
                        "MGR": "样本经理",
                        "TOTALDAYS": "4年又12天",
                        "NETNAV": "85.30亿",
                        "PENAVGROWTH": "18.25",
                    }
                ],
            }
        },
    )

    profile = market_core.fetch_fund_profile("512480", "20260708")

    assert profile["scale"]["latest_size_yi"] == 354.21
    assert profile["scale"]["asof"] == "2026-03-31"
    assert profile["scale"]["mom"] == "-7.50%"
    assert profile["purchase_status"] == {"subscribe": "开放申购", "redeem": "开放赎回"}
    assert profile["managers"][0]["name"] == "样本经理"
    assert profile["managers"][0]["work_time"] == "4年又12天"
    assert profile["managers"][0]["fund_size"] == "85.30亿"
    assert profile["managers"][0]["tenure_return_pct"] == 18.25
    assert "eastmoney_fundmob_f10" in profile["_source"]


def test_historical_fund_holding_quotes_use_historical_kline(monkeypatch):
    def fail_live(*args, **kwargs):
        raise AssertionError("historical fund holding quote should not use live quote source")

    monkeypatch.setattr(market_core, "fetch_cn_stocks_sina", fail_live)
    monkeypatch.setattr(market_core, "fetch_cn_stocks_tencent", fail_live)
    monkeypatch.setattr(market_core, "fetch_cn_stocks_direct", fail_live)
    monkeypatch.setattr(
        market_core,
        "fetch_stock_history_quote",
        lambda symbol, trade_date: market_core.QuoteData(
            symbol=symbol,
            name="贵州茅台",
            market="cn_market",
            date=trade_date,
            price=1199.3,
            change_pct=0.88,
            volume=25776,
            turnover=3_072_000_000,
            currency="CNY",
            source="eastmoney-kline",
            completeness=100,
        ),
    )

    quotes = market_core.fetch_fund_holding_quotes(
        [{"code": "600519", "name": "贵州茅台", "weight_pct": 6.0}],
        "20260708",
    )

    assert quotes["600519"].price == 1199.3
    assert quotes["600519"].source == "eastmoney-kline"
