from stock_analysis import integrations, market_core


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
