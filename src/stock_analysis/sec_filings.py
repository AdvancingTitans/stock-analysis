"""Loginless SEC Company Facts adapter with publication-date cutoffs."""

from __future__ import annotations

from typing import Any

import requests

_SEC_USER_AGENT = "AdvancingTitans stock-analysis admin@advancingtitans.com"
_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}
_CONCEPTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "gross_profit": ("GrossProfit",),
    "operating_profit": ("OperatingIncomeLoss",),
    "parent_net_profit": ("NetIncomeLoss", "ProfitLoss"),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "total_debt": ("LongTermDebtAndFinanceLeaseObligations", "LongTermDebtAndCapitalLeaseObligations"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "cash_dividends_paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "share_repurchases": ("PaymentsForRepurchaseOfCommonStock",),
    "basic_eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
}


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": _SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return session


def _ticker_cik(symbol: str, session: requests.Session) -> int | None:
    response = session.get("https://www.sec.gov/files/company_tickers.json", timeout=20)
    response.raise_for_status()
    wanted = symbol.upper()
    for row in response.json().values():
        if str(row.get("ticker") or "").upper() == wanted:
            return int(row["cik_str"])
    return None


def _candidate_units(concept: dict[str, Any]) -> list[dict[str, Any]]:
    units = concept.get("units") or {}
    for key in ("USD", "USD/shares", "pure"):
        if units.get(key):
            return list(units[key])
    return next((list(rows) for rows in units.values() if rows), [])


def _period_kind(item: dict[str, Any]) -> str | None:
    form = str(item.get("form") or "")
    fp = str(item.get("fp") or "")
    if form.startswith(("10-K", "20-F", "40-F")) and fp == "FY":
        return "annual"
    if form.startswith("10-Q") and fp in {"Q1", "Q2", "Q3"}:
        return "quarter"
    return None


def fetch_sec_financials(symbol: str, trade_date: str) -> dict[str, Any]:
    """Return filed US-GAAP facts known on ``trade_date``; never use report end as filing date."""

    session = _session()
    cik = _ticker_cik(symbol, session)
    if cik is None:
        return {"periods": [], "_source": "SEC Company Facts", "_limitations": ["ticker not found"]}
    cik_padded = f"{cik:010d}"
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    taxonomies = payload.get("facts") or {}
    facts = taxonomies.get("us-gaap") or taxonomies.get("ifrs-full") or {}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for metric, tags in _CONCEPTS.items():
        concept = next((facts[tag] for tag in tags if tag in facts), None)
        if not concept:
            continue
        for item in _candidate_units(concept):
            filed = str(item.get("filed") or "").replace("-", "")
            end = str(item.get("end") or "")
            if not filed or filed > trade_date or not end or item.get("form") not in _FORMS:
                continue
            kind = _period_kind(item)
            if not kind:
                continue
            key = (metric, end, kind)
            current = selected.get(key)
            if current is None or str(item.get("filed")) > str(current.get("filed")):
                selected[key] = item
    for (metric, end, kind), item in selected.items():
        row = grouped.setdefault(
            (end, kind),
            {
                "report_date": end,
                "period_label": f"{end[:4]}FY" if kind == "annual" else end,
                "notice_date": item.get("filed"),
                "publication_date_status": "verified",
                "accounting_basis": "US-GAAP_or_IFRS_XBRL",
                "scope": "consolidated_entity_wide",
                "_source": "SEC Company Facts",
                "_source_url": url,
                "_source_type": "regulator_primary_xbrl",
                "_currency": "USD",
                "_accessions": [],
            },
        )
        row[metric] = item.get("val")
        row["notice_date"] = max(str(row.get("notice_date") or ""), str(item.get("filed") or ""))
        accession = str(item.get("accn") or "")
        if accession and accession not in row["_accessions"]:
            row["_accessions"].append(accession)
    periods = sorted(grouped.values(), key=lambda row: (row["report_date"], row["period_label"]), reverse=True)
    annual = [row for row in periods if str(row["period_label"]).endswith("FY")][:8]
    quarterly = [row for row in periods if not str(row["period_label"]).endswith("FY")][:12]
    periods = sorted(annual + quarterly, key=lambda row: (row["report_date"], row["period_label"]), reverse=True)
    for row in periods:
        capex = row.get("capital_expenditure")
        operating_cash = row.get("operating_cash_flow")
        if operating_cash is not None and capex is not None:
            row["free_cash_flow_lite"] = float(operating_cash) - abs(float(capex))
        revenue = row.get("revenue")
        gross_profit = row.get("gross_profit")
        if revenue not in (None, 0) and gross_profit is not None:
            row["gross_margin"] = float(gross_profit) / float(revenue) * 100
        liabilities = row.get("total_liabilities")
        assets = row.get("total_assets")
        if assets not in (None, 0) and liabilities is not None:
            row["debt_asset_ratio"] = float(liabilities) / float(assets) * 100
    return {
        "periods": periods,
        "cik": cik_padded,
        "entity_name": payload.get("entityName"),
        "_source": "SEC Company Facts",
        "_source_url": url,
        "_source_type": "regulator_primary_xbrl",
        "_limitations": [
            "entity-wide standardized XBRL facts do not include issuer-specific segment dimensions",
            "amended filings supersede earlier values only when filed by the research cutoff",
        ],
    }
