"""Company lens opinions and committee synthesis over one frozen Evidence snapshot."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .committee_selection import DEFAULT_RESEARCH_QUESTION, select_committee
from .lens_engine import DEFAULT_COMMITTEE_MEMBERS, LensEngine

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
            for key in ("coverage", "available_modules", "missing_modules", "source_events")
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


def build_company_lens_opinions(
    snapshot: dict[str, Any],
    lenses: tuple[str, ...] | list[str] | None = None,
    research_question: str | None = None,
) -> dict[str, dict[str, Any]]:
    selected = tuple(lenses or select_company_committee(research_question))
    engine = LensEngine(mode="committee", lenses=selected)
    evidence = snapshot["evidence"]
    metric_items = _all_metric_items(evidence)
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
        readiness = len(available) / len(required) if required else 0.0
        status = "review_ready" if not missing else "evidence_insufficient"
        body = {
            "lens_id": lens_id,
            "lens_name": definition.get("chinese_name") or definition.get("name") or lens_id,
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "status": status,
            "required_modules": list(required),
            "available_modules": list(available),
            "missing_modules": list(missing),
            "supporting_evidence_ids": supporting,
            "counter_evidence_ids": counter,
            "metric_analyses": metric_analyses,
            "research_question": research_question or DEFAULT_RESEARCH_QUESTION,
            "readiness": round(readiness, 3),
            "confidence": "high" if readiness >= 0.85 else "medium" if readiness >= 0.6 else "low",
            "framework": definition.get("core_philosophy"),
            "valuation_preference": definition.get("valuation_preference"),
            "risk_focus": definition.get("risk_focus"),
            "conclusion": (
                "框架所需证据仍有缺口，维持观察。"
                if missing
                else "已具备框架复核基础；仍需人工确认估值假设与行动条件。"
            ),
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
    insufficient = [lens_id for lens_id in ordered_ids if opinions[lens_id]["status"] != "review_ready"]
    ready = [lens_id for lens_id in ordered_ids if lens_id not in insufficient]
    missing_modules = list(snapshot["evidence"]["_meta"].get("missing_modules") or [])
    core_modules = {"C2", "C3", "C5", "C6", "C7"}
    available_modules = set(snapshot["evidence"]["_meta"].get("available_modules") or [])
    action = "manual_review" if core_modules <= available_modules else "observe"
    consensus = [
        "全部 Company lens 使用同一冻结 Evidence 快照，未发生跨版本拼接。",
        (
            "核心质量、增长、资本配置、估值与风险模块尚未同时通过，只保留观察条件。"
            if action == "observe"
            else "核心结构化证据已可支持条件化研究判断；商业质量与护城河缺口仍作为人工复核条件。"
        ),
    ]
    disagreements = [
        f"证据门分化：ready={', '.join(ready) or '无'}；insufficient={', '.join(insufficient) or '无'}。",
        "各 lens 对商业质量、资本配置、估值与宏观风险的优先级不同；差异保留在各自 required_modules 与 valuation_preference 中。",
    ]
    risk_vetoes = [f"缺失 Company module：{module}" for module in missing_modules]
    if not risk_vetoes:
        c7 = snapshot["evidence"]["modules"].get("C7") or {}
        risk_vetoes.extend(f"C7 缺口：{gap}" for gap in c7.get("gaps") or [])
    body = {
        "schema_version": "1.0",
        "evidence_snapshot_id": snapshot["snapshot_id"],
        "opinion_ids": [opinions[lens_id]["opinion_id"] for lens_id in ordered_ids],
        "members": ordered_ids,
        "consensus": consensus,
        "disagreements": disagreements,
        "risk_vetoes": risk_vetoes,
        "action": action,
        "action_conditions": [
            "补齐 risk_vetoes 后重新冻结 Evidence 并重跑全部 Company lens。",
            "估值与资本配置判断必须引用结构化 C5/C6 evidence_id。",
        ],
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
