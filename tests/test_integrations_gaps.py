from stock_analysis.integrations import (
    _merge_index_turnover,
    fetch_a_indices,
    fetch_board_list,
    fetch_hk_indices,
    fetch_single_quote,
    fetch_us_indices,
    is_historical_date,
)
from stock_analysis.models import QuoteData


def test_merge_index_turnover_fills_missing_fields(monkeypatch):
    rows = [{"f12": "000001", "f14": "上证指数", "f2": 4100, "f6": None}]
    monkeypatch.setattr("stock_analysis.integrations._eastmoney_index_history_amounts", lambda _trade_date: {})
    monkeypatch.setattr(
        "stock_analysis.integrations.market_core.get_index",
        lambda trade_date: [{"f12": "000001", "f6": 123456789.0}],
    )
    merged = _merge_index_turnover(rows, "20260701")
    assert merged[0]["f6"] == 123456789.0
    assert merged[0]["_turnover_source"] == "eastmoney"


def test_merge_index_turnover_fills_each_missing_row_from_eastmoney(monkeypatch):
    rows = [
        {"f12": "000001", "f14": "上证指数", "f2": 4100, "f6": 123.0},
        {"f12": "000300", "f14": "沪深300", "f2": 4800, "f6": None},
    ]
    monkeypatch.setattr(
        "stock_analysis.integrations._eastmoney_index_history_amounts",
        lambda _trade_date: {"000001": 999.0},
    )
    monkeypatch.setattr(
        "stock_analysis.integrations.market_core.get_index",
        lambda trade_date: [{"f12": "000300", "f6": 456789000000.0}],
    )

    merged = _merge_index_turnover(rows, "20260703")

    assert merged[0]["f6"] == 999.0
    assert merged[0]["_turnover_source"] == "eastmoney-kline"
    assert merged[1]["f6"] == 456789000000.0
    assert merged[1]["_turnover_source"] == "eastmoney"


def test_historical_a_indices_replace_tencent_volume_with_eastmoney_amount(monkeypatch):
    trade_date = "20260703"

    def fake_quote(_code, *, symbol, name, market, currency, trade_date, **_kwargs):
        return QuoteData(
            symbol=symbol,
            name=name,
            market=market,
            price=4043.64,
            change=14.74,
            change_pct=0.37,
            volume=602009738.0,
            turnover=None,
            currency=currency,
            trade_date=trade_date,
            source="tencent-kline",
        )

    monkeypatch.setattr("stock_analysis.integrations._fetch_tencent_historical_quote", fake_quote)
    monkeypatch.setattr(
        "stock_analysis.integrations._eastmoney_index_history_amounts",
        lambda _trade_date: {"000001": 1465563104853.7},
    )

    rows = fetch_a_indices(trade_date)
    first = rows[0]

    assert first["f12"] == "000001"
    assert first["f5"] == 602009738.0
    assert first["f6"] == 1465563104853.7
    assert first["_turnover_source"] == "eastmoney-kline"


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


def test_fetch_us_indices_use_nearest_trading_day_for_market_holiday(monkeypatch):
    trade_date = "20260703"

    def fake_history(symbol, requested_date, *, allow_nearest=False):
        if not allow_nearest:
            return None
        return QuoteData(
            symbol=symbol,
            name=symbol,
            market="us",
            price=100,
            change=1,
            change_pct=1,
            currency="USD",
            trade_date="20260702",
            source="sina-kline",
            quality_flags=["nearest_available_kline"],
            fallback_reason=f"requested={requested_date}",
        )

    monkeypatch.setattr("stock_analysis.integrations._fetch_sina_us_history", fake_history)

    rows = fetch_us_indices(trade_date)

    assert [row.name for row in rows] == ["标普500", "纳斯达克", "道琼斯"]
    assert all(row.trade_date == "20260702" for row in rows)
    assert all("nearest_available_kline" in row.quality_flags for row in rows)


def test_fetch_single_quote_uses_nearest_us_trading_day_for_historical_holiday(monkeypatch):
    trade_date = "20260703"

    def fake_history(symbol, requested_date, *, allow_nearest=False):
        if symbol != "TSLA" or requested_date != trade_date or not allow_nearest:
            return None
        return QuoteData(
            symbol="TSLA",
            name="TSLA",
            market="us",
            price=393.45,
            change=-31.85,
            change_pct=-7.49,
            currency="USD",
            trade_date="20260702",
            source="sina-kline",
            quality_flags=["nearest_available_kline"],
            fallback_reason=f"requested={requested_date}",
        )

    monkeypatch.setattr("stock_analysis.integrations._fetch_sina_us_history", fake_history)

    quote = fetch_single_quote("TSLA", trade_date)

    assert quote is not None
    assert quote.price == 393.45
    assert quote.trade_date == "20260702"


def test_fetch_board_list_allows_historical_cache(monkeypatch):
    cached = {"board_type": "industry", "rows": [{"name": "半导体", "rank": 1}]}
    monkeypatch.setattr("stock_analysis.integrations.is_historical_date", lambda _trade_date: True)
    monkeypatch.setattr("stock_analysis.integrations.market_core.cache_load", lambda *args, **kwargs: cached)
    result = fetch_board_list("industry", "20260701", limit=5)
    assert result["rows"][0]["name"] == "半导体"
