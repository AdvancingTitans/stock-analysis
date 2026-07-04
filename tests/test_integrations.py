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
