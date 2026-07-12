import json
from pathlib import Path

from stock_analysis import app, company_evidence
from stock_analysis.models import QuoteData
from stock_analysis.thesis import create_thesis, review_thesis
from stock_analysis.workflows import render_earnings_review, render_price_move, render_stock_review


def _financials():
    return {
        "periods": [
            {
                "report_date": "2026-03-31",
                "revenue": 78_000_000_000,
                "parent_netprofit": 25_000_000_000,
                "roe_weighted": 10.57,
                "gross_margin": 91.2,
                "debt_asset_ratio": 12.12,
                "operating_cash_flow": 26_910_000_000,
                "free_cash_flow_lite": 26_305_000_000,
            }
        ]
    }


def _company_pack(monkeypatch):
    monkeypatch.setattr(
        company_evidence,
        "fetch_single_quote",
        lambda *_: QuoteData(
            symbol="600519", name="贵州茅台", market="a", price=1500.0, currency="CNY", trade_date="20260710", source="tencent"
        ),
    )
    monkeypatch.setattr(company_evidence, "fetch_a_share_financial_snapshot", lambda *_: _financials())
    monkeypatch.setattr(
        company_evidence,
        "fetch_a_share_price_volume",
        lambda *_: {"source": "tencent-kline", "metrics": {"returns_20d": 0.12, "atr_14": 30.2}},
    )
    monkeypatch.setattr(
        company_evidence,
        "fetch_futu_public_pulse",
        lambda *_: {"event_title": "公司回购公告", "evidence_url": "https://example.com", "news_tone": "偏正面", "news_count": 2},
    )
    return company_evidence.build_company_evidence("600519", "20260710")


def test_company_evidence_has_c1_to_c8_and_explicit_gaps(monkeypatch):
    pack = _company_pack(monkeypatch)

    assert list(pack["modules"]) == ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]
    assert pack["modules"]["C2"]["available"] is True
    assert pack["modules"]["C4"]["available"] is False
    assert pack["_meta"]["coverage"] == 62.5
    assert {event["source"] for event in pack["_meta"]["source_events"]} == {
        "tencent",
        "eastmoney_datacenter",
        "futu_public",
    }


def test_company_workflow_reports_do_not_turn_gaps_into_scores(monkeypatch):
    pack = _company_pack(monkeypatch)

    stock = render_stock_review(pack)
    earnings = render_earnings_review(pack)
    price_move = render_price_move(pack)

    assert "证据不足，维持观察" in stock
    assert "C4 护城河证据" in stock
    assert "护城河只能由可观测" in stock
    assert "roe_weighted" in earnings
    assert "不将事件断言为异动主因" in price_move


def test_thesis_create_and_review_persist_only_structured_evidence(monkeypatch, tmp_path):
    pack = _company_pack(monkeypatch)
    monkeypatch.setenv("STOCK_ANALYSIS_THESIS_DIR", str(tmp_path))

    thesis, path = create_thesis(pack)
    reviewed, reviewed_path, changes = review_thesis(pack)

    assert path == reviewed_path
    assert path.exists()
    assert thesis["status"] == "evidence_insufficient"
    assert reviewed is not None
    assert "未发现可由当前结构化 Evidence 自动判定的变化" in changes
    assert json.loads(path.read_text(encoding="utf-8"))["symbol"] == "600519"


def test_cli_stock_review_emits_company_evidence(monkeypatch, tmp_path, capsys):
    pack = {"symbol": "600519", "name": "贵州茅台", "trade_date": "20260710", "_meta": {"coverage": 0, "available_modules": [], "missing_modules": list(company_evidence.COMPANY_MODULES), "source_events": []}, "financial_facts": [], "quote": {}, "modules": {key: {"available": False, "evidence": [], "gaps": ["缺口"]} for key in company_evidence.COMPANY_MODULES}}
    monkeypatch.setattr(app, "build_company_evidence", lambda *_: pack)
    monkeypatch.chdir(tmp_path)

    assert app.run(["--market", "stock-review", "--symbol", "600519", "--date", "20260710", "--emit-evidence"]) == 0

    assert "公司研究" in capsys.readouterr().out
    assert (tmp_path / "company_evidence_600519_20260710.json").exists()


def test_agent_entrypoints_are_generated_from_canonical_catalog():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "agent-workflows" / "commands.json").read_text(encoding="utf-8"))

    for command in catalog:
        assert (root / "codex-skills" / command["id"] / "SKILL.md").exists()
        assert (root / "codex-prompts" / f"{command['id']}.md").exists()
        assert (root / "claude-commands" / f"{command['id']}.md").exists()
