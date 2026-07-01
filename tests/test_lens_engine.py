from stock_analysis.lens_engine import LensContext, LensEngine


def _sample_evidence():
    return {
        "M1": {
            "available": True,
            "a_indices": [
                {"name": "上证指数", "change_pct": 1.2, "trade_date": "20260618"},
                {"name": "创业板指", "change_pct": -0.4, "trade_date": "20260618"},
            ],
            "hk_indices": [{"name": "恒生指数", "change_pct": 0.3, "trade_date": "20260618"}],
            "us_indices": [{"name": "纳斯达克", "change_pct": 0.8, "trade_date": "20260617"}],
            "breadth": {"available": True, "up": 3200, "down": 1800, "ratio": 1.78},
        },
        "M2": {"available": True, "summary": "AI 与消费轮动"},
        "M3": {"available": True, "pool_stats": {"zt_count": 48, "blowup_ratio": 0.18}},
        "M4": {"available": True, "pool_stats": {"dt_count": 5, "blowup_ratio": 0.18}},
        "M5": {"available": True, "summary": "成长风格活跃"},
        "M6": {"available": True, "summary": "结构性承接仍在", "resilient": ["半导体", "白酒"]},
    }


def _sample_pulses():
    return [
        {
            "symbol": "NVDA",
            "news_tone": "偏正面",
            "news_count": 2,
            "event_title": "NVIDIA AI demand expands as cloud orders rise",
            "community_label": "偏多",
            "community_sample_count": 6,
            "community_bull_pct": 66.7,
            "community_bear_pct": 16.7,
            "evidence_url": "https://news.futunn.com/post/1",
        },
        {
            "symbol": "600519",
            "news_tone": "中性",
            "news_count": 1,
            "event_title": "贵州茅台发布分红安排",
            "community_label": "分歧",
            "community_sample_count": 4,
            "community_bull_pct": 50.0,
            "community_bear_pct": 50.0,
        },
    ]


def _sample_chinese_news_items():
    return [
        {
            "title": "贵州茅台发布重大分红安排",
            "source": "东方财富",
            "urgency": "medium",
            "relevance_score": 0.95,
            "sentiment_score": 0.4,
        },
        {
            "title": "贵州茅台发布重大分红安排",
            "source": "新浪财经",
            "urgency": "medium",
            "relevance_score": 0.8,
            "sentiment_score": 0.35,
        },
        {
            "title": "财联社：白酒板块出现政策预期扰动",
            "source": "财联社",
            "urgency": "high",
            "relevance_score": 0.9,
            "sentiment_score": -0.3,
        },
        {
            "title": "腾讯财经跟踪消费复苏线索",
            "source": "腾讯财经",
            "urgency": "low",
            "relevance_score": 0.6,
            "sentiment_score": 0.1,
        },
    ]


def _sample_chinese_community_items():
    return [
        {"source": "雪球", "text": "分红稳定，继续看多", "sentiment_score": 0.5},
        {"source": "东方财富股吧", "text": "估值还是有分歧", "sentiment_score": -0.1},
        {"source": "微博", "text": "消费复苏带来关注", "sentiment_score": 0.2},
    ]


def test_default_engine_uses_committee_and_deepens_m1_m6():
    context = LensEngine().build_context(_sample_evidence(), public_pulses=_sample_pulses())

    assert isinstance(context, LensContext)
    assert context.mode == "committee"
    assert context.lenses[:4] == ("buffett", "munger", "duan_yongping", "zhang_kun")
    assert "M1" in context.activated_modules
    assert "M6" in context.activated_modules
    assert context.adjusted_evidence["M1"]["committee_deep_analysis"]["cross_validation"]["lens_count"] == len(context.lenses)
    assert context.adjusted_evidence["M1"]["committee_deep_analysis"]["trend_consistency"]["direction"] == "分化"
    assert context.adjusted_evidence["M1"]["committee_deep_analysis"]["anomalies"]
    assert context.adjusted_evidence["M6"]["committee_deep_analysis"]["risk_score"] > 0
    assert context.community_sentiment_summary["overall_sentiment_band"] == "Mildly Bullish"
    assert context.community_sentiment_summary["confidence"] == "medium"
    assert context.community_sentiment_summary["overall_sentiment_score"] > 0
    assert context.community_sentiment_summary["key_sentiment_sources"][0]["symbol"] == "NVDA"
    assert context.community_sentiment_summary["source_breakdown"]["news"]["sample_count"] == 3
    assert context.community_sentiment_summary["source_breakdown"]["community"]["sample_count"] == 10
    assert context.community_sentiment_summary["cross_source_divergences"]
    assert context.community_sentiment_summary["dominant_narratives"]
    assert context.community_sentiment_summary["fundamental_sentiment_divergences"]
    assert context.community_sentiment_summary["sentiment_catalysts_or_risks"]
    assert context.community_sentiment_summary["sentiment_signal_table"][0]["source"] in {"news", "community"}
    assert any("committee" in note for note in context.debate_or_synthesis_notes)


def test_committee_adds_tradingagents_cn_news_framework():
    context = LensEngine().build_context(
        _sample_evidence(),
        public_pulses=_sample_pulses(),
        chinese_news_items=_sample_chinese_news_items(),
        chinese_community_items=_sample_chinese_community_items(),
    )

    summary = context.community_sentiment_summary

    assert summary["chinese_data_source_framework"]["market_data_sources"] == ["Tushare", "AkShare", "BaoStock"]
    assert "财联社" in summary["chinese_data_source_framework"]["high_priority_news_sources"]
    assert "多源聚合" in summary["news_analysis_framework"]["pipeline"][0]
    assert summary["chinese_news_analysis"]["raw_count"] == 4
    assert summary["chinese_news_analysis"]["deduplicated_count"] == 3
    assert summary["chinese_news_analysis"]["source_distribution"] == {"东方财富": 1, "财联社": 1, "腾讯财经": 1}
    assert summary["chinese_news_analysis"]["urgency_breakdown"]["high"] == 1
    assert summary["chinese_news_analysis"]["quality_assessment"]["level"] == "medium"
    assert summary["chinese_sentiment_components"]["news"]["sample_count"] == 3
    assert summary["chinese_sentiment_components"]["forum"]["status"] == "available"
    assert summary["chinese_sentiment_components"]["forum"]["sample_count"] == 3
    assert summary["chinese_sentiment_components"]["media"]["status"] == "registered_no_samples"
    assert summary["chinese_data_source_framework"]["source_status"]["雪球"] == "available"
    assert summary["chinese_data_source_framework"]["source_status"]["微博"] == "available"


def test_single_lens_constructor_keeps_legacy_call_shape():
    context = LensEngine(lens=" Buffett ").build_context(_sample_evidence())

    assert context.mode == "single"
    assert context.lenses == ("buffett",)
    assert "M1" in context.activated_modules
    assert "M6" in context.activated_modules
    assert context.community_sentiment_summary["status"] == "not_applicable"
    assert "lens_weight_adjustments" in context.adjusted_evidence["_meta"]


def test_lens_engine_accepts_natural_language_aliases():
    single = LensEngine(lens="巴菲特模式").build_context(_sample_evidence())
    debate = LensEngine(mode="adversarial", lenses=("巴菲特", "芒格")).build_context(_sample_evidence())

    assert single.lenses == ("buffett",)
    assert single.lens_labels["buffett"] == "巴菲特"
    assert debate.lenses == ("buffett", "munger")


def test_adversarial_mode_requires_two_lenses_and_records_debate_notes():
    context = LensEngine(mode="adversarial", lenses=("buffett", "soros")).build_context(_sample_evidence())

    assert context.mode == "adversarial"
    assert context.lenses == ("buffett", "soros")
    assert context.community_sentiment_summary["status"] == "not_applicable"
    assert any("buffett" in note and "soros" in note for note in context.debate_or_synthesis_notes)


def test_explicit_empty_public_pulses_do_not_fall_back_to_evidence_meta():
    evidence = {
        **_sample_evidence(),
        "_meta": {"portfolio_public_pulse": _sample_pulses()},
    }

    context = LensEngine().build_context(evidence, public_pulses=[])

    assert context.community_sentiment_summary["status"] == "insufficient"
    assert context.community_sentiment_summary["key_sentiment_sources"] == []
