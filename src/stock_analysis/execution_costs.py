"""Scenario-based execution cost model shared by stocks, funds, and portfolios."""

from __future__ import annotations

import math
from typing import Any


def build_execution_cost_model(
    *,
    symbol: str,
    price_volume: dict[str, Any],
    microstructure: dict[str, Any],
    premium_discount: dict[str, Any] | None = None,
    annual_fees: dict[str, Any] | None = None,
    instrument_type: str | None = None,
    market: str = "a",
    currency: str | None = None,
    commission_bps_one_way: float = 2.5,
    order_values_cny: tuple[int, ...] = (100_000, 1_000_000, 5_000_000),
) -> dict[str, Any]:
    instrument_type = instrument_type or ("etf" if str(symbol).startswith(("5", "1")) else "stock")
    market = str(market or "a").lower()
    currency = currency or ("CNY" if market == "a" else None)
    exchange_fee_bps_one_way = 0.4 if instrument_type == "etf" else 0.341
    transfer_fee_bps_one_way = 0.0 if instrument_type == "etf" else 0.1
    stamp_duty_bps_buy = 0.0
    stamp_duty_bps_sell = 0.0 if instrument_type == "etf" else 5.0
    market_rules_complete = market == "a"
    if market == "hk":
        exchange_fee_bps_one_way = 0.85
        transfer_fee_bps_one_way = 0.0
        stamp_duty_bps_buy = stamp_duty_bps_sell = 10.0
    elif market in {"us", "jp", "kr"}:
        exchange_fee_bps_one_way = 0.0
        transfer_fee_bps_one_way = 0.0
        stamp_duty_bps_sell = 0.0
    spread_bps = _number(microstructure.get("spread_bps"))
    liquidity = price_volume.get("liquidity") or {}
    average_turnover = _number(liquidity.get("average_turnover_20d_cny"))
    turnover_field = "average_turnover_20d_cny"
    local_turnover = _number(liquidity.get("average_turnover_20d_local"))
    if average_turnover is None and local_turnover is not None:
        average_turnover = local_turnover
        turnover_field = "average_turnover_20d_local"
    annual_volatility = _number((price_volume.get("metrics") or {}).get("annualized_volatility_60d_pct"))
    missing = [
        name
        for name, value in (
            ("spread_bps", spread_bps),
            (turnover_field, average_turnover),
            ("annualized_volatility_60d_pct", annual_volatility),
        )
        if value is None
    ]
    fees = annual_fees or {}
    management_fee = _number(fees.get("management_fee_pct")) or 0.0
    custodian_fee = _number(fees.get("custodian_fee_pct")) or 0.0
    latest_premium = ((premium_discount or {}).get("latest") or {}).get("premium_discount_pct")
    nav_dislocation_bps = _number(latest_premium)
    nav_dislocation_bps = nav_dislocation_bps * 100 if nav_dislocation_bps is not None else None
    scenarios = []
    if not missing:
        daily_volatility_bps = annual_volatility / math.sqrt(252) * 100
        for order_value in order_values_cny:
            participation = order_value / average_turnover
            # ponytail: square-root impact with a conservative 10% coefficient; calibrate when intraday fills exist.
            impact = 0.1 * daily_volatility_bps * math.sqrt(participation)
            buy_cost = (
                spread_bps / 2 + commission_bps_one_way + exchange_fee_bps_one_way
                + transfer_fee_bps_one_way + stamp_duty_bps_buy + impact
            )
            sell_cost = buy_cost + stamp_duty_bps_sell
            scenarios.append({
                "order_value_cny": order_value,
                "order_value": order_value,
                "order_currency": currency,
                "participation_of_20d_adv_pct": participation * 100,
                "spread_cost_bps_one_way": spread_bps / 2,
                "commission_bps_one_way": commission_bps_one_way,
                "exchange_fee_bps_one_way": exchange_fee_bps_one_way,
                "transfer_fee_bps_one_way": transfer_fee_bps_one_way,
                "stamp_duty_bps_sell": stamp_duty_bps_sell,
                "stamp_duty_bps_buy": stamp_duty_bps_buy,
                "market_impact_bps_one_way": impact,
                "buy_cost_bps": buy_cost,
                "sell_cost_bps": sell_cost,
                "round_trip_cost_bps": buy_cost + sell_cost,
            })
    return {
        "available": not missing,
        "symbol": symbol,
        "instrument_type": instrument_type,
        "market": market,
        "currency": currency,
        "model_status": (
            "scenario_complete" if not missing and market_rules_complete
            else "scenario_partial_market_rules" if not missing
            else "insufficient_inputs"
        ),
        "spread_bps": spread_bps,
        "average_turnover_20d_cny": average_turnover,
        "average_turnover_20d_local": average_turnover if turnover_field.endswith("_local") else None,
        "turnover_input_field": turnover_field,
        "annualized_volatility_60d_pct": annual_volatility,
        "commission_bps_one_way_assumption": commission_bps_one_way,
        "exchange_fee_bps_one_way_assumption": exchange_fee_bps_one_way,
        "transfer_fee_bps_one_way_assumption": transfer_fee_bps_one_way,
        "stamp_duty_bps_sell_assumption": stamp_duty_bps_sell,
        "stamp_duty_bps_buy_assumption": stamp_duty_bps_buy,
        "cost_rules_asof": "2026-07-18",
        "cost_rules_source": (
            "https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Hong-Kong%29/Trading/Transaction?sc_lang=en"
            if market == "hk" else None
        ),
        "annual_holding_cost_pct": management_fee + custodian_fee,
        "nav_dislocation_bps": nav_dislocation_bps,
        "scenarios": scenarios,
        "missing_inputs": missing,
        "limitations": [
            "佣金采用可覆盖的情景参数，未包含券商最低收费和用户专属费率。",
            "市场冲击采用波动率与成交额参与率的平方根模型，需用真实成交回报持续校准。",
            "已按股票/ETF区分交易所经手费、过户费与卖出印花税；税费规则变更时必须更新假设日期。",
            "未包含融资利息、最低佣金、申赎费用或衍生品对冲成本；不适用的成本不得强行计入。",
            *([] if market_rules_complete else ["该市场的券商佣金、监管费或交易税并未全部标准化，情景结果保持 conditional。"]),
        ],
    }


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
