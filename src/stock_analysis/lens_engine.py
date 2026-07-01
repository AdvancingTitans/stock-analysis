from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chinese_public_sources import build_chinese_public_signal_summary

DEFAULT_COMMITTEE_MEMBERS = (
    "buffett",
    "munger",
    "duan_yongping",
    "zhang_kun",
    "graham",
    "dalio",
)
MODULES = ("M1", "M2", "M3", "M4", "M5", "M6")
VALID_MODES = {"single", "committee", "adversarial"}


@dataclass(frozen=True)
class LensContext:
    mode: str
    lenses: tuple[str, ...]
    lens_labels: dict[str, str]
    adjusted_evidence: dict[str, Any]
    activated_modules: tuple[str, ...]
    community_sentiment_summary: dict[str, Any]
    debate_or_synthesis_notes: list[str]


class LensEngine:
    def __init__(
        self,
        *,
        lens: str | None = None,
        lenses: tuple[str, ...] | list[str] | None = None,
        mode: str | None = None,
        lenses_dir: str | Path | None = None,
    ) -> None:
        self.lenses_dir = Path(lenses_dir) if lenses_dir is not None else _default_lenses_dir()
        requested_lenses = tuple(lenses or ())
        if lens and not requested_lenses:
            requested_lenses = (lens,)

        if mode is None:
            mode = "single" if requested_lenses else "committee"
        mode = mode.strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {', '.join(sorted(VALID_MODES))}")

        if not requested_lenses and mode == "committee":
            requested_lenses = DEFAULT_COMMITTEE_MEMBERS
        if not requested_lenses and mode == "single":
            raise ValueError("single mode requires lens")
        if mode == "adversarial" and len(requested_lenses) != 2:
            raise ValueError("adversarial mode requires exactly two lenses")
        if mode == "single" and len(requested_lenses) != 1:
            raise ValueError("single mode requires exactly one lens")

        self.mode = mode
        self.definitions = _load_lens_definitions(self.lenses_dir)
        self.lenses = tuple(_resolve_lens_id(value, self.definitions) for value in requested_lenses)
        unknown = [lens_id for lens_id in self.lenses if lens_id not in self.definitions]
        if unknown:
            raise KeyError(f"unknown lens: {', '.join(unknown)}")

    def build_context(
        self,
        evidence: Any,
        *,
        public_pulses: list[dict[str, Any]] | None = None,
        chinese_news_items: list[dict[str, Any]] | None = None,
        chinese_community_items: list[dict[str, Any]] | None = None,
    ) -> LensContext:
        adjusted = _evidence_to_dict(evidence)
        selected = {lens_id: self.definitions[lens_id] for lens_id in self.lenses}
        weight_adjustments = _combined_weight_adjustments(selected.values())
        _attach_weight_adjustments(adjusted, weight_adjustments, self.mode, self.lenses)

        activated = _activated_modules(adjusted, selected.values())
        notes: list[str] = []
        if self.mode == "committee":
            adjusted.setdefault("M1", {})["committee_deep_analysis"] = _committee_m1_analysis(
                adjusted.get("M1") or {},
                selected,
            )
            adjusted.setdefault("M6", {})["committee_deep_analysis"] = _committee_m6_analysis(
                adjusted,
                selected,
            )
            pulses = public_pulses if public_pulses is not None else _pulses_from_evidence_meta(evidence)
            news_items = (
                chinese_news_items
                if chinese_news_items is not None
                else _chinese_news_from_evidence_meta(evidence)
            )
            community_items = (
                chinese_community_items
                if chinese_community_items is not None
                else _chinese_community_from_evidence_meta(evidence)
            )
            sentiment = _community_sentiment_summary(
                pulses,
                chinese_news_items=news_items,
                chinese_community_items=community_items,
            )
            notes.extend(_committee_notes(selected))
        elif self.mode == "adversarial":
            sentiment = {"status": "not_applicable", "reason": "community sentiment is standard only in committee mode"}
            notes.extend(_adversarial_notes(selected))
        else:
            sentiment = {"status": "not_applicable", "reason": "community sentiment is standard only in committee mode"}
            notes.extend(_single_notes(selected))

        return LensContext(
            mode=self.mode,
            lenses=self.lenses,
            lens_labels={
                lens_id: str(definition.get("chinese_name") or definition.get("name") or lens_id)
                for lens_id, definition in selected.items()
            },
            adjusted_evidence=adjusted,
            activated_modules=activated,
            community_sentiment_summary=sentiment,
            debate_or_synthesis_notes=notes,
        )


def _default_lenses_dir() -> Path:
    override = os.environ.get("STOCK_ANALYSIS_LENSES_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "skills" / "stock-analysis" / "config" / "lenses"


def _normalize_lens_text(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[\s_\-·.]+", "", text)
    for token in ("模式", "风格", "视角", "专家", "lens", "mode", "style"):
        text = text.replace(token, "")
    return text


def _resolve_lens_id(value: str, definitions: dict[str, dict[str, Any]]) -> str:
    raw = value.strip().lower()
    if raw in definitions:
        return raw
    normalized = _normalize_lens_text(value)
    aliases: dict[str, str] = {}
    for lens_id, definition in definitions.items():
        aliases[_normalize_lens_text(lens_id)] = lens_id
        for key in ("name", "chinese_name"):
            label = definition.get(key)
            if label:
                aliases[_normalize_lens_text(str(label))] = lens_id
    return aliases.get(normalized, raw)


def _load_lens_definitions(directory: Path) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.stem} lens definition must be an object")
        for key in ("evidence_weight_adjustments", "analysis_modules_to_emphasize", "committee_role"):
            if key not in payload:
                raise ValueError(f"{path.stem} lens definition missing {key}")
        definitions[path.stem] = payload
    if not definitions:
        raise FileNotFoundError(f"no lens definitions found in {directory}")
    return definitions


def _evidence_to_dict(evidence: Any) -> dict[str, Any]:
    if hasattr(evidence, "modules"):
        payload = copy.deepcopy(evidence.modules)
        payload["_meta"] = copy.deepcopy(getattr(evidence, "meta", {}))
        return payload
    return copy.deepcopy(dict(evidence))


def _combined_weight_adjustments(definitions: Any) -> dict[str, float]:
    totals = {module.lower(): 0.0 for module in MODULES}
    count = 0
    for definition in definitions:
        weights = definition.get("evidence_weight_adjustments") or {}
        for module in totals:
            totals[module] += float(weights.get(module, 0))
        count += 1
    return {module: round(value / count, 2) if count else 0.0 for module, value in totals.items()}


def _attach_weight_adjustments(
    evidence: dict[str, Any],
    weights: dict[str, float],
    mode: str,
    lenses: tuple[str, ...],
) -> None:
    meta = evidence.setdefault("_meta", {})
    meta["lens_mode"] = mode
    meta["lenses"] = list(lenses)
    meta["lens_weight_adjustments"] = weights
    for module in MODULES:
        payload = evidence.get(module)
        if isinstance(payload, dict):
            payload["_lens_weight_adjustment"] = weights.get(module.lower(), 0.0)


def _activated_modules(evidence: dict[str, Any], definitions: Any) -> tuple[str, ...]:
    modules = {module for module in MODULES if isinstance(evidence.get(module), dict) and evidence[module].get("available", True)}
    for definition in definitions:
        modules.update(str(module).upper() for module in definition.get("analysis_modules_to_emphasize") or [])
    return tuple(module for module in MODULES if module in modules)


def _committee_m1_analysis(m1: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = _index_rows(m1)
    values = [_safe_float(row.get("change_pct")) for row in rows]
    values = [value for value in values if value is not None]
    positives = sum(value > 0 for value in values)
    negatives = sum(value < 0 for value in values)
    if not values:
        direction = "数据不足"
    elif positives == len(values):
        direction = "一致上行"
    elif negatives == len(values):
        direction = "一致下行"
    elif positives and negatives:
        direction = "分化"
    else:
        direction = "窄幅震荡"

    dates = sorted({str(row.get("trade_date") or "") for row in rows if row.get("trade_date")})
    anomalies: list[str] = []
    if len(dates) > 1:
        anomalies.append("指数交易日不一致，需要核验跨市场时区或数据源延迟。")
    breadth = m1.get("breadth") or {}
    if breadth.get("available") and values:
        breadth_ratio = _safe_float(breadth.get("ratio"))
        if breadth_ratio is not None and breadth_ratio > 1.2 and sum(values) / len(values) < 0:
            anomalies.append("涨跌家数偏强但指数均值偏弱，可能存在权重股拖累。")
        if breadth_ratio is not None and breadth_ratio < 0.8 and sum(values) / len(values) > 0:
            anomalies.append("指数均值偏强但市场宽度偏弱，可能存在少数权重股支撑。")
    if direction == "分化":
        anomalies.append("市场方向分化，committee 需要区分 beta、行业轮动和持仓暴露。")

    return {
        "cross_validation": {
            "lens_count": len(definitions),
            "lenses": list(definitions),
            "roles": [str(item.get("committee_role")) for item in definitions.values()],
        },
        "trend_consistency": {
            "direction": direction,
            "positive_count": positives,
            "negative_count": negatives,
            "sample_count": len(values),
            "range_pct": round(max(values) - min(values), 2) if values else None,
        },
        "anomalies": anomalies or ["未识别出显著异常点。"],
    }


def _committee_m6_analysis(evidence: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    risks: list[str] = []
    for lens_id, definition in definitions.items():
        risks.append(f"{lens_id}: {definition.get('risk_focus')}")
    m3_stats = ((evidence.get("M3") or {}).get("pool_stats") or {})
    m4_stats = ((evidence.get("M4") or {}).get("pool_stats") or {})
    blowup = _safe_float(m4_stats.get("blowup_ratio") if m4_stats else m3_stats.get("blowup_ratio")) or 0.0
    dt_count = _safe_float(m4_stats.get("dt_count")) or 0.0
    m1_direction = ((evidence.get("M1") or {}).get("committee_deep_analysis") or {}).get("trend_consistency", {}).get("direction")
    score = min(100, round(20 + blowup * 100 + dt_count * 2 + (15 if m1_direction == "分化" else 0), 1))
    conflicts = _lens_conflicts(definitions)
    return {
        "risk_summary": risks,
        "conflict_reconciliation": conflicts,
        "risk_score": score,
        "risk_score_scale": "0-100, higher means higher multi-lens risk",
    }


def _community_sentiment_summary(
    pulses: list[dict[str, Any]],
    *,
    chinese_news_items: list[dict[str, Any]] | None = None,
    chinese_community_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    chinese_news = _chinese_news_analysis(chinese_news_items or [])
    chinese_public = build_chinese_public_signal_summary(
        news_items=chinese_news_items or [],
        community_items=chinese_community_items or [],
    )
    chinese_framework = _chinese_data_source_framework(chinese_public)
    news_framework = _news_analysis_framework()
    if not pulses:
        return {
            "status": "insufficient",
            "overall_sentiment_score": 0.0,
            "overall_sentiment_band": "Neutral",
            "confidence": "low",
            "source_coverage": {
                "news": "missing",
                "community": "missing",
                "stocktwits": "not_integrated",
                "reddit": "not_integrated",
            },
            "source_breakdown": {
                "news": {"sample_count": 0, "tone": "数据不足"},
                "community": {"sample_count": 0, "tone": "数据不足"},
            },
            "key_sentiment_sources": [],
            "cross_source_divergences": [],
            "dominant_narratives": [],
            "fundamental_sentiment_divergences": ["缺少 Futu news/community pulse，暂不放大情绪信号。"],
            "sentiment_catalysts_or_risks": [],
            "sentiment_signal_table": [],
            "chinese_data_source_framework": chinese_framework,
            "news_analysis_framework": news_framework,
            "chinese_news_analysis": chinese_news,
            "chinese_sentiment_components": _chinese_sentiment_components(chinese_news, chinese_public),
        }
    scored = [(_pulse_score(pulse), pulse) for pulse in pulses]
    overall = round(sum(score for score, _ in scored) / len(scored), 1)
    news_count = sum(int(_safe_float(pulse.get("news_count")) or 0) for pulse in pulses)
    community_count = sum(int(_safe_float(pulse.get("community_sample_count")) or 0) for pulse in pulses)
    news_scores = [_news_score(pulse) for pulse in pulses if pulse.get("news_tone") not in (None, "", "暂无相关新闻")]
    community_scores = [_community_score(pulse) for pulse in pulses if pulse.get("community_label") not in (None, "", "证据不足")]
    sources = [
        {
            "symbol": str(pulse.get("symbol") or ""),
            "news_tone": pulse.get("news_tone"),
            "community_label": pulse.get("community_label"),
            "event_title": pulse.get("event_title") or "",
            "evidence_url": pulse.get("evidence_url") or "",
            "score": round(score, 1),
        }
        for score, pulse in sorted(scored, key=lambda item: abs(item[0]), reverse=True)[:5]
    ]
    cross_source_divergences = _cross_source_divergences(scored)
    dominant_narratives = _dominant_narratives(pulses)
    catalysts = [
        f"{pulse.get('symbol')}: {pulse.get('event_title')}"
        for score, pulse in scored
        if pulse.get("event_title") and abs(score) >= 20
    ]
    signal_table = _sentiment_signal_table(scored)
    return {
        "status": "ok",
        "overall_sentiment_score": overall,
        "overall_sentiment_band": _sentiment_band(overall),
        "confidence": _sentiment_confidence(pulses, news_count, community_count),
        "source_coverage": {
            "news": "available" if news_count else "missing",
            "community": "available" if community_count else "missing",
            "stocktwits": "not_integrated",
            "reddit": "not_integrated",
        },
        "source_breakdown": {
            "news": {
                "sample_count": news_count,
                "tone": _direction_from_score(sum(news_scores) / len(news_scores) if news_scores else 0),
                "role": "event/institutional framing",
            },
            "community": {
                "sample_count": community_count,
                "tone": _direction_from_score(sum(community_scores) / len(community_scores) if community_scores else 0),
                "role": "retail mood/opinion stream",
            },
        },
        "key_sentiment_sources": sources,
        "cross_source_divergences": cross_source_divergences,
        "dominant_narratives": dominant_narratives,
        "fundamental_sentiment_divergences": cross_source_divergences or ["情绪与基本面暂无显著分歧。"],
        "sentiment_catalysts_or_risks": catalysts or ["暂无可单独驱动结论的情绪催化剂。"],
        "sentiment_signal_table": signal_table,
        "chinese_data_source_framework": chinese_framework,
        "news_analysis_framework": news_framework,
        "chinese_news_analysis": chinese_news,
        "chinese_sentiment_components": _chinese_sentiment_components(chinese_news, chinese_public),
    }


def _pulse_score(pulse: dict[str, Any]) -> float:
    return (_news_score(pulse) + _community_score(pulse)) / 2


def _news_score(pulse: dict[str, Any]) -> float:
    return {"偏正面": 30.0, "偏负面": -30.0, "中性": 0.0, "暂无相关新闻": 0.0}.get(str(pulse.get("news_tone")), 0.0)


def _community_score(pulse: dict[str, Any]) -> float:
    label = {"偏多": 35.0, "偏空": -35.0, "分歧": 0.0, "中性": 0.0, "证据不足": 0.0}.get(
        str(pulse.get("community_label")),
        0.0,
    )
    bull = _safe_float(pulse.get("community_bull_pct"))
    bear = _safe_float(pulse.get("community_bear_pct"))
    return (bull - bear) if bull is not None and bear is not None else label


def _sentiment_band(score: float) -> str:
    if score >= 35:
        return "Bullish"
    if score >= 10:
        return "Mildly Bullish"
    if score <= -35:
        return "Bearish"
    if score <= -10:
        return "Mildly Bearish"
    return "Mixed" if abs(score) > 3 else "Neutral"


def _sentiment_confidence(pulses: list[dict[str, Any]], news_count: int, community_count: int) -> str:
    if news_count == 0 or community_count < 3:
        return "low"
    if len(pulses) >= 3 and news_count >= 5 and community_count >= 15:
        return "high"
    return "medium"


def _direction_from_score(score: float) -> str:
    if score >= 10:
        return "positive"
    if score <= -10:
        return "negative"
    return "mixed_or_neutral"


def _cross_source_divergences(scored: list[tuple[float, dict[str, Any]]]) -> list[str]:
    divergences = []
    for _, pulse in scored:
        news = _news_score(pulse)
        community = _community_score(pulse)
        symbol = pulse.get("symbol") or ""
        if str(pulse.get("community_label") or "") == "分歧":
            divergences.append(f"{symbol}: 社区内部偏多/偏空分歧，需降低情绪置信度。")
        elif news * community < 0:
            divergences.append(f"{symbol}: 新闻事件方向与社区讨论方向相反，情绪信号需要与基本面交叉验证。")
    return divergences


def _dominant_narratives(pulses: list[dict[str, Any]]) -> list[str]:
    narratives = []
    for pulse in pulses:
        title = str(pulse.get("event_title") or "").strip()
        if title:
            narratives.append(f"{pulse.get('symbol')}: {title}")
    return narratives[:5]


def _sentiment_signal_table(scored: list[tuple[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for score, pulse in scored:
        title = str(pulse.get("event_title") or "")
        if title:
            rows.append(
                {
                    "source": "news",
                    "symbol": str(pulse.get("symbol") or ""),
                    "direction": _direction_from_score(_news_score(pulse)),
                    "evidence": title,
                }
            )
        rows.append(
            {
                "source": "community",
                "symbol": str(pulse.get("symbol") or ""),
                "direction": _direction_from_score(_community_score(pulse)),
                "evidence": "label={label}, samples={samples}, score={score}".format(
                    label=pulse.get("community_label") or "",
                    samples=pulse.get("community_sample_count") or 0,
                    score=round(score, 1),
                ),
            }
        )
    return rows[:8]


def _pulses_from_evidence_meta(evidence: Any) -> list[dict[str, Any]]:
    meta = getattr(evidence, "meta", None)
    if meta is None and isinstance(evidence, dict):
        meta = evidence.get("_meta")
    pulses = (meta or {}).get("portfolio_public_pulse") or []
    return [pulse for pulse in pulses if isinstance(pulse, dict)]


def _chinese_news_from_evidence_meta(evidence: Any) -> list[dict[str, Any]]:
    meta = getattr(evidence, "meta", None)
    if meta is None and isinstance(evidence, dict):
        meta = evidence.get("_meta")
    items = (meta or {}).get("chinese_news_items") or (meta or {}).get("news_items") or []
    return [item for item in items if isinstance(item, dict)]


def _chinese_community_from_evidence_meta(evidence: Any) -> list[dict[str, Any]]:
    meta = getattr(evidence, "meta", None)
    if meta is None and isinstance(evidence, dict):
        meta = evidence.get("_meta")
    items = (meta or {}).get("chinese_community_items") or (meta or {}).get("community_items") or []
    return [item for item in items if isinstance(item, dict)]


def _chinese_data_source_framework(chinese_public: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_data_sources": ["Tushare", "AkShare", "BaoStock"],
        "high_priority_news_sources": chinese_public["registered_news_sources"],
        "community_sources": chinese_public["registered_community_sources"],
        "source_status": chinese_public["source_status"],
        "status_note": "stock-analysis 内置中文金融新闻与社区讨论源注册表；无样本时标记 registered_no_samples。",
    }


def _news_analysis_framework() -> dict[str, Any]:
    return {
        "pipeline": [
            "多源聚合：专业快讯、财经门户、个股新闻、社区讨论分别保留来源标签。",
            "多层过滤：先做标的相关性，再做标题去重、时间排序和样本量检查。",
            "质量评估：按来源覆盖、相关度、紧急度、重复率和样本量给出置信度。",
            "事件/观点分离：新闻事件进入催化剂，社区讨论进入情绪和分歧。",
            "综合调和：与 M1-M6 基本面、价格、风险模块交叉验证，不把情绪当价格预测。",
        ],
        "quality_dimensions": ["source_coverage", "deduplication", "relevance", "urgency", "sample_size"],
    }


def _chinese_news_analysis(items: list[dict[str, Any]]) -> dict[str, Any]:
    unique: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in items:
        title = " ".join(str(item.get("title") or "").split())
        if len(title) <= 6:
            continue
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        unique.append({**item, "title": title})

    source_distribution: dict[str, int] = {}
    urgency_breakdown = {"high": 0, "medium": 0, "low": 0}
    relevance_values: list[float] = []
    sentiment_values: list[float] = []
    for item in unique:
        source = str(item.get("source") or "unknown")
        source_distribution[source] = source_distribution.get(source, 0) + 1
        urgency = str(item.get("urgency") or "low").lower()
        urgency_breakdown[urgency if urgency in urgency_breakdown else "low"] += 1
        relevance = _safe_float(item.get("relevance_score"))
        sentiment = _safe_float(item.get("sentiment_score"))
        if relevance is not None:
            relevance_values.append(relevance)
        if sentiment is not None:
            sentiment_values.append(sentiment)

    average_relevance = sum(relevance_values) / len(relevance_values) if relevance_values else 0.0
    duplicate_count = len(items) - len(unique)
    quality_score = min(
        100.0,
        len(source_distribution) * 15 + len(unique) * 6 + average_relevance * 25 - duplicate_count * 5,
    )
    return {
        "raw_count": len(items),
        "deduplicated_count": len(unique),
        "duplicate_count": duplicate_count,
        "source_distribution": source_distribution,
        "urgency_breakdown": urgency_breakdown,
        "average_relevance_score": round(average_relevance, 2),
        "average_sentiment_score": round(sum(sentiment_values) / len(sentiment_values), 2) if sentiment_values else 0.0,
        "quality_assessment": {
            "score": round(max(0.0, quality_score), 1),
            "level": _quality_level(quality_score),
        },
    }


def _quality_level(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _chinese_sentiment_components(news_analysis: dict[str, Any], chinese_public: dict[str, Any]) -> dict[str, Any]:
    news_count = int(news_analysis.get("deduplicated_count") or 0)
    community_count = int(chinese_public["community"].get("sample_count") or 0)
    news_confidence = min(news_count / 10, 1.0)
    return {
        "news": {
            "status": "available" if news_count else "missing",
            "sample_count": news_count,
            "sentiment_score": news_analysis.get("average_sentiment_score", 0.0),
            "confidence": round(news_confidence, 2),
        },
        "forum": {
            "status": "available" if community_count else "registered_no_samples",
            "registered_sources": chinese_public["registered_community_sources"],
            "sample_count": community_count,
            "sentiment_score": chinese_public["community"].get("average_sentiment_score", 0.0),
            "confidence": round(min(community_count / 10, 1.0), 2),
        },
        "media": {
            "status": "registered_no_samples",
            "registered_sources": ["财联社", "新浪财经", "腾讯财经"],
            "sample_count": 0,
            "confidence": 0,
        },
    }


def _committee_notes(definitions: dict[str, dict[str, Any]]) -> list[str]:
    return [
        "committee synthesis: M1 uses cross-lens validation, trend consistency, and anomaly checks before conclusions.",
        "committee synthesis: M6 reconciles risk focus conflicts and produces a final risk score.",
        "committee sentiment: Futu news and community pulse are aggregated before being compared with fundamentals.",
    ] + [f"{lens_id}: {definition.get('committee_role')}" for lens_id, definition in definitions.items()]


def _single_notes(definitions: dict[str, dict[str, Any]]) -> list[str]:
    lens_id, definition = next(iter(definitions.items()))
    return [f"single lens deep mode: {lens_id} follows {definition.get('core_philosophy')}"]


def _adversarial_notes(definitions: dict[str, dict[str, Any]]) -> list[str]:
    left, right = definitions.keys()
    return [
        f"adversarial debate: {left} challenges {right} on evidence priority, valuation, and risk.",
        f"adversarial debate: {right} challenges {left} on blind spots and timing risk.",
    ]


def _lens_conflicts(definitions: dict[str, dict[str, Any]]) -> list[str]:
    positive_m3 = [lens_id for lens_id, item in definitions.items() if (item.get("evidence_weight_adjustments") or {}).get("m3", 0) > 0]
    negative_m3 = [lens_id for lens_id, item in definitions.items() if (item.get("evidence_weight_adjustments") or {}).get("m3", 0) < 0]
    conflicts = []
    if positive_m3 and negative_m3:
        conflicts.append(f"M3 短线强度分歧：{', '.join(positive_m3)} 更重视，{', '.join(negative_m3)} 降权。")
    conflicts.append("最终调和顺序：先确认数据质量，再区分短期价格风险、长期商业风险与组合暴露风险。")
    return conflicts


def _index_rows(m1: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("a_indices", "hk_indices", "us_indices"):
        rows.extend(item for item in m1.get(key, []) if isinstance(item, dict))
    return rows


def _safe_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None
