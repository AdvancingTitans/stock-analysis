from stock_analysis.futu_public import (
    build_public_pulse,
    classify_community_posts,
    filter_symbol_posts,
)


def test_filter_symbol_posts_rejects_global_feed_noise_and_low_quality():
    posts = [
        {
            "id": "1",
            "title": '<nnstock stockcode="NVDA" stocksymbol="NVDA.US">NVDA</nnstock> AI需求继续增长，回调仍看多',
            "desc": "",
            "publish_time": "1781779000",
        },
        {
            "id": "2",
            "title": '<nnstock stockcode="TSLA" stocksymbol="TSLA.US">TSLA</nnstock> 今晚380',
            "desc": "",
            "publish_time": "1781778990",
        },
        {
            "id": "3",
            "title": '<nnstock stockcode="NVDA" stocksymbol="NVDA.US">NVDA</nnstock> 涨',
            "desc": "",
            "publish_time": "1781778980",
        },
    ]

    filtered = filter_symbol_posts(posts, symbol="NVDA", name="英伟达")

    assert len(filtered) == 1
    assert "AI需求" in filtered[0]["text"]


def test_community_sentiment_requires_three_valid_posts():
    result = classify_community_posts(
        [
            {"text": "AI需求强劲，回调仍看多", "publish_time": "1"},
            {"text": "估值太高，担心继续下跌", "publish_time": "2"},
        ]
    )

    assert result["status"] == "insufficient"
    assert result["sample_count"] == 2
    assert result["label"] == "证据不足"


def test_build_public_pulse_deduplicates_news_and_keeps_evidence_link():
    pulse = build_public_pulse(
        symbol="NVDA",
        name="英伟达",
        market="us",
        news_items=[
            {
                "title": "<em>NVIDIA</em> AI demand expands as cloud orders rise",
                "publish_time": "1781755409",
                "url": "https://news.futunn.com/post/1",
            },
            {
                "title": "<em>NVIDIA</em> AI demand expands as cloud orders rise",
                "publish_time": "1781755300",
                "url": "https://news.futunn.com/post/2",
            },
            {
                "title": "<em>NVIDIA</em> faces export restrictions in a key market",
                "publish_time": "1781755200",
                "url": "https://news.futunn.com/post/3",
            },
        ],
        feed_items=[],
    )

    assert pulse["news_count"] == 2
    assert pulse["news_tone"] == "中性"
    assert pulse["event_title"] == "NVIDIA AI demand expands as cloud orders rise"
    assert pulse["evidence_url"] == "https://news.futunn.com/post/1"
    assert pulse["community_label"] == "证据不足"


def test_build_public_pulse_excludes_titles_using_stock_only_as_benchmark():
    pulse = build_public_pulse(
        symbol="600519",
        name="贵州茅台",
        market="a",
        news_items=[
            {
                "title": "4只千元股持续受追捧！中际旭创总市值超过贵州茅台",
                "publish_time": "1781755409",
                "url": "https://news.futunn.com/post/benchmark",
            },
            {
                "title": "芯片产业链大涨，中际旭创反超贵州茅台",
                "publish_time": "1781755350",
                "url": "https://news.futunn.com/post/benchmark-2",
            },
            {
                "title": "贵州茅台发布年度分红安排",
                "publish_time": "1781755300",
                "url": "https://news.futunn.com/post/direct",
            },
        ],
        feed_items=[],
    )

    assert pulse["news_count"] == 1
    assert pulse["event_title"] == "贵州茅台发布年度分红安排"
    assert pulse["evidence_url"] == "https://news.futunn.com/post/direct"


def test_build_public_pulse_distinguishes_source_failure_from_empty_results():
    pulse = build_public_pulse(
        symbol="NVDA",
        name="英伟达",
        market="us",
        news_items=[],
        feed_items=[],
        news_status="error",
        feed_status="error",
    )

    assert pulse["news_tone"] == "数据暂不可用"
    assert pulse["community_label"] == "数据暂不可用"
