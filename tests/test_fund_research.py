import json

from stock_analysis import app
from stock_analysis.fund_research import (
    _official_fund_evidence,
    build_fund_research_workspace,
    freeze_fund_evidence,
    synthesize_fund_committee,
)


def _pack():
    modules = {
        f"F{index}": {
            "available": index != 5,
            "evidence": [
                {
                    "evidence_id": f"F{index}:fixture",
                    "metric": f"metric_{index}",
                    "value": index,
                    "validation_status": "accepted",
                }
            ] if index != 5 else [],
            "gaps": ["缺少成分股估值"] if index == 5 else [],
        }
        for index in range(1, 9)
    }
    return {
        "schema_version": "1.0",
        "asset_type": "fund",
        "symbol": "512480",
        "name": "半导体ETF国联安",
        "trade_date": "20260717",
        "modules": modules,
        "profile": {"returns": {"近1年": 107.79}, "scale": {"latest_size_yi": 199.06}},
        "estimate": {"estimate_nav": 1.0714, "estimate_change_pct": -7.71},
        "price_volume": {"metrics": {
            "returns_5d": -21.84,
            "atr_14_pct": 9.53,
            "max_drawdown_60d_pct": -28.81,
            "annualized_volatility_60d_pct": 65.13,
        }},
        "premium_discount": {"latest": {"premium_discount_pct": -0.18}},
        "holdings": {"asof": "2026-03-31", "holdings": [{"code": "688256", "name": "寒武纪", "weight_pct": 6.64}]},
        "_meta": {
            "coverage": 87.5,
            "available_modules": ["F1", "F2", "F3", "F4", "F6", "F7", "F8"],
            "missing_modules": ["F5"],
            "source_events": [{"source": "fixture", "status": "ok"}],
        },
    }


def test_fund_snapshot_and_committee_share_one_frozen_evidence():
    snapshot = freeze_fund_evidence(_pack())
    committee, opinions = synthesize_fund_committee(snapshot, research_question="半导体景气、估值和回撤风险")

    assert snapshot["snapshot_id"].startswith("sha256:")
    assert len(opinions) == 6
    assert all(item["evidence_snapshot_id"] == snapshot["snapshot_id"] for item in opinions.values())
    assert committee["evidence_snapshot_id"] == snapshot["snapshot_id"]
    assert committee["action"] == "manual_review"


def test_fund_workspace_uses_institutional_skeleton(tmp_path):
    manifest, workspace = build_fund_research_workspace(_pack(), root=tmp_path)

    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(encoding="utf-8")
    for heading in (
        "## 一、执行摘要",
        "## 二、产品定位与指数契约",
        "## 三、持仓结构与产业暴露",
        "## 四、业绩、趋势与风险",
        "## 五、估值、折溢价与交易实现",
        "## 六、投委会审议",
        "## 八、投委会结论与条件化动作",
    ):
        assert heading in report
    assert "证据不足，维持观察" not in report
    assert "manual_review" not in report
    assert "Evidence Dashboard" not in report
    assert "底层估值模块 F5 尚未结构化" not in report
    assert "冻结 Evidence" not in report
    assert "fund-committee:" not in report
    assert "sha256:" not in report
    assert "审计与待核验事项" not in report
    assert json.loads((workspace / "02-frozen-fund-evidence.json").read_text(encoding="utf-8"))["snapshot_id"]


def test_research_cli_routes_fund_asset_type(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "build_fund_evidence", lambda *_: _pack())

    assert app.run([
        "--market", "research", "--symbol", "512480", "--date", "20260717",
        "--asset-type", "fund", "--workspace-dir", str(tmp_path),
    ]) == 0

    output = capsys.readouterr().out
    assert "基金深度研究报告 · 投委会" in output
    assert f"Research Workspace: {tmp_path / '512480' / '20260717'}" in output


def test_every_selected_fund_expert_consumes_valuation_and_risk_metrics():
    pack = _pack()
    pack["modules"]["F5"] = {
        "available": True,
        "evidence": [
            {"evidence_id": "F5:pe", "metric": "positive_pe_harmonic_proxy", "value": 173.16, "validation_status": "conditional"},
            {"evidence_id": "F5:index-pe", "metric": "index_pe_calculation_share", "value": 108.15, "validation_status": "accepted"},
        ],
        "gaps": [],
    }
    pack["modules"]["F6"]["evidence"] = [
        {"evidence_id": "F6:drawdown", "metric": "max_drawdown_60d_pct", "value": -28.81, "validation_status": "accepted"},
        {"evidence_id": "F6:volatility", "metric": "annualized_volatility_60d_pct", "value": 65.13, "validation_status": "accepted"},
    ]
    pack["modules"]["F7"]["evidence"] = [
        {"evidence_id": "F7:index-cap", "metric": "index_single_constituent_cap_pct", "value": 15.0, "validation_status": "accepted"},
        {"evidence_id": "F7:fee", "metric": "management_fee_pct", "value": 0.5, "validation_status": "accepted"},
    ]
    pack["_meta"]["available_modules"].append("F5")
    pack["_meta"]["missing_modules"] = []
    snapshot = freeze_fund_evidence(pack)
    committee, opinions = synthesize_fund_committee(snapshot, research_question="估值、景气和交易风险")

    assert len(opinions) == 6
    required = {
        "positive_pe_harmonic_proxy",
        "index_pe_calculation_share",
        "max_drawdown_60d_pct",
        "annualized_volatility_60d_pct",
        "index_single_constituent_cap_pct",
        "management_fee_pct",
    }
    assert all(required <= {item["metric"] for item in opinion["metric_analyses"]} for opinion in opinions.values())
    assert all(committee["evidence_consumption_audit"][metric] == list(opinions) for metric in required)


def test_official_fund_contract_and_index_methodology_are_structured():
    evidence = _official_fund_evidence("512480", "20260717")
    metrics = {item["metric"] for items in evidence.values() for item in items}

    assert {
        "index_single_constituent_cap_pct", "index_rebalance_months",
        "minimum_index_constituent_nav_pct", "management_fee_pct", "custodian_fee_pct",
    } <= metrics
    assert all(item["source_type"] == "primary_disclosure" for items in evidence.values() for item in items)
    assert all(item["url"] and item["page"] for items in evidence.values() for item in items)


def test_simons_reservation_reconciles_with_index_history_and_execution_cost_evidence(tmp_path):
    pack = _pack()
    pack["modules"]["F5"]["evidence"] = [
        {"evidence_id": "F5:index-pe", "metric": "index_pe_calculation_share", "value": 108.15, "validation_status": "accepted"},
    ]
    pack["modules"]["F6"]["evidence"] = [
        {"evidence_id": "F6:index-sample", "metric": "index_history_sample_size", "value": 90, "validation_status": "accepted"},
        {"evidence_id": "F6:index-vol", "metric": "index_annualized_volatility_60d_pct", "value": 60.0, "validation_status": "accepted"},
    ]
    pack["modules"]["F7"]["evidence"] = [
        {"evidence_id": "F7:cost-status", "metric": "execution_cost_model_status", "value": "scenario_complete", "validation_status": "conditional"},
        {"evidence_id": "F7:cost", "metric": "execution_round_trip_cost_1m_bps", "value": 8.2, "validation_status": "conditional"},
    ]
    manifest, workspace = build_fund_research_workspace(
        pack, root=tmp_path, research_question="量化、指数趋势、交易成本和回撤"
    )
    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(encoding="utf-8")
    simons_row = next(line for line in report.splitlines() if line.startswith("| 西蒙斯 |"))

    assert "缺少标的指数日线与完整交易成本模型" not in simons_row
    assert "指数日线样本 90" in simons_row
    assert "100万元往返成本 8.20bps" in simons_row
