from stock_analysis.app import _portfolio_advice_sections, _style_distribution
from stock_analysis.evidence import EvidenceBundle
from stock_analysis.quality import EvidenceQuality
from stock_analysis.reporting import generate_report, render_report, render_report_with_metadata


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
            "trade_date": "20260617",
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
                    "public_pulse": {
                        "news_tone": "偏正面",
                        "event_title": "贵州茅台回购计划获市场关注",
                        "community_label": "证据不足",
                        "community_sample_count": 1,
                        "evidence_url": "https://news.futunn.com/post/1",
                    },
                }
            ],
        },
        report_format="full",
    )
    assert "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额/量 |" in report
    assert "| 资金项 | 净流向 |" in report
    assert "| 市场广度 | 上涨家数 | 下跌家数 | 涨跌比 |" in report
    assert "| 板块 | 涨跌幅 | 上涨家数 | 下跌家数 |" in report
    assert "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |" in report
    assert "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |" in report
    assert "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |" in report
    assert "| 600519 | 贵州茅台 | 上证指数 | -1.65 |" in report
    assert "| 代码 | 新闻倾向 | 最新高信号事件 | 证据 |" in report
    assert "[原文](https://news.futunn.com/post/1)" in report
    assert "| 股票 | 连板 | 封单金额 |" in report
    assert "来源：API" not in report
    assert "口径来自" not in report
    assert "M7" not in report
    assert "社区情绪" not in report
    assert "最新统计时点" not in report
    assert "标普500" in report
    assert "成交额 --" not in report


def test_index_table_renders_volume_when_turnover_is_missing():
    evidence = _sample_evidence()
    evidence.modules["M1"]["us_indices"][0]["volume"] = 3_687_282_528

    report = render_report(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
    )

    assert "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额/量 |" in report
    assert "| 标普500 | 7,420.10 | -90.20 | -1.21% | 3,687,282,528 |" in report


def test_report_result_defaults_to_committee_and_returns_metadata_json():
    evidence = _sample_evidence()
    evidence.meta["portfolio_public_pulse"] = [
        {
            "symbol": "600519",
            "news_tone": "偏正面",
            "news_count": 2,
            "event_title": "贵州茅台回购计划获市场关注",
            "community_label": "分歧",
            "community_sample_count": 4,
            "community_bull_pct": 50.0,
            "community_bear_pct": 50.0,
            "evidence_url": "https://news.futunn.com/post/1",
        }
    ]

    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
    )

    assert "**报告日期**：2026-06-17" in result.markdown
    assert "**分析模式**：投委会（默认）" in result.markdown
    assert "## 执行摘要" in result.markdown
    assert "## 一、大盘指数概览" in result.markdown
    assert "M7" not in result.markdown
    assert "社区情绪" not in result.markdown
    assert "m1 综合深度分析" in result.markdown
    assert "m6 综合风险评分" in result.markdown
    assert result.metadata["analysis_mode"] == "committee"
    assert result.metadata["analysis_mode_label"] == "投委会（默认）"
    assert result.metadata["lenses"][:4] == ["buffett", "munger", "duan_yongping", "zhang_kun"]
    assert result.metadata["committee_deep_analysis"]["m1"]["trend_consistency"]["direction"]
    assert result.metadata["committee_deep_analysis"]["m6"]["risk_score"] >= 0
    assert "community_sentiment_summary" not in result.metadata
    assert "evidence_quality_with_m7" not in result.metadata
    assert evidence.meta["report_metadata"]["analysis_mode"] == "committee"


def test_default_committee_report_uses_m1_m6_deep_review_structure():
    evidence = _sample_evidence()
    evidence.meta["portfolio_public_pulse"] = [
        {
            "symbol": "600519",
            "news_tone": "偏正面",
            "news_count": 2,
            "event_title": "贵州茅台回购计划获市场关注",
            "community_label": "偏多",
            "community_sample_count": 5,
            "community_bull_pct": 60.0,
            "community_bear_pct": 20.0,
            "evidence_url": "https://news.futunn.com/post/1",
        }
    ]

    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
    )

    headings = [
        "## 执行摘要",
        "## 一、大盘指数概览",
        "## 二、六模块深度复盘",
        "## 三、通用市场建议与风险提示",
    ]
    positions = [result.markdown.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "## 2. 分析视角说明" not in result.markdown
    assert "evidence_quality_with_m7" not in result.metadata
    assert "- m1–m6 原始数据及本次报告调整记录：" in result.markdown
    assert "社区情绪分析数据来源与方法说明" not in result.markdown
    assert "- 各 lens 证据权重调整明细：" in result.markdown
    assert "- 主要交叉验证与分歧调和记录：" in result.markdown
    assert "- 免责声明与数据来源：" in result.markdown


def test_committee_full_report_keeps_fixed_structure_when_holdings_quality_is_simplified():
    evidence = _sample_evidence()
    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=evidence,
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 0, "M3": 0, "M4": 0, "M5": 0, "M6": 0},
            missing_modules=["M2", "M3", "M4", "M5", "M6"],
        ),
        portfolio_snapshot={
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
                    "benchmark_name": "上证指数",
                    "relative_label": "跑输",
                    "relative_pct": -1.65,
                }
            ],
            "top3_ratio": 1,
            "dominant_ratio": 1,
        },
        report_format="full",
    )

    headings = [
        "## 执行摘要",
        "## 一、大盘指数概览",
        "## 二、持仓分析",
        "## 三、六模块深度复盘",
        "### M1. 基础数据与核心指标",
        "### M2. 板块资金与集中度",
        "### M3. 赚钱效应与上涨主线",
        "### M4. 爆量下跌风险",
        "### M5. 特征分组",
        "### M6. 综合风险与抗跌方向",
        "## 四、综合持仓建议与风险提示",
        "### 现状总结",
        "### 基准跑赢/跑输",
        "### 条件化仓位动作",
        "### 下一交易日观察清单",
        "### 风险提示",
    ]
    positions = [result.markdown.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "贵州茅台跌1.25%" in result.markdown
    assert "贵州茅台跑输上证指数1.65个百分点" in result.markdown
    assert "证据暂缺" in result.markdown


def test_committee_report_ignores_portfolio_snapshot_sentiment_pulses():
    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=_sample_evidence(),
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={
            "details": [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "public_pulse": {
                        "symbol": "600519",
                        "news_tone": "偏正面",
                        "news_count": 1,
                        "event_title": "贵州茅台回购计划获市场关注",
                        "community_label": "偏多",
                        "community_sample_count": 4,
                        "community_bull_pct": 75.0,
                        "community_bear_pct": 0.0,
                    },
                }
            ]
        },
        report_format="full",
    )

    assert "community_sentiment_summary" not in result.metadata
    assert "社区情绪" not in result.markdown
    assert "M7" not in result.markdown


def test_generate_report_is_simple_llm_facing_entrypoint():
    result = generate_report(evidence=_sample_evidence(), trade_date="20260617")

    assert "**分析模式**：投委会（默认）" in result.markdown
    assert result.metadata["analysis_mode"] == "committee"


def test_committee_report_falls_back_to_single_when_committee_context_fails():
    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=_sample_evidence(),
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
        mode="committee",
        lenses=("not_a_lens", "buffett"),
    )

    assert "**分析模式**：单一专家" in result.markdown
    assert "**使用视角**：巴菲特" in result.markdown
    assert result.metadata["analysis_mode"] == "single"
    assert result.metadata["fallback"]["from_mode"] == "committee"
    assert result.metadata["fallback"]["to_mode"] == "single"
    assert "not_a_lens" in result.metadata["fallback"]["reason"]


def test_single_lens_report_hides_using_lens_when_user_did_not_request_committee_members():
    result = render_report_with_metadata(
        trade_date="20260617",
        session_label="盘后",
        evidence=_sample_evidence(),
        quality=EvidenceQuality(
            module_scores={"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10},
            missing_modules=[],
        ),
        portfolio_snapshot={"details": []},
        report_format="full",
        lens="buffett",
    )

    assert "**分析模式**：单一专家" in result.markdown
    assert "**使用视角**：巴菲特" in result.markdown
    assert "## 6. 社区情绪分析" not in result.markdown
    assert result.metadata["analysis_mode"] == "single"


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
        portfolio_snapshot={
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
                    "benchmark_name": "上证指数",
                    "relative_label": "跑输",
                    "relative_pct": -1.65,
                }
            ],
            "top3_ratio": 1,
            "dominant_ratio": 1,
        },
        report_format="full",
    )
    assert "## 二、持仓分析" in report
    assert "## 四、综合持仓建议与风险提示" in report
    assert "现状总结" in report
    assert "贵州茅台跌1.25%" in report
    assert "基准跑赢/跑输" in report
    assert "条件化仓位动作" in report
    assert "下一交易日观察清单" in report
    assert "风险提示" in report


def test_report_omits_portfolio_sections_without_holdings():
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
    assert "## 二、持仓分析" not in report
    assert "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |" not in report
    assert "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |" not in report
    assert "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |" not in report
    assert "## 二、六模块深度复盘" in report
    assert "## 三、通用市场建议与风险提示" in report
    assert "M7" not in report
    assert "社区情绪" not in report
    assert "现状总结" in report
    assert "基准跑赢/跑输" in report
    assert "条件化仓位动作" in report
    assert "下一交易日观察清单" in report
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
    assert "## 二、持仓分析" not in report
    assert "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |" not in report
    assert "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |" not in report
    assert "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |" not in report
    assert "## 一、盘前资讯与外围线索" in report
    assert "## 三、盘前预判与观察清单" in report
    assert "## 二、六模块深度复盘" not in report
    assert "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。" in report


def test_key_points_uses_intraday_briefing_structure():
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
    assert "## 一、盘中市场快照" in report
    assert "## 三、赚钱效应与风险监控" in report
    assert "## 四、盘中预判与观察清单" in report
    assert "### M5. 特征分组" not in report
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


def test_portfolio_advice_describes_negative_extreme_index_move_as_drop():
    sections = _portfolio_advice_sections(
        {"details": []},
        {"a_indices": [{"name": "创业板指", "change_pct": -3.47}]},
        {},
        {"pool_stats": {}},
        {"pool_stats": {}},
    )

    assert any("创业板指单日跌幅达到3.47%" in item for item in sections["risks"])
    assert not any("涨幅达到-3.47%" in item for item in sections["risks"])
