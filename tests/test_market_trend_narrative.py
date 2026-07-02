from stock_analysis.reporting import _market_trend_narrative


def test_market_trend_narrative_detects_growth_divergence():
    text = _market_trend_narrative(
        {
            "a_indices": [
                {"name": "上证指数", "change_pct": 0.4},
                {"name": "创业板指", "change_pct": -1.8},
                {"name": "科创50", "change_pct": -2.4},
            ]
        },
        {"pool_stats": {"zt_count": 152}},
        {"pool_stats": {"blowup_ratio": 0.327}},
    )
    assert "分化" in text
    assert "炸板率" in text
    assert "A股主要指数整体强于港股和美股" not in text
