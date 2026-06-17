from stock_analysis.quality import EvidenceQuality


def test_quality_score_and_degrade_modes():
    quality = EvidenceQuality(
        module_scores={"M1": 20, "M2": 18, "M3": 20, "M4": 15, "M5": 10, "M6": 10},
        missing_modules=["M5"],
    )
    assert quality.total_score == 93
    assert quality.degrade_mode == "full"

    degraded = EvidenceQuality(
        module_scores={"M1": 20, "M2": 0, "M3": 0, "M4": 0, "M5": 0, "M6": 0},
        missing_modules=["M2", "M3", "M4", "M5", "M6"],
    )
    assert degraded.total_score == 20
    assert degraded.degrade_mode == "simplified"
