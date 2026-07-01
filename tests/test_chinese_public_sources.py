from stock_analysis.chinese_public_sources import (
    COMMUNITY_DISCUSSION_SOURCES,
    FINANCIAL_NEWS_SOURCES,
    build_chinese_public_signal_summary,
)


def test_chinese_public_source_registry_includes_news_and_social_sources():
    news_ids = {source["id"] for source in FINANCIAL_NEWS_SOURCES}
    community_ids = {source["id"] for source in COMMUNITY_DISCUSSION_SOURCES}

    assert {"cailianshe", "eastmoney", "sina_finance", "tencent_finance", "futu"} <= news_ids
    assert {"xueqiu", "eastmoney_guba", "weibo"} <= community_ids
    assert all(source["status"] == "registered" for source in FINANCIAL_NEWS_SOURCES)
    assert all(source["status"] == "registered" for source in COMMUNITY_DISCUSSION_SOURCES)


def test_chinese_public_signal_summary_counts_registered_sources_and_samples():
    summary = build_chinese_public_signal_summary(
        news_items=[
            {"source": "东方财富", "title": "贵州茅台发布重大分红安排", "sentiment_score": 0.4},
            {"source": "财联社", "title": "白酒板块出现政策预期扰动", "sentiment_score": -0.3},
        ],
        community_items=[
            {"source": "雪球", "text": "分红稳定，继续看多", "sentiment_score": 0.5},
            {"source": "东方财富股吧", "text": "估值还是有分歧", "sentiment_score": -0.1},
            {"source": "微博", "text": "消费复苏带来关注", "sentiment_score": 0.2},
        ],
    )

    assert summary["registered_news_sources"] == ["财联社", "东方财富", "新浪财经", "腾讯财经", "Futu"]
    assert summary["registered_community_sources"] == ["雪球", "东方财富股吧", "微博"]
    assert summary["news"]["sample_count"] == 2
    assert summary["community"]["sample_count"] == 3
    assert summary["source_status"]["雪球"] == "available"
    assert summary["source_status"]["新浪财经"] == "registered_no_samples"
