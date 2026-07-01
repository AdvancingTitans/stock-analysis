import json

from stock_analysis.models import Holding
from stock_analysis.profile import load_holdings_from_profile, save_holdings_to_profile


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
    monkeypatch.setenv("STOCK_ANALYSIS_PROFILE", str(path))

    holdings = load_holdings_from_profile()

    assert [(item.symbol, item.buy_price) for item in holdings] == [
        ("600519", 1420.5),
        ("161725", 1.234),
    ]


def test_save_holdings_uses_stock_analysis_profile_namespace(monkeypatch, tmp_path):
    profile = tmp_path / ".stock_analysis" / "profile.json"
    young_profile = tmp_path / ".young_stock" / "profile.json"
    monkeypatch.setenv("STOCK_ANALYSIS_PROFILE", str(profile))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(young_profile))

    save_holdings_to_profile(
        [
            Holding(
                symbol="600519",
                asset_type="stock",
                market="a",
                quantity=100,
                buy_date="2026-01-15",
                buy_price=1420.5,
                currency="CNY",
                name="贵州茅台",
            ),
            Holding(
                symbol="161725",
                asset_type="fund",
                market="fund",
                quantity=1000,
                buy_date="2026-01-10",
                buy_price=1.234,
                currency="CNY",
                name="招商中证白酒指数",
            ),
        ]
    )

    assert profile.exists()
    assert not young_profile.exists()
    saved = json.loads(profile.read_text(encoding="utf-8"))
    assert saved["positions"]["stocks"]["600519"]["buy_price"] == 1420.5
    assert saved["positions"]["funds"]["161725"]["quantity"] == 1000
    assert [(item.symbol, item.buy_price) for item in load_holdings_from_profile()] == [
        ("600519", 1420.5),
        ("161725", 1.234),
    ]
