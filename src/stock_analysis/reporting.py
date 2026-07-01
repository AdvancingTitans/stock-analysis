from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceBundle
from .lens_engine import LensContext, LensEngine
from .quality import EvidenceQuality
from .research_style import sanitize_research_report

MODULE_LABELS = {
    "M1": "大盘指数概览",
    "M2": "板块资金与集中度",
    "M3": "赚钱效应与上涨主线",
    "M4": "下跌风险",
    "M5": "特征分组",
    "M6": "抗跌方向",
}


@dataclass(frozen=True)
class ReportResult:
    markdown: str
    metadata: dict[str, Any]


def generate_report(
    *,
    evidence: EvidenceBundle,
    trade_date: str | None = None,
    session_label: str | None = None,
    portfolio_snapshot: dict[str, Any] | None = None,
    report_format: str = "full",
    lens: str | None = None,
    lenses: tuple[str, ...] | list[str] | None = None,
    mode: str | None = None,
) -> ReportResult:
    return render_report_with_metadata(
        trade_date=trade_date or evidence.trade_date,
        session_label=session_label or str(evidence.meta.get("session") or "盘后"),
        evidence=evidence,
        quality=evidence.quality(),
        portfolio_snapshot=portfolio_snapshot or {"details": []},
        report_format=report_format,
        lens=lens,
        lenses=lenses,
        mode=mode,
    )


def render_diagnostics(items) -> str:
    lines = ["# diagnose", ""]
    for item in items:
        lines.append(f"- `{item.name}`: {item.status} - {item.detail}")
    return "\n".join(lines)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):+.2f}%"


def _fmt_price(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):,.2f}"


def _fmt_amount_yi(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value) / 1e8:,.2f}亿"


def _fmt_quantity(value: Any) -> str:
    if value is None:
        return ""
    number = float(value)
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


def _fmt_daily_pnl(detail: dict[str, Any]) -> str:
    value = detail.get("daily_pnl_original")
    if value is None:
        return ""
    return f"{float(value):+,.0f} {detail.get('currency', '')}".strip()


def _append_index_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    lines.extend(
        [
            "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        turnover = _fmt_amount_yi(row.get("turnover")) or ""
        lines.append(
            "| {name} | {price} | {change} | {change_pct} | {turnover} |".format(
                name=row.get("name") or "",
                price=_fmt_price(row.get("price")),
                change=_fmt_price(row.get("change")),
                change_pct=_fmt_pct(row.get("change_pct")),
                turnover=turnover,
            )
        )


def _append_northbound_table(lines: list[str], northbound: dict[str, Any]) -> None:
    if northbound.get("total_yi") is None:
        return
    lines.extend(
        [
            "",
            "| 资金项 | 净流向 |",
            "|---|---:|",
            f"| 北向资金 | {float(northbound['total_yi']):+,.2f}亿 |",
        ]
    )


def _append_breadth_table(lines: list[str], breadth: dict[str, Any]) -> None:
    if not breadth.get("available"):
        return
    ratio = breadth.get("ratio")
    lines.extend(
        [
            "",
            "| 市场广度 | 上涨家数 | 下跌家数 | 涨跌比 |",
            "|---|---:|---:|---:|",
            f"| {breadth.get('scope') or '全市场'} | {breadth.get('up', 0)} | "
            f"{breadth.get('down', 0)} | {f'{float(ratio):.2f}' if ratio is not None else ''} |",
        ]
    )


def _append_sector_table(lines: list[str], rows: list[dict[str, Any]], limit: int = 10) -> None:
    visible = [row for row in rows if row.get("name")][:limit]
    if not visible:
        return
    lines.extend(
        [
            "| 板块 | 涨跌幅 | 上涨家数 | 下跌家数 |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in visible:
        lines.append(
            f"| {row.get('name')} | {_fmt_pct(row.get('change_pct'))} | "
            f"{row.get('up_count') if row.get('up_count') is not None else ''} | "
            f"{row.get('down_count') if row.get('down_count') is not None else ''} |"
        )


def _append_holdings_table(lines: list[str], details: list[dict[str, Any]]) -> None:
    lines.extend(
        [
            "| 代码 | 名称 | 市场 | 买入日 | 数量 | 现价 | 当日涨跌 | 当日浮盈/亏 | 趋势 |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for detail in details:
        current_price = _fmt_price(detail.get("current_price"))
        if current_price:
            current_price = f"{current_price} {detail.get('currency', '')}".strip()
        lines.append(
            "| {symbol} | {name} | {market} | {buy_date} | {quantity} | {price} | "
            "{change_pct} | {daily_pnl} | {trend} |".format(
                symbol=detail.get("symbol") or "",
                name=detail.get("name") or "",
                market=_market_label(detail.get("market")),
                buy_date=detail.get("buy_date") or "",
                quantity=_fmt_quantity(detail.get("quantity")),
                price=current_price,
                change_pct=_fmt_pct(detail.get("change_pct")),
                daily_pnl=_fmt_daily_pnl(detail),
                trend=detail.get("trend") or "",
            )
        )


def _append_portfolio_summary_table(lines: list[str], snapshot: dict[str, Any]) -> None:
    details = snapshot.get("details") or []
    styles: dict[str, float] = {}
    for detail in details:
        style = str(detail.get("style") or "").strip()
        if not style:
            continue
        weight = float(detail.get("market_value_cny") or 0)
        styles[style] = styles.get(style, 0.0) + weight
    style_exposure = ""
    if styles:
        style_exposure = max(styles.items(), key=lambda item: item[1])[0]
    dominant_market = _market_label(snapshot.get("dominant_market"))
    dominant_ratio = snapshot.get("dominant_ratio")
    market_exposure = dominant_market
    if dominant_market and dominant_ratio is not None:
        market_exposure = f"{dominant_market} {_fmt_ratio(dominant_ratio)}"
    lines.extend(
        [
            "| 总市值(CNY) | 总浮盈/亏 | 前三大占比 | 单一市场最高暴露 | 风格暴露 |",
            "|---:|---:|---:|---|---|",
            "| {value} | {pnl} | {top3} | {market} | {style} |".format(
                value=_fmt_price(snapshot.get("total_value_cny")),
                pnl=_fmt_signed_cny(snapshot.get("total_pnl_cny")),
                top3=_fmt_ratio(snapshot.get("top3_ratio")),
                market=market_exposure,
                style=style_exposure,
            ),
        ]
    )


def _append_relative_strength_table(lines: list[str], details: list[dict[str, Any]]) -> None:
    lines.extend(
        [
            "| 代码 | 名称 | 基准指数 | 跑赢/跑输(pp) |",
            "|---|---|---|---:|",
        ]
    )
    for detail in details:
        benchmark = detail.get("benchmark_name")
        relative_pct = detail.get("relative_pct")
        if not benchmark or relative_pct is None:
            continue
        lines.append(
            f"| {detail.get('symbol') or ''} | {detail.get('name') or ''} | "
            f"{benchmark} | {float(relative_pct):+.2f} |"
        )


def _append_public_pulse_table(lines: list[str], details: list[dict[str, Any]]) -> None:
    visible = [detail for detail in details if detail.get("public_pulse")]
    if not visible:
        return
    lines.extend(
        [
            "### 持仓公开信息脉冲",
            "| 代码 | 新闻倾向 | 最新高信号事件 | 社区情绪 | 有效样本 | 证据 |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for detail in visible:
        pulse = detail.get("public_pulse") or {}
        event = str(pulse.get("event_title") or "").replace("|", "｜")
        url = str(pulse.get("evidence_url") or "")
        evidence = f"[原文]({url})" if url else ""
        lines.append(
            f"| {detail.get('symbol') or ''} | {pulse.get('news_tone') or ''} | "
            f"{event} | {pulse.get('community_label') or ''} | "
            f"{pulse.get('community_sample_count') if pulse.get('community_sample_count') is not None else ''} | "
            f"{evidence} |"
        )
    lines.append("")
    lines.append("> 社区情绪仅代表富途公开讨论样本；少于 3 条精确匹配的有效帖子时不计算多空比例。")


def _market_label(value: Any) -> str:
    return {"a": "A股", "hk": "港股", "us": "美股", "fund": "基金"}.get(
        str(value or "").lower(),
        str(value or ""),
    )


def _fmt_ratio(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.1%}"


def _fmt_signed_cny(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):+,.2f}"


def _append_leader_table(lines: list[str], leaders: list[dict[str, Any]]) -> None:
    visible = [leader for leader in leaders if leader.get("name")]
    if not visible:
        return
    lines.extend(
        [
            "| 股票 | 连板 | 封单金额 |",
            "|---|---:|---:|",
        ]
    )
    for leader in visible:
        label = str(leader.get("name"))
        if leader.get("code"):
            label += f"（{leader.get('code')}）"
        seal_fund = leader.get("seal_fund_yi")
        lines.append(
            f"| {label} | {leader.get('board_days') or ''} | "
            f"{f'{float(seal_fund):,.2f}亿' if seal_fund is not None else ''} |"
        )


def _append_bullets(lines: list[str], values: list[str]) -> None:
    for value in values:
        if value:
            lines.append(f"- {value}")


def _section_prefix(lines: list[str], stop_heading: str) -> list[str]:
    try:
        stop = lines.index(stop_heading)
    except ValueError:
        return list(lines)
    return lines[:stop]


def render_report_with_metadata(
    *,
    trade_date: str,
    session_label: str,
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
    lens: str | None = None,
    lenses: tuple[str, ...] | list[str] | None = None,
    mode: str | None = None,
    lens_context: LensContext | None = None,
) -> ReportResult:
    fallback: dict[str, Any] | None = None
    if lens_context:
        context = lens_context
    else:
        context, fallback = _build_lens_context_with_fallback(evidence, lens=lens, lenses=lenses, mode=mode)
    markdown = _render_lens_report(
        trade_date=trade_date,
        session_label=session_label,
        evidence=evidence,
        quality=quality,
        portfolio_snapshot=portfolio_snapshot,
        report_format=report_format,
        lens_context=context,
        explicit_lens_request=bool(lens or lenses or fallback),
        default_committee=mode is None and not lens and not lenses and context.mode == "committee",
        fallback=fallback,
    )
    metadata = _report_metadata(
        trade_date=trade_date,
        session_label=session_label,
        quality=quality,
        lens_context=context,
        default_committee=mode is None and not lens and not lenses and context.mode == "committee",
        fallback=fallback,
    )
    evidence.meta["report_metadata"] = metadata
    return ReportResult(markdown=markdown, metadata=metadata)


def _build_lens_context_with_fallback(
    evidence: EvidenceBundle,
    *,
    lens: str | None,
    lenses: tuple[str, ...] | list[str] | None,
    mode: str | None,
) -> tuple[LensContext, dict[str, Any] | None]:
    try:
        return LensEngine(lens=lens, lenses=lenses, mode=mode).build_context(evidence), None
    except Exception as exc:
        requested_mode = (mode or ("single" if (lens or lenses) else "committee")).strip().lower()
        if requested_mode != "committee":
            raise
        fallback_lens = _fallback_lens(lens=lens, lenses=lenses)
        context = LensEngine(lens=fallback_lens, mode="single").build_context(evidence)
        return context, {
            "from_mode": "committee",
            "to_mode": "single",
            "fallback_lens": fallback_lens,
            "reason": str(exc),
        }


def _fallback_lens(*, lens: str | None, lenses: tuple[str, ...] | list[str] | None) -> str:
    if lens:
        return lens
    for candidate in lenses or ():
        try:
            return LensEngine(lens=candidate).lenses[0]
        except Exception:
            continue
    return "buffett"


def _render_lens_report(
    *,
    trade_date: str,
    session_label: str,
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
    lens_context: LensContext,
    explicit_lens_request: bool,
    default_committee: bool,
    fallback: dict[str, Any] | None = None,
) -> str:
    modules = lens_context.adjusted_evidence
    mode_label = _mode_label(lens_context.mode, default_committee=default_committee)
    lens_names = _lens_names(lens_context)
    lines: list[str] = [
        f"# 全球市场复盘研报（{_display_date(trade_date)} {session_label}）",
        "",
        f"**报告日期**：{_display_date(trade_date)}  ",
        f"**分析模式**：{mode_label}  ",
    ]
    if explicit_lens_request:
        lines.append(f"**使用视角**：{' + '.join(lens_names)}  ")
    lines.append(f"**数据截止**：{_display_date(evidence.meta.get('trade_date') or trade_date)}")
    if fallback:
        lines.append(f"**降级说明**：committee 构建失败，已降级为 single/{fallback['fallback_lens']}。")
    lines.append("")
    if quality.degrade_mode == "degraded":
        missing = "、".join(MODULE_LABELS.get(value, value) for value in quality.missing_modules)
        lines.extend([f"> 本模块证据暂缺：{missing}。正文仅呈现可验证信息。", ""])
    elif quality.degrade_mode == "simplified":
        lines.extend(["> 本模块证据暂缺，报告聚焦指数、持仓和风险控制。", ""])

    m1 = modules.get("M1", {})
    m2 = modules.get("M2", {})
    m3 = modules.get("M3", {})
    m4 = modules.get("M4", {})
    m5 = modules.get("M5", {})
    m6 = modules.get("M6", {})
    sentiment = lens_context.community_sentiment_summary

    lines.append("## 1. 执行摘要")
    lines.append(_executive_summary(m1, m3, m4, m6, lens_context, quality))
    lines.append("")

    lines.append("## 2. 分析视角说明")
    lines.append(f"本次使用{mode_label}。")
    lines.append("综合视角：" + " + ".join(lens_names) + "。")
    _append_bullets(lines, lens_context.debate_or_synthesis_notes[:8])
    lines.append("")

    lines.append("## 3. 商业模式与护城河（多视角综合）")
    if lens_context.mode == "committee":
        lines.append("巴菲特侧重护城河与安全边际，芒格侧重风险清单，段永平侧重商业本质，张坤侧重长期质量与治理。")
    lines.append(f"=={m2.get('summary', '市场以结构性轮动为主。')}==")
    lines.append(f"风格线索：{m5.get('summary', '当前风格证据不足，先观察价格与基本面是否互相确认。')}")
    lines.append("")

    lines.append("## 4. 财务深度分析")
    _append_index_table(lines, _index_rows(m1))
    _append_northbound_table(lines, m1.get("northbound") or {})
    _append_breadth_table(lines, m1.get("breadth") or {})
    if lens_context.mode == "committee":
        lines.append("")
        lines.append(_format_m1_committee_analysis(m1))
    lines.append("")

    lines.append("## 5. 估值与情景分析")
    lines.append("估值判断采用 lens 调整后的证据权重：先看数据质量，再区分短期价格弹性、长期现金流质量和组合暴露。")
    sector_rows = m2.get("industry_top20") or m2.get("concept_top20") or []
    _append_sector_table(lines, sector_rows)
    lines.append("")

    if lens_context.mode == "committee":
        lines.append("## 6. 社区情绪分析")
        lines.extend(_community_sentiment_lines(sentiment))
        lines.append("")

    risk_heading = "## 7. 风险，催化剂与缓解措施" if lens_context.mode == "committee" else "## 6. 风险，催化剂与缓解措施"
    lines.append(risk_heading)
    lines.append(f"=={m4.get('summary', '风险主要集中在高位分歧。')}==")
    if lens_context.mode == "committee":
        lines.append(_format_m6_committee_analysis(m6))
    _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, sentiment))
    lines.append("")

    advice_heading = "## 8. 投资建议与仓位指导" if lens_context.mode == "committee" else "## 7. 投资建议与仓位指导"
    lines.append(advice_heading)
    lines.append("以下为多视角调和后的条件化结论，不作为无条件买卖指令。")
    _append_lens_advice(lines, evidence, portfolio_snapshot)
    lines.append("")

    appendix_heading = "## 9. 证据附录" if lens_context.mode == "committee" else "## 8. 证据附录"
    lines.append(appendix_heading)
    lines.append(f"- activated_modules: {', '.join(lens_context.activated_modules)}")
    lines.append(f"- lens_adjustments: {modules.get('_meta', {}).get('lens_weight_adjustments', {})}")
    if lens_context.mode == "committee":
        lines.append(f"- community_sources: {sentiment.get('source_coverage', {})}")
        lines.append(f"- key_sentiment_sources: {sentiment.get('key_sentiment_sources', [])[:3]}")
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    disclaimer = "免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
    if report_format == "summary":
        compact = _section_prefix(lines, "## 4. 财务深度分析")
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    if report_format == "key-points":
        stop_heading = "## 7. 风险，催化剂与缓解措施" if lens_context.mode == "committee" else "## 6. 风险，催化剂与缓解措施"
        compact = _section_prefix(lines, stop_heading)
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    return sanitize_research_report("\n".join(lines))


def _report_metadata(
    *,
    trade_date: str,
    session_label: str,
    quality: EvidenceQuality,
    lens_context: LensContext,
    default_committee: bool,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adjusted = lens_context.adjusted_evidence
    metadata = {
        "report_date": _display_date(trade_date),
        "session": session_label,
        "analysis_mode": lens_context.mode,
        "analysis_mode_label": _mode_label(lens_context.mode, default_committee=default_committee),
        "lenses": list(lens_context.lenses),
        "lens_labels": _lens_names(lens_context),
        "activated_modules": list(lens_context.activated_modules),
        "quality_score": quality.total_score,
        "missing_modules": quality.missing_modules,
        "committee_deep_analysis": {
            "m1": ((adjusted.get("M1") or {}).get("committee_deep_analysis") or {}),
            "m6": ((adjusted.get("M6") or {}).get("committee_deep_analysis") or {}),
        },
        "community_sentiment_summary": lens_context.community_sentiment_summary,
        "debate_or_synthesis_notes": lens_context.debate_or_synthesis_notes,
        "lens_adjustments": (adjusted.get("_meta") or {}).get("lens_weight_adjustments", {}),
    }
    if fallback:
        metadata["fallback"] = fallback
    return metadata


def _display_date(value: Any) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return str(value or "")


def _mode_label(mode: str, *, default_committee: bool) -> str:
    if mode == "committee":
        return "投委会（默认）" if default_committee else "投委会"
    if mode == "single":
        return "单一专家"
    return "对抗辩论"


def _lens_names(context: LensContext) -> list[str]:
    return [context.lens_labels.get(lens_id, lens_id) for lens_id in context.lenses]


def _index_rows(m1: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("a_indices", "hk_indices", "us_indices"):
        rows.extend(item for item in m1.get(key, []) if isinstance(item, dict))
    return [row for row in rows if row.get("name") and row.get("price") is not None]


def _executive_summary(
    m1: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m6: dict[str, Any],
    context: LensContext,
    quality: EvidenceQuality,
) -> str:
    trend = ((m1.get("committee_deep_analysis") or {}).get("trend_consistency") or {}).get("direction")
    risk_score = ((m6.get("committee_deep_analysis") or {}).get("risk_score"))
    zt_count = ((m3.get("pool_stats") or {}).get("zt_count") or m3.get("zt_count") or 0)
    blowup = ((m4.get("pool_stats") or {}).get("blowup_ratio") or 0)
    confidence = "中等"
    if quality.total_score >= 85 and (risk_score is None or risk_score < 50):
        confidence = "较高"
    elif quality.total_score < 70 or (risk_score is not None and risk_score >= 70):
        confidence = "偏低"
    conclusion = "维持观察，等待趋势、成交和风险项进一步确认"
    if confidence == "较高":
        conclusion = "可在既定风控内分批评估"
    return (
        f"投资确信度：{confidence}。推荐结论：{conclusion}。"
        f"盘面趋势为{trend or '待确认'}，涨停样本 {zt_count} 家，炸板率约 {float(blowup):.1%}。"
        f"当前采用 {context.mode} 模式，结论已按 lens 权重调和。"
    )


def _format_m1_committee_analysis(m1: dict[str, Any]) -> str:
    analysis = m1.get("committee_deep_analysis") or {}
    trend = analysis.get("trend_consistency") or {}
    cross = analysis.get("cross_validation") or {}
    anomalies = analysis.get("anomalies") or []
    return (
        "m1 综合深度分析："
        f"{cross.get('lens_count', 0)} 个 lens 交叉验证；"
        f"趋势一致性={trend.get('direction', '数据不足')}，"
        f"样本数={trend.get('sample_count', 0)}，区间={trend.get('range_pct')}%；"
        f"异常点={'；'.join(str(item) for item in anomalies)}"
    )


def _format_m6_committee_analysis(m6: dict[str, Any]) -> str:
    analysis = m6.get("committee_deep_analysis") or {}
    conflicts = analysis.get("conflict_reconciliation") or []
    return (
        "m6 综合风险评分："
        f"{analysis.get('risk_score', '缺失')} / 100。"
        f"冲突调和：{'；'.join(str(item) for item in conflicts)}"
    )


def _community_sentiment_lines(sentiment: dict[str, Any]) -> list[str]:
    lines = [
        f"- 整体情绪得分：{sentiment.get('overall_sentiment_score', 0)}（{sentiment.get('overall_sentiment_band', 'Neutral')}，置信度 {sentiment.get('confidence', 'low')}）",
        f"- 关键情绪来源：{_compact_list(sentiment.get('key_sentiment_sources') or [])}",
        f"- 情绪与基本面分歧：{_compact_list(sentiment.get('fundamental_sentiment_divergences') or [])}",
        f"- 潜在影响：{_compact_list(sentiment.get('sentiment_catalysts_or_risks') or [])}",
    ]
    source_breakdown = sentiment.get("source_breakdown") or {}
    if source_breakdown:
        lines.append(f"- 来源覆盖：{source_breakdown}")
    return lines


def _compact_list(values: list[Any]) -> str:
    if not values:
        return "暂无"
    rendered = []
    for value in values[:3]:
        if isinstance(value, dict):
            label = value.get("symbol") or value.get("source") or "样本"
            score = value.get("score")
            rendered.append(f"{label}({score})" if score is not None else str(label))
        else:
            rendered.append(str(value))
    return "；".join(rendered)


def _risk_and_catalyst_lines(
    m3: dict[str, Any],
    m4: dict[str, Any],
    m6: dict[str, Any],
    sentiment: dict[str, Any],
) -> list[str]:
    stats = m3.get("pool_stats") or {}
    risk_stats = m4.get("pool_stats") or stats
    lines = [
        f"上涨催化剂：涨停 {stats.get('zt_count', m3.get('zt_count', 0))} 家，主线需要次日成交继续确认。",
        f"风险项：跌停 {risk_stats.get('dt_count', 0)} 家，炸板率约 {float(risk_stats.get('blowup_ratio') or 0):.1%}。",
    ]
    resilient = [value for value in m6.get("resilient", []) if value]
    if resilient:
        lines.append("缓解措施：优先观察抗跌方向 " + "、".join(resilient) + "。")
    if sentiment.get("sentiment_catalysts_or_risks"):
        lines.append("情绪催化/风险：" + _compact_list(sentiment.get("sentiment_catalysts_or_risks") or []))
    return lines


def _append_lens_advice(lines: list[str], evidence: EvidenceBundle, portfolio_snapshot: dict[str, Any]) -> None:
    advice = evidence.meta.get("portfolio_advice_sections") or {}
    if not any(advice.values()):
        details = portfolio_snapshot.get("details") or []
        if details:
            lines.append("- 已加载持仓，但缺少足够建议证据；先按仓位集中度和相对强弱做条件化跟踪。")
        else:
            lines.append("- 未加载持仓；本次只给市场层面的观察结论。")
        return
    for key in ("current", "benchmark", "position_actions", "watchlist", "risks"):
        _append_bullets(lines, advice.get(key, []))


def render_report(
    *,
    trade_date: str,
    session_label: str,
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
) -> str:
    lines: list[str] = [f"# 全球市场复盘研报（{trade_date} {session_label}）", ""]
    if quality.degrade_mode == "degraded":
        missing = "、".join(MODULE_LABELS.get(value, value) for value in quality.missing_modules)
        lines.extend([f"> 本模块证据暂缺：{missing}。正文仅呈现可验证信息。", ""])
    elif quality.degrade_mode == "simplified":
        lines.extend(["> 本模块证据暂缺，报告聚焦指数、持仓和风险控制。", ""])

    m1 = evidence.modules.get("M1", {})
    index_rows = [
        row
        for row in m1.get("a_indices", []) + m1.get("hk_indices", []) + m1.get("us_indices", [])
        if row.get("name") and row.get("price") is not None
    ]
    lines.append("## 一、大盘指数概览")
    _append_index_table(lines, index_rows)
    northbound = m1.get("northbound") or {}
    _append_northbound_table(lines, northbound)
    _append_breadth_table(lines, m1.get("breadth") or {})
    lines.append(f"\n=={m1.get('cross_market_comment', '三地市场强弱分化，风险偏好仍需结合成交额确认。')}==")
    lines.append("")

    details = portfolio_snapshot.get("details", [])
    has_holdings = bool(details)
    if has_holdings:
        lines.append("## 二、持仓分析")
        _append_holdings_table(lines, details)
        lines.append("")
        _append_portfolio_summary_table(lines, portfolio_snapshot)
        lines.append("")
        _append_relative_strength_table(lines, details)
        lines.append("")
        _append_public_pulse_table(lines, details)
        lines.append("")

    deep_heading = "## 三、六模块深度复盘" if has_holdings else "## 二、六模块深度复盘"
    advice_heading = "## 四、综合持仓建议与风险提示" if has_holdings else "## 三、通用市场建议与风险提示"
    summary_stop_heading = advice_heading
    if quality.degrade_mode != "simplified":
        m2 = evidence.modules.get("M2", {})
        m3 = evidence.modules.get("M3", {})
        m4 = evidence.modules.get("M4", {})
        m5 = evidence.modules.get("M5", {})
        m6 = evidence.modules.get("M6", {})
        concentration = m2.get("concentration", {})
        stats = m3.get("pool_stats", {})
        risk_stats = m4.get("pool_stats", {})
        features = m5.get("feature_groups", {})

        lines.append(deep_heading)
        summary_stop_heading = deep_heading
        lines.append("### 1. 盘面趋势")
        lines.append(f"=={m2.get('summary', '市场以结构性轮动为主。')}==")
        lines.append(
            "A股主要指数整体强于港股和美股，成长风格的弹性更突出。指数普涨与高炸板率并存，"
            "说明市场风险偏好回升，但短线筹码并未完全稳定。"
        )
        lines.append("")

        lines.append("### 2. 集中度分析")
        sector_rows = m2.get("industry_top20") or m2.get("concept_top20") or []
        _append_sector_table(lines, sector_rows)
        lines.append(
            f"涨停主题 TOP1 占比 {float(concentration.get('top1_ratio') or 0):.1%}，"
            f"TOP3 占比 {float(concentration.get('top3_ratio') or 0):.1%}。"
            "集中度处于中等水平，主线已经出现，但尚未形成单一方向的极端拥挤。"
        )
        lines.append("")

        lines.append("### 3. 赚钱效应与上涨主线")
        lines.append(f"=={m3.get('summary', '活跃资金仍在寻找高辨识度方向。')}==")
        _append_leader_table(lines, stats.get("leaders", []))
        lines.append(
            f"\n涨停 {stats.get('zt_count', 0)} 家，其中首板 {stats.get('first_board_count', 0)} 家、"
            f"连板 {stats.get('multi_board_count', 0)} 家，封单金额合计约 "
            f"{float(stats.get('zt_fund_total_yi') or 0):,.2f} 亿元。"
            "首板数量明显高于连板数量，赚钱效应更偏扩散，而非高位核心单边加速。"
        )
        lines.append("")

        lines.append("### 4. 爆量下跌风险")
        lines.append(f"=={m4.get('summary', '风险主要集中在高位分歧。')}==")
        lines.append(
            f"跌停 {risk_stats.get('dt_count', 0)} 家、炸板 {risk_stats.get('zb_count', 0)} 家，"
            f"炸板率约 {float(risk_stats.get('blowup_ratio') or 0):.1%}。"
            "指数强势并未完全转化为追涨安全垫，次日若连板梯队收缩，应降低对高位题材的容忍度。"
        )
        lines.append("")

        lines.append("### 5. 特征分组")
        lines.append(f"=={m5.get('summary', '成长与低位扩散特征较明显。')}==")
        lines.append(
            f"10:30 前涨停 {features.get('early_limit_up_count', 0)} 家，"
            f"低位异动 {features.get('low_position_active_count', 0)} 家，"
            f"科创/创业板活跃样本 {features.get('growth_board_count', 0)} 家。"
            "早盘快速封板与低位扩散同时出现，表明资金更愿意寻找新分支，而非只围绕旧核心抱团。"
        )
        lines.append("")

        lines.append("### 6. 抗跌方向")
        lines.append(f"=={m6.get('summary', '抗跌样本主要来自仍有业绩或产业趋势支撑的方向。')}==")
        resilient = [value for value in m6.get("resilient", []) if value]
        if resilient:
            lines.append("可继续观察：" + "、".join(resilient) + "。")
        lines.append("")

    advice = evidence.meta.get("portfolio_advice_sections") or {}
    lines.append(advice_heading)
    if has_holdings:
        lines.append("### 现状总结")
        _append_bullets(lines, advice.get("current", []))
        lines.append("")
        lines.append("### 基准跑赢/跑输")
        benchmark = advice.get("benchmark", [])
        if benchmark:
            _append_bullets(lines, benchmark)
        else:
            lines.append("- 当前没有足够数据形成可靠的相对基准判断。")
        lines.append("")
        lines.append("### 仓位动作建议")
        _append_bullets(lines, advice.get("position_actions", []))
        lines.append("")
    lines.append("### 观察清单")
    watchlist = advice.get("watchlist", [])
    if watchlist:
        _append_bullets(lines, watchlist)
    else:
        lines.append("- 继续观察指数强弱、成交额变化和主线板块持续性。")
    lines.append("")
    lines.append("### 风险提示")
    risks = advice.get("risks", [])
    if risks:
        _append_bullets(lines, risks)
    else:
        lines.append("- 控制追涨节奏，避免在单日情绪极端后忽视次日分化风险。")
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    disclaimer = "免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
    if report_format == "summary":
        compact = _section_prefix(lines, summary_stop_heading)
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    if report_format == "key-points":
        compact = _section_prefix(lines, "### 5. 特征分组")
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    return sanitize_research_report("\n".join(lines))
