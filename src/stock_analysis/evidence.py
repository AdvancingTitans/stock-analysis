from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .quality import EvidenceQuality

MODULE_WEIGHTS = {"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10}

LENS_REQUIREMENTS = {
    "buffett": ("fundamental_quality", "valuation_safety_margin", "portfolio_risk_exposure"),
    "munger": ("fundamental_quality", "portfolio_risk_exposure", "news_samples"),
    "graham": ("fundamental_quality", "valuation_safety_margin", "risk_liquidity"),
    "klarman": ("valuation_safety_margin", "risk_liquidity", "news_samples"),
    "lynch": ("fundamental_quality", "valuation_safety_margin", "sector_rotation_leaders"),
    "o_neil": ("price_volume_behavior", "sector_rotation_leaders", "limit_pool_behavior"),
    "wood": ("sector_rotation_leaders", "news_samples", "risk_liquidity"),
    "dalio": ("market_index_activity", "sector_rotation_leaders", "portfolio_risk_exposure"),
    "soros": ("market_index_activity", "sector_rotation_leaders", "news_samples"),
    "livermore": ("price_volume_behavior", "limit_pool_behavior", "risk_liquidity"),
    "minervini": ("price_volume_behavior", "sector_rotation_leaders", "risk_liquidity"),
    "simons": ("price_volume_behavior", "microstructure_costs", "crowding_proxy", "slippage_sensitivity"),
    "duan_yongping": ("fundamental_quality", "valuation_safety_margin", "news_samples"),
    "zhang_kun": ("fundamental_quality", "valuation_safety_margin", "portfolio_risk_exposure"),
    "feng_liu": ("sector_rotation_leaders", "news_samples", "limit_pool_behavior"),
}


@dataclass
class EvidenceBundle:
    trade_date: str
    modules: dict[str, dict] = field(default_factory=dict)
    meta: dict[str, object] = field(default_factory=dict)

    def quality(self) -> EvidenceQuality:
        self.meta["style"] = "research-report"
        self.meta["style_filter"] = "research-report-sanitized"
        module_scores: dict[str, int] = {}
        missing: list[str] = []
        diagnostics: dict[str, dict[str, object]] = {}

        for module, weight in MODULE_WEIGHTS.items():
            payload = self.modules.get(module) or {}
            if module == "M1":
                score, gaps, available = _score_m1(payload, weight)
            elif module == "M2":
                score, gaps, available = _score_m2(payload, weight)
            else:
                score, gaps, available = _score_simple(payload, weight)

            module_scores[module] = score
            diagnostics[module] = {"score": score, "max": weight, "gaps": gaps, "available": available}
            if not available:
                missing.append(module)

        quality = EvidenceQuality(module_scores=module_scores, missing_modules=missing)
        self.meta["quality_score"] = quality.total_score
        self.meta["missing_modules"] = missing
        self.meta["module_diagnostics"] = diagnostics
        self.meta["source_health"] = _source_health(self.modules, self.meta)
        self.meta["field_health"] = _field_health(self.modules, self.meta)
        self.meta["conditional_evidence"] = _conditional_evidence(self.modules, self.meta)
        self.meta["lens_readiness"] = _lens_readiness(self.meta["conditional_evidence"])
        return quality


def _score_simple(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    available = bool(payload) and payload.get("available", True)
    if available:
        return weight, [], True
    return 0, ["unavailable"], False


def _score_m1(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    gaps: list[str] = []
    score = 0
    a_indices = payload.get("a_indices") or []
    hk_indices = payload.get("hk_indices") or []
    us_indices = payload.get("us_indices") or []
    breadth = payload.get("breadth") or {}

    if a_indices:
        score += 8
    else:
        gaps.append("a_indices")

    index_rows = a_indices + hk_indices + us_indices
    activity_gaps = _index_activity_gaps(index_rows)
    active_count = len(index_rows) - len(activity_gaps)
    if index_rows and active_count == len(index_rows):
        score += 4
    elif active_count:
        score += 2
    else:
        gaps.append("turnover")
    gaps.extend(activity_gaps)

    if hk_indices:
        score += 4
    else:
        gaps.append("hk_indices")

    if breadth.get("available"):
        score += 4
    else:
        gaps.append("breadth")

    available = bool(a_indices or hk_indices or us_indices) and score >= 8
    return min(score, weight), gaps, available


def _index_activity_gaps(rows: list[dict]) -> list[str]:
    gaps: list[str] = []
    for row in rows:
        has_turnover = float(row.get("turnover") or 0) > 0
        has_volume = float(row.get("volume") or 0) > 0
        if not has_turnover and not has_volume:
            gaps.append(f"index_activity:{row.get('name') or row.get('symbol') or 'unknown'}")
    return gaps


def _score_m2(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    gaps: list[str] = []
    score = 0
    industry_rows = payload.get("industry_top20") or []
    concept_rows = payload.get("concept_top20") or []
    fund_flow = payload.get("fund_flow") or {}
    concentration = payload.get("concentration") or {}

    if industry_rows or concept_rows:
        score += 12
    else:
        gaps.append("board_rankings")

    if any(fund_flow.get(key) for key in ("_concept_in", "_concept_out", "_sector_in", "_sector_out", "rows")):
        score += 4
    else:
        gaps.append("fund_flow")

    if concentration.get("top1_ratio") is not None or concentration.get("top3_ratio") is not None:
        score += 4
    else:
        gaps.append("concentration")

    available = score >= 8
    if not available and score > 0:
        gaps.append("partial_only")
    return min(score, weight), gaps, available


def _source_health(modules: dict[str, dict], meta: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}

    for row in _index_rows(modules.get("M1") or {}):
        source = str(row.get("source") or "").strip()
        if source:
            sources.setdefault(source, {"status": "ok", "evidence": []})["evidence"].append("M1.index")

    for event in meta.get("source_events") or []:
        if not isinstance(event, dict):
            continue
        status_text = str(event.get("status") or event.get("fallback") or "").lower()
        status = "unavailable" if ("不可用" in status_text or "unavailable" in status_text) else "ok"
        for source in event.get("sources") or []:
            _merge_source_status(sources, str(source), status, event)
        module = str(event.get("module") or "").strip()
        if module:
            _merge_source_status(sources, module, status, event)

    overall = "warn" if any(item["status"] != "ok" for item in sources.values()) else "ok"
    return {"status": overall, "sources": sources, "events_count": len(meta.get("source_events") or [])}


def _merge_source_status(sources: dict[str, dict[str, Any]], name: str, status: str, event: dict[str, Any]) -> None:
    if not name:
        return
    row = sources.setdefault(name, {"status": "ok", "evidence": []})
    if status == "unavailable":
        row["status"] = "unavailable"
    row["evidence"].append(event)


def _field_health(modules: dict[str, dict], meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    m1 = modules.get("M1") or {}
    m2 = modules.get("M2") or {}
    m3 = modules.get("M3") or {}
    m4 = modules.get("M4") or {}
    fund_flow = m2.get("fund_flow") or {}
    return {
        "M1.index_activity": _field_status(bool(_index_rows(m1)) and not _index_activity_gaps(_index_rows(m1))),
        "M1.breadth": _field_status(bool((m1.get("breadth") or {}).get("available"))),
        "M2.board_rankings": _field_status(bool(m2.get("industry_top20") or m2.get("concept_top20"))),
        "M2.fund_flow": _field_status(any(fund_flow.get(key) for key in ("_concept_in", "_concept_out", "_sector_in", "_sector_out", "rows"))),
        "M3.limit_up_pool": _field_status(bool((m3.get("pool_stats") or {}).get("zt_count") or m3.get("zt_count"))),
        "M4.risk_pools": _field_status(bool((m4.get("pool_stats") or {}).get("dt_count") or m4.get("dt_count"))),
        "fundamental_quality": _field_status(_has_financial_periods(meta.get("stock_financials") or {})),
        "portfolio_exposure": _field_status(bool((meta.get("portfolio_exposure") or {}).get("available"))),
        "stock_microstructure": _field_status(_has_available_pack(meta.get("stock_microstructure") or {})),
        "stock_trading_costs": _field_status(_has_available_pack(meta.get("stock_trading_costs") or {})),
        "news_samples": _field_status(_has_news_samples(meta)),
    }


def _field_status(available: bool, *, reason: str = "") -> dict[str, Any]:
    return {"status": "available" if available else "missing", "reason": reason}


def _conditional_evidence(modules: dict[str, dict], meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    m1 = modules.get("M1") or {}
    m2 = modules.get("M2") or {}
    m3 = modules.get("M3") or {}
    m4 = modules.get("M4") or {}
    fund_flow = m2.get("fund_flow") or {}
    index_rows = _index_rows(m1)
    has_index_activity = bool(index_rows) and not _index_activity_gaps(index_rows)
    has_board_rows = bool(m2.get("industry_top20") or m2.get("concept_top20"))
    has_flow = any(fund_flow.get(key) for key in ("_concept_in", "_concept_out", "_sector_in", "_sector_out", "rows"))
    has_limit_pool = bool((m3.get("pool_stats") or {}).get("zt_count") or m3.get("zt_count"))
    has_risk_pool = bool((m4.get("pool_stats") or {}).get("dt_count") or m4.get("dt_count") or (m4.get("pool_stats") or {}).get("blowup_ratio") is not None)
    has_financials = _has_financial_periods(meta.get("stock_financials") or {})
    has_portfolio = bool((meta.get("portfolio_exposure") or {}).get("available"))
    has_microstructure = _has_available_pack(meta.get("stock_microstructure") or {})
    has_trading_costs = _has_available_pack(meta.get("stock_trading_costs") or {})
    has_news = _has_news_samples(meta)
    price_volume = meta.get("market_price_volume") or m1.get("price_volume") or {}
    has_price_volume = bool(price_volume.get("available"))
    price_volume_fields = list(price_volume.get("available_fields") or [])
    price_volume_missing = list(price_volume.get("missing") or [])
    fund_profile_fields = _fund_profile_fields(meta)
    fund_profile_missing = [field for field in ("returns", "scale", "fees", "managers") if field not in fund_profile_fields]
    has_fund_profile = bool(fund_profile_fields)

    return {
        "market_index_activity": _evidence_status(
            has_index_activity,
            available_fields=["1d_return", "turnover_or_volume"] if has_index_activity else [],
            missing=[] if has_index_activity else ["index_turnover_or_volume"],
        ),
        "price_volume_behavior": _evidence_status(
            has_price_volume,
            conditional=has_index_activity or bool(price_volume_fields),
            available_fields=price_volume_fields or (["1d_return", "turnover_or_volume"] if has_index_activity else []),
            missing=price_volume_missing or (["returns_5d", "returns_20d", "returns_60d", "volume_zscore", "atr_14_pct"] if not has_price_volume else []),
            conditions=list(price_volume.get("conditions") or ([] if has_price_volume else ["先恢复指数行情与成交字段"])),
        ),
        "sector_rotation_leaders": _evidence_status(
            has_board_rows and has_flow,
            conditional=has_board_rows or has_flow,
            available_fields=["board_rankings", "fund_flow"] if has_board_rows and has_flow else [],
            missing=[] if has_board_rows and has_flow else ["board_rankings" if not has_board_rows else "fund_flow"],
            conditions=[] if has_board_rows and has_flow else ["东财 clist 或同花顺 fallback 返回非空行"],
        ),
        "limit_pool_behavior": _evidence_status(
            has_limit_pool,
            conditional=has_risk_pool,
            available_fields=["zt_pool"] if has_limit_pool else [],
            missing=[] if has_limit_pool else ["zt_pool"],
            conditions=["涨跌停池按端点单独归一化价格字段，保留 raw 字段"] if has_limit_pool or has_risk_pool else ["东财涨跌停池返回非空"],
        ),
        "risk_liquidity": _evidence_status(
            has_risk_pool,
            conditional=has_index_activity or has_trading_costs,
            available_fields=["risk_pools"] if has_risk_pool else [],
            missing=[] if has_risk_pool else ["limit_down_or_blowup_pool", "slippage_bucket"],
            conditions=["交易成本/滑点需要更完整成交额与换手率"] if has_index_activity else [],
        ),
        "microstructure_costs": _evidence_status(
            has_microstructure,
            conditional=has_trading_costs,
            available_fields=["best_bid", "best_ask", "spread_bps"] if has_microstructure else [],
            missing=[] if has_microstructure else ["best_bid", "best_ask", "spread_bps"],
            conditions=["Sina A股盘口为快照级；历史订单簿、逐笔成交和 ETF/指数期货对冲成本未建模"],
        ),
        "crowding_proxy": _evidence_status(
            False,
            conditional=has_board_rows or has_limit_pool or has_flow,
            available_fields=["board_rankings", "limit_up_theme_concentration", "sector_money_flow"]
            if (has_board_rows or has_limit_pool or has_flow)
            else [],
            missing=["consumer_crowding_index", "institutional_positioning"],
            conditions=["当前只能用板块排名、涨停主题集中度和行业资金流做 proxy；消费拥挤度完整指标仍不可得"],
        ),
        "slippage_sensitivity": _evidence_status(
            False,
            conditional=has_trading_costs,
            available_fields=["spread_bps", "daily_turnover_cny", "turnover_rate", "liquidity_bucket"]
            if has_trading_costs
            else [],
            missing=["tick_impact_curve", "intraday_adv_profile", "hedge_cost"],
            conditions=["先用于中低频再平衡成本 proxy；超短线信号不得升级为可交易建议"],
        ),
        "fundamental_quality": _evidence_status(
            has_financials,
            missing=[] if has_financials else ["roe", "cash_flow", "debt_ratio"],
            conditions=["仅 A股已披露 datacenter 财务快照进入结构化证据"],
        ),
        "valuation_safety_margin": _evidence_status(
            False,
            conditional=has_financials,
            available_fields=["financial_snapshot"] if has_financials else [],
            missing=["pe_pb_percentiles", "sector_relative_valuation", "downside_to_median_pb"],
            conditions=["先使用 PE/PB/股息率快照；历史估值分位需稳定历史估值源"],
        ),
        "portfolio_risk_exposure": _evidence_status(
            has_portfolio,
            missing=[] if has_portfolio else ["portfolio_weights", "market_exposure", "hhi"],
            conditions=["相关性/beta 需完整持仓与足够历史 K线"],
        ),
        "news_samples": _evidence_status(
            has_news,
            missing=[] if has_news else ["deduped_news_or_community_samples"],
            conditions=["资讯样本必须带 source/url/time/title，并先去重聚合"],
        ),
        "fund_profile": _evidence_status(
            has_fund_profile and not fund_profile_missing,
            conditional=has_fund_profile and bool(fund_profile_missing),
            available_fields=sorted(fund_profile_fields),
            missing=fund_profile_missing,
            conditions=[] if not fund_profile_missing else ["基金持仓变化仅在解析出有效 holdings 后进入证据"],
        ),
    }


def _fund_profile_fields(meta: dict[str, Any]) -> set[str]:
    profiles = list((meta.get("fund_profiles") or {}).values())
    if meta.get("fund_profile"):
        profiles.append(meta["fund_profile"])
    fields: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        for profile_field in ("returns", "scale", "fees", "managers"):
            if profile.get(profile_field):
                fields.add(profile_field)
    return fields


def _evidence_status(
    is_available: bool,
    *,
    conditional: bool = False,
    available_fields: list[str] | None = None,
    missing: list[str] | None = None,
    conditions: list[str] | None = None,
) -> dict[str, Any]:
    status = "available" if is_available else ("conditional" if conditional else "unavailable")
    return {
        "status": status,
        "available": available_fields or [],
        "missing": missing or [],
        "conditions": conditions or [],
    }


def _lens_readiness(conditional: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for lens, requirements in LENS_REQUIREMENTS.items():
        available = [item for item in requirements if conditional.get(item, {}).get("status") == "available"]
        conditioned = [item for item in requirements if conditional.get(item, {}).get("status") == "conditional"]
        missing = [item for item in requirements if conditional.get(item, {}).get("status") == "unavailable"]
        if len(available) == len(requirements):
            status = "ready"
        elif available or conditioned:
            status = "partial"
        else:
            status = "blocked"
        result[lens] = {
            "status": status,
            "required_evidence": list(requirements),
            "available": available,
            "conditional": conditioned,
            "missing": missing,
        }
    return result


def _index_rows(m1: dict[str, Any]) -> list[dict[str, Any]]:
    return list(m1.get("a_indices") or []) + list(m1.get("hk_indices") or []) + list(m1.get("us_indices") or [])


def _has_financial_periods(stock_financials: dict[str, Any]) -> bool:
    return any((snapshot or {}).get("periods") for snapshot in stock_financials.values())


def _has_news_samples(meta: dict[str, Any]) -> bool:
    return bool(
        meta.get("news_samples")
        or meta.get("chinese_news_items")
        or meta.get("chinese_community_items")
        or meta.get("portfolio_public_pulse")
    )


def _has_available_pack(pack: dict[str, Any]) -> bool:
    return any(isinstance(item, dict) and bool(item.get("available")) for item in pack.values())
