import json
from pathlib import Path

import pytest

from stock_analysis.screening_baseline import (
    FINANCIAL_FIELD_CONTRACT,
    PERCENT_POINTS,
    annual_report_filter,
    normalize_annual_financial_row,
    normalize_bse_security_master_row,
    normalize_sse_security_master_row,
    normalize_szse_security_master_row,
)


def _fixture_rows():
    return json.loads((Path(__file__).parent / "fixtures" / "eastmoney_2025_annual_rows.json").read_text())


def test_annual_report_filter_excludes_new_third_board_records():
    assert annual_report_filter(2025) == '(DATATYPE="2025年 年报")(SECURITY_TYPE="A股")'


def test_normalized_financial_contract_keeps_percent_points_and_negative_growth():
    normalized = normalize_annual_financial_row(_fixture_rows()[0], fiscal_year=2025)

    assert normalized["report_period"] == "2025FY"
    assert normalized["fields"]["roe_weighted_pct"] == {
        "raw_value": 9.15,
        "normalized_value": 9.15,
        "unit": PERCENT_POINTS,
        "status": "reported",
    }
    assert normalized["fields"]["revenue_growth_yoy_pct"]["normalized_value"] == pytest.approx(-10.3977640683)
    assert FINANCIAL_FIELD_CONTRACT["revenue_growth_yoy_pct"]["source_field"] == "YSTZ"


def test_normalized_financial_contract_rejects_non_a_share_rows():
    with pytest.raises(ValueError, match="SECURITY_TYPE"):
        normalize_annual_financial_row(_fixture_rows()[2], fiscal_year=2025)


def test_sse_security_master_record_requires_snapshot_date_and_listing_date():
    row = {
        "LISTING_BOARD": "0",
        "SECURITY_ABBR_A": "浦发银行",
        "SECURITY_CODE_A": "600000",
        "LISTING_DATE": "1999-11-10",
    }

    assert normalize_sse_security_master_row(row, universe_as_of="2026-07-10") == {
        "symbol": "600000",
        "name": "浦发银行",
        "exchange": "SSE",
        "board": "main",
        "listed_at": "1999-11-10",
        "universe_as_of": "2026-07-10",
        "source": "sse:stock-list",
    }


def test_szse_and_bse_records_share_the_same_security_master_shape():
    szse = normalize_szse_security_master_row(
        {
            "bk": "主板",
            "agdm": "000001",
            "agjc": "<a href='x'><u>平安银行</u></a>",
            "agssrq": "1991-04-03",
        },
        universe_as_of="2026-07-10",
    )
    bse = normalize_bse_security_master_row(
        {"xxzqdm": "920000", "xxzqjc": "安徽凤凰", "fxssrq": "20201223"},
        universe_as_of="2026-07-10",
    )

    assert szse["name"] == "平安银行"
    assert szse["source"] == "szse:stock-list"
    assert bse["listed_at"] == "2020-12-23"
    assert bse["source"] == "bse:stock-list"
