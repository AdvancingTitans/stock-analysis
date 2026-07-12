from decimal import Decimal

from stock_analysis.calculators import free_cash_flow_yield, market_cap, scenario_value


def test_financial_calculators_use_exact_decimal_and_keep_missing_values_missing():
    assert market_cap("510", "9.11e9") == Decimal("4646100000000")
    assert free_cash_flow_yield("100", "1000") == Decimal("0.1")
    assert scenario_value("100", "0.1", "-0.2") == Decimal("88.00")
    assert market_cap(None, "1") is None
