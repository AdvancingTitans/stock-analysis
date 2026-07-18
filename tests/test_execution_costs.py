from stock_analysis.execution_costs import build_execution_cost_model


def test_execution_cost_model_combines_spread_adv_impact_fees_and_nav_dislocation():
    model = build_execution_cost_model(
        symbol="512480",
        price_volume={
            "metrics": {"annualized_volatility_60d_pct": 65.13},
            "liquidity": {"average_turnover_20d_cny": 2_100_000_000},
        },
        microstructure={"available": True, "spread_bps": 1.2, "trade_date": "20260717"},
        premium_discount={"latest": {"premium_discount_pct": -0.18}},
        annual_fees={"management_fee_pct": 0.5, "custodian_fee_pct": 0.1},
    )

    assert model["available"] is True
    assert model["model_status"] == "scenario_complete"
    assert model["annual_holding_cost_pct"] == 0.6
    assert model["instrument_type"] == "etf"
    assert model["scenarios"][0]["stamp_duty_bps_sell"] == 0.0
    assert model["scenarios"][0]["exchange_fee_bps_one_way"] == 0.4
    assert model["nav_dislocation_bps"] == -18.0
    assert model["scenarios"][0]["order_value_cny"] == 100_000
    assert model["scenarios"][0]["round_trip_cost_bps"] > model["spread_bps"]
    assert model["scenarios"][-1]["market_impact_bps_one_way"] > model["scenarios"][0]["market_impact_bps_one_way"]


def test_execution_cost_model_remains_conditional_without_spread_or_adv():
    model = build_execution_cost_model(symbol="600519", price_volume={}, microstructure={})

    assert model["available"] is False
    assert model["model_status"] == "insufficient_inputs"
    assert {"spread_bps", "average_turnover_20d_cny"} <= set(model["missing_inputs"])


def test_a_share_stock_cost_model_includes_sell_stamp_duty_and_transfer_fee():
    model = build_execution_cost_model(
        symbol="600519",
        price_volume={
            "metrics": {"annualized_volatility_60d_pct": 25.0},
            "liquidity": {"average_turnover_20d_cny": 3_000_000_000},
        },
        microstructure={"spread_bps": 0.8},
    )

    scenario = model["scenarios"][1]
    assert model["instrument_type"] == "stock"
    assert scenario["stamp_duty_bps_sell"] == 5.0
    assert scenario["transfer_fee_bps_one_way"] == 0.1
    assert scenario["sell_cost_bps"] > scenario["buy_cost_bps"]
