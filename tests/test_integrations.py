from stock_analysis import integrations


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
