import pytest

from stock_analysis.market_time import MarketSession
from stock_analysis.models import Holding
from stock_analysis.trading import (
    IncompleteHoldingsError,
    parse_user_holdings_json,
    plan_trading_task,
    resolve_holdings,
)


def test_user_holdings_override_saved_memory_and_are_saved():
    saved = [Holding(symbol="000001", asset_type="stock", market="a", quantity=100, buy_date="20260101")]
    user = [Holding(symbol="600519", asset_type="stock", market="a", quantity=10, buy_date="20260601")]
    writes = []

    resolution = resolve_holdings(
        user_holdings=user,
        load_memory=lambda: saved,
        save_memory=writes.append,
    )

    assert resolution.source == "user"
    assert resolution.holdings == user
    assert resolution.include_holdings is True
    assert writes == [user]


def test_incomplete_user_holdings_ask_before_memory_fallback():
    saved = [Holding(symbol="000001", asset_type="stock", market="a", quantity=100, buy_date="20260101")]
    user = [Holding(symbol="600519", asset_type="stock", market="a", quantity=0, buy_date="")]

    with pytest.raises(IncompleteHoldingsError) as error:
        resolve_holdings(user_holdings=user, load_memory=lambda: saved)

    assert "600519" in error.value.message
    assert "quantity" in error.value.missing_by_symbol["600519"]
    assert "buy_date" in error.value.missing_by_symbol["600519"]


def test_memory_holdings_are_used_only_when_user_input_is_absent():
    saved = [Holding(symbol="000001", asset_type="stock", market="a", quantity=100, buy_date="20260101")]

    resolution = resolve_holdings(user_holdings=None, load_memory=lambda: saved)

    assert resolution.source == "memory"
    assert resolution.holdings == saved
    assert resolution.include_holdings is True


def test_no_user_or_memory_holdings_omits_portfolio_analysis():
    resolution = resolve_holdings(user_holdings=None, load_memory=lambda: [])

    assert resolution.source == "none"
    assert resolution.holdings == []
    assert resolution.include_holdings is False


def test_parse_user_holdings_json_converts_amount_when_buy_price_is_available():
    holdings = parse_user_holdings_json(
        '[{"symbol":"600519","buy_date":"20260601","amount":12400,"buy_price":1240}]'
    )

    assert holdings[0].quantity == 10


def test_amount_without_buy_price_is_incomplete_user_holding():
    holdings = parse_user_holdings_json('[{"symbol":"600519","buy_date":"20260601","amount":12400}]')

    with pytest.raises(IncompleteHoldingsError) as error:
        resolve_holdings(user_holdings=holdings, load_memory=lambda: [])

    assert "quantity" in error.value.missing_by_symbol["600519"]


def test_plan_trading_task_defaults_to_committee_and_session_format(monkeypatch):
    monkeypatch.setattr("stock_analysis.trading.load_holdings_from_profile", lambda: [])

    plan = plan_trading_task(
        cli_market="daily",
        session=MarketSession(label="早盘", depth="light", market="a"),
        requested_format="auto",
        user_holdings=None,
        lens=None,
        lenses=None,
        mode=None,
    )

    assert plan.market == "a"
    assert plan.report_format == "summary"
    assert plan.mode == "committee"
    assert plan.include_holdings is False


def test_plan_trading_task_switches_to_single_when_lens_is_requested(monkeypatch):
    monkeypatch.setattr("stock_analysis.trading.load_holdings_from_profile", lambda: [])

    plan = plan_trading_task(
        cli_market="a",
        session=MarketSession(label="盘后", depth="full", market="a"),
        requested_format="auto",
        user_holdings=None,
        lens="buffett",
        lenses=None,
        mode=None,
    )

    assert plan.report_format == "full"
    assert plan.mode == "single"
