from copy import deepcopy

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
            "evidence": [{"evidence_id": f"{code}:fixture", "metric": f"metric_{index}", "value": index, "validation_status": "accepted"}] if available else [],
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
