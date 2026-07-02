from stock_analysis.market_sentiment import (
    _title_sentiment,
    build_market_public_pulse,
    fetch_market_community_items,
    fetch_market_news_items,
)


def test_title_sentiment_detects_polarity():
    assert _title_sentiment("政策利好推动大盘反弹") > 0
    assert _title_sentiment("监管调查引发市场担忧") < 0


def test_build_market_public_pulse_from_news():
    items = [
        {"title": "A股放量上涨，北向资金回流", "sentiment_score": 0.4, "url": "https://example.com/a"},
        {"title": "创业板分化加剧", "sentiment_score": -0.1, "url": "https://example.com/b"},
        {"title": "沪指窄幅震荡", "sentiment_score": 0.0, "url": "https://example.com/c"},
    ]
    pulse = build_market_public_pulse(items)
    assert pulse is not None
    assert pulse["symbol"] == "MARKET"
    assert pulse["news_count"] == 3
    assert pulse["scope"] == "market_level"


def test_build_market_public_pulse_uses_community_samples():
    news_items = [
        {"title": "A股放量上涨，北向资金回流", "sentiment_score": 0.4, "url": "https://example.com/a"},
    ]
    community_items = [
        {"source": "雪球", "text": "大盘突破后继续看多", "sentiment_score": 0.5},
        {"source": "东方财富股吧", "text": "沪指反弹量能不错", "sentiment_score": 0.3},
        {"source": "微博", "text": "创业板强势上涨", "sentiment_score": 0.4},
    ]

    pulse = build_market_public_pulse(news_items, community_items)

    assert pulse is not None
    assert pulse["community_label"] == "偏多"
    assert pulse["community_sample_count"] == 3
    assert pulse["community_bull_pct"] == 100.0


def test_fetch_market_news_items_deduplicates(monkeypatch):
    def fake_search(keyword, size=5, lang="zh-CN", date_str=None, aliases=None):
        return {
            "data": [
                {"title": f"{keyword} 市场复盘", "source": "东方财富", "publish_time": 0, "url": "https://example.com/1"},
                {"title": f"{keyword} 市场复盘", "source": "新浪财经", "publish_time": 0, "url": "https://example.com/2"},
            ]
        }

    monkeypatch.setattr("stock_analysis.market_sentiment.market_core.combined_news_search", fake_search)
    items = fetch_market_news_items("20260701", size_per_keyword=2)
    assert len(items) >= 1
    titles = {item["title"] for item in items}
    assert len(titles) == len(items)


def test_fetch_market_community_items_falls_back_to_news_search(monkeypatch):
    monkeypatch.setattr(
        "stock_analysis.market_sentiment.market_core.futu_stock_feed",
        lambda *args, **kwargs: {"data": []},
    )

    def fake_search(keyword, size=3, lang="zh-CN", date_str=None, aliases=None):
        return {
            "data": [
                {
                    "title": f"{keyword} 投资者讨论看多反弹",
                    "source": "雪球",
                    "publish_time": 0,
                    "url": "https://example.com/community",
                }
            ]
        }

    monkeypatch.setattr("stock_analysis.market_sentiment.market_core.combined_news_search", fake_search)

    items = fetch_market_community_items("20260701", size_per_keyword=1)

    assert items
    assert items[0]["source"] == "雪球"


def test_fetch_market_community_items_uses_recent_discussion_proxy(monkeypatch):
    monkeypatch.setattr(
        "stock_analysis.market_sentiment.market_core.futu_stock_feed",
        lambda *args, **kwargs: {"data": []},
    )

    def fake_search(keyword, size=3, lang="zh-CN", date_str=None, aliases=None):
        if date_str:
            return {"data": []}
        return {
            "data": [
                {
                    "title": "A股上半年收官，投资者讨论回购分红",
                    "source": "futu_news",
                    "publish_time": "1782893233",
                    "url": "https://example.com/recent",
                },
                {
                    "title": "霍尼韦尔投资者电话会议",
                    "source": "futu_news",
                    "publish_time": "1782893233",
                    "url": "https://example.com/offtopic",
                },
            ]
        }

    monkeypatch.setattr("stock_analysis.market_sentiment.market_core.combined_news_search", fake_search)

    items = fetch_market_community_items("20260702", size_per_keyword=1)

    assert len(items) == 1
    assert items[0]["source"] == "财经社区聚合"
    assert "A股" in items[0]["text"]
