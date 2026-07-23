import json

from stock_analysis import app
from stock_analysis.research_workspace import build_research_workspace


def _pack(trade_date: str = "20260710", coverage: float = 37.5):
    modules = {
        f"C{index}": {
            "available": index in {2, 3, 6},
            "evidence": [
                {
                    "evidence_id": f"C{index}:fixture",
                    "metric": f"metric_{index}",
                    "value": index,
                    "source_type": "primary_disclosure",
                    "source": f"fixture-filing-C{index}",
                    "period": trade_date,
                    "validation_status": "accepted",
                }
            ]
            if index in {2, 3, 6}
            else [],
            "gaps": [] if index in {2, 3, 6} else [f"C{index} 缺口"],
        }
        for index in range(1, 9)
    }
    modules["C6"]["evidence"].extend(
        [
            {
                "evidence_id": "C6:price",
                "metric": "market_quote",
                "value": 1500.0,
                "source_type": "primary_disclosure",
                "source": "fixture-market-quote",
                "period": trade_date,
                "validation_status": "accepted",
            },
            {
                "evidence_id": "C6:market-cap",
                "metric": "total_market_cap",
                "value": 1_800_000_000_000,
                "source_type": "primary_disclosure",
                "source": "fixture-market-cap",
                "period": trade_date,
                "validation_status": "accepted",
            },
        ]
    )
    modules["C7"] = {
        "available": True,
        "evidence": [
            {
                "evidence_id": "C7:execution",
                "metric": "execution_cost_model_status",
                "value": "scenario_complete",
                "source_type": "primary_disclosure",
                "source": "fixture-execution",
                "period": trade_date,
                "validation_status": "accepted",
            }
        ],
        "gaps": [],
    }
    return {
        "schema_version": "1.0",
        "symbol": "600519",
        "name": "贵州茅台",
        "market": "a",
        "trade_date": trade_date,
        "generated_at": "2026-07-10T08:00:00+00:00",
        "financial_facts": [],
        "modules": modules,
        "_meta": {
            "coverage": coverage,
            "available_modules": ["C2", "C3", "C6", "C7"],
            "missing_modules": ["C1", "C4", "C5", "C8"],
            "source_events": [{"source": "fixture", "status": "ok"}],
        },
    }


def test_workspace_creates_recoverable_stage_artifacts(tmp_path):
    manifest, workspace = build_research_workspace(_pack(), root=tmp_path)

    assert manifest["status"] == "ready_for_analysis"
    assert manifest["stages"]["evidence_collection"] == "complete"
    assert manifest["stages"]["expert_analysis"] == "complete"
    assert manifest["stages"]["committee_review"] == "complete"
    assert set(manifest["artifacts"]) == {
        "research_plan",
        "company_evidence",
        "evidence_summary",
        "expert_readiness",
        "company_opinions",
        "committee_synthesis",
        "committee_review",
        "decision_memo",
        "institutional_report",
        "evidence_manifest",
        "claim_ledger",
        "coverage_report",
        "unpublished_claims",
    }
    assert (workspace / "workspace.json").exists()
    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(encoding="utf-8")
    assert "## 一、执行摘要" in report
    assert "## 二、行情、商业质量与核心矛盾" in report
    assert "## 六、投委会审议" in report
    assert "巴菲特" in report
    assert "冻结 Evidence" not in report
    assert "committee:" not in report
    assert "sha256:" not in report
    assert "审计与待核验事项" not in report
    assert "## 五、估值与情景分析" in report
    assert "## 八、投委会结论与条件化动作" in report
    assert "证据不足，维持观察" not in report
    assert "证据暂缺" not in report
    assert "manual_review" not in report
    assert "Evidence Dashboard" not in report
    assert "适用条件" in report
    assert "失效条件" in report
    assert "市场份额正在下降" not in report
    assert "由于缺乏市场份额数据，应保持谨慎" not in report
    assert "由于证据不足" not in report
    assert "数据有限，因此" not in report
    assert "仍需更多信息验证" not in report
    unpublished = json.loads((workspace / "unpublished_claims.json").read_text(encoding="utf-8"))
    assert any("市场份额" in item.get("question", "") for item in unpublished["claims"])
    for filename in (
        "evidence_manifest.json",
        "claim_ledger.json",
        "coverage_report.json",
        "unpublished_claims.json",
    ):
        assert json.loads((workspace / filename).read_text(encoding="utf-8"))


def test_workspace_resume_preserves_manually_edited_artifact(tmp_path):
    first, workspace = build_research_workspace(_pack(), root=tmp_path)
    report_path = workspace / first["artifacts"]["institutional_report"]["path"]
    report_path.write_text("manual committee note\n", encoding="utf-8")

    resumed, resumed_workspace = build_research_workspace(_pack(), root=tmp_path)

    assert resumed_workspace == workspace
    assert report_path.read_text(encoding="utf-8") == "manual committee note\n"
    generated = resumed["artifacts"]["institutional_report"]["path"]
    assert generated == "07-institutional-report.generated.md"
    assert (workspace / generated).exists()

    (workspace / generated).write_text("second manual note\n", encoding="utf-8")
    third, _ = build_research_workspace(_pack(), root=tmp_path)
    assert (workspace / generated).read_text(encoding="utf-8") == "second manual note\n"
    assert third["artifacts"]["institutional_report"]["path"] == "07-institutional-report.generated-2.md"


def test_workspace_uses_previous_date_as_diff_baseline(tmp_path):
    build_research_workspace(_pack("20260709", 25.0), root=tmp_path)
    manifest, workspace = build_research_workspace(_pack("20260710", 37.5), root=tmp_path)

    assert manifest["baseline"]["trade_date"] == "20260709"
    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(encoding="utf-8")
    assert "证据覆盖：25.0% → 37.5%" not in report
    assert manifest["baseline"]["trade_date"] == "20260709"
    assert json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))["symbol"] == "600519"


def test_research_cli_prints_report_and_workspace_path(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "build_company_evidence", lambda *_: _pack())

    assert app.run([
        "--market", "research", "--symbol", "600519", "--date", "20260710",
        "--workspace-dir", str(tmp_path), "--research-question", "短线趋势、量价突破和止损",
    ]) == 0

    output = capsys.readouterr().out
    assert "个股深度研究报告 · 投委会" in output
    assert f"Research Workspace: {tmp_path / '600519' / '20260710'}" in output
    opinions = json.loads((tmp_path / "600519" / "20260710" / "04-company-lens-opinions.json").read_text(encoding="utf-8"))
    assert len(opinions) == 6
    assert {"livermore", "o_neil", "minervini"} <= set(opinions)
    assert "研究问题**：短线趋势、量价突破和止损" in output


def test_missing_price_blocks_actions_without_suppressing_supported_research(tmp_path):
    pack = _pack()
    pack["modules"]["C6"]["evidence"] = [
        item for item in pack["modules"]["C6"]["evidence"]
        if item["metric"] != "market_quote"
    ]

    manifest, workspace = build_research_workspace(pack, root=tmp_path)
    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(
        encoding="utf-8"
    )

    assert manifest["status"] == "action_blocked"
    assert "## 一、执行摘要" in report
    assert "估值或交易执行行动被阻断" in report
    assert "建议保持谨慎" not in report
    assert "维持观察" not in report


def test_explicit_identity_conflict_blocks_the_research_report(tmp_path):
    pack = _pack()
    pack["_meta"]["identity_validation"] = {"status": "conflict"}

    manifest, workspace = build_research_workspace(pack, root=tmp_path)
    report = (workspace / manifest["artifacts"]["institutional_report"]["path"]).read_text(
        encoding="utf-8"
    )

    assert manifest["status"] == "blocked_report"
    assert "## 重大安全阻断" in report
    assert "## 一、执行摘要" not in report
