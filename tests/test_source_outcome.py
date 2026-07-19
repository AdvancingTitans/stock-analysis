from stock_analysis.source_outcome import capture_source


def test_source_failure_is_distinct_from_unavailable_data():
    def fail():
        raise TimeoutError("fixture timeout")

    failed = capture_source("quote", fail, None)
    unavailable = capture_source("quote", lambda: None, None)

    assert failed.event(available=False) == {
        "source": "quote",
        "status": "source_error",
        "error_type": "TimeoutError",
    }
    assert unavailable.event(available=False) == {"source": "quote", "status": "unavailable"}
