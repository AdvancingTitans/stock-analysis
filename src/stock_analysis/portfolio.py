from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .analytics import moving_average_summary
from .exchange import fetch_cny_rates
from .http import em_get
from .integrations import (
    fetch_board_list,
    fetch_fund_buy_reference,
    fetch_fund_estimate,
    fetch_fund_holding_quotes,
    fetch_fund_holdings,
    fetch_single_quote,
    fetch_stock_buy_reference,
    is_historical_date,
)
from .models import Holding, HoldingValidation, QuoteData


def validate_holdings_quotes(
    holdings: list[Holding],
    quotes: dict[str, QuoteData],
) -> dict[str, HoldingValidation]:
    results: dict[str, HoldingValidation] = {}
    for holding in holdings:
        quote = quotes.get(holding.symbol) or QuoteData(symbol=holding.symbol, market=holding.market)
        missing = [field for field in ("price", "change", "change_pct") if getattr(quote, field) is None]
        if missing:
            note = "数据暂不可用；已触发全链路 fallback，仍缺失关键字段。"
            if quote.trade_date:
                note += f" 最后成功交易日: {quote.trade_date}"
            results[holding.symbol] = HoldingValidation(
                holding=holding,
                quote=quote,
                status="unavailable",
                note=note,
            )
            continue
        results[holding.symbol] = HoldingValidation(
            holding=holding,
            quote=quote,
            status="ok",
        )
    return results


def _style_for_symbol(symbol: str, market: str) -> str:
    if market == "fund":
        return "配置型"
    if market == "us":
        return "成长型"
    if symbol.startswith(("6", "0", "3")):
        return "价值型" if symbol.startswith("6") else "成长型"
    return "成长型"


def _style_label_for_fund(name: str) -> str:
    if any(keyword in name for keyword in ("白酒", "消费", "红利")):
        return "消费/防御型"
    if any(keyword in name for keyword in ("成长", "科技", "芯片", "创新")):
        return "成长型"
    return "配置型"


def _board_lookup(board_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("name") or ""): row for row in board_rows}


def build_portfolio_snapshot(holdings: list[Holding], trade_date: str) -> dict[str, Any]:
    rates = fetch_cny_rates()
    industry = fetch_board_list("industry", trade_date, limit=20)
    concept = fetch_board_list("concept", trade_date, limit=20)
    board_top20 = (industry.get("rows") or [])[:20] + (concept.get("rows") or [])[:20]
    board_names = [str(row.get("name") or "") for row in board_top20]
    board_map = _board_lookup(board_top20)

    details: list[dict[str, Any]] = []
    market_values: list[float] = []
    market_counter: dict[str, float] = {"a": 0.0, "hk": 0.0, "us": 0.0, "fund": 0.0}
    total_pnl_cny = 0.0
    total_value_cny = 0.0

    for holding in holdings:
        if holding.asset_type == "fund":
            if is_historical_date(trade_date):
                historical_nav = fetch_fund_buy_reference(holding.symbol, trade_date)
                fund_metadata = fetch_fund_estimate(holding.symbol, trade_date)
                nav_date = str(historical_nav.get("date") or "").replace("-", "")
                historical_price = historical_nav.get("nav") if nav_date == trade_date else None
                estimate = {
                    "name": fund_metadata.get("name") or holding.symbol,
                    "nav": historical_price,
                    "date": historical_nav.get("date") or trade_date,
                    "_source": "历史基金净值",
                }
            else:
                estimate = fetch_fund_estimate(holding.symbol, trade_date)
            buy_ref = fetch_fund_buy_reference(holding.symbol, holding.buy_date)
            price = _safe_float(estimate.get("estimate_nav")) or _safe_float(estimate.get("nav"))
            change_pct = _safe_float(estimate.get("estimate_change_pct"))
            buy_price = _safe_float(buy_ref.get("nav"))
            currency = "CNY"
            source = estimate.get("_source", "天天基金实时估值")
            detail = {
                "symbol": holding.symbol,
                "name": estimate.get("name") or holding.symbol,
                "market": "fund",
                "quantity": holding.quantity,
                "buy_date": holding.buy_date,
                "current_price": price,
                "change_pct": change_pct,
                "buy_price": buy_price,
                "currency": currency,
                "source": source,
                "trade_date": estimate.get("date") or trade_date,
                "trend": None,
                "sector": None,
                "sector_flow": None,
                "theme_status": None,
                "style": _style_label_for_fund(str(estimate.get("name") or holding.symbol)),
            }
            holdings_data = fetch_fund_holdings(holding.symbol, trade_date, limit=5)
            fund_holdings = holdings_data.get("holdings") or []
            quotes_by_code = fetch_fund_holding_quotes(fund_holdings, trade_date)
            detail["fund_holdings"] = [
                {
                    "code": item.get("code"),
                    "name": item.get("name"),
                    "weight_pct": item.get("weight_pct"),
                    "price": quotes_by_code.get(str(item.get("code")), QuoteData(symbol="")).price,
                    "change_pct": quotes_by_code.get(str(item.get("code")), QuoteData(symbol="")).change_pct,
                }
                for item in fund_holdings
            ]
            top_holding = fund_holdings[0] if fund_holdings else None
            if top_holding:
                detail["sector"] = f"重仓方向偏 {top_holding.get('name')}"
        else:
            quote = fetch_single_quote(holding.symbol, trade_date)
            if quote is None:
                quote = QuoteData(symbol=holding.symbol, market=holding.market, trade_date=trade_date)
            buy_ref = fetch_stock_buy_reference(holding.symbol, holding.buy_date)
            ma = moving_average_summary(holding.symbol, holding.market, trade_date=trade_date)
            boards = []
            if holding.market == "a":
                try:
                    market_code = 1 if holding.symbol.startswith("6") else 0
                    params = {
                        "fltt": "2",
                        "invt": "2",
                        "secid": f"{market_code}.{holding.symbol}",
                        "spt": "3",
                        "pi": "0",
                        "pz": "200",
                        "po": "1",
                        "fields": "f12,f14,f3,f128",
                    }
                    response = em_get(
                        "https://push2.eastmoney.com/api/qt/slist/get",
                        params=params,
                        headers={"Referer": "https://quote.eastmoney.com/", "User-Agent": "Mozilla/5.0"},
                        timeout=10,
                    )
                    payload = response.json()
                    diff = ((payload.get("data") or {}).get("diff") or {})
                    items = diff.values() if isinstance(diff, dict) else diff
                    boards = list(items)
                except Exception:
                    boards = []
            board_name = ""
            board_flow = None
            theme_status = None
            for board in boards:
                candidate = str(board.get("f14") or "")
                if candidate in board_names:
                    board_name = candidate
                    board_flow = "主力净流入" if (board_map.get(candidate, {}).get("change_pct") or 0) >= 0 else "主力净流出"
                    theme_status = "当日主线板块"
                    break
                if not board_name and candidate:
                    board_name = candidate
            price = quote.price
            change_pct = quote.change_pct
            buy_price = _safe_float(buy_ref.get("close"))
            detail = {
                "symbol": holding.symbol,
                "name": quote.name or holding.symbol,
                "market": holding.market,
                "quantity": holding.quantity,
                "buy_date": holding.buy_date,
                "current_price": price,
                "change_pct": change_pct,
                "buy_price": buy_price,
                "currency": quote.currency,
                "source": quote.source,
                "trade_date": quote.trade_date or trade_date,
                "trend": None if ma.get("trend") == "数据不足" else ma.get("trend"),
                "ma5": ma.get("ma5"),
                "ma10": ma.get("ma10"),
                "ma20": ma.get("ma20"),
                "sector": board_name or None,
                "sector_flow": board_flow,
                "theme_status": theme_status or ("非当日主线板块" if board_name else None),
                "style": _style_for_symbol(holding.symbol, holding.market),
                "quote": asdict(quote),
            }

        fx_rate = rates.get(detail["currency"], 1.0)
        if detail.get("current_price") is not None:
            market_value_cny = float(detail["current_price"]) * holding.quantity * fx_rate
            total_value_cny += market_value_cny
            market_values.append(market_value_cny)
            exposure_market = "a" if holding.market == "fund" else holding.market
            market_counter[exposure_market] = market_counter.get(exposure_market, 0.0) + market_value_cny
            detail["market_value_cny"] = market_value_cny
            if detail.get("buy_price") is not None:
                pnl_cny = (float(detail["current_price"]) - float(detail["buy_price"])) * holding.quantity * fx_rate
                detail["total_pnl_cny"] = pnl_cny
                total_pnl_cny += pnl_cny
            daily_pnl_original = _daily_pnl(
                current_price=float(detail["current_price"]),
                change_pct=detail.get("change_pct"),
                change=detail.get("quote", {}).get("change") if detail.get("quote") else None,
                quantity=holding.quantity,
            )
            if daily_pnl_original is not None:
                detail["daily_pnl_original"] = daily_pnl_original
                detail["daily_pnl_cny"] = daily_pnl_original * fx_rate
        details.append(detail)

    sorted_values = sorted(market_values, reverse=True)
    top3_ratio = (sum(sorted_values[:3]) / total_value_cny) if total_value_cny else 0.0
    dominant_market = max(market_counter.items(), key=lambda item: item[1])[0] if market_counter else "a"
    dominant_ratio = (market_counter.get(dominant_market, 0.0) / total_value_cny) if total_value_cny else 0.0
    return {
        "details": details,
        "fx_rates": rates,
        "total_value_cny": total_value_cny,
        "total_pnl_cny": total_pnl_cny,
        "top3_ratio": top3_ratio,
        "dominant_market": dominant_market,
        "dominant_ratio": dominant_ratio,
    }


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _daily_pnl(
    *,
    current_price: float,
    change_pct: Any,
    change: Any,
    quantity: float,
) -> float | None:
    absolute_change = _safe_float_signed(change)
    if absolute_change is not None:
        return absolute_change * quantity
    pct = _safe_float_signed(change_pct)
    if pct is None or pct <= -100:
        return None
    previous_price = current_price / (1 + pct / 100)
    return (current_price - previous_price) * quantity


def _safe_float_signed(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
