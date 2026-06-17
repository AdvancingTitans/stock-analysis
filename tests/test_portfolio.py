from stock_analysis.models import Holding, QuoteData
from stock_analysis.portfolio import validate_holdings_quotes


def test_validate_holdings_quotes_marks_missing_fields():
    holding = Holding(symbol="0700.HK", asset_type="stock", market="hk", quantity=100, buy_date="20260101")
    quote = QuoteData(symbol="0700.HK", name="腾讯控股", market="hk", price=None, change=None, change_pct=None)
    validated = validate_holdings_quotes([holding], {"0700.HK": quote})
    result = validated["0700.HK"]
    assert result.status == "unavailable"
    assert "数据暂不可用" in result.note
