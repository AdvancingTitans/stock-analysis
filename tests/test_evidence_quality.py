from stock_analysis.evidence import EvidenceBundle


def test_m1_partial_score_when_turnover_and_breadth_missing():
    bundle = EvidenceBundle(
        trade_date="20260701",
        modules={
            "M1": {
                "available": True,
                "a_indices": [{"name": "上证指数", "price": 4100, "change_pct": 0.4, "turnover": None}],
                "hk_indices": [],
                "us_indices": [],
                "breadth": {"available": False},
            },
            "M2": {"available": True, "industry_top20": [{"name": "半导体"}], "concentration": {"top1_ratio": 0.1}},
            "M3": {"available": True},
            "M4": {"available": True},
            "M5": {"available": True},
            "M6": {"available": True},
        },
    )
    quality = bundle.quality()
    assert quality.module_scores["M1"] == 8
    assert "turnover" in bundle.meta["module_diagnostics"]["M1"]["gaps"]
    assert "M1" not in quality.missing_modules


def test_m1_diagnostics_name_indices_without_turnover_or_volume():
    bundle = EvidenceBundle(
        trade_date="20260701",
        modules={
            "M1": {
                "available": True,
                "a_indices": [{"name": "上证指数", "price": 4100, "change_pct": 0.4, "turnover": 1e12}],
                "hk_indices": [{"name": "国企指数", "price": 7600, "change_pct": 0.0, "turnover": 0}],
                "us_indices": [{"name": "标普500", "price": 7400, "change_pct": -0.2, "volume": None}],
                "breadth": {"available": True, "up": 100, "down": 50, "ratio": 2.0},
            },
            "M2": {"available": True, "industry_top20": [{"name": "半导体"}], "concentration": {"top1_ratio": 0.1}},
            "M3": {"available": True},
            "M4": {"available": True},
            "M5": {"available": True},
            "M6": {"available": True},
        },
    )

    quality = bundle.quality()

    gaps = bundle.meta["module_diagnostics"]["M1"]["gaps"]
    assert "index_activity:国企指数" in gaps
    assert "index_activity:标普500" in gaps
    assert quality.module_scores["M1"] == 18


def test_m2_partial_score_when_only_concentration_available():
    bundle = EvidenceBundle(
        trade_date="20260701",
        modules={
            "M1": {
                "available": True,
                "a_indices": [{"name": "上证指数", "price": 4100, "change_pct": 0.4, "turnover": 1e12}],
                "hk_indices": [{"name": "恒生指数", "price": 22000, "change_pct": -0.5, "turnover": 1e11}],
                "breadth": {"available": True, "up": 100, "down": 50, "ratio": 2.0},
            },
            "M2": {
                "available": False,
                "industry_top20": [],
                "concept_top20": [],
                "fund_flow": {},
                "concentration": {"top1_ratio": 0.07, "top3_ratio": 0.15},
            },
            "M3": {"available": True},
            "M4": {"available": True},
            "M5": {"available": True},
            "M6": {"available": True},
        },
    )
    quality = bundle.quality()
    assert quality.module_scores["M2"] == 4
    assert "M2" in quality.missing_modules


def test_m2_full_score_when_board_and_concentration_available():
    bundle = EvidenceBundle(
        trade_date="20260701",
        modules={
            "M1": {
                "available": True,
                "a_indices": [{"name": "上证指数", "price": 4100, "change_pct": 0.4, "turnover": 1e12}],
                "hk_indices": [{"name": "恒生指数", "price": 22000, "change_pct": -0.5, "turnover": 1e11}],
                "breadth": {"available": True, "up": 100, "down": 50, "ratio": 2.0},
            },
            "M2": {
                "available": True,
                "industry_top20": [{"name": "半导体"}],
                "concentration": {"top1_ratio": 0.07, "top3_ratio": 0.15},
                "fund_flow": {"_concept_in": "[]"},
            },
            "M3": {"available": True},
            "M4": {"available": True},
            "M5": {"available": True},
            "M6": {"available": True},
        },
    )
    quality = bundle.quality()
    assert quality.module_scores["M2"] == 20
    assert "M2" not in quality.missing_modules


def test_quality_adds_health_readiness_and_conditional_evidence_pack():
    bundle = EvidenceBundle(
        trade_date="20260701",
        modules={
            "M1": {
                "available": True,
                "a_indices": [
                    {
                        "name": "上证指数",
                        "price": 4100,
                        "change_pct": 0.4,
                        "turnover": 1e12,
                        "source": "tencent",
                    }
                ],
                "hk_indices": [{"name": "恒生指数", "price": 22000, "change_pct": -0.5, "turnover": 1e11}],
                "breadth": {"available": True, "up": 100, "down": 50, "ratio": 2.0},
            },
            "M2": {
                "available": True,
                "industry_top20": [{"name": "半导体", "change_pct": 5.6, "leader": "中芯国际"}],
                "fund_flow": {"_sector_in": '[["半导体", 99.5]]'},
                "concentration": {"top1_ratio": 0.07, "top3_ratio": 0.15},
            },
            "M3": {"available": True, "pool_stats": {"zt_count": 75, "leaders": [{"name": "亚联机械"}]}},
            "M4": {"available": True, "pool_stats": {"dt_count": 2, "blowup_ratio": 0.2}},
            "M5": {"available": True},
            "M6": {"available": True, "resilient": [{"name": "红利"}]},
        },
        meta={
            "source_events": [
                {"market": "a", "sources": ["tencent"], "trade_dates": ["20260701"]},
                {"module": "browser.camofox", "status": "数据源不可用"},
            ],
            "stock_financials": {
                "600519": {
                    "available": True,
                    "periods": [{"roe_weighted": 10.57, "free_cash_flow_lite": 26_305_000_000}],
                }
            },
            "portfolio_exposure": {"available": True, "hhi": 1.0, "top3_ratio": 1.0},
            "stock_microstructure": {
                "600519": {
                    "available": True,
                    "spread_bps": 0.0846,
                    "best_bid": 1182.19,
                    "best_ask": 1182.2,
                    "source": "sina",
                }
            },
            "stock_trading_costs": {
                "600519": {
                    "available": True,
                    "liquidity_bucket": "very_deep",
                    "daily_turnover_cny": 4_035_216_946,
                    "spread_bps": 0.0846,
                }
            },
            "news_samples": [{"title": "样本新闻", "url": "https://example.com"}],
        },
    )

    bundle.quality()

    assert bundle.meta["source_health"]["sources"]["tencent"]["status"] == "ok"
    assert bundle.meta["source_health"]["sources"]["browser.camofox"]["status"] == "unavailable"
    assert bundle.meta["field_health"]["M2.board_rankings"]["status"] == "available"
    assert bundle.meta["conditional_evidence"]["price_volume_behavior"]["status"] == "conditional"
    assert "returns_5d" in bundle.meta["conditional_evidence"]["price_volume_behavior"]["missing"]
    assert bundle.meta["conditional_evidence"]["sector_rotation_leaders"]["status"] == "available"
    assert bundle.meta["conditional_evidence"]["microstructure_costs"]["status"] == "available"
    assert bundle.meta["conditional_evidence"]["crowding_proxy"]["status"] == "conditional"
    assert bundle.meta["conditional_evidence"]["slippage_sensitivity"]["status"] == "conditional"
    assert bundle.meta["conditional_evidence"]["valuation_safety_margin"]["status"] == "conditional"
    assert "microstructure_costs" in bundle.meta["lens_readiness"]["simons"]["available"]
    assert "crowding_proxy" in bundle.meta["lens_readiness"]["simons"]["conditional"]
    assert bundle.meta["lens_readiness"]["o_neil"]["status"] == "partial"
    assert bundle.meta["lens_readiness"]["buffett"]["status"] == "partial"
