from stock_analysis import market_core


def test_a_share_financial_snapshot_combines_statement_rows(monkeypatch):
    calls = []

    def fake_datacenter(report_name, **kwargs):
        calls.append((report_name, kwargs))
        if report_name == "RPT_LICO_FN_CPD":
            return [
                {
                    "SECURITY_CODE": "600519",
                    "SECURITY_NAME_ABBR": "贵州茅台",
                    "QDATE": "2026Q1",
                    "REPORTDATE": "2026-03-31 00:00:00",
                    "NOTICE_DATE": "2026-04-29 00:00:00",
                    "WEIGHTAVG_ROE": 10.57,
                    "XSMLL": 91.2,
                    "BASIC_EPS": 19.16,
                    "BPS": 202.3,
                    "TOTAL_OPERATE_INCOME": 78_000_000_000,
                    "PARENT_NETPROFIT": 25_000_000_000,
                }
            ]
        if report_name == "RPT_DMSK_FN_BALANCE":
            return [
                {
                    "SECURITY_CODE": "600519",
                    "REPORT_DATE": "2026-03-31 00:00:00",
                    "DEBT_ASSET_RATIO": 12.12,
                    "TOTAL_ASSETS": 320_000_000_000,
                    "TOTAL_LIABILITIES": 38_784_000_000,
                }
            ]
        if report_name == "RPT_DMSK_FN_CASHFLOW":
            return [
                {
                    "SECURITY_CODE": "600519",
                    "REPORT_DATE": "2026-03-31 00:00:00",
                    "NETCASH_OPERATE": 26_910_000_000,
                    "CONSTRUCT_LONG_ASSET": 605_000_000,
                }
            ]
        return []

    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "eastmoney_datacenter", fake_datacenter)

    snapshot = market_core.fetch_a_share_financial_snapshot("600519", "20260708")

    assert snapshot["available"] is True
    assert snapshot["symbol"] == "600519"
    assert snapshot["name"] == "贵州茅台"
    assert snapshot["availability"]["roe"] is True
    assert snapshot["availability"]["debt_asset_ratio"] is True
    assert snapshot["availability"]["free_cash_flow_lite"] is True
    assert snapshot["periods"][0]["report_date"] == "2026-03-31"
    assert snapshot["periods"][0]["roe_weighted"] == 10.57
    assert snapshot["periods"][0]["debt_asset_ratio"] == 12.12
    assert snapshot["periods"][0]["free_cash_flow_lite"] == 26_305_000_000
    assert snapshot["forecasts"]["available"] is False
    assert "仅在公司披露时存在" in snapshot["limitations"][0]
    assert {call[0] for call in calls} >= {
        "RPT_LICO_FN_CPD",
        "RPT_DMSK_FN_BALANCE",
        "RPT_DMSK_FN_CASHFLOW",
        "RPT_PUBLIC_OP_NEWPREDICT",
        "RPT_PUBLIC_OP_NEWDISCOVER",
    }


def test_a_share_financial_snapshot_keeps_disclosure_gaps(monkeypatch):
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "eastmoney_datacenter", lambda *args, **kwargs: [])

    snapshot = market_core.fetch_a_share_financial_snapshot("600519", "20260708")

    assert snapshot["available"] is False
    assert snapshot["periods"] == []
    assert snapshot["availability"]["roe"] is False
    assert "业绩预告/快报仅在公司披露时存在" in snapshot["gaps"]
