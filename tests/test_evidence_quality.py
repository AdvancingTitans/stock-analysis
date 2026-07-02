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
