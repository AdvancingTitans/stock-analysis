import json

from stock_analysis.profile import load_holdings_from_profile


def test_load_holdings_preserves_saved_buy_price(monkeypatch, tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "positions": {
                    "stocks": {
                        "600519": {
                            "buy_date": "2026-01-15",
                            "quantity": 100,
                            "buy_price": 1420.5,
                        }
                    },
                    "funds": {
                        "161725": {
                            "buy_date": "2026-01-10",
                            "quantity": 1000,
                            "buy_price": 1.234,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(path))

    holdings = load_holdings_from_profile()

    assert [(item.symbol, item.buy_price) for item in holdings] == [
        ("600519", 1420.5),
        ("161725", 1.234),
    ]
