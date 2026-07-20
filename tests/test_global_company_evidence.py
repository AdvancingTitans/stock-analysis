from stock_analysis import company_evidence, sec_filings
from stock_analysis.execution_costs import build_execution_cost_model
from stock_analysis.models import QuoteData


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _SecSession:
    def get(self, url, **_kwargs):
        if url.endswith("company_tickers.json"):
            return _Response({"0": {"ticker": "TEST", "cik_str": 1}})
        fact = {
            "units": {
                "USD": [
                    {
                        "start": "2025-01-01", "end": "2025-12-31", "val": 100,
                        "accn": "0000000001-26-000001", "fy": 2025, "fp": "FY",
                        "form": "10-K", "filed": "2026-02-15",
                    }
                ]
            }
        }
        return _Response({
            "entityName": "Test Inc.",
            "facts": {"us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": fact,
                "NetIncomeLoss": fact,
                "NetCashProvidedByUsedInOperatingActivities": fact,
                "PaymentsToAcquirePropertyPlantAndEquipment": fact,
            }},
        })


def test_sec_companyfacts_uses_filing_date_cutoff(monkeypatch):
    monkeypatch.setattr(sec_filings, "_session", _SecSession)

    before = sec_filings.fetch_sec_financials("TEST", "20260214")
    after = sec_filings.fetch_sec_financials("TEST", "20260215")

    assert before["periods"] == []
    assert after["periods"][0]["notice_date"] == "2026-02-15"
    assert after["periods"][0]["free_cash_flow_lite"] == 0
    assert after["_source_type"] == "regulator_primary_xbrl"


def test_global_execution_model_does_not_apply_a_share_tax_rules():
    model = build_execution_cost_model(
        symbol="AAPL",
        market="us",
        currency="USD",
        price_volume={
            "liquidity": {"average_turnover_20d_local": 1_000_000_000},
            "metrics": {"annualized_volatility_60d_pct": 24},
        },
        microstructure={"spread_bps": 1},
    )

    assert model["model_status"] == "scenario_partial_market_rules"
    assert model["stamp_duty_bps_sell_assumption"] == 0
    assert model["turnover_input_field"] == "average_turnover_20d_local"
    assert model["scenarios"][0]["order_currency"] == "USD"


def test_us_company_pack_prefers_sec_and_emits_primary_reach_requests(monkeypatch):
    monkeypatch.setattr(
        company_evidence,
        "fetch_single_quote",
        lambda *_: QuoteData(symbol="AAPL", name="Apple", market="us", price=200, currency="USD", trade_date="20260720", source="sina"),
    )
    monkeypatch.setattr(company_evidence, "fetch_sec_financials", lambda *_: {
        "periods": [{
            "report_date": "2025-09-27", "period_label": "2025FY", "notice_date": "2025-10-31",
            "publication_date_status": "verified", "revenue": 100, "parent_net_profit": 20,
            "operating_cash_flow": 30, "capital_expenditure": 10, "free_cash_flow_lite": 20,
            "total_assets": 200, "total_liabilities": 100, "_currency": "USD",
            "_source": "SEC Company Facts", "_source_url": "https://data.sec.gov/test.json",
            "_source_type": "regulator_primary_xbrl",
        }],
        "_source_type": "regulator_primary_xbrl",
    })
    monkeypatch.setattr(company_evidence, "fetch_global_price_volume", lambda *_: {})
    monkeypatch.setattr(company_evidence, "fetch_company_disclosures", lambda *_: {"rows": []})
    monkeypatch.setattr(company_evidence, "fetch_futu_public_pulse", lambda *_: {})
    monkeypatch.setattr(company_evidence, "load_issuer_primary_facts", lambda *_: {f"C{i}": [] for i in range(1, 9)})

    pack = company_evidence.build_company_evidence("AAPL", "20260720")

    assert pack["modules"]["C2"]["available"] is True
    assert any(item.get("confidence") == "primary" for item in pack["modules"]["C2"]["evidence"])
    assert {row["module"] for row in pack["_meta"]["primary_evidence_requests"]} >= {"C1", "C4", "C5", "C7", "C8"}
