from stock_analysis import analytics


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": {
                "hk00700": {
                    "day": [
                        ["2026-06-17", "500.0", "510.0", "515.0", "498.0", "100"],
                        ["2026-06-18", "510.0", "520.0", "525.0", "508.0", "120"],
                    ]
                }
            }
        }


class _Session:
    def get(self, url, **kwargs):
        assert "gtimg.cn" in url
        assert kwargs["params"]["param"].startswith("hk00700,day")
        return _Response()


def test_hk_kline_uses_tencent_without_yahoo(monkeypatch):
    monkeypatch.setattr(analytics, "_direct_session", lambda: _Session())
    assert analytics._fetch_hk_closes_tencent("0700.HK", 30) == [510.0, 520.0]
