from copy import deepcopy

from stock_analysis.committee_selection import relevant_research_modules
from stock_analysis.company_lens import (
    build_company_lens_opinions,
    freeze_company_evidence,
    select_company_committee,
    synthesize_company_committee,
)


def _pack():
    modules = {}
    for index in range(1, 9):
        code = f"C{index}"
        available = code in {"C2", "C3", "C5", "C6", "C7", "C8"}
        modules[code] = {
            "available": available,
            "evidence": [{
                "evidence_id": f"{code}:fixture",
                "metric": f"metric_{index}",
                "value": index,
                "period": "20260710",
                "validation_status": "accepted",
                "source_type": "primary_disclosure",
                "source": f"fixture-filing-{code}",
            }] if available else [],
            "gaps": [] if available else [f"{code} gap"],
        }
    return {
        "schema_version": "1.1",
        "symbol": "600519",
        "name": "贵州茅台",
        "market": "a",
        "trade_date": "20260710",
        "generated_at": "ignored-by-snapshot-hash",
        "financial_facts": [],
        "modules": modules,
        "_meta": {"coverage": 75.0, "available_modules": ["C2", "C3", "C5", "C6", "C7", "C8"], "missing_modules": ["C1", "C4"], "source_events": []},
    }


def test_frozen_snapshot_is_content_addressed_and_ignores_generation_time():
    pack = _pack()
    first = freeze_company_evidence(pack)
    changed_timestamp = deepcopy(pack)
    changed_timestamp["generated_at"] = "later"
    second = freeze_company_evidence(changed_timestamp)

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["snapshot_id"].startswith("sha256:")
    assert first["evidence"]["symbol"] == "600519"


def test_company_lenses_and_committee_consume_one_frozen_snapshot():
    snapshot = freeze_company_evidence(_pack())
    opinions = build_company_lens_opinions(snapshot, research_question="长期商业质量、资本配置和估值安全边际")
    committee = synthesize_company_committee(snapshot, opinions)

    assert len(opinions) == 6
    assert all(opinion["evidence_snapshot_id"] == snapshot["snapshot_id"] for opinion in opinions.values())
    assert all(opinion["supporting_evidence_ids"] for opinion in opinions.values())
    assert committee["evidence_snapshot_id"] == snapshot["snapshot_id"]
    assert committee["opinion_ids"] == [opinion["opinion_id"] for opinion in opinions.values()]
    assert committee["action"] == "manual_review"
    assert committee["consensus"]
    assert committee["disagreements"]


def test_committee_selection_changes_with_the_research_question():
    quality = select_company_committee("长期护城河、现金流、治理和安全边际")
    momentum = select_company_committee("短线趋势、量价突破、交易成本和止损")

    assert len(quality) == len(momentum) == 6
    assert {"buffett", "munger", "duan_yongping"} <= set(quality)
    assert {"livermore", "o_neil", "minervini"} <= set(momentum)
    assert quality != momentum


def test_committee_selection_understands_plain_english_investor_questions():
    quality = select_company_committee("long-term moat, cash flow, governance and capital allocation")
    trading = select_company_committee("momentum, price volume, volatility, drawdown and trading costs")

    assert {"buffett", "munger"} <= set(quality)
    assert {"simons", "minervini"} <= set(trading)
    assert relevant_research_modules("business model", asset_type="company") == ("C1",)
    assert relevant_research_modules("product mandate", asset_type="fund") == ("F1",)
    assert relevant_research_modules("无法映射的专门问题", asset_type="company") == ()


def test_every_selected_lens_consumes_new_business_quality_metrics():
    pack = _pack()
    pack["modules"]["C1"] = {
        "available": True,
        "evidence": [
            {"evidence_id": "C1:margin", "metric": "parent_net_margin_pct", "value": 49.8, "validation_status": "conditional"},
            {"evidence_id": "C1:cash", "metric": "operating_cash_conversion_pct", "value": 98.78, "validation_status": "conditional"},
        ],
        "gaps": [],
    }
    pack["_meta"]["available_modules"] = ["C1", *pack["_meta"]["available_modules"]]
    pack["_meta"]["missing_modules"] = ["C4"]
    snapshot = freeze_company_evidence(pack)
    opinions = build_company_lens_opinions(snapshot, research_question="增长质量、现金流和估值")
    committee = synthesize_company_committee(snapshot, opinions)

    assert len(opinions) == 6
    for opinion in opinions.values():
        consumed = {item["metric"] for item in opinion["metric_analyses"]}
        assert {"parent_net_margin_pct", "operating_cash_conversion_pct"} <= consumed
        assert all(item["interpretation"] for item in opinion["metric_analyses"])
    assert committee["evidence_consumption_audit"]["parent_net_margin_pct"] == list(opinions)
    assert committee["evidence_consumption_audit"]["operating_cash_conversion_pct"] == list(opinions)


def _add_cash_quality_metrics(pack, *, cash_flow_yoy, receivables_yoy, revenue_yoy):
    pack["modules"]["C2"]["evidence"].extend(
        [
            {
                "evidence_id": "C2:ocf-yoy",
                "metric": "operating_cash_flow_yoy_pct",
                "value": cash_flow_yoy,
                "validation_status": "accepted",
            },
            {
                "evidence_id": "C2:ar-yoy",
                "metric": "accounts_receivable_yoy_pct",
                "value": receivables_yoy,
                "validation_status": "accepted",
            },
        ]
    )
    pack["modules"]["C3"]["evidence"].append(
        {
            "evidence_id": "C3:revenue-yoy",
            "metric": "revenue_yoy_pct",
            "value": revenue_yoy,
            "validation_status": "accepted",
        }
    )


def test_removing_nonblocking_market_share_does_not_make_supported_direction_conservative():
    full = _pack()
    _add_cash_quality_metrics(full, cash_flow_yoy=12, receivables_yoy=4, revenue_yoy=8)
    full["modules"]["C4"] = {
        "available": True,
        "evidence": [
            {
                "evidence_id": "C4:market-share",
                "metric": "market_share_pct",
                "value": 25,
                "period": "20260710",
                "validation_status": "accepted",
                "source_type": "primary_disclosure",
                "source": "fixture-market-share-filing",
            }
        ],
        "gaps": [],
    }
    narrowed = deepcopy(full)
    narrowed["modules"]["C4"] = {
        "available": False,
        "evidence": [],
        "gaps": ["market_share"],
    }

    full_snapshot = freeze_company_evidence(full)
    full_opinions = build_company_lens_opinions(full_snapshot)
    full_committee = synthesize_company_committee(full_snapshot, full_opinions)
    narrowed_snapshot = freeze_company_evidence(narrowed)
    narrowed_opinions = build_company_lens_opinions(narrowed_snapshot)
    narrowed_committee = synthesize_company_committee(narrowed_snapshot, narrowed_opinions)

    assert any(
        claim["claim"] == "增长的现金实现质量保持稳定" and claim["direction"] == "bullish"
        for claim in full_committee["publishable_claims"]
    )
    assert any(
        claim["claim"] == "增长的现金实现质量保持稳定" and claim["direction"] == "bullish"
        for claim in narrowed_committee["publishable_claims"]
    )
    assert not any(
        claim["direction"] == "bearish" and "market_share" in str(claim)
        for claim in narrowed_committee["publishable_claims"]
    )


def test_real_cash_quality_deterioration_remains_publishable_bearish_evidence():
    pack = _pack()
    _add_cash_quality_metrics(pack, cash_flow_yoy=-15, receivables_yoy=25, revenue_yoy=5)
    snapshot = freeze_company_evidence(pack)
    committee = synthesize_company_committee(snapshot, build_company_lens_opinions(snapshot))
    claim = next(
        item for item in committee["publishable_claims"]
        if item["claim"] == "增长的现金实现质量下降"
    )

    assert claim["direction"] == "bearish"
    assert set(claim["evidence_ids"]) == {"C2:ocf-yoy", "C2:ar-yoy", "C3:revenue-yoy"}


def test_cash_quality_calculation_requires_comparable_periods():
    pack = _pack()
    _add_cash_quality_metrics(pack, cash_flow_yoy=-15, receivables_yoy=25, revenue_yoy=5)
    pack["modules"]["C3"]["evidence"][-1]["period"] = "2025Q4"
    snapshot = freeze_company_evidence(pack)
    committee = synthesize_company_committee(snapshot, build_company_lens_opinions(snapshot))

    assert not any(
        claim["claim"] == "增长的现金实现质量下降"
        for claim in committee["publishable_claims"]
    )


def test_every_publishable_company_claim_is_conditionally_verifiable():
    snapshot = freeze_company_evidence(_pack())
    committee = synthesize_company_committee(snapshot, build_company_lens_opinions(snapshot))
    known_ids = {
        item["evidence_id"]
        for section in snapshot["evidence"]["modules"].values()
        for item in section["evidence"]
    }

    assert committee["publishable_claims"]
    for claim in committee["publishable_claims"]:
        assert claim["evidence_ids"]
        assert set(claim["evidence_ids"]) <= known_ids
        assert claim["applicable_period"]
        assert claim["conditions"]
        assert claim["invalidators"]
        assert claim["claim_status"] in {"supported", "strongly_supported"}


def test_question_with_only_unrelated_supported_claims_blocks_report():
    pack = _pack()
    for code, section in pack["modules"].items():
        section["available"] = code == "C3"
        section["evidence"] = section["evidence"] if code == "C3" else []
        section["gaps"] = [] if code == "C3" else [f"{code} gap"]
    snapshot = freeze_company_evidence(pack)
    opinions = build_company_lens_opinions(
        snapshot,
        research_question="商业模式如何创造价值？",
    )
    committee = synthesize_company_committee(snapshot, opinions)

    assert committee["publishable_claims"] == []
    assert committee["publication_status"] == "block_report"
    assert any(
        issue["code"] == "NO_SUPPORTED_CLAIMS"
        for issue in committee["safety_gate"]["issues"]
    )
