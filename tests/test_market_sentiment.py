from stock_analysis.market_sentiment import (
    _title_sentiment,
    build_market_public_pulse,
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