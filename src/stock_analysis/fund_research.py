"""Institutional fund research over one content-addressed Evidence snapshot."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .committee_selection import relevant_research_modules
from .company_lens import interpret_metric_for_lens, select_company_committee
from .csi_index import FUND_INDEX_CODES, build_csi_index_snapshot
from .execution_costs import build_execution_cost_model
from .integrations import (
    fetch_a_share_financial_snapshot,
    fetch_a_share_order_book_snapshot,
    fetch_a_share_price_volume,
    fetch_fund_estimate,
    fetch_fund_holding_quotes,
    fetch_fund_holdings,
    fetch_fund_profile,
    fetch_listed_fund_premium_discount,
    fetch_single_quote,
)
from .lens_engine import LensEngine
from .research_claims import (
    PublicationDecision,
    build_claim_audit_artifacts,
    build_evidence_integrity_audit,
    compile_metric_claims,
    evaluate_safety_gate,
    partition_claims,
)
from .research_workspace import DISCLAIMER
from .source_outcome import capture_source
from .time_series import compare_price_series
from .workspace_store import (
    atomic_write as _atomic_write,
)
from .workspace_store import (
    load_json as _load_json,
)
from .workspace_store import (
    previous_workspace as _previous_workspace,
)
from .workspace_store import (
    research_root,
)
from .workspace_store import (
    safe_symbol as _safe_symbol,
)
from .workspace_store import (
    write_artifact as _write_artifact,
)

FUND_MODULES = {
    "F1": "产品定位与指数契约",
    "F2": "成分暴露与集中度",
    "F3": "业绩与趋势",
    "F4": "跟踪、折溢价与交易实现",
    "F5": "底层估值",
    "F6": "风险预算与回撤代理",
    "F7": "治理、规模与运营",
    "F8": "催化剂与跟踪条件",
}
FUND_LENS_MODULES = {
    "buffett": ("F1", "F2", "F3", "F5", "F7"),
    "munger": ("F1", "F2", "F5", "F7"),
    "duan_yongping": ("F1", "F2", "F3", "F5", "F7"),
    "zhang_kun": ("F2", "F3", "F5", "F6", "F7"),
    "graham": ("F3", "F4", "F5", "F6"),
    "klarman": ("F4", "F5", "F6", "F8"),
    "lynch": ("F2", "F3", "F5", "F8"),
    "o_neil": ("F2", "F3", "F6", "F8"),
    "wood": ("F1", "F2", "F3", "F5", "F8"),
    "dalio": ("F2", "F3", "F6", "F7", "F8"),
    "soros": ("F3", "F4", "F6", "F8"),
    "livermore": ("F3", "F4", "F6"),
    "minervini": ("F2", "F3", "F6"),
    "simons": ("F2", "F3", "F4", "F5", "F6"),
    "feng_liu": ("F2", "F3", "F4", "F5", "F8"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _content_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _item(module: str, metric: str, value: Any, source: str, **extra: Any) -> dict[str, Any]:
    body = {
        "metric": metric,
        "value": value,
        "source": source,
        "validation_status": extra.pop("validation_status", "accepted"),
        **extra,
    }
    body["evidence_id"] = f"{module}:{hashlib.sha256(_canonical(body).encode('utf-8')).hexdigest()[:16]}"
    return body


def _section(evidence: list[dict[str, Any]], gaps: list[str]) -> dict[str, Any]:
    return {"available": bool(evidence), "evidence": evidence, "gaps": gaps}


def _official_fund_evidence(code: str, trade_date: str) -> dict[str, list[dict[str, Any]]]:
    """Verified product-contract and index-methodology facts with page anchors."""

    result = {module: [] for module in FUND_MODULES}
    if code != "512480" or trade_date.replace("-", "") < "20260324":
        return result
    product_url = "https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-24/512480_20260324_KW7A.pdf"
    index_url = "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/H30184_Index_Methodology_cn.pdf"

    def official(module: str, metric: str, value: Any, source: str, url: str, page: int, **extra: Any) -> dict[str, Any]:
        return _item(
            module, metric, value, source,
            source_type="primary_disclosure", url=url, page=page, published_at="2026-03-24", **extra,
        )

    result["F1"] = [
        official("F1", "index_code", "H30184", "中证指数编制方案", index_url, 1),
        official("F1", "index_liquidity_exclusion_bottom_pct", 10, "中证指数编制方案", index_url, 2),
        official("F1", "index_cumulative_market_cap_cutoff_pct", 90, "中证指数编制方案", index_url, 2),
        official("F1", "index_single_constituent_cap_pct", 15, "中证指数编制方案", index_url, 2),
        official("F1", "index_rebalance_months", [6, 12], "中证指数编制方案", index_url, 2),
        official("F1", "minimum_index_constituent_nav_pct", 90, "上交所基金产品资料概要", product_url, 2),
        official("F1", "minimum_index_constituent_non_cash_pct", 80, "上交所基金产品资料概要", product_url, 2),
        official("F1", "replication_method", "完全复制法；特殊情形可采用抽样复制", "上交所基金产品资料概要", product_url, 2),
    ]
    result["F7"] = [
        official("F7", "management_fee_pct", 0.5, "上交所基金产品资料概要", product_url, 3),
        official("F7", "custodian_fee_pct", 0.1, "上交所基金产品资料概要", product_url, 3),
        official("F7", "subscription_redemption_commission_cap_pct", 0.5, "上交所基金产品资料概要", product_url, 3),
    ]
    result["F8"] = [
        official("F8", "index_rebalance_months", [6, 12], "中证指数编制方案", index_url, 2),
    ]
    return result


def build_fund_evidence(code: str, trade_date: str) -> dict[str, Any]:
    estimate_outcome = capture_source("fund_estimate", lambda: fetch_fund_estimate(code, trade_date), {})
    profile_outcome = capture_source("fund_profile", lambda: fetch_fund_profile(code, trade_date), {})
    holdings_outcome = capture_source("fund_holdings", lambda: fetch_fund_holdings(code, trade_date, limit=10), {})
    price_volume_outcome = capture_source("price_volume", lambda: fetch_a_share_price_volume(code, trade_date), {})
    premium_outcome = capture_source(
        "premium_discount", lambda: fetch_listed_fund_premium_discount(code, trade_date), {}
    )
    index_outcome = capture_source(
        "csi_index_snapshot",
        lambda: build_csi_index_snapshot(FUND_INDEX_CODES[code], trade_date) if code in FUND_INDEX_CODES else {},
        {},
    )
    microstructure_outcome = capture_source(
        "order_book",
        lambda: fetch_a_share_order_book_snapshot(code, trade_date),
        lambda exc: {"available": False, "symbol": code, "reason": str(exc)},
    )
    estimate = estimate_outcome.value
    profile = profile_outcome.value
    holdings = holdings_outcome.value
    price_volume = price_volume_outcome.value
    premium = premium_outcome.value
    index_snapshot = index_outcome.value
    microstructure = microstructure_outcome.value
    official = _official_fund_evidence(code, trade_date)
    official_fee_values = {
        item["metric"]: item.get("value")
        for item in official["F7"]
    }
    execution_cost_model = build_execution_cost_model(
        symbol=code,
        price_volume=price_volume,
        microstructure=microstructure,
        premium_discount=premium,
        annual_fees=official_fee_values,
    )
    index_history = index_snapshot.get("history") or {}
    index_comparison = compare_price_series(price_volume.get("rows") or [], index_history.get("rows") or [])
    holding_rows = holdings.get("holdings") or []
    holding_quotes_outcome = capture_source(
        "holding_quotes", lambda: fetch_fund_holding_quotes(holding_rows, trade_date), {}
    )
    holding_quotes = holding_quotes_outcome.value

    for holding in holding_rows:
        holding_code = str(holding.get("code") or "")
        if holding_code and holding_code not in holding_quotes:
            try:
                quote = fetch_single_quote(holding_code, trade_date)
            except Exception:
                quote = None
            if quote is not None and quote.price is not None:
                holding_quotes[holding_code] = quote
    for holding_code, quote in holding_quotes.items():
        if quote.pe is not None or quote.price is None:
            continue
        try:
            financials = fetch_a_share_financial_snapshot(holding_code, trade_date)
        except Exception:
            financials = {}
        annual = next(
            (row for row in financials.get("periods") or [] if str(row.get("period_label") or "").endswith("FY")),
            None,
        )
        eps = annual.get("basic_eps") if annual else None
        if eps not in (None, 0):
            quote.pe = float(quote.price) / float(eps)
            quote.extra["pe_basis"] = "market_price / latest_disclosed_fiscal_year_basic_eps"

    holding_quote_rows = {
        symbol: {
            key: getattr(quote, key, None)
            for key in ("symbol", "name", "price", "change_pct", "pe", "pb", "trade_date", "source", "extra")
        }
        for symbol, quote in holding_quotes.items()
    }

    metadata = premium.get("tracking_metadata") or {}
    returns = profile.get("returns") or {}
    scale = profile.get("scale") or {}
    managers = profile.get("managers") or []
    metrics = price_volume.get("metrics") or {}
    latest_premium = premium.get("latest") or {}
    weights = [float(row.get("weight_pct") or 0) for row in holding_rows]
    top5 = sum(weights[:5]) if weights else None
    top10 = sum(weights[:10]) if weights else None
    disclosed_count = len(weights)

    f1 = []
    if estimate.get("name"):
        f1.append(_item("F1", "fund_name", estimate["name"], estimate.get("_source") or "public_fund_profile"))
    if metadata.get("tracked_index") or metadata.get("benchmark"):
        f1.append(_item("F1", "tracked_index", metadata.get("tracked_index") or metadata.get("benchmark"), premium.get("source") or "fund_disclosure"))

    f2 = []
    index_constituents = index_snapshot.get("constituents") or []
    index_weights = [float(row.get("weight_pct") or 0) for row in index_constituents]
    if index_snapshot.get("available"):
        f2.extend([
            _item("F2", "index_constituent_asof", index_snapshot.get("constituent_asof"), index_snapshot["source"]),
            _item("F2", "index_weight_asof", index_snapshot.get("weight_asof"), index_snapshot["source"]),
            _item("F2", "index_constituent_count", index_snapshot.get("constituent_count"), index_snapshot["source"]),
            _item("F2", "index_weight_coverage_pct", index_snapshot.get("weight_sum_pct"), index_snapshot["source"]),
            _item("F2", "top5_weight_pct", sum(index_weights[:5]), index_snapshot["source"]),
            _item("F2", "top10_weight_pct", sum(index_weights[:10]), index_snapshot["source"]),
        ])
    elif holding_rows:
        f2.extend([
            _item("F2", "holdings_asof", holdings.get("asof"), holdings.get("_source") or "public_holdings"),
            _item("F2", "top5_weight_pct", top5, holdings.get("_source") or "public_holdings"),
            _item("F2", "top10_weight_pct", top10, holdings.get("_source") or "public_holdings"),
            _item("F2", "disclosed_holding_count", disclosed_count, holdings.get("_source") or "public_holdings"),
        ])

    f3 = [_item("F3", label, value, profile.get("_source") or "public_fund_profile") for label, value in returns.items()]
    f3.extend(_item("F3", metric, value, price_volume.get("source") or "listed_price_kline") for metric, value in metrics.items() if metric.startswith("returns_"))

    f4 = []
    if latest_premium.get("premium_discount_pct") is not None:
        f4.extend([
            _item("F4", "premium_discount_pct", latest_premium["premium_discount_pct"], premium.get("source") or "official_nav_and_listed_price"),
            _item("F4", "premium_discount_20d_mean_pct", premium.get("premium_discount_20d_mean_pct"), premium.get("source") or "official_nav_and_listed_price"),
            _item("F4", "premium_discount_20d_std_pct", premium.get("premium_discount_20d_std_pct"), premium.get("source") or "official_nav_and_listed_price"),
        ])
    if metadata.get("reported_annual_tracking_error_pct") is not None:
        f4.append(_item("F4", "reported_annual_tracking_error_pct", metadata["reported_annual_tracking_error_pct"], "fund_disclosure", validation_status="conditional"))
    if index_comparison.get("available"):
        for metric in ("aligned_days", "correlation", "beta", "annualized_tracking_error_pct", "annualized_active_return_pct"):
            f4.append(_item("F4", f"recomputed_{metric}", index_comparison.get(metric), "ETF与中证指数官方日线严格对齐"))

    valued = []
    loss_weight = 0.0
    for holding in holding_rows:
        code_key = str(holding.get("code") or "")
        quote = holding_quotes.get(code_key)
        weight = float(holding.get("weight_pct") or 0)
        pe = getattr(quote, "pe", None) if quote else None
        if pe is not None and pe > 0:
            valued.append((weight, float(pe)))
        elif pe is not None and pe <= 0:
            loss_weight += weight
    valued_weight = sum(weight for weight, _ in valued)
    f5 = []
    index_valuation = index_snapshot.get("valuation") or {}
    if index_snapshot.get("available"):
        f5.extend([
            _item("F5", "index_valuation_asof", index_valuation.get("asof"), index_snapshot["source"]),
            _item("F5", "index_pe_total_share", index_valuation.get("pe_total_share"), index_snapshot["source"]),
            _item("F5", "index_pe_calculation_share", index_valuation.get("pe_calculation_share"), index_snapshot["source"]),
            _item("F5", "index_dividend_yield_pct", index_valuation.get("dividend_yield_calculation_share_pct"), index_snapshot["source"]),
            _item("F5", "index_valuation_scope_pct", 100.0, index_snapshot["source"]),
        ])
    if valued_weight > 0:
        harmonic_pe = valued_weight / sum(weight / pe for weight, pe in valued)
        f5.extend([
            _item("F5", "disclosed_holdings_valuation_coverage_pct", valued_weight, "holding_quotes", validation_status="conditional"),
            _item("F5", "positive_pe_harmonic_proxy", harmonic_pe, "holding_quotes", validation_status="conditional"),
            _item("F5", "loss_making_disclosed_weight_pct", loss_weight, "holding_quotes", validation_status="conditional"),
        ])
    f1.extend(official["F1"])

    f6 = [
        _item("F6", metric, value, price_volume.get("source") or "listed_price_kline")
        for metric, value in metrics.items()
        if metric in {
            "atr_14_pct", "volume_zscore", "returns_5d", "returns_20d", "returns_60d",
            "max_drawdown_60d_pct", "annualized_volatility_60d_pct",
        }
    ]
    if top5 is not None:
        f6.append(_item("F6", "top5_weight_pct", top5, holdings.get("_source") or "public_holdings"))
    if index_history.get("available"):
        f6.append(_item("F6", "index_history_sample_size", index_history.get("sample_size"), index_history.get("source")))
        for metric, value in (index_history.get("metrics") or {}).items():
            f6.append(_item("F6", f"index_{metric}", value, index_history.get("source")))

    f7 = []
    if scale.get("latest_size_yi") is not None:
        f7.append(_item("F7", "latest_size_yi", scale["latest_size_yi"], profile.get("_source") or "public_fund_profile", period=scale.get("asof")))
    scale_history = scale.get("history") or []
    if len(scale_history) >= 2:
        latest_scale = float(scale_history[-1]["size_yi"])
        previous_scale = float(scale_history[-2]["size_yi"])
        f7.append(_item(
            "F7", "disclosed_aum_change_yi", latest_scale - previous_scale,
            profile.get("_source") or "public_fund_profile",
            period=f"{scale_history[-2]['asof']}..{scale_history[-1]['asof']}",
            validation_status="conditional",
        ))
    purchase_status = profile.get("purchase_status") or {}
    for action in ("subscribe", "redeem"):
        if purchase_status.get(action):
            f7.append(_item(
                "F7", f"{action}_status", purchase_status[action],
                profile.get("_source") or "public_fund_profile",
            ))
    if managers:
        f7.append(_item("F7", "manager_count", len(managers), profile.get("_source") or "public_fund_profile"))
    fees = profile.get("fees") or {}
    for metric in ("front_end_source_rate_pct", "front_end_rate_pct"):
        if fees.get(metric) is not None:
            f7.append(_item("F7", metric, fees[metric], profile.get("_source") or "public_fund_profile"))
    f7.extend(official["F7"])
    f7.extend([
        _item("F7", "execution_cost_model_status", execution_cost_model.get("model_status"), "公开盘口、ETF日线与费率情景模型", validation_status="conditional"),
        _item("F7", "execution_spread_bps", execution_cost_model.get("spread_bps"), "Sina盘口快照", validation_status="conditional"),
        _item("F7", "execution_average_turnover_20d_cny", execution_cost_model.get("average_turnover_20d_cny"), "Tencent ETF日线", validation_status="conditional"),
        _item("F7", "execution_nav_dislocation_bps", execution_cost_model.get("nav_dislocation_bps"), "场内价与官方净值", validation_status="conditional"),
    ])
    for scenario in execution_cost_model.get("scenarios") or []:
        order_value = int(scenario["order_value_cny"] / 10_000)
        f7.append(_item(
            "F7", f"execution_round_trip_cost_{order_value}w_bps", scenario["round_trip_cost_bps"],
            "公开盘口、20日成交额与平方根冲击模型", validation_status="conditional",
        ))

    f8 = []
    if estimate.get("estimate_change_pct") is not None:
        f8.append(_item("F8", "latest_estimate_change_pct", float(estimate["estimate_change_pct"]), estimate.get("_source") or "public_fund_estimate", validation_status="conditional"))
    if holdings.get("asof"):
        f8.append(_item("F8", "next_holdings_refresh_trigger", holdings["asof"], holdings.get("_source") or "public_holdings", validation_status="conditional"))
    f8.extend(official["F8"])

    modules = {
        "F1": _section(f1, [] if len(f1) >= 2 else ["基金合同、指数编制细则或完整产品契约尚未结构化"]),
        "F2": _section(
            f2,
            ([] if index_snapshot.get("available") else ["官方完整指数样本与权重不可用"])
            + ["基金季报通常只披露前十大持仓；指数成分不等同于基金当日真实持仓，行业暴露需完整 PCF/组合披露"],
        ),
        "F3": _section(f3, [] if f3 else ["阶段收益与场内价格序列不可用"]),
        "F4": _section(f4, [] if f4 else ["官方净值与前复权场内价格无法逐日匹配"]),
        "F5": _section(
            f5,
            [] if index_snapshot.get("available") else ["官方完整指数估值不可用；重仓股估值仅作为降级代理"],
        ),
        "F6": _section(f6, ["完整净值最大回撤、波动率与情景压力测试尚未结构化"]),
        "F7": _section(
            f7,
            ["公开规模变化同时包含净申赎和净值涨跌，不能当作真实净申赎；真实份额申赎流仍缺失"]
            + (["管理费、托管费、份额变动与跟踪治理尚未完整结构化"] if not fees else []),
        ),
        "F8": _section(f8, ["宏观、产业周期和指数调仓日历尚未结构化"]),
    }
    available = [code for code, section in modules.items() if section["available"]]
    missing = [code for code in FUND_MODULES if code not in available]
    result = {
        "schema_version": "1.0",
        "asset_type": "fund",
        "symbol": code,
        "name": estimate.get("name") or profile.get("name") or code,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "estimate": estimate,
        "profile": profile,
        "holdings": holdings,
        "index_snapshot": index_snapshot,
        "holding_quotes": holding_quote_rows,
        "holding_quote_coverage": {"available": len(holding_quotes), "total": len(holding_rows)},
        "microstructure": microstructure,
        "execution_cost_model": execution_cost_model,
        "index_comparison": index_comparison,
        "price_volume": price_volume,
        "premium_discount": premium,
        "modules": modules,
        "_meta": {
            "coverage": round(len(available) / len(FUND_MODULES) * 100, 1),
            "available_modules": available,
            "missing_modules": missing,
            "source_events": [
                estimate_outcome.event(available=bool(estimate), source=estimate.get("_source") or "fund_estimate"),
                profile_outcome.event(available=bool(profile), source=profile.get("_source") or "fund_profile"),
                holdings_outcome.event(available=bool(holding_rows), source=holdings.get("_source") or "fund_holdings"),
                premium_outcome.event(
                    available=bool(premium.get("available")),
                    source=premium.get("source") or "premium_discount",
                ),
                index_outcome.event(
                    available=bool(index_snapshot.get("available")),
                    source=index_snapshot.get("source") or "csi_index_snapshot",
                ),
                price_volume_outcome.event(available=bool(price_volume)),
                microstructure_outcome.event(available=bool(microstructure.get("available"))),
                {"source": "csi_index_history", "status": "ok" if index_history.get("available") else "unavailable"},
                {"source": "execution_cost_model", "status": "ok" if execution_cost_model.get("available") else "unavailable"},
                (
                    holding_quotes_outcome.event(available=False)
                    if holding_quotes_outcome.error_type
                    else {
                        "source": "holding_quotes",
                        "status": "ok" if len(holding_quotes) == len(holding_rows) and holding_rows else "partial_or_unavailable",
                    }
                ),
            ],
        },
    }
    result["_meta"].update(
        build_evidence_integrity_audit(
            modules,
            requested_symbol=code,
            resolved_symbol=(
                estimate.get("fundcode")
                or profile.get("fundcode")
                or price_volume.get("symbol")
                or premium.get("fundcode")
                or (
                    code
                    if any(section.get("evidence") for section in modules.values())
                    else None
                )
            ),
            trade_date=trade_date,
        )
    )
    return result


def freeze_fund_evidence(pack: dict[str, Any]) -> dict[str, Any]:
    evidence = {key: copy.deepcopy(value) for key, value in pack.items() if key != "generated_at"}
    return {
        "schema_version": "1.0",
        "snapshot_id": _content_id("sha256", evidence),
        "symbol": pack["symbol"],
        "trade_date": pack["trade_date"],
        "evidence": evidence,
    }


def _module_ids(evidence: dict[str, Any], modules: tuple[str, ...]) -> list[str]:
    return [item["evidence_id"] for code in modules for item in evidence["modules"][code]["evidence"]]


def synthesize_fund_committee(
    snapshot: dict[str, Any],
    research_question: str | None = None,
    lenses: tuple[str, ...] | list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    evidence = snapshot["evidence"]
    selected = tuple(lenses or select_company_committee(research_question, asset_type="fund"))
    engine = LensEngine(mode="committee", lenses=selected)
    question_modules = set(
        relevant_research_modules(research_question, asset_type="fund")
    )
    metric_items = [
        (module, item)
        for module, section in evidence["modules"].items()
        for item in section.get("evidence") or []
        if item.get("metric") and item.get("evidence_id")
    ]
    publishable_claims, unpublished_claims = compile_metric_claims(
        evidence,
        claim_prefix="fund-claim",
    )
    all_claims = [*publishable_claims, *unpublished_claims]
    opinions = {}
    for lens_id in engine.lenses:
        definition = engine.definitions[lens_id]
        name = definition.get("chinese_name") or definition.get("name") or lens_id
        required = FUND_LENS_MODULES[lens_id]
        available = [code for code in required if evidence["modules"][code]["available"]]
        # Plan section 8: selected question modules define claim relevance.
        claim_partition = partition_claims(
            [
                claim
                for claim in all_claims
                if claim.scope in required and claim.scope in question_modules
            ]
        )
        body = {
            "lens_id": lens_id,
            "lens_name": name,
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "required_modules": list(required),
            "available_modules": available,
            "missing_modules": [code for code in required if code not in available],
            "readiness": round(len(available) / len(required), 3),
            "supporting_evidence_ids": _module_ids(evidence, tuple(evidence["modules"])),
            "metric_analyses": [
                {
                    "evidence_id": item["evidence_id"],
                    "module": module,
                    "metric": item["metric"],
                    "value": item.get("value"),
                    "relevance": "core" if module in required else "context",
                    "interpretation": interpret_metric_for_lens(lens_id, item["metric"], item.get("value"), module),
                }
                for module, item in metric_items
            ],
            "research_question": research_question or "指数、行业景气、估值、波动、组合风险与交易实现",
            "question_modules": sorted(question_modules),
            "framework": definition.get("core_philosophy"),
            "risk_focus": definition.get("risk_focus"),
            "publishable_claims": claim_partition["publishable_claims"],
            "unpublished_questions": claim_partition["unpublished_claims"],
            "report_blockers": claim_partition.get("report_blockers", []),
        }
        body["opinion_id"] = _content_id(f"fund-opinion:{lens_id}", body)
        opinions[lens_id] = body
    publishable_by_id: dict[str, dict[str, Any]] = {}
    unpublished_by_id: dict[str, dict[str, Any]] = {}
    report_blockers_by_id: dict[str, dict[str, Any]] = {}
    for opinion in opinions.values():
        for claim in opinion["publishable_claims"]:
            publishable_by_id.setdefault(str(claim["claim_id"]), claim)
        for claim in opinion["unpublished_questions"]:
            unpublished_by_id.setdefault(str(claim["claim_id"]), claim)
        for claim in opinion.get("report_blockers") or []:
            report_blockers_by_id.setdefault(str(claim["claim_id"]), claim)
    serialized_publishable = list(publishable_by_id.values())
    serialized_unpublished = list(unpublished_by_id.values())
    report_blockers = list(report_blockers_by_id.values())
    safety_gate = evaluate_safety_gate(
        evidence,
        serialized_publishable,
        asset_type="fund",
        report_blockers=report_blockers,
    )
    publication_status = safety_gate["decision"]
    action = "block_report" if publication_status == PublicationDecision.BLOCK_REPORT.value else "manual_review"
    committee = {
        "schema_version": "1.0",
        "evidence_snapshot_id": snapshot["snapshot_id"],
        "opinion_ids": [opinion["opinion_id"] for opinion in opinions.values()],
        "members": list(opinions),
        "consensus": [
            "全部 Fund lens 使用同一冻结 Evidence 快照。",
            "委员会只综合达到发布门槛的命题，未解决问题不计入多空方向。",
        ],
        "disagreements": [],
        "risk_vetoes": [],
        "action": action,
        "publication_status": publication_status,
        "safety_gate": safety_gate,
        "action_conditions": list(dict.fromkeys(
            condition
            for claim in serialized_publishable
            for condition in claim["conditions"]
        )),
        "publishable_claims": serialized_publishable,
        "report_blockers": report_blockers,
        "unpublished_questions": serialized_unpublished,
        "research_question": next(iter(opinions.values()))["research_question"],
        "evidence_consumption_audit": {
            metric: [
                lens_id for lens_id, opinion in opinions.items()
                if metric in {item["metric"] for item in opinion["metric_analyses"]}
            ]
            for metric in dict.fromkeys(
                item["metric"]
                for opinion in opinions.values()
                for item in opinion["metric_analyses"]
            )
        },
    }
    committee["committee_id"] = _content_id("fund-committee", committee)
    return committee, opinions


def _metric(pack: dict[str, Any], code: str, metric: str) -> Any:
    return next((item.get("value") for item in pack["modules"][code]["evidence"] if item.get("metric") == metric), None)


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "未取得"
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _fund_report_v48(pack: dict[str, Any], opinions: dict[str, dict[str, Any]], committee: dict[str, Any], changes: list[str]) -> str:
    returns = pack.get("profile", {}).get("returns") or {}
    metrics = pack.get("price_volume", {}).get("metrics") or {}
    latest = pack.get("premium_discount", {}).get("latest") or {}
    metadata = pack.get("premium_discount", {}).get("tracking_metadata") or {}
    holdings = pack.get("holdings", {}).get("holdings") or []
    estimate = pack.get("estimate") or {}
    top5 = _metric(pack, "F2", "top5_weight_pct")
    meta = pack["_meta"]
    lines = [
        f"# Institutional Fund Research Report：{pack['name']}（{pack['symbol']}）",
        "",
        f"**Evidence as of**：{pack['trade_date']}  ",
        f"**Coverage**：{meta['coverage']}%",
        "",
        "## Executive Summary",
        "",
        f"该产品提供对 **{metadata.get('tracked_index') or metadata.get('benchmark') or '半导体主题指数'}** 的高纯度暴露。"
        f"近 1 年收益 {_fmt(returns.get('近1年'), 2, '%')}、近 5 日场内收益 {_fmt(metrics.get('returns_5d'), 2, '%')}、"
        f"14 日 ATR {_fmt(metrics.get('atr_14_pct'), 2, '%')}，显示高收益与高波动并存。",
        f"最新折溢价 {_fmt(latest.get('premium_discount_pct'), 2, '%')}，20 日均值 {_fmt(pack.get('premium_discount', {}).get('premium_discount_20d_mean_pct'), 2, '%')}；"
        "当前交易价格没有明显溢价压力，但不能替代底层成分股估值判断。",
        f"Committee action：**{committee['action']}**。这表示进入人工配置与风险预算复核，不是自动买卖评级。",
        "",
        "## What's Changed Since Last Review",
        "",
    ]
    lines.extend(f"- {item}" for item in changes)
    lines.extend([
        "",
        "## Investment Thesis",
        "",
        f"- **暴露假设**：前五大披露权重 {_fmt(top5, 2, '%')}，收益主要由少数半导体龙头和产业 beta 驱动；指数方法或权重变化会改变该假设。",
        f"- **周期假设**：近 3 月/1 年收益 {_fmt(returns.get('近3月'), 2, '%')} / {_fmt(returns.get('近1年'), 2, '%')}，但近 1 月 {_fmt(returns.get('近1月'), 2, '%')}；产品适合表达周期与成长暴露，不是低波动核心资产替代。",
        f"- **实现假设**：披露年化 tracking error {_fmt(metadata.get('reported_annual_tracking_error_pct'), 2, '%')}，折溢价处于可控区间；该披露值不是本工具按日重算。",
        "- **反证条件**：底层盈利与估值恶化、指数高度集中、持续溢价、跟踪偏离或流动性下降，都会削弱配置逻辑。",
        "",
        "## Evidence Dashboard",
        "",
        "| Available | Missing | Coverage |",
        "|---|---|---:|",
        f"| {', '.join(meta['available_modules'])} | {', '.join(meta['missing_modules']) or '无'} | {meta['coverage']}% |",
        "",
        "## Product, Index Exposure & Governance",
        "",
        f"- 跟踪标的：{metadata.get('tracked_index') or metadata.get('benchmark') or '未取得'}。",
        f"- 规模：{_fmt((pack.get('profile', {}).get('scale') or {}).get('latest_size_yi'), 2, '亿元')}；截止 {(pack.get('profile', {}).get('scale') or {}).get('asof') or '未取得'}。",
        f"- 基金经理：{', '.join(row.get('name') or '' for row in pack.get('profile', {}).get('managers') or []) or '未取得'}。",
        f"- 持仓披露日：{pack.get('holdings', {}).get('asof') or '未取得'}；重仓行情覆盖 {pack.get('holding_quote_coverage', {}).get('available', 0)}/{pack.get('holding_quote_coverage', {}).get('total', 0)}。",
        "",
        "| # | 代码 | 名称 | 权重 |",
        "|---:|---|---|---:|",
    ])
    for index, row in enumerate(holdings, start=1):
        lines.append(f"| {index} | {row.get('code') or ''} | {row.get('name') or ''} | {_fmt(row.get('weight_pct'), 2, '%')} |")
    lines.extend([
        "",
        "## Performance & Risk",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
    ])
    for label in ("近1月", "近3月", "近6月", "近1年"):
        lines.append(f"| {label} | {_fmt(returns.get(label), 2, '%')} |")
    for key, label in (("returns_5d", "5日场内收益"), ("returns_20d", "20日场内收益"), ("returns_60d", "60日场内收益"), ("atr_14_pct", "14日 ATR"), ("volume_zscore", "成交量 z-score")):
        lines.append(f"| {label} | {_fmt(metrics.get(key), 2, '%' if key != 'volume_zscore' else '')} |")
    lines.extend([
        "",
        "## Valuation, Implementation & Scenarios",
        "",
        f"- 最新估算净值：{_fmt(estimate.get('estimate_nav'), 4)}；估算日变动 {_fmt(estimate.get('estimate_change_pct'), 2, '%')}。",
        f"- 场内收盘/官方净值折溢价：{_fmt(latest.get('premium_discount_pct'), 2, '%')}；20 日均值/标准差 {_fmt(pack.get('premium_discount', {}).get('premium_discount_20d_mean_pct'), 2, '%')} / {_fmt(pack.get('premium_discount', {}).get('premium_discount_20d_std_pct'), 2, '%')}。",
        "- **Bull**：底层盈利兑现、产业景气扩散且折溢价稳定，指数 beta 可继续释放。",
        "- **Base**：高波动震荡，收益更多来自仓位纪律与再平衡，而非线性外推近期涨幅。",
        "- **Bear**：估值压缩、产业预期下修或拥挤交易反转；高 ATR 会放大净值回撤。",
        "- 底层估值模块 F5 尚未结构化，因此本报告不以 ETF 单价判断贵贱。",
        "",
        "## Expert Debate",
        "",
        "| Lens | Coverage | Core View |",
        "|---|---:|---|",
    ])
    views = {
        "index_methodology": "先确认指数契约与成分暴露，再讨论主题代表性。",
        "portfolio_construction": "高收益不能脱离集中度和组合机会成本。",
        "risk": "短期回撤和 ATR 已要求显式风险预算。",
        "implementation": "折溢价与 tracking quality 决定表达效率。",
    }
    for lens_id, opinion in opinions.items():
        lines.append(f"| {opinion['lens_name']} | {opinion['readiness']:.1%} | {views[lens_id]} |")
    lines.extend([
        "",
        "## Risks, Catalysts & Scenario Triggers",
        "",
        "- 风险：半导体周期、成分集中、估值压缩、高波动、持仓披露滞后、跟踪和流动性偏离。",
        "- 催化：底层盈利上修、产业资本开支、国产替代进展、指数调仓与资金流改善；需由新 Evidence 验证。",
        "- 触发重跑：新定期报告、指数样本调整、折溢价显著偏离历史区间或 20 日风险指标跳变。",
        "",
        "## Committee Decision Memo",
        "",
        f"- 决策：**{committee['action']}**。",
        "- 定位：高 beta 主题工具；不自动等同于组合核心仓位。",
        "- 动作条件：先定义可承受回撤与主题风险预算，再复核底层估值、集中度和交易实现。",
        "- 失效条件：Evidence 日期、持仓披露、指数方法或折溢价口径变化后，旧 committee 自动失效。",
        "",
        "## Sources & Run Manifest",
        "",
    ])
    lines.extend(f"- {event['source']}：{event['status']}" for event in meta["source_events"])
    lines.extend(["", DISCLAIMER, "股市有风险，投资需谨慎。", ""])
    return "\n".join(lines)


def _fund_claim_lines(claims: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for claim in claims:
        lines.extend([f"### {claim['claim']}", ""])
        period = str(claim.get("applicable_period") or "").strip()
        if period:
            lines.append(f"- 适用期：{period}")
        lines.extend(f"- 适用条件：{condition}" for condition in claim.get("conditions") or [])
        lines.extend(f"- 失效条件：{invalidator}" for invalidator in claim.get("invalidators") or [])
        lines.append("")
    return lines


def _fund_claims_by_section(claims: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    section_by_scope = {
        "F1": 2,
        "F2": 3,
        "F3": 4,
        "F4": 5,
        "F5": 5,
        "F6": 4,
        "F7": 5,
        "F8": 7,
    }
    grouped = {section: [] for section in range(2, 8)}
    for claim in claims:
        section = section_by_scope.get(str(claim.get("scope") or ""), 6)
        grouped[section].append(claim)
    return grouped


def _fund_report(
    pack: dict[str, Any],
    opinions: dict[str, dict[str, Any]],
    committee: dict[str, Any],
    changes: list[str],
) -> str:
    """Render only committee-published claims as required by plan sections 3-5."""

    del changes
    publication_status = str(committee.get("publication_status") or PublicationDecision.PUBLISH.value)
    title = f"# {pack['name']}（{pack['symbol']}）基金深度研究报告 · 投委会"
    if publication_status == PublicationDecision.BLOCK_REPORT.value:
        reasons = [
            str(issue["reason"])
            for issue in (committee.get("safety_gate") or {}).get("issues") or []
            if issue.get("decision") == PublicationDecision.BLOCK_REPORT.value
        ]
        return "\n".join(
            [
                title,
                "",
                f"**报告日期**：{pack['trade_date']}",
                "",
                "## 重大安全阻断",
                "",
                *(f"- {reason}" for reason in reasons),
                "",
                DISCLAIMER,
                "股市有风险，投资需谨慎。",
                "",
            ]
        )

    claims = list(committee.get("publishable_claims") or [])
    grouped = _fund_claims_by_section(claims)
    committee_names = "、".join(str(opinion["lens_name"]) for opinion in opinions.values())
    lines = [
        title,
        "",
        f"**报告日期**：{pack['trade_date']}  ",
        f"**研究问题**：{committee.get('research_question') or '基金研究'}  ",
        f"**分析模式**：动态投委会（{committee_names}）",
        "",
        "## 一、执行摘要",
        "",
    ]
    directional_claims = [claim for claim in claims if claim.get("direction") != "neutral"]
    lines.extend(_fund_claim_lines(directional_claims or claims[:3]))
    sections = {
        2: "## 二、产品定位与指数契约",
        3: "## 三、持仓结构与产业暴露",
        4: "## 四、业绩、趋势与风险",
        5: "## 五、估值、折溢价与交易实现",
        6: "## 六、投委会审议",
        7: "## 七、风险、催化剂与跟踪指标",
    }
    for section, heading in sections.items():
        lines.extend([heading, ""])
        lines.extend(_fund_claim_lines(grouped[section]))
    lines.extend(["## 八、投委会结论与条件化动作", ""])
    if publication_status == PublicationDecision.BLOCK_ACTION.value:
        action_reasons = [
            str(issue["reason"])
            for issue in (committee.get("safety_gate") or {}).get("issues") or []
            if issue.get("decision") == PublicationDecision.BLOCK_ACTION.value
        ]
        lines.extend(
            [
                "估值或交易执行行动被阻断；本报告不生成具体仓位、价格区间或买卖指令。",
                *(f"- {reason}" for reason in action_reasons),
                "",
            ]
        )
    else:
        lines.extend(["以上可发布命题构成本轮条件化研究结论，不生成无条件买卖指令。", ""])
    lines.extend([DISCLAIMER, "股市有风险，投资需谨慎。", ""])
    return "\n".join(lines)

def _simple_doc(title: str, pack: dict[str, Any], body: list[str]) -> str:
    return "\n".join([f"# {title}：{pack['name']}（{pack['symbol']}）", "", *body, ""])


def build_fund_research_workspace(
    pack: dict[str, Any],
    root: Path | str | None = None,
    research_question: str | None = None,
    lenses: tuple[str, ...] | list[str] | None = None,
) -> tuple[dict[str, Any], Path]:
    root_path = Path(root).expanduser() if root is not None else research_root()
    symbol_dir = root_path / _safe_symbol(pack["symbol"])
    workspace = symbol_dir / pack["trade_date"]
    workspace.mkdir(parents=True, exist_ok=True)
    previous_manifest = _load_json(workspace / "workspace.json")
    baseline = _previous_workspace(symbol_dir, pack["trade_date"])
    changes = ["首次研究，无历史基线。"] if not baseline else ["已建立上一期基线；本期按冻结 Evidence 重新复核。"]
    snapshot = freeze_fund_evidence(pack)
    committee, opinions = synthesize_fund_committee(snapshot, research_question=research_question, lenses=lenses)
    audit_artifacts = build_claim_audit_artifacts(snapshot, opinions, committee)
    now = datetime.now(timezone.utc).isoformat()
    evidence_json = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    opinions_json = json.dumps(opinions, ensure_ascii=False, indent=2) + "\n"
    committee_json = json.dumps(committee, ensure_ascii=False, indent=2) + "\n"
    contents = {
        "research_plan": ("01-research-plan.md", _simple_doc("Fund Research Plan", pack, [f"- {code} {label}" for code, label in FUND_MODULES.items()])),
        "fund_evidence": ("02-frozen-fund-evidence.json", evidence_json),
        "evidence_summary": ("03-evidence-summary.md", _simple_doc("Fund Evidence Summary", pack, [f"- 覆盖率：{pack['_meta']['coverage']}%", f"- 缺失：{', '.join(pack['_meta']['missing_modules']) or '无'}"])),
        "expert_readiness": ("04-fund-lens-opinions.md", _simple_doc("Fund Lens Opinions", pack, [f"- {item['lens_name']}：{item['readiness']:.1%}" for item in opinions.values()])),
        "fund_opinions": ("04-fund-lens-opinions.json", opinions_json),
        "committee_synthesis": ("05-committee-synthesis.json", committee_json),
        "committee_review": ("05-committee-review.md", _simple_doc("Fund Committee Review", pack, [f"- action：{committee['action']}", *[f"- {item}" for item in committee["consensus"]]])),
        "decision_memo": ("06-decision-memo.md", _simple_doc("Fund Decision Memo", pack, [f"- action：{committee['action']}", *[f"- {item}" for item in committee["action_conditions"]], "", DISCLAIMER])),
        "institutional_report": ("07-institutional-report.md", _fund_report(pack, opinions, committee, changes)),
        "evidence_manifest": (
            "evidence_manifest.json",
            json.dumps(audit_artifacts["evidence_manifest"], ensure_ascii=False, indent=2) + "\n",
        ),
        "claim_ledger": (
            "claim_ledger.json",
            json.dumps(audit_artifacts["claim_ledger"], ensure_ascii=False, indent=2) + "\n",
        ),
        "coverage_report": (
            "coverage_report.json",
            json.dumps(audit_artifacts["coverage_report"], ensure_ascii=False, indent=2) + "\n",
        ),
        "unpublished_claims": (
            "unpublished_claims.json",
            json.dumps(audit_artifacts["unpublished_claims"], ensure_ascii=False, indent=2) + "\n",
        ),
    }
    previous_artifacts = previous_manifest.get("artifacts") or {}
    artifacts = {
        key: _write_artifact(workspace, filename, content, previous_artifacts.get(key), now)
        for key, (filename, content) in contents.items()
    }
    manifest = {
        "schema_version": "1.0",
        "asset_type": "fund",
        "symbol": pack["symbol"],
        "name": pack["name"],
        "trade_date": pack["trade_date"],
        "research_question": committee.get("research_question"),
        "committee_members": list(opinions),
        "created_at": previous_manifest.get("created_at") or now,
        "updated_at": now,
        "status": {
            "block_report": "blocked_report",
            "block_action": "action_blocked",
        }.get(committee["publication_status"], "ready_for_analysis"),
        "publication_status": committee["publication_status"],
        "stages": {stage: "complete" for stage in ("scope", "research_plan", "evidence_collection", "evidence_validation", "expert_analysis", "committee_review", "report")},
        "baseline": {"trade_date": baseline.get("trade_date"), "path": baseline.get("workspace_path")} if baseline else None,
        "evidence_snapshot": {
            "coverage": pack["_meta"]["coverage"],
            "available_modules": pack["_meta"]["available_modules"],
            "missing_modules": pack["_meta"]["missing_modules"],
            "sha256": snapshot["snapshot_id"].removeprefix("sha256:"),
            "snapshot_id": snapshot["snapshot_id"],
            "committee_id": committee["committee_id"],
        },
        "artifacts": artifacts,
        "workspace_path": str(workspace),
    }
    _atomic_write(workspace / "workspace.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest, workspace
