from stock_analysis.integrations import (
    _merge_index_turnover,
    fetch_board_list,
    fetch_hk_indices,
    is_historical_date,
)


def test_merge_index_turnover_fills_missing_fields(monkeypatch):
    rows = [{"f12": "000001", "f14": "上证指数", "f2": 4100, "f6": None}]
    monkeypatch.setattr(
        "stock_analysis.integrations.market_core.get_index",
        lambda trade_date: [{"f12": "000001", "f6": 123456789.0}],
    )
    merged = _merge_index_turnover(rows, "20260701")
    assert merged[0]["f6"] == 123456789.0
    assert merged[0]["_turnover_source"] == "eastmoney"


def test_fetch_hk_indices_uses_nearest_kline_or_live(monkeypatch):
    trade_date = "20260701"
    assert is_historical_date(trade_date)

    class Quote:
        def __init__(self, symbol):
            self.symbol = symbol
            self.name = symbol
            self.market = "hk"
            self.price = 1.0
            self.change = 0.1
            self.change_pct = 0.1
            self.turnover = 100.0
            self.trade_date = trade_date
            self.source = "live"
            self.currency = "HKD"
            self.quality_flags = []
            self.fallback_reason = None

    monkeypatch.setattr(
        "stock_analysis.integrations._fetch_tencent_historical_quote",
        lambda *args, **kwargs: Quote("^HSI"),
    )
    rows = fetch_hk_indices(trade_date)
    assert len(rows) >= 1


def test_fetch_board_list_allows_historical_cache(monkeypatch):
    cached = {"board_type": "industry", "rows": [{"name": "半导体", "rank": 1}]}
    monkeypatch.setattr("stock_analysis.integrations.is_historical_date", lambda _trade_date: True)
    monkeypatch.setattr("stock_analysis.integrations.market_core.cache_load", lambda *args, **kwargs: cached)
    result = fetch_board_list("industry", "20260701", limit=5)
    assert result["rows"][0]["name"] == "半导体"
