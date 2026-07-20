import json
from datetime import datetime

import pytest

from stock_analysis import global_markets
from stock_analysis.market_calendar import is_session_day, session_hours
from stock_analysis.market_time import detect_market_session, resolve_trade_date
from stock_analysis.normalize import normalize_code
from stock_analysis.reached_evidence import load_reached_primary_evidence
from stock_analysis.sources.router import build_quote_route


class _Response:
    def __init__(self, *, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Session:
    def __init__(self, response):
        self.response = response

    def get(self, *_args, **_kwargs):
        return self.response


def test_jp_kr_symbols_are_explicit_and_routes_are_market_specific():
    assert normalize_code("JP:7203") == "7203.T"
    assert normalize_code("KR:005930") == "005930.KS"
    assert normalize_code("247540.KQ") == "247540.KQ"
    assert build_quote_route("jp").chain == ["yahoo-chart", "last-success-cache"]
    assert build_quote_route("kr").chain[:2] == ["naver-chart", "yahoo-chart"]


def test_calendar_snapshot_covers_election_labor_day_and_tse_hours_change():
    assert not is_session_day("20240410", "kr")
    assert not is_session_day("20240501", "kr")
    assert not is_session_day("20240212", "jp")
    assert session_hours("20241101", "jp").close.hour == 15
    assert session_hours("20241105", "jp").close.minute == 30
    with pytest.raises(ValueError, match="only verified"):
        is_session_day("20280104", "jp")


def test_market_time_uses_jp_break_and_kr_holidays():
    assert detect_market_session(datetime(2026, 7, 17, 12, 0), "jp").label == "午间"
    assert detect_market_session(datetime(2026, 7, 20, 10, 0), "jp").label == "休市"
    assert resolve_trade_date(datetime(2024, 4, 10, 12, 0), "kr") == "20240409"


def test_naver_history_parser_keeps_raw_ohlcv(monkeypatch):
    text = '[["날짜"],["20240627",81300,81600,80500,81600,11739720],["20240628",81900,81900,80800,81500,9455929]]'
    monkeypatch.setattr(global_markets, "_direct_session", lambda: _Session(_Response(text=text)))
    result = global_markets.fetch_naver_history("005930.KS", "20240628")
    assert result["source"] == "naver-chart"
    assert result["rows"][-1] == {
        "date": "20240628",
        "open": 81900.0,
        "high": 81900.0,
        "low": 80800.0,
        "close": 81500.0,
        "volume": 9455929.0,
        "adj_close": None,
    }


def test_naver_financials_discard_estimates_and_scale_monetary_values(monkeypatch):
    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 20)

    table = """
    <div class="section cop_analysis"><table><thead><tr>
    <th scope="col">2025.12</th><th scope="col">2026.12<em>(E)</em></th>
    </tr></thead><tbody>
    <tr><th scope="row"><strong>매출액</strong></th><td>1,234</td><td>9,999</td></tr>
    <tr><th scope="row"><strong>EPS(원)</strong></th><td>100</td><td>200</td></tr>
    </tbody></table></div>
    """
    monkeypatch.setattr(global_markets, "_direct_session", lambda: _Session(_Response(text=table)))
    monkeypatch.setattr(global_markets, "datetime", _Now)
    result = global_markets.fetch_naver_financials("005930.KS", "20260720")
    assert len(result["periods"]) == 1
    assert result["periods"][0]["revenue"] == 123_400_000_000
    assert result["periods"][0]["basic_eps"] == 100


def test_reached_primary_evidence_enforces_symbol_url_and_date(tmp_path):
    path = tmp_path / "primary.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "symbol": "7203.T",
                "retrieval_method": "agent-reach-or-host-web",
                "items": [
                    {
                        "module": "C2",
                        "metric": "revenue",
                        "period": "2026FY",
                        "value": 48_000_000_000_000,
                        "currency": "JPY",
                        "source": "issuer annual report",
                        "url": "https://example.com/annual-report.pdf",
                        "published_at": "2026-05-01",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_reached_primary_evidence(path, symbol="JP:7203", trade_date="20260720")
    assert loaded["C2"][0]["source_type"] == "issuer_primary_disclosure"
    assert loaded["C2"][0]["validation_status"] == "conditional"
    with pytest.raises(ValueError, match="publication-date cutoff"):
        load_reached_primary_evidence(path, symbol="7203.T", trade_date="20260430")
