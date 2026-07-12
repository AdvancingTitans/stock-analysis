"""Company-level Evidence Pack built from deterministic public-market inputs.

The market M1-M6 pack answers what happened in the market.  This module keeps
company research separate so an Agent cannot mistake a market proxy for a
company fact.  Empty sections are explicit evidence gaps, never positive data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .futu_public import fetch_futu_public_pulse
from .integrations import fetch_a_share_financial_snapshot, fetch_a_share_price_volume, fetch_single_quote
from .normalize import normalize_code

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
        "roe_weighted",
        "gross_margin",
        "debt_asset_ratio",
        "operating_cash_flow",
        "free_cash_flow_lite",
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
            }
        )
    return facts


def _section(available: bool, evidence: list[dict[str, Any]], gaps: list[str], **extra: Any) -> dict[str, Any]:
    return {"available": available, "evidence": evidence, "gaps": gaps, **extra}


def build_company_evidence(symbol: str, trade_date: str) -> dict[str, Any]:
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
    pulse: dict[str, Any] = {}
    if quote and quote.name:
        try:
            pulse = fetch_futu_public_pulse(normalized, quote.name, market)
        except Exception as exc:  # public news is an enhancement, not a hard dependency
            pulse = {"available": False, "reason": str(exc)}

    facts = _financial_facts(financials)
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
    growth_evidence = [item for item in facts if item["metric"] in {"revenue", "parent_netprofit"}]
    valuation_evidence = [quote_fact] if quote_fact["value"] is not None else []
    price_metrics = (price_volume.get("metrics") or {}) if price_volume else {}
    event_evidence = []
    if pulse.get("event_title"):
        event_evidence.append(
            {
                "title": pulse.get("event_title"),
                "url": pulse.get("evidence_url"),
                "tone": pulse.get("news_tone"),
                "sample_count": pulse.get("news_count"),
                "source": "futu_public",
            }
        )
    financial_gap = "当前市场缺少可验证的结构化财务事实" if market != "a" else "财务披露字段不足"
    no_management_gap = "尚未接入经核验的管理层、回购、分红、增减持和治理事件源"
    sections = {
        "C1": _section(False, [], ["收入分部、客户集中度、经常性收入和定价权数据尚未结构化"]),
        "C2": _section(bool(quality_evidence), quality_evidence, [] if quality_evidence else [financial_gap]),
        "C3": _section(bool(growth_evidence), growth_evidence, [] if growth_evidence else [financial_gap]),
        "C4": _section(False, [], ["护城河只能由可观测的留存、份额、成本或定价证据支持；当前证据不足"]),
        "C5": _section(False, [], [no_management_gap]),
        "C6": _section(bool(valuation_evidence), valuation_evidence, ["历史估值分位、同行比较和情景估值尚未齐备"]),
        "C7": _section(
            bool(price_metrics or event_evidence),
            [{"metric": key, "value": value, "source": price_volume.get("source")} for key, value in price_metrics.items()]
            + event_evidence,
            ["尚未接入公司级监管、诉讼和治理风险事件源"] if not event_evidence else [],
        ),
        "C8": _section(bool(event_evidence), event_evidence, ["尚未建立该标的的持久化论文或催化剂日历"] if not event_evidence else []),
    }
    available = [key for key, value in sections.items() if value["available"]]
    missing = [key for key, value in sections.items() if not value["available"]]
    return {
        "schema_version": "1.0",
        "symbol": normalized,
        "name": quote.name if quote else normalized,
        "market": market,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quote": quote_fact,
        "financial_facts": facts,
        "modules": sections,
        "_meta": {
            "available_modules": available,
            "missing_modules": missing,
            "coverage": round(len(available) / len(COMPANY_MODULES) * 100, 1),
            "source_events": [
                {"source": quote.source if quote else "quote", "status": "ok" if quote_fact["value"] is not None else "unavailable"},
                {"source": "eastmoney_datacenter", "status": "ok" if facts else "unavailable"},
                {"source": "futu_public", "status": "ok" if event_evidence else "unavailable"},
            ],
        },
    }
