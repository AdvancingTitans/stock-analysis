"""Company lens opinions and committee synthesis over one frozen Evidence snapshot."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .committee_selection import (
    DEFAULT_RESEARCH_QUESTION,
    relevant_research_modules,
    select_committee,
)
from .lens_engine import DEFAULT_COMMITTEE_MEMBERS, LensEngine
from .research_claims import (
    MissingEvidenceEffect,
    PublicationDecision,
    ResearchClaim,
    SupportStatus,
    claim_source_ids,
    evaluate_safety_gate,
    partition_claims,
    validate_claim_evidence_ids,
    validated_calculation_inputs,
)

DEFAULT_COMPANY_COMMITTEE = DEFAULT_COMMITTEE_MEMBERS
COMPANY_LENS_MODULES = {
    "buffett": ("C1", "C2", "C4", "C5", "C6", "C7"),
    "munger": ("C1", "C4", "C5", "C7"),
    "duan_yongping": ("C1", "C2", "C4", "C5", "C6"),
    "zhang_kun": ("C1", "C2", "C4", "C5", "C6", "C7"),
    "graham": ("C2", "C3", "C6", "C7"),
    "dalio": ("C3", "C6", "C7", "C8"),
    "klarman": ("C2", "C5", "C6", "C7", "C8"),
    "lynch": ("C1", "C2", "C3", "C6", "C7", "C8"),
    "o_neil": ("C2", "C3", "C6", "C7", "C8"),
    "wood": ("C1", "C2", "C3", "C5", "C6", "C7", "C8"),
    "soros": ("C3", "C6", "C7", "C8"),
    "livermore": ("C3", "C6", "C7", "C8"),
    "minervini": ("C2", "C3", "C6", "C7"),
    "simons": ("C2", "C3", "C6", "C7"),
    "feng_liu": ("C1", "C3", "C6", "C7", "C8"),
}


def select_company_committee(research_question: str | None, *, asset_type: str = "company") -> tuple[str, ...]:
    return select_committee(research_question, asset_type=asset_type)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def freeze_company_evidence(pack: dict[str, Any]) -> dict[str, Any]:
    """Freeze business evidence; volatile generation metadata does not affect identity."""

    evidence = {
        "schema_version": pack.get("schema_version"),
        "symbol": pack["symbol"],
        "name": pack.get("name") or pack["symbol"],
        "market": pack.get("market"),
        "trade_date": pack["trade_date"],
        "quote": copy.deepcopy(pack.get("quote") or {}),
        "financial_facts": copy.deepcopy(pack.get("financial_facts") or []),
        "financial_history": copy.deepcopy(pack.get("financial_history") or []),
        "modules": copy.deepcopy(pack["modules"]),
        "_meta": {
            key: copy.deepcopy((pack.get("_meta") or {}).get(key))
            for key in (
                "coverage",
                "available_modules",
                "missing_modules",
                "source_events",
                "identity_validation",
                "publication_cutoff_audit",
                "basis_conflicts",
                "primary_conflicts",
            )
        },
    }
    return {
        "schema_version": "1.0",
        "snapshot_id": _content_id("sha256", evidence),
        "symbol": evidence["symbol"],
        "trade_date": evidence["trade_date"],
        "evidence": evidence,
    }


def _module_evidence_ids(evidence: dict[str, Any], modules: tuple[str, ...]) -> list[str]:
    result = []
    for module in modules:
        for item in (evidence["modules"].get(module) or {}).get("evidence") or []:
            evidence_id = item.get("evidence_id")
            if evidence_id and evidence_id not in result:
                result.append(str(evidence_id))
    return result


def _all_metric_items(evidence: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (module, item)
        for module, section in evidence["modules"].items()
        for item in section.get("evidence") or []
        if item.get("metric") and item.get("evidence_id")
    ]


def _metric_text(metric: str, value: Any) -> str:
    if value is None:
        return metric
    suffix = "%" if metric.endswith("_pct") or metric.startswith("returns_") else ""
    try:
        return f"{metric}={float(value):.2f}{suffix}"
    except (TypeError, ValueError):
        return f"{metric}={value}"


def interpret_metric_for_lens(lens_id: str, metric: str, value: Any, module: str) -> str:
    rendered = _metric_text(metric, value)
    focus = {
        "buffett": "检验长期单位经济性、owner earnings 与安全边际",
        "munger": "用于反向排查商业模式、激励和会计利润错配",
        "duan_yongping": "检验好生意能否持续创造真实现金",
        "zhang_kun": "检验长期自由现金流、竞争格局和机会成本",
        "graham": "检验盈利保护与估值下行缓冲",
        "klarman": "检验永久损失风险、折价和催化兑现",
        "lynch": "检验增长故事是否转化为收入、利润和现金",
        "o_neil": "检验盈利加速是否得到价格与成交确认",
        "wood": "检验长期增长是否有单位经济性和融资能力支撑",
        "dalio": "检验周期、波动和组合风险贡献",
        "soros": "检验预期差与价格反馈是否改变基本面",
        "livermore": "检验趋势确认与仓位风险",
        "minervini": "检验盈利、相对强度和风险收益比",
        "simons": "检验指标定义、稳定性与成本后信号",
        "feng_liu": "检验市场认知、边际变化和赔率",
    }[lens_id]
    return f"{rendered}；{focus}（{module}）。"


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _claim_period(item: dict[str, Any], trade_date: str) -> str:
    return str(item.get("period") or item.get("report_date") or trade_date)


def _claim_source_support(item: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if str(item.get("validation_status") or "").lower() != "accepted":
        return (), ()
    return claim_source_ids(item)


def _metric_claim(
    module: str,
    item: dict[str, Any],
    trade_date: str,
    evidence_by_id: dict[str, dict[str, Any]],
) -> ResearchClaim:
    evidence_id = str(item["evidence_id"])
    metric = str(item["metric"])
    primary_ids, secondary_ids = _claim_source_support(item)
    calculation_inputs = validated_calculation_inputs(item, evidence_by_id)
    supported = bool(primary_ids or len(set(secondary_ids)) >= 2 or calculation_inputs)
    return ResearchClaim(
        claim_id=_content_id("claim", {"module": module, "metric": metric, "evidence_id": evidence_id}),
        claim=f"{_metric_text(metric, item.get('value'))}。",
        direction="neutral",
        scope=module,
        evidence_ids=tuple(dict.fromkeys((evidence_id, *calculation_inputs))),
        claim_status=SupportStatus.SUPPORTED if supported else SupportStatus.UNSUPPORTED,
        applicable_period=_claim_period(item, trade_date),
        conditions=("指标口径、单位和报告期与本次引用证据保持一致。",),
        invalidators=("后续一手披露更正该指标、口径或报告期。",),
        missing_evidence_effect=MissingEvidenceEffect.NO_MATERIAL_EFFECT,
        primary_source_ids=primary_ids,
        secondary_source_ids=secondary_ids,
        calculation_input_evidence_ids=calculation_inputs,
    )


def _cash_conversion_claim(
    metric_items: list[tuple[str, dict[str, Any]]], trade_date: str
) -> ResearchClaim | None:
    by_metric = {str(item["metric"]): (module, item) for module, item in metric_items}
    wanted = (
        "operating_cash_flow_yoy_pct",
        "accounts_receivable_yoy_pct",
        "revenue_yoy_pct",
    )
    if any(metric not in by_metric for metric in wanted):
        return None
    cash_flow = _safe_float(by_metric[wanted[0]][1].get("value"))
    receivables = _safe_float(by_metric[wanted[1]][1].get("value"))
    revenue = _safe_float(by_metric[wanted[2]][1].get("value"))
    if cash_flow is None or receivables is None or revenue is None:
        return None
    bearish = cash_flow < 0 and receivables > revenue
    bullish = cash_flow >= 0 and receivables <= revenue
    if not (bearish or bullish):
        return None
    items = [by_metric[metric][1] for metric in wanted]
    if any(str(item.get("validation_status") or "").lower() != "accepted" for item in items):
        return None
    # Plan sections 3 and 10: derived conclusions require comparable inputs.
    periods = {_claim_period(item, trade_date) for item in items}
    scopes = {str(item.get("scope") or "") for item in items}
    units = {
        (str(item.get("unit") or ""), str(item.get("currency") or ""))
        for item in items
    }
    if len(periods) != 1 or len(scopes) != 1 or len(units) != 1:
        return None
    evidence_ids = tuple(str(item["evidence_id"]) for item in items)
    primary_ids = tuple(
        dict.fromkeys(
            source_id
            for item in items
            for source_id in _claim_source_support(item)[0]
        )
    )
    secondary_ids = tuple(
        dict.fromkeys(
            source_id
            for item in items
            for source_id in _claim_source_support(item)[1]
        )
    )
    return ResearchClaim(
        claim_id=_content_id(
            "claim",
            {"kind": "cash_conversion_decline" if bearish else "cash_conversion_stable", "evidence_ids": evidence_ids},
        ),
        claim="增长的现金实现质量下降" if bearish else "增长的现金实现质量保持稳定",
        direction="bearish" if bearish else "bullish",
        scope="growth_quality",
        evidence_ids=evidence_ids,
        claim_status=(
            SupportStatus.STRONGLY_SUPPORTED
            if len(set((*primary_ids, *secondary_ids))) >= 2 or primary_ids
            else SupportStatus.SUPPORTED
        ),
        applicable_period=next(iter(periods)),
        conditions=("经营现金流、应收账款与营业收入同比指标采用可比报告期和一致口径。",),
        invalidators=(
            "经营现金流同比转正，或应收账款同比不再高于营业收入同比。"
            if bearish
            else "经营现金流同比转负，且应收账款同比高于营业收入同比。",
        ),
        missing_evidence_effect=MissingEvidenceEffect.NO_MATERIAL_EFFECT,
        primary_source_ids=primary_ids,
        secondary_source_ids=secondary_ids,
        calculation_input_evidence_ids=evidence_ids,
    )


def _unpublished_question(
    lens_id: str,
    scope: str,
    question: str,
    missing_evidence: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "question_id": _content_id(
            "question",
            {"lens_id": lens_id, "scope": scope, "question": question},
        ),
        "question": question,
        "scope": scope,
        "missing_evidence": list(missing_evidence),
        "missing_evidence_effect": MissingEvidenceEffect.BLOCKS_CLAIM.value,
        "publication_decision": PublicationDecision.AUDIT_ONLY.value,
        "reason": "相关证据未达到命题发布门槛。",
    }


def _company_claims(evidence: dict[str, Any]) -> list[ResearchClaim]:
    metric_items = _all_metric_items(evidence)
    evidence_by_id = {
        str(item["evidence_id"]): item
        for _, item in metric_items
    }
    claims = [
        _metric_claim(
            module,
            item,
            str(evidence["trade_date"]),
            evidence_by_id,
        )
        for module, item in metric_items
    ]
    cash_conversion = _cash_conversion_claim(metric_items, str(evidence["trade_date"]))
    if cash_conversion is not None:
        claims.append(cash_conversion)
    known_evidence_ids = set(_module_evidence_ids(evidence, tuple(evidence["modules"])))
    for claim in claims:
        validate_claim_evidence_ids(claim, known_evidence_ids)
    return claims


def _claim_module(claim: ResearchClaim) -> str:
    """Map derived scopes back to their research module for question relevance."""

    return {"growth_quality": "C3"}.get(claim.scope, claim.scope)


def build_company_lens_opinions(
    snapshot: dict[str, Any],
    lenses: tuple[str, ...] | list[str] | None = None,
    research_question: str | None = None,
) -> dict[str, dict[str, Any]]:
    selected = tuple(lenses or select_company_committee(research_question))
    engine = LensEngine(mode="committee", lenses=selected)
    evidence = snapshot["evidence"]
    question_modules = set(
        relevant_research_modules(research_question, asset_type="company")
    )
    metric_items = _all_metric_items(evidence)
    claims = _company_claims(evidence)
    market_share_available = any(
        "market_share" in str(item["metric"]).lower() for _, item in metric_items
    )
    opinions: dict[str, dict[str, Any]] = {}
    for lens_id in engine.lenses:
        definition = engine.definitions[lens_id]
        required = COMPANY_LENS_MODULES.get(lens_id, tuple(evidence["modules"]))
        available = tuple(code for code in required if (evidence["modules"].get(code) or {}).get("available"))
        missing = tuple(code for code in required if code not in available)
        supporting = _module_evidence_ids(evidence, tuple(evidence["modules"]))
        counter = _module_evidence_ids(evidence, ("C7",))
        metric_analyses = [
            {
                "evidence_id": item["evidence_id"],
                "module": module,
                "metric": item["metric"],
                "value": item.get("value"),
                "relevance": "core" if module in required else "context",
                "interpretation": interpret_metric_for_lens(lens_id, item["metric"], item.get("value"), module),
            }
            for module, item in metric_items
        ]
        # Plan section 8: a question is answerable only through claims relevant
        # to modules selected for that question; unrelated claims carry no weight.
        relevant_claims = [
            claim
            for claim in claims
            if _claim_module(claim) in required
            and _claim_module(claim) in question_modules
        ]
        claim_partition = partition_claims(relevant_claims)
        unpublished_questions = list(claim_partition["unpublished_claims"])
        unpublished_questions.extend(
            _unpublished_question(
                lens_id,
                module,
                f"{module} 所需研究问题尚未形成可发布命题。",
                tuple(str(gap) for gap in (evidence["modules"].get(module) or {}).get("gaps") or (module,)),
            )
            for module in missing
        )
        if not market_share_available:
            unpublished_questions.append(
                _unpublished_question(
                    lens_id,
                    "C4",
                    "市场份额变化是否支持竞争地位判断？",
                    ("market_share",),
                )
            )
        readiness = len(available) / len(required) if required else 0.0
        publishable_claims = claim_partition["publishable_claims"]
        confidence = (
            "high"
            if any(claim["claim_status"] == SupportStatus.STRONGLY_SUPPORTED.value for claim in publishable_claims)
            else "medium"
            if publishable_claims
            else "low"
        )
        body = {
            "lens_id": lens_id,
            "lens_name": definition.get("chinese_name") or definition.get("name") or lens_id,
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "status": "review_ready",
            "required_modules": list(required),
            "available_modules": list(available),
            "missing_modules": list(missing),
            "supporting_evidence_ids": supporting,
            "counter_evidence_ids": counter,
            "metric_analyses": metric_analyses,
            "publishable_claims": publishable_claims,
            "report_blockers": claim_partition.get("report_blockers", []),
            "unpublished_questions": unpublished_questions,
            "research_question": research_question or DEFAULT_RESEARCH_QUESTION,
            "question_modules": sorted(question_modules),
            "readiness": round(readiness, 3),
            "confidence": confidence,
            "framework": definition.get("core_philosophy"),
            "valuation_preference": definition.get("valuation_preference"),
            "risk_focus": definition.get("risk_focus"),
            "conclusion": f"已形成 {len(publishable_claims)} 条可发布命题。",
        }
        body["opinion_id"] = _content_id(f"opinion:{lens_id}", body)
        opinions[lens_id] = body
    return opinions


def synthesize_company_committee(
    snapshot: dict[str, Any], opinions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if not opinions:
        raise ValueError("company committee requires at least one lens opinion")
    snapshot_ids = {opinion.get("evidence_snapshot_id") for opinion in opinions.values()}
    if snapshot_ids != {snapshot["snapshot_id"]}:
        raise ValueError("all company opinions must consume the same frozen Evidence snapshot")

    ordered_ids = list(opinions)
    publishable_by_id: dict[str, dict[str, Any]] = {}
    unpublished_by_id: dict[str, dict[str, Any]] = {}
    report_blockers_by_id: dict[str, dict[str, Any]] = {}
    for opinion in opinions.values():
        for claim in opinion.get("publishable_claims") or []:
            publishable_by_id.setdefault(str(claim["claim_id"]), claim)
        for question in opinion.get("unpublished_questions") or []:
            audit_id = str(question.get("claim_id") or question.get("question_id"))
            unpublished_by_id.setdefault(audit_id, question)
        for claim in opinion.get("report_blockers") or []:
            report_blockers_by_id.setdefault(str(claim["claim_id"]), claim)
    publishable_claims = list(publishable_by_id.values())
    report_blockers = list(report_blockers_by_id.values())
    safety_gate = evaluate_safety_gate(
        snapshot["evidence"],
        publishable_claims,
        asset_type="company",
        report_blockers=report_blockers,
    )
    publication_status = safety_gate["decision"]
    consensus = [str(claim["claim"]) for claim in publishable_claims]
    directions_by_scope: dict[str, set[str]] = {}
    for claim in publishable_claims:
        directions_by_scope.setdefault(str(claim["scope"]), set()).add(str(claim["direction"]))
    disagreements = [
        f"{scope} 同时存在 bullish 与 bearish 可发布命题。"
        for scope, directions in directions_by_scope.items()
        if {"bullish", "bearish"} <= directions
    ]
    if not disagreements:
        disagreements.append("当前可发布命题未形成相反方向的证据冲突。")
    action_conditions = list(
        dict.fromkeys(
            str(condition)
            for claim in publishable_claims
            for condition in claim.get("conditions") or []
        )
    )
    body = {
        "schema_version": "1.0",
        "evidence_snapshot_id": snapshot["snapshot_id"],
        "opinion_ids": [opinions[lens_id]["opinion_id"] for lens_id in ordered_ids],
        "members": ordered_ids,
        "publishable_claims": publishable_claims,
        "report_blockers": report_blockers,
        "unpublished_questions": list(unpublished_by_id.values()),
        "consensus": consensus,
        "disagreements": disagreements,
        "risk_vetoes": [],
        "action": "block_report" if publication_status == PublicationDecision.BLOCK_REPORT.value else "manual_review",
        "publication_status": publication_status,
        "safety_gate": safety_gate,
        "action_conditions": action_conditions,
        "research_question": next(iter(opinions.values())).get("research_question") or DEFAULT_RESEARCH_QUESTION,
        "evidence_consumption_audit": {
            metric: [
                lens_id for lens_id, opinion in opinions.items()
                if metric in {item["metric"] for item in opinion.get("metric_analyses") or []}
            ]
            for metric in dict.fromkeys(
                item["metric"]
                for opinion in opinions.values()
                for item in opinion.get("metric_analyses") or []
            )
        },
    }
    body["committee_id"] = _content_id("committee", body)
    return body
