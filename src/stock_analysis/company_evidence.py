"""Company-level Evidence Pack built from deterministic public-market inputs.

The market M1-M6 pack answers what happened in the market.  This module keeps
company research separate so an Agent cannot mistake a market proxy for a
company fact.  Empty sections are explicit evidence gaps, never positive data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .execution_costs import build_execution_cost_model
from .expectations import build_expectation_model
from .futu_public import fetch_futu_public_pulse
from .integrations import (
    fetch_a_share_financial_snapshot,
    fetch_a_share_order_book_snapshot,
    fetch_a_share_price_volume,
    fetch_company_disclosures,
    fetch_single_quote,
)
from .normalize import normalize_code
from .primary_disclosures import load_issuer_primary_facts

COMPANY_MODULES = {
    "C1": "商业质量",
    "C2": "财务质量",
    "C3": "增长质量",
    "C4": "护城河证据",
    "C5": "管理层与资本配置",
    "C6": "估值与安全边际",
    "C7": "风险与反证",
    "C8": "催化剂与论文跟踪",
}
def _issuer_primary_facts(symbol: str, trade_date: str) -> dict[str, list[dict[str, Any]]]:
    """Extract verified issuer facts through the generic catalog-driven PDF adapter."""

    return load_issuer_primary_facts(normalize_code(symbol), trade_date)


def _market_for(symbol: str, quote_market: str) -> str:
    if quote_market:
        return quote_market
    normalized = normalize_code(symbol)
    if normalized.endswith(".HK"):
        return "hk"
    return "a" if normalized.isdigit() else "us"


def _financial_facts(financials: dict[str, Any]) -> list[dict[str, Any]]:
    periods = financials.get("periods") or []
    if not periods:
        return []
    latest = periods[0]
    fact_keys = (
        "revenue",
        "parent_netprofit",
        "parent_net_profit",
        "roe_weighted",
        "gross_margin",
        "basic_eps",
        "bps",
        "debt_asset_ratio",
        "operating_cash_flow",
        "free_cash_flow_lite",
        "net_cash_invest",
        "net_cash_finance",
    )
    facts = []
    for key in fact_keys:
        value = latest.get(key)
        if value is None:
            continue
        facts.append(
            {
                "metric": key,
                "period": latest.get("report_date") or latest.get("period") or "unknown",
                "value": value,
                "currency": "CNY",
                "accounting_basis": "reported",
                "scope": "consolidated",
                "source_type": "structured_public_disclosure",
                "source": "eastmoney_datacenter",
                "confidence": "secondary",
                "notice_date": latest.get("notice_date"),
            }
        )
    return facts


def _period_fact(metric: str, value: Any, period: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "metric": metric,
        "period": period.get("report_date") or period.get("period_label") or "unknown",
        "value": value,
        "currency": "CNY",
        "accounting_basis": "reported",
        "scope": "consolidated",
        "source_type": "structured_public_disclosure",
        "source": "eastmoney_datacenter",
        "confidence": "secondary",
        "notice_date": period.get("notice_date"),
        **extra,
    }


def _growth_facts(financials: dict[str, Any]) -> list[dict[str, Any]]:
    periods = financials.get("periods") or []
    if not periods:
        return []
    latest = periods[0]
    latest_label = str(latest.get("period_label") or "")
    prior_label = latest_label.replace(str(latest.get("report_date") or "")[:4], str(int(str(latest.get("report_date"))[:4]) - 1), 1)
    prior = next((row for row in periods[1:] if row.get("period_label") == prior_label), None)
    result = []
    for metric in ("revenue", "parent_net_profit"):
        value = latest.get(metric)
        if value is not None:
            result.append(_period_fact(metric, value, latest))
        prior_value = prior.get(metric) if prior else None
        if value is not None and prior_value not in (None, 0):
            result.append(
                _period_fact(
                    f"{metric}_yoy_pct",
                    (float(value) / float(prior_value) - 1) * 100,
                    latest,
                    source_type="derived_from_structured_public_disclosure",
                    confidence="conditional",
                    comparison_period=prior.get("report_date"),
                )
            )
    return result


def _valuation_facts(financials: dict[str, Any], quote_fact: dict[str, Any]) -> list[dict[str, Any]]:
    price = quote_fact.get("value")
    if price is None:
        return []
    annual = next(
        (row for row in financials.get("periods") or [] if str(row.get("period_label") or "").endswith("FY")),
        None,
    )
    if not annual:
        return []
    eps = annual.get("basic_eps")
    bps = annual.get("bps")
    result = []
    if eps not in (None, 0):
        result.append(
            _period_fact(
                "pe_static_proxy",
                float(price) / float(eps),
                annual,
                source_type="derived_valuation",
                confidence="conditional",
                formula="market_quote / latest_disclosed_fiscal_year_basic_eps",
            )
        )
        for multiple in (15, 18, 22):
            result.append(
                _period_fact(
                    f"scenario_price_{multiple}x_pe",
                    float(eps) * multiple,
                    annual,
                    source_type="derived_valuation",
                    confidence="conditional",
                    formula=f"latest_disclosed_fiscal_year_basic_eps * {multiple}",
                )
            )
    if bps not in (None, 0):
        result.append(
            _period_fact(
                "pb_reported_proxy",
                float(price) / float(bps),
                annual,
                source_type="derived_valuation",
                confidence="conditional",
                formula="market_quote / latest_disclosed_fiscal_year_bps",
            )
        )
    return result


def _business_quality_facts(financials: dict[str, Any]) -> list[dict[str, Any]]:
    periods = financials.get("periods") or []
    if not periods:
        return []
    latest = periods[0]
    revenue = latest.get("revenue")
    profit = latest.get("parent_net_profit")
    cash_flow = latest.get("operating_cash_flow")
    result = []
    if revenue not in (None, 0) and profit is not None:
        result.append(_period_fact(
            "parent_net_margin_pct", float(profit) / float(revenue) * 100, latest,
            source_type="derived_business_quality", confidence="conditional",
            formula="parent_net_profit / revenue",
        ))
    if profit not in (None, 0) and cash_flow is not None:
        result.append(_period_fact(
            "operating_cash_conversion_pct", float(cash_flow) / float(profit) * 100, latest,
            source_type="derived_business_quality", confidence="conditional",
            formula="operating_cash_flow / parent_net_profit",
        ))
    return result


def _moat_proxy_facts(financials: dict[str, Any]) -> list[dict[str, Any]]:
    annual = [
        row for row in financials.get("periods") or []
        if str(row.get("period_label") or "").endswith("FY")
    ]
    margins = [float(row["gross_margin"]) for row in annual if row.get("gross_margin") is not None]
    if not margins:
        return []
    latest = annual[0]
    result = [_period_fact(
        "annual_gross_margin_pct", margins[0], latest,
        source_type="observable_moat_proxy", confidence="conditional",
        interpretation="持续高毛利可作为定价权代理，但不能单独证明品牌或竞争优势",
    )]
    if len(margins) >= 2:
        result.append(_period_fact(
            "annual_gross_margin_range_pct", max(margins) - min(margins), latest,
            source_type="observable_moat_proxy", confidence="conditional",
            sample_size=len(margins),
            formula="max(annual_gross_margin) - min(annual_gross_margin)",
        ))
    return result


def _disclosure_facts(financials: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for key, disclosure_type in (("forecasts", "earnings_forecast"), ("earnings_flash", "earnings_flash")):
        for row in (financials.get(key) or {}).get("rows") or []:
            facts.append(
                {
                    "title": row.get("title") or disclosure_type,
                    "type": row.get("type") or disclosure_type,
                    "period": row.get("report_date"),
                    "published_at": row.get("notice_date"),
                    "summary": row.get("summary"),
                    "lower": row.get("lower"),
                    "upper": row.get("upper"),
                    "source": "eastmoney_datacenter",
                    "source_type": "structured_public_disclosure",
                    "confidence": "secondary",
                    "category": "financial_disclosure",
                }
            )
    return facts


def _evidence_id(module: str, item: dict[str, Any]) -> str:
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"{module}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _identify_evidence(sections: dict[str, dict[str, Any]]) -> None:
    for module, section in sections.items():
        identified = []
        for raw in section["evidence"]:
            item = dict(raw)
            item["validation_status"] = (
                "conditional"
                if item.get("confidence") == "conditional"
                or item.get("source_type") in {"public_announcement_index", "news_sample"}
                else "accepted"
            )
            item["evidence_id"] = _evidence_id(module, item)
            identified.append(item)
        section["evidence"] = identified


def _section(available: bool, evidence: list[dict[str, Any]], gaps: list[str], **extra: Any) -> dict[str, Any]:
    return {"available": available, "evidence": evidence, "gaps": gaps, **extra}


def build_company_evidence(
    symbol: str,
    trade_date: str,
    expectations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a C1-C8 pack without making investment assertions.

    A-share financial facts are currently the only fully structured company
    accounting route.  HK/US sections deliberately remain gaps until their
    primary-filing adapters are available.
    """

    try:
        quote = fetch_single_quote(symbol, trade_date)
    except Exception:
        quote = None
    normalized = normalize_code(quote.symbol if quote else symbol)
    market = _market_for(normalized, quote.market if quote else "")
    try:
        financials = fetch_a_share_financial_snapshot(normalized, trade_date) if market == "a" else {}
    except Exception:
        financials = {}
    try:
        price_volume = fetch_a_share_price_volume(normalized, trade_date) if market == "a" else {}
    except Exception:
        price_volume = {}
    try:
        microstructure = fetch_a_share_order_book_snapshot(normalized, trade_date) if market == "a" else {}
    except Exception as exc:
        microstructure = {"available": False, "symbol": normalized, "reason": str(exc)}
    execution_cost_model = build_execution_cost_model(
        symbol=normalized,
        price_volume=price_volume,
        microstructure=microstructure,
    )
    pulse: dict[str, Any] = {}
    if quote and quote.name:
        try:
            pulse = fetch_futu_public_pulse(normalized, quote.name, market)
        except Exception as exc:  # public news is an enhancement, not a hard dependency
            pulse = {"available": False, "reason": str(exc)}
    try:
        disclosures = fetch_company_disclosures(normalized, quote.name if quote else normalized, trade_date)
    except Exception as exc:
        disclosures = {"available": False, "rows": [], "reason": str(exc), "_source": "Futu 免登录公告搜索"}

    facts = _financial_facts(financials)
    issuer_primary = _issuer_primary_facts(normalized, trade_date)
    primary_disclosures = _disclosure_facts(financials)
    quote_fact = {
        "metric": "market_quote",
        "period": quote.trade_date if quote else trade_date,
        "value": quote.price if quote else None,
        "currency": quote.currency if quote else None,
        "source_type": "market_quote",
        "source": quote.source if quote else None,
        "confidence": "primary" if quote and quote.price is not None else "unavailable",
    }
    quality_evidence = [item for item in facts if item["metric"] in {"roe_weighted", "gross_margin", "operating_cash_flow", "free_cash_flow_lite", "debt_asset_ratio"}]
    business_evidence = _business_quality_facts(financials) + issuer_primary["C1"]
    moat_evidence = _moat_proxy_facts(financials) + issuer_primary["C4"]
    growth_evidence = _growth_facts(financials)
    valuation_evidence = [quote_fact] if quote_fact["value"] is not None else []
    for metric, value in (
        ("pe_ttm", quote.pe if quote else None),
        ("pb", quote.pb if quote else None),
        ("total_market_cap", quote.total_market_cap if quote else None),
        ("float_market_cap", quote.float_market_cap if quote else None),
    ):
        if value is None:
            continue
        valuation_evidence.append(
            {
                "metric": metric,
                "period": quote.trade_date or trade_date,
                "value": value,
                "currency": quote.currency if "market_cap" in metric else None,
                "source": quote.source,
                "source_type": "market_valuation_snapshot",
                "confidence": "primary",
            }
        )
    valuation_evidence.extend(_valuation_facts(financials, quote_fact))
    expectation_model = build_expectation_model(
        quote.total_market_cap if quote else None,
        expectations,
    )
    for row in expectation_model.get("market_implied") or []:
        multiple = row["multiple"]
        suffix = str(int(multiple)) if float(multiple).is_integer() else str(multiple).replace(".", "_")
        valuation_evidence.append({
            "metric": f"implied_net_profit_{suffix}x",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": row["implied_net_profit"],
            "currency": expectation_model.get("currency") or (quote.currency if quote else None),
            "source": "market_cap_expectations_bridge",
            "source_type": "derived_market_implied_expectation",
            "confidence": "conditional",
            "formula": "total_market_cap / assumed_valuation_multiple",
        })
    forward_model = expectation_model.get("forward_model") or {}
    for index, item in enumerate(forward_model.get("product_lines") or [], start=1):
        slug = "".join(char.lower() if char.isalnum() else "_" for char in str(item["name"])).strip("_") or str(index)
        for field in ("revenue", "net_profit"):
            valuation_evidence.append({
                "metric": f"forward_product_{slug}_{field}",
                "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
                "value": item[field],
                "currency": expectation_model.get("currency"),
                "source": "user_supplied_research_assumption",
                "source_type": "derived_forward_product_model",
                "confidence": "conditional",
                "formula": item["formula"],
            })
    for index, item in enumerate(forward_model.get("segments") or [], start=1):
        slug = "".join(char.lower() if char.isalnum() else "_" for char in str(item["name"])).strip("_") or str(index)
        valuation_evidence.append({
            "metric": f"forward_segment_{slug}_value",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": item["value"],
            "currency": expectation_model.get("currency"),
            "source": "user_supplied_research_assumption",
            "source_type": "derived_forward_sotp",
            "confidence": "conditional",
            "formula": item["formula"],
        })
    bridge = expectation_model.get("sotp_bridge") or {}
    if forward_model.get("forward_net_profit") is not None:
        valuation_evidence.append({
            "metric": "forward_net_profit",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": forward_model["forward_net_profit"],
            "currency": expectation_model.get("currency"),
            "source": "user_supplied_research_assumption",
            "source_type": "forward_valuation_assumption",
            "confidence": "conditional",
        })
    if forward_model.get("segments"):
        valuation_evidence.append({
            "metric": "sotp_residual_value",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": bridge.get("residual_value"),
            "currency": expectation_model.get("currency"),
            "source": "market_cap_expectations_bridge",
            "source_type": "derived_forward_reverse_reconciliation",
            "confidence": "conditional",
            "formula": bridge.get("formula"),
            "reconciliation_status": bridge.get("status"),
        })
    for row in expectation_model.get("expectation_gap") or []:
        multiple = row["multiple"]
        suffix = str(int(multiple)) if float(multiple).is_integer() else str(multiple).replace(".", "_")
        valuation_evidence.append({
            "metric": f"expectation_gap_{suffix}x",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": row["gap"],
            "currency": expectation_model.get("currency"),
            "source": "forward_reverse_expectations_bridge",
            "source_type": "derived_forward_reverse_reconciliation",
            "confidence": "conditional",
            "formula": "forward_net_profit - market_implied_net_profit",
        })
    option_value = expectation_model.get("option_value") or {}
    for field in ("required_net_profit", "required_revenue"):
        if option_value.get(field) is None:
            continue
        valuation_evidence.append({
            "metric": f"option_{field}",
            "period": expectation_model.get("valuation_year") or "valuation_horizon_not_supplied",
            "value": option_value[field],
            "currency": expectation_model.get("currency"),
            "source": "market_cap_expectations_bridge",
            "source_type": "derived_option_value_requirement",
            "confidence": "conditional",
            "formula": option_value.get("formula"),
        })
    price_metrics = (price_volume.get("metrics") or {}) if price_volume else {}
    execution_evidence = [
        {
            "metric": "execution_cost_model_status",
            "value": execution_cost_model.get("model_status"),
            "source": "公开盘口、日线成交额与交易成本情景模型",
            "source_type": "execution_scenario",
            "confidence": "conditional",
        }
    ]
    for scenario in execution_cost_model.get("scenarios") or []:
        order_value = int(scenario["order_value_cny"] / 10_000)
        execution_evidence.append({
            "metric": f"execution_round_trip_cost_{order_value}w_bps",
            "value": scenario["round_trip_cost_bps"],
            "source": "公开盘口、20日成交额与平方根冲击模型",
            "source_type": "execution_scenario",
            "confidence": "conditional",
        })
    event_evidence = []
    if pulse.get("event_title"):
        event_evidence.append(
            {
                "title": pulse.get("event_title"),
                "url": pulse.get("evidence_url"),
                "tone": pulse.get("news_tone"),
                "sample_count": pulse.get("news_count"),
                "source": "futu_public",
                "source_type": "news_sample",
            }
        )
    disclosure_rows = [dict(row) for row in disclosures.get("rows") or []]
    capital_allocation = [row for row in disclosure_rows if row.get("category") == "capital_allocation"]
    governance = [row for row in disclosure_rows if row.get("category") == "governance"]
    annual_period = next(
        (row for row in financials.get("periods") or [] if str(row.get("period_label") or "").endswith("FY")),
        {},
    )
    financing_facts = [
        _period_fact(metric, annual_period[metric], annual_period)
        for metric in ("net_cash_invest", "net_cash_finance")
        if annual_period.get(metric) is not None
    ]
    management_evidence = governance + capital_allocation + financing_facts + issuer_primary["C5"]
    monitoring_evidence = [
        {
            "metric": item["metric"],
            "value": item.get("baseline"),
            "period": item.get("next_check_date") or trade_date,
            "view_change_condition": item["view_change_condition"],
            "source": item.get("source") or "user_supplied_research_assumption",
            "source_type": "thesis_monitoring_trigger",
            "confidence": "conditional",
        }
        for item in expectation_model.get("monitoring") or []
    ]
    financial_gap = "当前市场缺少可验证的结构化财务事实" if market != "a" else "财务披露字段不足"
    no_management_gap = "尚未接入经核验的管理层、回购、分红、增减持和治理事件源"
    sections = {
        "C1": _section(bool(business_evidence), business_evidence, ["收入分部、客户集中度和渠道经营数据仍需原始披露复核"]),
        "C2": _section(bool(quality_evidence), quality_evidence, [] if quality_evidence else [financial_gap]),
        "C3": _section(bool(growth_evidence or primary_disclosures), growth_evidence + primary_disclosures, [] if growth_evidence or primary_disclosures else [financial_gap]),
        "C4": _section(bool(moat_evidence), moat_evidence, ["毛利率仅为护城河代理，品牌、份额、批价和渠道库存仍需一手经营证据"]),
        "C5": _section(bool(management_evidence), management_evidence, [] if management_evidence else [no_management_gap]),
        "C6": _section(
            len(valuation_evidence) > 1,
            valuation_evidence,
            [
                "市场隐含利润已按估值倍数反推；未提供 expectations 文件时，正向分部模型、SOTP 对账与预期差仍为空"
                if expectation_model.get("status") == "market_implied_only"
                else "历史估值分位和同行比较尚未齐备"
            ],
            expectation_model=expectation_model,
        ),
        "C7": _section(
            bool(price_metrics or event_evidence or governance or issuer_primary["C7"]),
            [{"metric": key, "value": value, "source": price_volume.get("source")} for key, value in price_metrics.items()]
            + execution_evidence
            + event_evidence
            + governance
            + issuer_primary["C7"],
            ["尚未取得可核验的公司级监管、诉讼或治理风险披露"] if not governance else [],
        ),
        "C8": _section(
            bool(event_evidence or disclosure_rows or primary_disclosures or issuer_primary["C8"] or monitoring_evidence),
            event_evidence + disclosure_rows + primary_disclosures + issuer_primary["C8"] + monitoring_evidence,
            ["尚未建立该标的的持久化论文或催化剂日历"] if not event_evidence and not disclosure_rows and not primary_disclosures and not issuer_primary["C8"] and not monitoring_evidence else [],
            monitoring=expectation_model.get("monitoring") or [],
        ),
    }
    _identify_evidence(sections)
    available = [key for key, value in sections.items() if value["available"]]
    missing = [key for key, value in sections.items() if not value["available"]]
    result = {
        "schema_version": "1.2",
        "symbol": normalized,
        "name": quote.name if quote else normalized,
        "market": market,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quote": quote_fact,
        "financial_facts": facts,
        "financial_history": financials.get("periods") or [],
        "price_volume": price_volume,
        "microstructure": microstructure,
        "execution_cost_model": execution_cost_model,
        "expectation_model": expectation_model,
        "modules": sections,
        "_meta": {
            "available_modules": available,
            "missing_modules": missing,
            "coverage": round(len(available) / len(COMPANY_MODULES) * 100, 1),
            "source_events": [
                {"source": quote.source if quote else "quote", "status": "ok" if quote_fact["value"] is not None else "unavailable"},
                {"source": "eastmoney_datacenter", "status": "ok" if facts else "unavailable"},
                {"source": "futu_public", "status": "ok" if event_evidence else "unavailable"},
                {"source": disclosures.get("_source") or "Futu 免登录公告搜索", "status": "ok" if disclosure_rows else "unavailable"},
                {"source": "issuer_primary_disclosure", "status": "ok" if any(issuer_primary.values()) else "unavailable"},
                {"source": "execution_cost_model", "status": "ok" if execution_cost_model.get("available") else "unavailable"},
                {"source": "expectations_model", "status": expectation_model.get("status")},
            ],
        },
    }
    from .company_lens import freeze_company_evidence

    result["_meta"]["evidence_snapshot_id"] = freeze_company_evidence(result)["snapshot_id"]
    return result
