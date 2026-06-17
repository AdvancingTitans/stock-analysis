from stock_analysis.normalize import normalize_code


def test_normalize_code_for_mainland_sources():
    assert normalize_code("sh600519", source="tencent") == "600519"
    assert normalize_code("sz399001", source="eastmoney") == "399001"
    assert normalize_code("000300.SH", source="generic") == "000300"


def test_normalize_code_for_hk_and_us():
    assert normalize_code("hk00700", source="tencent") == "0700.HK"
    assert normalize_code("00700.HK", source="sina") == "0700.HK"
    assert normalize_code("usAAPL", source="tencent") == "AAPL"
    assert normalize_code("gb_aapl", source="sina") == "AAPL"


def test_normalize_code_for_funds():
    assert normalize_code("fu161725", source="sina") == "161725"
    assert normalize_code("161725", source="eastmoney") == "161725"
