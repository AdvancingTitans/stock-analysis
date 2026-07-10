import json
from pathlib import Path
from time import perf_counter

import pytest

from stock_analysis.screening import (
    load_security_master,
    parse_filter,
    parse_sort,
    render_markdown,
    screen,
)


def _annual_rows():
    return json.loads((Path(__file__).parent / "fixtures" / "eastmoney_2025_annual_rows.json").read_text())[:2]


def _universe():
    return {
        "complete": True,
        "reported_total": 1,
        "pages_fetched": 1,
        "unique_symbols": 1,
        "universe_as_of": "2026-07-10",
        "sources": ["https://www.sse.com.cn/assortment/stock/list/share/"],
        "records": [{"symbol": _annual_rows()[0]["SECURITY_CODE"]}],
    }


def _pagination():
    return {"complete": True, "reported_total": 2, "expected_pages": 1, "pages_fetched": 1}


def test_screen_uses_strict_and_filters_and_keeps_outside_universe_unknown():
    result = screen(
        _annual_rows(),
        fiscal_year=2025,
        universe=_universe(),
        filters=[parse_filter("roe_weighted:gt:8%"), parse_filter("revenue_growth_yoy:gt:-11")],
        sort=parse_sort("roe_weighted:desc"),
        limit=20,
        pagination=_pagination(),
    )

    assert result["results"][0]["symbol"] == _annual_rows()[0]["SECURITY_CODE"]
    assert result["decisions"][0]["status"] == "PASS"
    assert result["decisions"][1]["status"] == "UNKNOWN"
    assert result["quality"]["whole_market_eligible"] is True
    assert "条件命中股票" in render_markdown(result)


def test_screen_treats_equal_value_as_fail_and_missing_as_unknown():
    rows = _annual_rows()
    rows[0]["WEIGHTAVG_ROE"] = 9.15
    rows[1]["WEIGHTAVG_ROE"] = None
    universe = _universe()
    universe["reported_total"] = universe["unique_symbols"] = 2
    universe["records"].append({"symbol": rows[1]["SECURITY_CODE"]})
    result = screen(
        rows,
        fiscal_year=2025,
        universe=universe,
        filters=[parse_filter("roe_weighted:gt:9.15")],
        sort=parse_sort("roe_weighted:desc"),
        limit=20,
        pagination=_pagination(),
    )

    assert [item["status"] for item in result["decisions"]] == ["FAIL", "UNKNOWN"]


def test_screen_rejects_partial_pagination_before_labeling_whole_market():
    with pytest.raises(ValueError, match="partial"):
        screen(
            _annual_rows(),
            fiscal_year=2025,
            universe=_universe(),
            filters=[parse_filter("roe_weighted:gt:8")],
            sort=parse_sort("roe_weighted:desc"),
            limit=20,
            pagination={"complete": False},
        )


def test_load_security_master_rejects_partial_or_non_unique_snapshot(tmp_path):
    path = tmp_path / "universe.json"
    path.write_text(json.dumps({**_universe(), "complete": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="partial"):
        load_security_master(path)

    path.write_text(json.dumps({**_universe(), "unique_symbols": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="uniqueness"):
        load_security_master(path)


def test_parse_rejects_unsupported_conditions():
    with pytest.raises(ValueError, match="only strict gt"):
        parse_filter("roe_weighted:gte:8")
    with pytest.raises(ValueError, match="unsupported screening field"):
        parse_sort("price:desc")


def test_six_thousand_row_fixture_screening_finishes_under_one_second():
    seed = _annual_rows()[0]
    rows = []
    records = []
    for index in range(6000):
        symbol = f"{index:06d}"
        row = dict(seed, SECURITY_CODE=symbol, SECURITY_NAME_ABBR=f"样本{index}")
        rows.append(row)
        records.append({"symbol": symbol})
    universe = {
        **_universe(),
        "reported_total": 6000,
        "unique_symbols": 6000,
        "records": records,
    }

    started = perf_counter()
    result = screen(
        rows,
        fiscal_year=2025,
        universe=universe,
        filters=[parse_filter("roe_weighted:gt:8")],
        sort=parse_sort("roe_weighted:desc"),
        limit=20,
        pagination={"complete": True},
    )

    assert len(result["results"]) == 20
    assert perf_counter() - started < 1.0
