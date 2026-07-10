from stock_analysis import market_core


def test_annual_slice_paginates_and_caches_only_complete_results(monkeypatch):
    responses = [
        {"result": {"count": 2, "pages": 2, "data": [{"SECURITY_CODE": "000001"}]}},
        {"result": {"count": 2, "pages": 2, "data": [{"SECURITY_CODE": "000002"}]}},
    ]
    saved = []
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args: saved.append(args))
    monkeypatch.setattr(market_core, "fetch_json", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(market_core.time, "sleep", lambda _: None)

    result = market_core.fetch_a_share_annual_report_slice(2025, page_size=1)

    assert result["complete"] is True
    assert result["pages_fetched"] == 2
    assert result["unique_symbols"] == 2
    assert len(saved) == 1


def test_annual_slice_never_caches_partial_result(monkeypatch):
    saved = []
    monkeypatch.setattr(market_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_core, "cache_save", lambda *args: saved.append(args))
    monkeypatch.setattr(
        market_core,
        "fetch_json",
        lambda *args, **kwargs: {"result": {"count": 2, "pages": 2, "data": [{"SECURITY_CODE": "000001"}]}},
    )
    monkeypatch.setattr(market_core.time, "sleep", lambda _: None)

    result = market_core.fetch_a_share_annual_report_slice(2025, page_size=1)

    assert result["complete"] is False
    assert result["pages_fetched"] == 2
    assert saved == []
