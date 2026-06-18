from stock_analysis.config import SourceConfig
from stock_analysis.models import QuoteData
from stock_analysis.sources import mootdx_adapter
from stock_analysis.sources.router import build_quote_route, needs_mootdx


def test_mootdx_is_only_selected_for_specialized_requests():
    assert needs_mootdx("order_book")
    assert not needs_mootdx("quote")
    normal = build_quote_route("a", request_type="quote")
    depth = build_quote_route("a", request_type="minute_kline")
    assert "mootdx-depth" not in normal.chain
    assert "mootdx-depth" in depth.chain


def test_disabled_mootdx_falls_back_to_basic_quote(monkeypatch):
    monkeypatch.setattr(
        "stock_analysis.integrations.fetch_single_quote",
        lambda symbol, trade_date: QuoteData(
            symbol=symbol,
            market="a",
            price=10.0,
            change=0.1,
            change_pct=1.0,
            source="tencent",
            trade_date=trade_date,
        ),
    )
    result = mootdx_adapter.fetch_mootdx_specialized(
        "sh600519",
        "order_book",
        config=SourceConfig(enable_mootdx=False),
        trade_date="20260618",
    )
    assert result["status"] == "fallback"
    assert result["source"] == "tencent"
    assert result["symbol"] == "600519"
