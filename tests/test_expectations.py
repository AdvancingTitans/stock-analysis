import pytest

from stock_analysis.expectations import arbitrate_evidence, audit_premises, build_expectation_model
from stock_analysis.research_workspace import _expectation_valuation_lines


def _assumptions():
    return {
        "valuation_year": 2027,
        "multiples": [25, 30, 35],
        "forward_net_profit": 18_000_000_000,
        "product_lines": [
            {"name": "800G", "units": 1_000_000, "asp": 8_000, "net_margin_pct": 20},
            {"name": "1.6T", "units": 500_000, "asp": 12_000, "net_margin_pct": 25},
            {"name": "optical_chip_internal", "units": 1_000_000, "asp": 1_000, "net_margin_pct": 40},
        ],
        "segments": [
            {"name": "body", "net_profit": 3_800_000_000, "multiple": 22},
            {
                "name": "optical_core",
                "net_profit": 10_000_000_000,
                "multiple": 30,
                "includes_product_lines": ["800G", "1.6T", "optical_chip_internal"],
            },
        ],
        "option_value": {"name": "external_chip_sales", "multiple": 40, "net_margin_pct": 40},
        "premises": [
            {"claim": "2027 body profit", "asserted_value": 3.8, "verified_value": 3.8, "tolerance": 0.01},
            {"claim": "reported margin", "asserted_value": 0.76, "verified_value": -1.2},
        ],
        "monitoring": [
            {
                "metric": "1.6T quarterly shipments",
                "baseline": 500_000,
                "next_check_date": "2027Q1",
                "view_change_condition": "two consecutive quarters below the forward model",
            }
        ],
    }


def test_forward_and_reverse_models_reconcile_without_double_counting():
    model = build_expectation_model(443_100_000_000, _assumptions())

    assert model["market_implied"][1]["implied_net_profit"] == pytest.approx(14_770_000_000)
    assert model["forward_model"]["product_lines"][0]["revenue"] == 8_000_000_000
    assert model["sotp_bridge"]["residual_value"] == 59_500_000_000
    assert model["option_value"]["required_net_profit"] == 1_487_500_000
    assert model["option_value"]["required_revenue"] == 3_718_750_000
    assert model["expectation_gap"][1]["gap"] == pytest.approx(3_230_000_000)
    assert [item["status"] for item in model["premise_audit"]] == ["verified", "incorrect"]
    assert model["monitoring"][0]["status"] == "pending"


def test_negative_sotp_residual_is_visible_not_clamped_to_zero():
    assumptions = {"segments": [{"name": "core", "net_profit": 20, "multiple": 10}]}

    model = build_expectation_model(100, assumptions)

    assert model["sotp_bridge"] == {
        "market_cap": 100.0,
        "known_segment_value": 200.0,
        "residual_value": -100.0,
        "status": "overallocated",
        "formula": "market_cap - known_segment_value",
    }


def test_product_line_cannot_be_counted_in_two_segments():
    assumptions = {
        "product_lines": [{"name": "chip", "units": 1, "asp": 1, "net_margin_pct": 10}],
        "segments": [
            {"name": "a", "net_profit": 1, "multiple": 10, "includes_product_lines": ["chip"]},
            {"name": "b", "net_profit": 1, "multiple": 10, "includes_product_lines": ["chip"]},
        ],
    }

    with pytest.raises(ValueError, match="counted in more than one segment"):
        build_expectation_model(100, assumptions)


def test_evidence_arbitration_prefers_authoritative_comparable_evidence_then_freshness():
    decisions = arbitrate_evidence([
        {"metric": "profit", "period": "2026Q1", "scope": "attributable", "value": 12, "source_tier": 2, "published_at": "2026-04-20"},
        {"metric": "profit", "period": "2026Q1", "scope": "attributable", "value": 10, "source_tier": 1, "published_at": "2026-04-10"},
        {"metric": "profit", "period": "2026Q1", "scope": "adjusted", "value": 15, "source_tier": 1, "published_at": "2026-04-30"},
    ])

    attributable = next(item for item in decisions if item["scope"] == "attributable")
    assert attributable["selected"]["value"] == 10
    assert attributable["conflicts"][0]["value"] == 12
    assert len(decisions) == 2


def test_premise_scope_mismatch_remains_ambiguous():
    result = audit_premises([{
        "claim": "margin",
        "asserted_value": 1,
        "verified_value": 1,
        "asserted_scope": "adjusted",
        "verified_scope": "reported",
    }])

    assert result[0]["status"] == "ambiguous"


def test_report_lines_explain_what_is_priced_in_and_reconcile_sotp():
    pack = {"expectation_model": build_expectation_model(443_100_000_000, _assumptions())}

    rendered = "\n".join(_expectation_valuation_lines(pack))

    assert "当前市值在交易什么（2027）" in rendered
    assert "正向产品线模型" in rendered
    assert "SOTP 与市值剩余价值" in rendered
    assert "正向模型与市场隐含预期对账" in rendered
    assert "内部配套产品若已进入分部利润，不得再次作为独立期权计价" in rendered
