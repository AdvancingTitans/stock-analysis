from stock_analysis.app import _portfolio_advice_sections, _style_distribution
from stock_analysis.evidence import EvidenceBundle
from stock_analysis.quality import EvidenceQuality
from stock_analysis.reporting import render_report


def _sample_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        trade_date="20260617",
        modules={
            "M1": {
                "available": True,
                "a_indices": [
                    {
                        "name": "上证指数",
                        "price": 4108.08,
                        "change": 16.3,
                        "change_pct": 0.4,
                        "turnover": 1_403_145_910_000,
                        "source": "eastmoney/sina/tencent",
                    }
                ],
                "hk_indices": [],
                "us_indices": [
                    {
                        "name": "标普500",
                        "price": 7420.1,
                        "change": -90.2,
                        "change_pct": -1.21,
                        "turnover": None,
                        "source": "sina",
                    }
                ],
                "northbound": {
                    "total_yi": -40.38,
                    "latest_time": "15:00",
                    "_source": "同花顺北向资金 hsgtApi",
                },
                "breadth": {
                    "available": True,
                    "up": 3200,
                    "down": 1900,
                    "ratio": 1.68,
                    "scope": "行业板块成分汇总",
                },
                "cross_market_comment": "A股相对最强。",
            },
            "M2": {
                "available": True,
                "summary": "主线偏科技制造。",
                "concentration": {},
                "industry_top20": [
                    {"name": "半导体", "change_pct": 3.2, "up_count": 48, "down_count": 5}
                ],
            },
            "M3": {
                "available": True,
                "summary": "涨停梯队完整。",
                "pool_stats": {
                    "zt_count": 2,
                    "first_board_count": 1,
                    "multi_board_count": 1,
                    "zt_fund_total_yi": 3.2,
                    "leaders": [
                        {"name": "样本股份", "code": "600000", "board_days": 3, "seal_fund_yi": 2.1}
                    ],
                },
            },
            "M4": {"available": True, "summary": "高位分歧。", "pool_stats": {}},
            "M5": {"available": True, "summary": "成长占优。", "feature_groups": {}},
            "M6": {"available": True, "summary": "部分方向抗跌。", "resilient": []},
        },
        meta={
            "portfolio_advice_sections": {
                "current": ["贵州茅台跌1.25%，当日浮亏1,575元。"],
                "benchmark": ["贵州茅台跑输上证指数1.65个百分点。"],
                "position_actions": ["若食品饮料继续跑输上证指数，优先控制集中度。"],
                "watchlist": ["观察科创50能否消化高开获利盘。"],
                "risks": ["科创50单日大涨，警惕次日分化。"],
            }
        },
    )


def test_report_uses_tables_and_hides_source_language():
    evidence = _sample_evidence()
    report = render_report(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={
            "total_value_cny": 100_000,
            "total_pnl_cny": -10_000,
            "top3_ratio": 0.9,
            "dominant_market": "a",
            "dominant_ratio": 0.8,
            "details": [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "market": "a",
                    "buy_date": "2026-01-15",
                    "quantity": 100,
                    "current_price": 1240,
                    "change_pct": -1.25,
                    "currency": "CNY",
                    "daily_pnl_original": -1575,
                    "trend": "震荡",
                    "style": "价值型",
                    "benchmark_name": "上证指数",
                    "relative_label": "跑输",
                    "relative_pct": -1.65,
                }
            ],
        },
        report_format="full",
    )
    assert "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额 |" in report
    assert "| 资金项 | 净流向 |" in report
    assert "| 市场广度 | 上涨家数 | 下跌家数 | 涨跌比 |" in report
    assert "| 板块 | 涨跌幅 | 上涨家数 | 下跌家数 |" in report
    assert "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |" in report
    assert "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |" in report
    assert "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |" in report
    assert "| 600519 | 贵州茅台 | 上证指数 | -1.65 |" in report
    assert "| 股票 | 连板 | 封单金额 |" in report
    assert "来源" not in report
    assert "口径来自" not in report
    assert "最新统计时点" not in report
    assert "标普500" in report
    assert "成交额 --" not in report
    assert "| 标普500 | 7,420.10 | -90.20 | -1.21% |  |" in report


def test_report_renders_specific_portfolio_advice_sections():
    evidence = _sample_evidence()
    report = render_report(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": [], "top3_ratio": 0, "dominant_ratio": 0},
        report_format="full",
    )
    assert "现状总结" in report
    assert "贵州茅台跌1.25%" in report
    assert "基准跑赢/跑输" in report
    assert "仓位动作建议" in report
    assert "观察清单" in report
    assert "风险提示" in report


def test_summary_keeps_mandatory_disclaimer():
    evidence = _sample_evidence()
    report = render_report(
        trade_date="20260617",
        session_label="早盘",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="summary",
    )
    assert "## 二、持仓分析" in report
    assert "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |" in report
    assert "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |" in report
    assert "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |" in report
    assert "## 三、六模块深度复盘" not in report
    assert "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。" in report


def test_key_points_stops_after_downside_module():
    evidence = _sample_evidence()
    report = render_report(
        trade_date="20260617",
        session_label="盘中",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="key-points",
    )
    assert "### 4. 爆量下跌风险" in report
    assert "### 5. 特征分组" not in report
    assert "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。" in report


def test_style_distribution_is_value_weighted():
    styles = _style_distribution(
        [
            {"style": "价值型", "market_value_cny": 120_000},
            {"style": "成长型", "market_value_cny": 20_000},
            {"style": "成长型", "market_value_cny": 5_000},
        ]
    )
    assert max(styles, key=styles.get) == "价值型"


def test_portfolio_advice_detects_duplicate_exposure_and_benchmark_tracking():
    sections = _portfolio_advice_sections(
        {
            "top3_ratio": 0.9,
            "dominant_ratio": 0.85,
            "details": [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "style": "价值型",
                    "change_pct": -1.25,
                    "relative_label": "跑输",
                    "relative_pct": -1.65,
                    "benchmark_name": "上证指数",
                },
                {
                    "symbol": "NVDA",
                    "name": "英伟达",
                    "style": "成长型",
                    "change_pct": -1.33,
                    "relative_label": "跑赢",
                    "relative_pct": 0.01,
                    "benchmark_name": "纳斯达克",
                },
                {
                    "symbol": "161725",
                    "name": "招商中证白酒指数",
                    "style": "消费/防御型",
                    "change_pct": -0.7,
                    "fund_holdings": [{"code": "600519", "name": "贵州茅台"}],
                },
            ],
        },
        {"a_indices": [], "hk_indices": [], "us_indices": []},
        {},
        {"pool_stats": {"theme_counter": {"元件": 10}, "multi_board_count": 5}},
        {"pool_stats": {"blowup_ratio": 0.2}},
    )
    assert any("重复暴露" in item for item in sections["position_actions"])
    assert any("跟随纳斯达克" in item for item in sections["position_actions"])
    assert any("贵州茅台" in item and "跑输" in item for item in sections["benchmark"])
    assert sections["watchlist"]
