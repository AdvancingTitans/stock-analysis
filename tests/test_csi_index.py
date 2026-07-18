from stock_analysis.csi_index import build_csi_index_snapshot


def test_csi_snapshot_selects_complete_constituents_weights_and_daily_valuation():
    tables = {
        "cons": [
            ["日期Date", "成份券代码Constituent Code", "成份券名称Constituent Name", "交易所Exchange"],
            ["20260717", "001309", "德明利", "深圳证券交易所"],
            ["20260717", "688256", "寒武纪", "上海证券交易所"],
        ],
        "closeweight": [
            ["日期Date", "成份券代码Constituent Code", "权重(%)weight"],
            ["20260630", "001309", 2.162],
            ["20260630", "688256", 7.24],
        ],
        "indicator": [
            ["日期Date", "市盈率1（总股本）P/E1", "市盈率2（计算用股本）P/E2", "股息率1（总股本）D/P1", "股息率2（计算用股本）D/P2"],
            ["20260718", 120.0, 118.0, 0.14, 0.15],
            ["20260717", 111.82, 108.15, 0.15, 0.16],
        ],
    }

    def downloader(url):
        return next(rows for name, rows in tables.items() if f"/{name}/" in url)

    snapshot = build_csi_index_snapshot(
        "H30184", "20260717", downloader=downloader, performance_loader=lambda *_: []
    )

    assert snapshot["available"] is True
    assert snapshot["constituent_count"] == 2
    assert snapshot["constituents"][0]["code"] == "688256"
    assert snapshot["valuation"]["asof"] == "20260717"
    assert snapshot["valuation"]["pe_calculation_share"] == 108.15
    assert snapshot["weight_asof"] == "20260630"


def test_csi_snapshot_never_uses_future_valuation():
    header = ["日期Date", "市盈率2（计算用股本）P/E2"]
    tables = {
        "cons": [["日期Date", "成份券代码Constituent Code", "成份券名称Constituent Name", "交易所Exchange"], ["20260717", "001309", "德明利", "深圳"]],
        "closeweight": [["日期Date", "成份券代码Constituent Code", "权重(%)weight"], ["20260630", "001309", 100.0]],
        "indicator": [header, ["20260718", 120.0]],
    }

    def downloader(url):
        return next(rows for name, rows in tables.items() if f"/{name}/" in url)

    snapshot = build_csi_index_snapshot(
        "H30184", "20260717", downloader=downloader, performance_loader=lambda *_: []
    )
    assert snapshot["available"] is False
    assert snapshot["valuation"]["pe_calculation_share"] is None


def test_csi_snapshot_includes_strict_index_daily_series_and_risk_metrics():
    tables = {
        "cons": [["日期Date", "成份券代码Constituent Code", "成份券名称Constituent Name", "交易所Exchange"], ["20260717", "001309", "德明利", "深圳"]],
        "closeweight": [["日期Date", "成份券代码Constituent Code", "权重(%)weight"], ["20260630", "001309", 100.0]],
        "indicator": [["日期Date", "市盈率2（计算用股本）P/E2"], ["20260717", 108.15]],
    }

    def downloader(url):
        return next(rows for name, rows in tables.items() if f"/{name}/" in url)

    history = [
        {
            "tradeDate": f"2026{1 + day // 28:02d}{1 + day % 28:02d}",
            "open": 1000 + day,
            "high": 1010 + day,
            "low": 990 + day,
            "close": 1005 + day,
            "tradingVol": 1_000_000 + day,
            "tradingValue": 100 + day,
        }
        for day in range(90)
    ]
    snapshot = build_csi_index_snapshot(
        "H30184", "20260717", downloader=downloader, performance_loader=lambda *_: history
    )

    assert snapshot["history"]["available"] is True
    assert snapshot["history"]["sample_size"] >= 61
    assert {"returns_60d", "max_drawdown_60d_pct", "annualized_volatility_60d_pct"} <= set(
        snapshot["history"]["metrics"]
    )
    assert snapshot["history"]["rows"][-1]["date"] <= "20260717"
