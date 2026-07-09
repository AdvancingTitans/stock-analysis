from stock_analysis.models import Holding, QuoteData
from stock_analysis.portfolio import _resolve_buy_price, build_portfolio_snapshot, validate_holdings_quotes


def test_validate_holdings_quotes_marks_missing_fields():
    holding = Holding(symbol="0700.HK", asset_type="stock", market="hk", quantity=100, buy_date="20260101")
    quote = QuoteData(symbol="0700.HK", name="腾讯控股", market="hk", price=None, change=None, change_pct=None)
    validated = validate_holdings_quotes([holding], {"0700.HK": quote})
    result = validated["0700.HK"]
    assert result.status == "unavailable"
    assert "数据暂不可用" in result.note


def test_saved_buy_price_takes_priority_over_date_reference():
    assert _resolve_buy_price(1420.5, {"close": 1500.0}, "close") == 1420.5
    assert _resolve_buy_price(None, {"close": 1500.0}, "close") == 1500.0


def test_historical_fund_holding_uses_nav_quote_for_daily_change(monkeypatch):
    monkeypatch.setattr("stock_analysis.portfolio.fetch_cny_rates", lambda: {"CNY": 1.0})
    monkeypatch.setattr("stock_analysis.portfolio.fetch_board_list", lambda *args, **kwargs: {"rows": []})
    monkeypatch.setattr(
        "stock_analysis.portfolio.fetch_fund_nav_quote",
        lambda code, trade_date: {
            "fundcode": code,
            "name": "招商中证白酒指数(LOF)A",
            "date": "2026-07-03",
            "nav": 0.5119,
            "previous_nav": 0.5111,
            "change": 0.0008,
            "change_pct": 0.1565,
            "_source": "东方财富历史净值",
        },
    )
    monkeypatch.setattr(
        "stock_analysis.portfolio.fetch_fund_buy_reference",
        lambda *args, **kwargs: {"nav": 0.5},
    )
    monkeypatch.setattr("stock_analysis.portfolio.fetch_fund_estimate", lambda *args, **kwargs: {})
    monkeypatch.setattr("stock_analysis.portfolio.fetch_fund_holdings", lambda *args, **kwargs: {"holdings": []})
    monkeypatch.setattr("stock_analysis.portfolio.fetch_fund_holding_quotes", lambda *args, **kwargs: {})

    snapshot = build_portfolio_snapshot(
        [Holding(symbol="161725", asset_type="fund", market="fund", quantity=1000, buy_date="20260110")],
        "20260703",
    )

    detail = snapshot["details"][0]
    assert detail["current_price"] == 0.5119
    assert detail["change_pct"] == 0.1565
    assert detail["trend"] == "上涨"
    assert round(detail["daily_pnl_original"], 4) == 0.8
