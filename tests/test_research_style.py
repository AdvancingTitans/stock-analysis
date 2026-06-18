from stock_analysis.evidence import EvidenceBundle
from stock_analysis.quality import EvidenceQuality
from stock_analysis.reporting import render_report
from stock_analysis.research_style import sanitize_research_report

FORBIDDEN_TERMS = (
    ".py",
    ".js",
    ".sh",
    "/Users/",
    "脚本",
    "采集",
    "推测",
    "不确定性",
    "猜测",
    "降级",
    "fallback",
    "push2",
    "exa",
)


def test_sanitize_research_report_removes_engineering_language():
    raw = """
# 复盘

aftermarket.py 脚本采集到 push2 数据，推测为全天数据，存在不确定性。
M2 降级后 fallback 到 exa，详情见 /Users/yjw/agent/run.sh。

| 指数 | 收盘 | 涨跌 | 涨跌幅 |
|---|---:|---:|---:|
| 上证指数 | 4108.08 | +16.32 | +0.40% |
"""
    cleaned = sanitize_research_report(raw)
    assert "据公开市场数据" in cleaned
    assert "按惯例回溯至该日" in cleaned
    assert "本模块证据暂缺" in cleaned
    assert "| 指数 | 收盘 | 涨跌 | 涨跌幅 |" in cleaned
    assert all(term.lower() not in cleaned.lower() for term in FORBIDDEN_TERMS)


def test_render_report_applies_final_research_style_filter():
    evidence = EvidenceBundle(
        trade_date="20260617",
        modules={
            "M1": {
                "available": True,
                "a_indices": [
                    {
                        "name": "上证指数",
                        "price": 4108.08,
                        "change": 16.32,
                        "change_pct": 0.4,
                    }
                ],
                "hk_indices": [],
                "us_indices": [],
                "cross_market_comment": "aftermarket.py 脚本采集后推测为全天数据。",
            },
            "M2": {"available": True, "summary": "M2 降级，fallback 到 push2。", "concentration": {}},
            "M3": {"available": False, "summary": "", "pool_stats": {}},
            "M4": {"available": False, "summary": "", "pool_stats": {}},
            "M5": {"available": False, "summary": "", "feature_groups": {}},
            "M6": {"available": False, "summary": "", "resilient": []},
        },
        meta={"portfolio_advice_sections": {}},
    )
    report = render_report(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 0, "M4": 0, "M5": 0, "M6": 0},
            missing_modules=["M3", "M4", "M5", "M6"],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
    )
    assert all(term.lower() not in report.lower() for term in FORBIDDEN_TERMS)
    assert "本模块证据暂缺" in report
    assert "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额 |" in report


def test_evidence_pack_declares_research_report_style():
    evidence = EvidenceBundle(trade_date="20260617")
    evidence.quality()
    assert evidence.meta["style"] == "research-report"
