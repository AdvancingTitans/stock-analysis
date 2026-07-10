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

EXPERT_REPORT_BLUEPRINTS = {
    "buffett": (
        {"title": "护城河与商业质量", "domains": ("M2", "M5", "portfolio"), "kind": "quality"},
        {"title": "估值安全边际", "domains": ("M2", "M4", "portfolio"), "kind": "margin"},
        {"title": "永久性本金损失风险", "domains": ("M4", "M6", "portfolio"), "kind": "downside"},
        {"title": "长期持有条件", "domains": ("M5", "M6", "portfolio"), "kind": "watchlist"},
    ),
    "munger": (
        {"title": "最可能失败的路径", "domains": ("M4", "M6", "portfolio"), "kind": "downside"},
        {"title": "激励、治理与复杂性", "domains": ("M5", "portfolio"), "kind": "quality"},
        {"title": "机会成本与反方证据", "domains": ("M2", "M4", "M6"), "kind": "margin"},
        {"title": "不做清单", "domains": ("M4", "M6", "portfolio"), "kind": "discipline"},
    ),
    "graham": (
        {"title": "下行保护", "domains": ("M4", "M6", "portfolio"), "kind": "downside"},
        {"title": "资产与盈利稳定性线索", "domains": ("M2", "M5", "portfolio"), "kind": "quality"},
        {"title": "保守估值纪律", "domains": ("M2", "M4"), "kind": "margin"},
        {"title": "买入或等待条件", "domains": ("M1", "M4", "M6"), "kind": "watchlist"},
    ),
    "klarman": (
        {"title": "折价来源与市场厌恶", "domains": ("M2", "M4"), "kind": "margin"},
        {"title": "催化剂可靠性", "domains": ("M3", "M6"), "kind": "catalyst"},
        {"title": "最坏情景与流动性", "domains": ("M1", "M4", "portfolio"), "kind": "downside"},
        {"title": "现金选择权", "domains": ("M4", "M6", "portfolio"), "kind": "discipline"},
    ),
    "lynch": (
        {"title": "公司类型与增长故事", "domains": ("M2", "M5", "portfolio"), "kind": "growth"},
        {"title": "盈利兑现线索", "domains": ("M3", "M5", "portfolio"), "kind": "quality"},
        {"title": "增长与估值匹配", "domains": ("M2", "M4"), "kind": "margin"},
        {"title": "故事破裂风险", "domains": ("M4", "M6"), "kind": "downside"},
    ),
    "o_neil": (
        {"title": "市场方向", "domains": ("M1", "M3", "M4"), "kind": "trend"},
        {"title": "强势行业与龙头", "domains": ("M2", "M3"), "kind": "leaders"},
        {"title": "量价确认", "domains": ("M1", "M3"), "kind": "trend"},
        {"title": "突破失败与止损条件", "domains": ("M4", "M6"), "kind": "discipline"},
    ),
    "wood": (
        {"title": "颠覆式创新假设", "domains": ("M2", "M5"), "kind": "growth"},
        {"title": "渗透率与平台扩张线索", "domains": ("M2", "M3", "M5"), "kind": "catalyst"},
        {"title": "融资与估值波动", "domains": ("M4", "M6"), "kind": "downside"},
        {"title": "关键里程碑", "domains": ("M3", "M6"), "kind": "watchlist"},
    ),
    "dalio": (
        {"title": "宏观周期与流动性", "domains": ("M1", "M2"), "kind": "macro"},
        {"title": "相关性与组合暴露", "domains": ("M1", "M5", "portfolio"), "kind": "portfolio"},
        {"title": "三情景推演", "domains": ("M1", "M2", "M4", "M6"), "kind": "scenarios"},
        {"title": "风险平衡动作", "domains": ("M4", "M6", "portfolio"), "kind": "discipline"},
    ),
    "soros": (
        {"title": "共识与预期差", "domains": ("M1", "M2", "M3"), "kind": "reflexivity"},
        {"title": "价格反馈链", "domains": ("M1", "M3", "M4"), "kind": "trend"},
        {"title": "政策或资金拐点", "domains": ("M1", "M2"), "kind": "macro"},
        {"title": "证伪信号", "domains": ("M4", "M6"), "kind": "discipline"},
    ),
    "livermore": (
        {"title": "趋势是否确认", "domains": ("M1", "M3"), "kind": "trend"},
        {"title": "关键点与成交确认", "domains": ("M1", "M3", "M4"), "kind": "leaders"},
        {"title": "亏损控制", "domains": ("M4", "M6"), "kind": "discipline"},
        {"title": "等待还是行动", "domains": ("M3", "M4", "M6"), "kind": "watchlist"},
    ),
    "minervini": (
        {"title": "趋势模板", "domains": ("M1", "M2", "M3"), "kind": "trend"},
        {"title": "相对强度与低风险买点", "domains": ("M2", "M3"), "kind": "leaders"},
        {"title": "风险收益比", "domains": ("M4", "M6"), "kind": "margin"},
        {"title": "止损宽度", "domains": ("M4", "M6"), "kind": "discipline"},
    ),
    "simons": (
        {"title": "信号定义与数据口径", "domains": ("M1", "M2", "M3", "M4"), "kind": "quant"},
        {"title": "样本稳定性", "domains": ("M2", "M3", "M4"), "kind": "quant"},
        {"title": "拥挤度与成本", "domains": ("M2", "M4", "M5"), "kind": "downside"},
        {"title": "概率化结论", "domains": ("M1", "M3", "M4", "M6"), "kind": "scenarios"},
    ),
    "duan_yongping": (
        {"title": "商业本质与用户价值", "domains": ("M2", "M5", "portfolio"), "kind": "quality"},
        {"title": "企业文化与能力圈边界", "domains": ("M5", "portfolio"), "kind": "quality"},
        {"title": "价格是否合理", "domains": ("M2", "M4", "portfolio"), "kind": "margin"},
        {"title": "睡得着的持有条件", "domains": ("M4", "M6", "portfolio"), "kind": "watchlist"},
    ),
    "zhang_kun": (
        {"title": "高质量商业模式", "domains": ("M2", "M5", "portfolio"), "kind": "quality"},
        {"title": "长期现金创造代理线索", "domains": ("M2", "M5", "portfolio"), "kind": "quality"},
        {"title": "估值与机会成本", "domains": ("M2", "M4", "portfolio"), "kind": "margin"},
        {"title": "组合权重与集中度", "domains": ("M5", "portfolio"), "kind": "portfolio"},
    ),
    "feng_liu": (
        {"title": "市场为何如此定价", "domains": ("M1", "M2", "M4"), "kind": "reflexivity"},
        {"title": "认知差与边际变化", "domains": ("M2", "M3", "M5"), "kind": "catalyst"},
        {"title": "赔率与反方证据", "domains": ("M4", "M6"), "kind": "margin"},
        {"title": "触发条件", "domains": ("M3", "M4", "M6"), "kind": "watchlist"},
    ),
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


def _fmt_activity(value: Any, volume: Any = None) -> str:
    if value is not None and float(value) > 0:
        return _fmt_amount_yi(value)
    if volume is not None and float(volume) > 0:
        return f"{_fmt_quantity(volume)}（成交量）"
    return "暂缺"


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
            "| 大盘 | 收盘 | 涨跌 | 涨跌幅 | 成交额/量 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        turnover = _fmt_activity(row.get("turnover"), row.get("volume"))
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
    if lines and lines[-1] != "":
        lines.append("")
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


def _append_board_summary_tables(lines: list[str], m2: dict[str, Any], limit: int = 10) -> None:
    groups = (
        ("行业涨幅榜", m2.get("industry_top20") or []),
        ("概念涨幅榜", m2.get("concept_top20") or []),
    )
    visible = [(title, rows) for title, rows in groups if any(row.get("name") for row in rows)]
    if not visible:
        lines.append("> 行业/概念板块榜暂缺；以下集中度来自涨跌停主题统计。")
        return
    taxonomy = m2.get("taxonomy") or {}
    if taxonomy.get("note"):
        lines.append(f"> 板块口径：{taxonomy['note']}")
    for title, rows in visible:
        lines.extend([f"**{title}**", ""])
        _append_sector_table(lines, rows, limit=limit)
        lines.append("")


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
            "| 代码 | 新闻倾向 | 最新高信号事件 | 证据 |",
            "|---|---|---|---|",
        ]
    )
    for detail in visible:
        pulse = detail.get("public_pulse") or {}
        event = str(pulse.get("event_title") or "").replace("|", "｜")
        url = str(pulse.get("evidence_url") or "")
        evidence = f"[原文]({url})" if url else ""
        lines.append(
            f"| {detail.get('symbol') or ''} | {pulse.get('news_tone') or ''} | "
            f"{event} | {evidence} |"
        )


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


def _append_bullets_or_default(lines: list[str], values: list[str], default: str) -> None:
    rendered = [value for value in values if value]
    if rendered:
        _append_bullets(lines, rendered)
    else:
        lines.append(f"- {default}")


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
        context, fallback = _build_lens_context_with_fallback(
            evidence,
            lens=lens,
            lenses=lenses,
            mode=mode,
            portfolio_snapshot=portfolio_snapshot,
        )
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
    metadata["module_diagnostics"] = evidence.meta.get("module_diagnostics", {})
    evidence.meta["report_metadata"] = metadata
    return ReportResult(markdown=markdown, metadata=metadata)


def _build_lens_context_with_fallback(
    evidence: EvidenceBundle,
    *,
    lens: str | None,
    lenses: tuple[str, ...] | list[str] | None,
    mode: str | None,
    portfolio_snapshot: dict[str, Any] | None = None,
) -> tuple[LensContext, dict[str, Any] | None]:
    public_pulses = _public_pulses(evidence, portfolio_snapshot)
    try:
        return LensEngine(lens=lens, lenses=lenses, mode=mode).build_context(
            evidence,
            public_pulses=public_pulses or None,
        ), None
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


def _portfolio_public_pulses(portfolio_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    details = (portfolio_snapshot or {}).get("details") or []
    return [detail["public_pulse"] for detail in details if isinstance(detail.get("public_pulse"), dict)]


def _public_pulses(evidence: EvidenceBundle, portfolio_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    meta_pulses = (evidence.meta or {}).get("portfolio_public_pulse") or []
    if meta_pulses:
        return [pulse for pulse in meta_pulses if isinstance(pulse, dict)]
    return _portfolio_public_pulses(portfolio_snapshot)


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
        lines.append(f"**使用专家**：{' + '.join(lens_names)}  ")
    lines.append(f"**数据截止**：{_display_date(evidence.meta.get('trade_date') or trade_date)}")
    if fallback:
        lines.append(f"**调整说明**：投委会框架暂未完成，已改用{fallback['fallback_lens']}专家框架。")
    lines.append("")
    if quality.degrade_mode == "degraded" and quality.missing_modules:
        missing = "、".join(MODULE_LABELS.get(value, value) for value in quality.missing_modules)
        lines.extend([f"> 本模块证据暂缺：{missing}。正文仅呈现可验证信息。", ""])
    elif quality.degrade_mode == "degraded":
        lines.extend(["> 部分证据字段不完整，正文仅呈现可验证信息。", ""])
    elif quality.degrade_mode == "simplified":
        lines.extend(["> 本模块证据暂缺，报告聚焦指数、持仓和风险控制。", ""])

    m1 = modules.get("M1", {})
    m2 = modules.get("M2", {})
    m3 = modules.get("M3", {})
    m4 = modules.get("M4", {})
    m5 = modules.get("M5", {})
    m6 = modules.get("M6", {})

    if lens_context.mode == "committee":
        return _render_committee_review_report(
            header_lines=lines,
            evidence=evidence,
            quality=quality,
            portfolio_snapshot=portfolio_snapshot,
            report_format=report_format,
            m1=m1,
            m2=m2,
            m3=m3,
            m4=m4,
            m5=m5,
            m6=m6,
            lens_context=lens_context,
        )
    if lens_context.mode == "single" and report_format == "full":
        return _render_single_lens_review_report(
            header_lines=lines,
            evidence=evidence,
            quality=quality,
            portfolio_snapshot=portfolio_snapshot,
            m1=m1,
            m2=m2,
            m3=m3,
            m4=m4,
            m5=m5,
            m6=m6,
            lens_context=lens_context,
        )

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
    lines.append("估值判断采用 lens 调整后的证据权重：先看数据质量，再区分短期价格弹性、长期经营质量和组合暴露。")
    sector_rows = m2.get("industry_top20") or m2.get("concept_top20") or []
    _append_sector_table(lines, sector_rows)
    lines.append("")

    risk_heading = "## 6. 风险，催化剂与缓解措施"
    lines.append(risk_heading)
    lines.append(f"=={m4.get('summary', '风险主要集中在高位分歧。')}==")
    if lens_context.mode == "committee":
        lines.append(_format_m6_committee_analysis(m6))
    _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, {}))
    lines.append("")

    advice_heading = "## 7. 投资建议与仓位指导"
    lines.append(advice_heading)
    lines.append("以下为多视角调和后的条件化结论，不作为无条件买卖指令。")
    _append_lens_advice(lines, evidence, portfolio_snapshot)
    lines.append("")

    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    disclaimer = "免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
    if report_format == "summary":
        compact = _section_prefix(lines, "## 4. 财务深度分析")
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    if report_format == "key-points":
        stop_heading = "## 6. 风险，催化剂与缓解措施"
        compact = _section_prefix(lines, stop_heading)
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    return sanitize_research_report("\n".join(lines))


def _render_single_lens_review_report(
    *,
    header_lines: list[str],
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m5: dict[str, Any],
    m6: dict[str, Any],
    lens_context: LensContext,
) -> str:
    lines = list(header_lines)
    notice = _missing_module_notice(quality)
    if notice:
        lines.extend([notice, ""])
    lens_name = _lens_names(lens_context)[0] if _lens_names(lens_context) else "专家"
    lines.append("## 执行摘要")
    lines.append(_executive_summary(m1, m3, m4, m6, lens_context, quality))
    lines.append(f"本报告服从{lens_name}框架：保留原盘后复盘骨架，仅将中间深度复盘区替换为该专家的证据链顺序。")
    lines.append("")

    lines.append("## 一、大盘指数概览")
    _append_index_table(lines, _index_rows(m1))
    _append_northbound_table(lines, m1.get("northbound") or {})
    _append_breadth_table(lines, m1.get("breadth") or {})
    lines.append("")
    lines.append(f"=={m1.get('cross_market_comment', '三地市场强弱分化，风险偏好仍需结合成交额确认。')}==")
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

    deep_heading = f"## 三、{lens_name}视角深度复盘" if has_holdings else f"## 二、{lens_name}视角深度复盘"
    advice_heading = f"## 四、{lens_name}持仓建议与风险提示" if has_holdings else "## 三、通用市场建议与风险提示"
    lines.append(deep_heading)
    _append_financial_evidence_coverage(lines, evidence.meta.get("stock_financials") or {})
    _append_expert_review_sections(
        lines,
        lens_context=lens_context,
        m1=m1,
        m2=m2,
        m3=m3,
        m4=m4,
        m5=m5,
        m6=m6,
        portfolio_snapshot=portfolio_snapshot,
    )
    _append_market_fact_sections(lines, evidence.meta.get("facts") or {})
    lines.append("")

    advice = evidence.meta.get("portfolio_advice_sections") or {}
    lines.append(advice_heading)
    lines.append("### 现状总结")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("current", []), "已加载持仓；现状以当日浮盈亏、集中度和相对基准表现为准。")
    else:
        lines.append(f"- {_market_trend_narrative(m1, m3, m4)}")
    lines.append("")
    lines.append("### 基准跑赢/跑输")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("benchmark", []), "当前没有足够数据形成可靠的相对基准判断。")
    else:
        lines.append("- 未加载持仓；以主要指数、市场广度和主线持续性作为通用市场基准。")
    lines.append("")
    lines.append("### 条件化仓位动作")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("position_actions", []), "若持仓继续跑输对应基准且成交未改善，优先降低新增暴露；若放量修复，再评估分批调整。")
    else:
        lines.append("- 若指数强弱、成交额和主线持续性同向改善，再考虑提高进攻性；若主线收缩或炸板率上升，维持防守仓位。")
    lines.append("")
    lines.append("### 下一交易日观察清单")
    _append_bullets_or_default(
        lines,
        advice.get("watchlist", []),
        "继续观察指数强弱、成交额变化和主线板块持续性是否互相确认。",
    )
    lines.append("")
    lines.append("### 风险提示")
    risks = advice.get("risks", [])
    if risks:
        _append_bullets(lines, risks)
    else:
        lines.append("- 控制追涨节奏，避免在单日情绪极端后忽视次日分化风险。")
    _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, {}))
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")
    return sanitize_research_report("\n".join(lines))


def _append_expert_review_sections(
    lines: list[str],
    *,
    lens_context: LensContext,
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m5: dict[str, Any],
    m6: dict[str, Any],
    portfolio_snapshot: dict[str, Any],
) -> None:
    lens_id = lens_context.lenses[0] if lens_context.lenses else "buffett"
    sections = EXPERT_REPORT_BLUEPRINTS.get(lens_id) or EXPERT_REPORT_BLUEPRINTS["buffett"]
    payloads = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5, "M6": m6}
    for section in sections:
        lines.append(f"### {section['title']}")
        domains = tuple(section.get("domains") or ())
        if not _expert_domains_available(domains, payloads, portfolio_snapshot):
            lines.append("==本节关键证据暂缺，只保留该专家框架下的观察清单，不外推结论。==")
        _append_expert_section_body(
            lines,
            kind=str(section.get("kind") or ""),
            m1=m1,
            m2=m2,
            m3=m3,
            m4=m4,
            m5=m5,
            m6=m6,
            portfolio_snapshot=portfolio_snapshot,
        )
        lines.append("")


def _append_financial_evidence_coverage(lines: list[str], stock_financials: dict[str, Any]) -> None:
    if not stock_financials:
        return
    lines.append("### 财务证据覆盖")
    rows = []
    missing = []
    disclosure_gap = False
    for symbol, snapshot in stock_financials.items():
        periods = (snapshot or {}).get("periods") or []
        if periods:
            latest = periods[0]
            rows.append((str(symbol), latest))
        gaps = [str(item) for item in ((snapshot or {}).get("gaps") or []) if item]
        if gaps:
            missing.append(f"{symbol}: {'、'.join(gaps)}")
        if not ((snapshot or {}).get("forecasts") or {}).get("available") and not (
            (snapshot or {}).get("earnings_flash") or {}
        ).get("available"):
            disclosure_gap = True
    if rows:
        lines.extend(
            [
                "| 代码 | 期间 | ROE | 毛利率 | 资产负债率 | 经营现金流 | 自由现金流-lite |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for symbol, row in rows:
            lines.append(
                "| {symbol} | {period_label} | {roe} | {gross_margin} | {debt} | {ocf} | {fcf} |".format(
                    symbol=symbol,
                    period_label=row.get("period_label") or row.get("report_date") or "",
                    roe=_fmt_pct(row.get("roe_weighted")),
                    gross_margin=_fmt_pct(row.get("gross_margin")),
                    debt=_fmt_pct(row.get("debt_asset_ratio")),
                    ocf=_fmt_amount_yi(row.get("operating_cash_flow")),
                    fcf=_fmt_amount_yi(row.get("free_cash_flow_lite")),
                )
            )
    else:
        lines.append("==结构化财务指标暂未取得；专家框架只保留观察清单，不补零、不外推。==")
    if missing:
        _append_bullets(lines, missing)
    if disclosure_gap:
        lines.append("- 业绩预告/快报仅在公司披露时存在；当前未取得已披露记录时，不把预告或快报写成确定证据。")
    lines.append("")


def _expert_domains_available(
    domains: tuple[str, ...],
    payloads: dict[str, dict[str, Any]],
    portfolio_snapshot: dict[str, Any],
) -> bool:
    for domain in domains:
        if domain == "portfolio":
            if portfolio_snapshot.get("details"):
                return True
            continue
        payload = payloads.get(domain) or {}
        if payload and payload.get("available", True):
            return True
    return False


def _append_expert_section_body(
    lines: list[str],
    *,
    kind: str,
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m5: dict[str, Any],
    m6: dict[str, Any],
    portfolio_snapshot: dict[str, Any],
) -> None:
    if kind == "quality":
        lines.append("- 市场级证据无法替代公司尽调；本节只用行业强弱、风格暴露和已加载持仓做质量线索。")
        lines.append(f"- 行业/主题线索：{m2.get('summary', '板块证据暂缺，无法判断行业质量是否得到市场确认。')}")
        lines.append(f"- 风格线索：{m5.get('summary', '风格证据暂缺，暂不判断质量溢价。')}")
        _append_sector_table(lines, m2.get("industry_top20") or m2.get("concept_top20") or [], limit=5)
        return
    if kind == "margin":
        lines.append("- 市场级安全边际用风险释放、板块热度和资金承接做代理，不把单日行情外推为单一公司的估值结论。")
        lines.append(f"- 结构性热度：{m2.get('summary', '板块热度证据暂缺。')}")
        lines.append(f"- 风险折价：{m4.get('summary', '下跌风险证据暂缺。')}")
        return
    if kind == "downside":
        stats = (m4.get("pool_stats") or m3.get("pool_stats") or {})
        lines.append(f"- {m4.get('summary', '下跌风险证据暂缺，先按仓位纪律处理。')}")
        lines.append(
            f"- 跌停 {stats.get('dt_count', 0)} 家、炸板 {stats.get('zb_count', 0)} 家，"
            f"炸板率约 {float(stats.get('blowup_ratio') or 0):.1%}。"
        )
        return
    if kind in {"trend", "leaders"}:
        lines.append(f"- {_market_trend_narrative(m1, m3, m4)}")
        stats = m3.get("pool_stats") or {}
        leaders = stats.get("leaders", [])
        if leaders:
            _append_leader_table(lines, leaders)
        lines.append(f"- {m3.get('summary', '赚钱效应证据暂缺，等待价格确认。')}")
        return
    if kind in {"growth", "catalyst", "reflexivity"}:
        lines.append(f"- 主线或预期差：{m2.get('summary', '板块主线证据暂缺。')}")
        lines.append(f"- 催化强度：{m3.get('summary', '涨停和活跃资金证据暂缺。')}")
        lines.append(f"- 证伪压力：{m4.get('summary', '风险证据暂缺。')}")
        return
    if kind == "macro":
        _append_index_table(lines, _index_rows(m1))
        _append_northbound_table(lines, m1.get("northbound") or {})
        _append_breadth_table(lines, m1.get("breadth") or {})
        lines.append(f"- 板块扩散：{m2.get('summary', '板块扩散证据暂缺。')}")
        return
    if kind == "portfolio":
        if portfolio_snapshot.get("details"):
            _append_portfolio_summary_table(lines, portfolio_snapshot)
        else:
            lines.append("- 未加载持仓；组合集中度、相关性和机会成本只能作为下一步输入要求。")
        lines.append(f"- 风格暴露：{m5.get('summary', '风格暴露证据暂缺。')}")
        return
    if kind == "quant":
        lines.extend(["| 信号域 | 可用性 | 摘要 |", "|---|---|---|"])
        for module, payload, label in (
            ("M1", m1, "指数/宽度"),
            ("M2", m2, "板块/资金"),
            ("M3", m3, "赚钱效应"),
            ("M4", m4, "风险"),
            ("M5", m5, "风格"),
            ("M6", m6, "抗跌"),
        ):
            available = "可用" if payload.get("available", True) else "暂缺"
            lines.append(f"| {module} {label} | {available} | {payload.get('summary') or payload.get('cross_market_comment') or ''} |")
        return
    if kind == "scenarios":
        lines.append(f"- 基准情景：{_market_trend_narrative(m1, m3, m4)}")
        lines.append(f"- 乐观情景：{m3.get('summary', '需要主线、成交和市场宽度继续改善。')}")
        lines.append(f"- 悲观情景：{m4.get('summary', '若炸板率和跌停数量抬升，风险偏好会快速降级。')}")
        return
    if kind == "discipline":
        _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, {}))
        lines.append("- 不满足确认条件时，等待本身就是有效动作。")
        return
    if kind == "watchlist":
        lines.append(f"- 持有条件一：{m6.get('summary', '抗跌方向尚不清晰，先观察承接是否恢复。')}")
        lines.append(f"- 持有条件二：{m3.get('summary', '赚钱效应仍需次日成交和连板梯队确认。')}")
        lines.append(f"- 失效条件：{m4.get('summary', '若风险池继续扩大，应降低高波动方向暴露。')}")
        if portfolio_snapshot.get("details"):
            lines.append("- 组合持仓仍需逐项核对买入理由、仓位集中度和相对基准表现。")
        else:
            lines.append("- 未加载持仓；本节只给市场观察条件，不判断任何单一标的能否长期持有。")
        return
    lines.append("- 本节仅使用当前已加载的市场证据做代理观察，保留为下一交易日确认项。")


def _append_market_fact_sections(lines: list[str], facts: dict[str, Any]) -> None:
    if not facts:
        return
    _append_hotspot_section(lines, facts.get("hotspots_24h") or [])
    _append_board_rankings_section(lines, facts.get("board_rankings") or {})
    _append_money_flow_section(lines, facts.get("money_flow") or {})
    _append_lhb_section(lines, facts.get("lhb_aftermarket") or {})
    _append_announcements_section(lines, facts.get("announcements") or {})


def _append_hotspot_section(lines: list[str], hotspots: list[dict[str, Any]]) -> None:
    rows = [row for row in hotspots if row.get("topic")][:5]
    if not rows:
        return
    lines.extend(
        [
            "### 24小时热点追踪",
            "| 主题 | 触发线索 | 涨停样本 | 代表个股 | 新闻样本 |",
            "|---|---|---:|---|---:|",
        ]
    )
    for row in rows:
        leaders = "、".join(str(value) for value in (row.get("leaders") or [])[:3])
        lines.append(
            f"| {row.get('topic')} | {row.get('summary') or ''} | "
            f"{int(row.get('limit_up_count') or 0)} | {leaders} | {int(row.get('news_count') or 0)} |"
        )
    lines.append("")


def _append_board_rankings_section(lines: list[str], rankings: dict[str, Any]) -> None:
    groups = (
        ("行业涨幅前五", rankings.get("industry_top5") or []),
        ("行业跌幅前五", rankings.get("industry_bottom5") or []),
        ("概念涨幅前五", rankings.get("concept_top5") or []),
        ("概念跌幅前五", rankings.get("concept_bottom5") or []),
    )
    visible = [(title, rows) for title, rows in groups if rows]
    if not visible:
        return
    lines.append("### 行业板块强弱前五")
    for title, rows in visible:
        lines.extend([f"**{title}**", "", "| 板块 | 涨跌幅 | 领涨/领跌股 | 个股涨跌幅 |", "|---|---:|---|---:|"])
        for row in rows[:5]:
            lines.append(
                f"| {row.get('name') or ''} | {_fmt_pct(row.get('change_pct'))} | "
                f"{row.get('leader') or ''} | {_fmt_pct(row.get('leader_change_pct'))} |"
            )
        lines.append("")


def _append_money_flow_section(lines: list[str], flow: dict[str, Any]) -> None:
    if not flow:
        return
    has_flow_rows = any(flow.get(key) for key in ("concept_in", "concept_out", "sector_in", "sector_out"))
    if flow.get("market_main_net") is None and not has_flow_rows:
        return
    lines.append("### 主力与行业资金流向")
    if flow.get("market_main_net") is not None:
        lines.extend(["| 资金项 | 金额 |", "|---|---:|", f"| 全市场主力净流入 | {_fmt_amount_yi(flow.get('market_main_net'))} |"])
    scope_note = str(flow.get("scope_note") or "")
    if scope_note:
        lines.append(f"> {scope_note}")
    sector_note = str(flow.get("sector_note") or "")
    if sector_note and sector_note != scope_note:
        lines.append(f"> {sector_note}")
    for title, key in (
        ("概念资金净流入前三", "concept_in"),
        ("概念资金净流出前三", "concept_out"),
        ("行业资金净流入前三", "sector_in"),
        ("行业资金净流出前三", "sector_out"),
    ):
        rows = flow.get(key) or []
        if not rows:
            continue
        lines.extend(["", f"**{title}**", "", "| 板块 | 净额 | 领涨/领跌股 |", "|---|---:|---|"])
        for row in rows[:3]:
            lines.append(f"| {row.get('name') or ''} | {_fmt_plain_number(row.get('net'))} | {row.get('leader') or ''} |")
    lines.append("")


def _append_lhb_section(lines: list[str], lhb: dict[str, Any]) -> None:
    rows = lhb.get("rows") or []
    lines.extend(
        [
            "### 盘后龙虎榜",
            "| 股票 | 收盘价 | 涨跌幅 | 买入金额(万) | 卖出金额(万) | 净买入(万) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    if not lhb.get("available") or not rows:
        lines.append("| 当日龙虎榜暂未取得可核验明细 |  |  |  |  |  |")
        lines.append("")
        return
    for row in rows[:5]:
        lines.append(
            f"| {row.get('name') or row.get('symbol') or ''} | {_fmt_price(row.get('close_price'))} | "
            f"{_fmt_pct(row.get('change_pct'))} | {_fmt_plain_number(row.get('buy_amount_wan'))} | "
            f"{_fmt_plain_number(row.get('sell_amount_wan'))} | {_fmt_plain_number(row.get('net_amount_wan'))} |"
        )
    lines.append("")


def _append_announcements_section(lines: list[str], announcements: dict[str, Any]) -> None:
    rows = announcements.get("rows") or []
    lines.extend(["### 重要公告速递", "| 代码 | 名称 | 公告 |", "|---|---|---|"])
    if not announcements.get("available") or not rows:
        lines.append("|  |  | 当日重要公告暂未取得可核验明细 |")
        lines.append("")
        return
    for row in rows[:8]:
        lines.append(f"| {row.get('symbol') or ''} | {row.get('name') or ''} | {row.get('title') or ''} |")
    lines.append("")


def _fmt_plain_number(value: Any) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):,.2f}"


def _render_committee_review_report(
    *,
    header_lines: list[str],
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m5: dict[str, Any],
    m6: dict[str, Any],
    lens_context: LensContext,
) -> str:
    if report_format in {"summary", "key-points"}:
        return _render_intraday_briefing_report(
            header_lines=header_lines,
            evidence=evidence,
            quality=quality,
            portfolio_snapshot=portfolio_snapshot,
            report_format=report_format,
            m1=m1,
            m2=m2,
            m3=m3,
            m4=m4,
            m6=m6,
            lens_context=lens_context,
        )

    lines = list(header_lines)
    notice = _missing_module_notice(quality)
    if notice:
        lines.extend([notice, ""])
    lines.append("## 执行摘要")
    lines.append(_executive_summary(m1, m3, m4, m6, lens_context, quality))
    lines.append("投委会结论已综合多 lens 分工：护城河与安全边际、风险清单、商业本质、长期质量和宏观情景。")
    lines.append("")

    lines.append("## 一、大盘指数概览")
    _append_index_table(lines, _index_rows(m1))
    _append_northbound_table(lines, m1.get("northbound") or {})
    _append_breadth_table(lines, m1.get("breadth") or {})
    lines.append("")
    lines.append(f"=={m1.get('cross_market_comment', '三地市场强弱分化，风险偏好仍需结合成交额确认。')}==")
    lines.append(_format_m1_committee_analysis(m1))
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

    concentration = m2.get("concentration", {})
    stats = m3.get("pool_stats", {})
    risk_stats = m4.get("pool_stats") or stats
    features = m5.get("feature_groups", {})

    lines.append(deep_heading)
    lines.append("### M1. 基础数据与核心指标")
    _append_index_table(lines, _index_rows(m1))
    _append_northbound_table(lines, m1.get("northbound") or {})
    _append_breadth_table(lines, m1.get("breadth") or {})
    lines.append(_format_m1_committee_analysis(m1))
    lines.append(_market_trend_narrative(m1, m3, m4))
    lines.append("")

    lines.append("### M2. 板块资金与集中度")
    if m2.get("available") is False:
        lines.append("==本模块证据暂缺，板块资金和集中度仅保留观察框架。==")
    else:
        lines.append(f"=={m2.get('summary', '市场以结构性轮动为主。')}==")
    _append_board_summary_tables(lines, m2)
    lines.append(
        f"涨停主题 TOP1 占比 {float(concentration.get('top1_ratio') or 0):.1%}，"
        f"TOP3 占比 {float(concentration.get('top3_ratio') or 0):.1%}。"
    )
    lines.append("")

    lines.append("### M3. 赚钱效应与上涨主线")
    if m3.get("available") is False:
        lines.append("==本模块证据暂缺，赚钱效应和上涨主线暂不外推。==")
    else:
        lines.append(f"=={m3.get('summary', '活跃资金仍在寻找高辨识度方向。')}==")
    _append_leader_table(lines, stats.get("leaders", []))
    lines.append(
        f"\n涨停 {stats.get('zt_count', 0)} 家，其中首板 {stats.get('first_board_count', 0)} 家、"
        f"连板 {stats.get('multi_board_count', 0)} 家。"
    )
    lines.append("")

    lines.append("### M4. 爆量下跌风险")
    if m4.get("available") is False:
        lines.append("==本模块证据暂缺，下跌风险以仓位纪律和次日验证为主。==")
    else:
        lines.append(f"=={m4.get('summary', '风险主要集中在高位分歧。')}==")
    lines.append(
        f"跌停 {risk_stats.get('dt_count', 0)} 家、炸板 {risk_stats.get('zb_count', 0)} 家，"
        f"炸板率约 {float(risk_stats.get('blowup_ratio') or 0):.1%}。"
    )
    lines.append("")

    lines.append("### M5. 特征分组")
    if m5.get("available") is False:
        lines.append("==本模块证据暂缺，风格分组只保留下一交易日验证项。==")
    else:
        lines.append(f"=={m5.get('summary', '成长与低位扩散特征较明显。')}==")
    lines.append(
        f"10:30 前涨停 {features.get('early_limit_up_count', 0)} 家，"
        f"低位异动 {features.get('low_position_active_count', 0)} 家，"
        f"科创/创业板活跃样本 {features.get('growth_board_count', 0)} 家。"
    )
    lines.append("")

    lines.append("### M6. 综合风险与抗跌方向")
    if m6.get("available") is False:
        lines.append("==本模块证据暂缺，抗跌方向需要等待价格、成交和情绪交叉确认。==")
    else:
        lines.append(f"=={m6.get('summary', '抗跌样本主要来自仍有业绩或产业趋势支撑的方向。')}==")
    lines.append(_format_m6_committee_analysis(m6))
    resilient = [value for value in m6.get("resilient", []) if value]
    if resilient:
        lines.append("可继续观察：" + "、".join(resilient) + "。")
    lines.append("")
    _append_market_fact_sections(lines, evidence.meta.get("facts") or {})
    lines.append("")

    advice = evidence.meta.get("portfolio_advice_sections") or {}
    lines.append(advice_heading)
    lines.append("### 现状总结")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("current", []), "已加载持仓；现状以当日浮盈亏、集中度和相对基准表现为准。")
    else:
        lines.append(f"- {_market_trend_narrative(m1, m3, m4)}")
    lines.append("")
    lines.append("### 基准跑赢/跑输")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("benchmark", []), "当前没有足够数据形成可靠的相对基准判断。")
    else:
        lines.append("- 未加载持仓；以主要指数、市场广度和主线持续性作为通用市场基准。")
    lines.append("")
    lines.append("### 条件化仓位动作")
    if has_holdings:
        _append_bullets_or_default(lines, advice.get("position_actions", []), "若持仓继续跑输对应基准且成交未改善，优先降低新增暴露；若放量修复，再评估分批调整。")
    else:
        lines.append("- 若指数强弱、成交额和主线持续性同向改善，再考虑提高进攻性；若主线收缩或炸板率上升，维持防守仓位。")
    lines.append("")
    lines.append("### 下一交易日观察清单")
    _append_bullets_or_default(
        lines,
        advice.get("watchlist", []),
        "继续观察指数强弱、成交额变化和主线板块持续性是否互相确认。",
    )
    lines.append("")
    lines.append("### 风险提示")
    risks = advice.get("risks", [])
    if risks:
        _append_bullets(lines, risks)
    else:
        lines.append("- 控制追涨节奏，避免在单日情绪极端后忽视次日分化风险。")
    _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, {}))
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    return sanitize_research_report("\n".join(lines))


def _render_intraday_briefing_report(
    *,
    header_lines: list[str],
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
    m6: dict[str, Any],
    lens_context: LensContext,
) -> str:
    lines = list(header_lines)
    title = "## 一、盘前资讯与外围线索" if report_format == "summary" else "## 一、盘中市场快照"
    lines.append(title)
    _append_index_table(lines, _index_rows(m1))
    _append_northbound_table(lines, m1.get("northbound") or {})
    lines.append("")
    lines.append(f"=={m1.get('cross_market_comment', '三地市场强弱分化，需结合成交额确认。')}==")
    lines.append(_market_trend_narrative(m1, m3, m4))
    lines.append("")

    lines.append("## 二、行业动态与主线板块")
    if m2.get("available") is False:
        lines.append("==板块证据暂缺，主线判断只保留观察框架。==")
    else:
        lines.append(f"=={m2.get('summary', '市场以结构性轮动为主。')}==")
    _append_board_summary_tables(lines, m2, limit=8)
    lines.append("")

    if report_format == "key-points":
        lines.append("## 三、赚钱效应与风险监控")
        lines.append(f"=={m3.get('summary', '活跃资金仍在寻找高辨识度方向。')}==")
        _append_leader_table(lines, (m3.get("pool_stats") or {}).get("leaders", [])[:6])
        lines.append(f"- {_format_m6_committee_analysis(m6)}")
        lines.append(f"- {_market_trend_narrative(m1, m3, m4)}")
        lines.append("")
        next_index = "四"
    else:
        next_index = "三"

    details = portfolio_snapshot.get("details") or []
    if details:
        lines.append(f"## {next_index}、持仓分析")
        _append_holdings_table(lines, details)
        lines.append("")
        _append_portfolio_summary_table(lines, portfolio_snapshot)
        lines.append("")
        _append_relative_strength_table(lines, details)
        lines.append("")
        next_index = "五" if report_format == "key-points" else "四"

    next_heading = f"## {next_index}、{'盘中' if report_format == 'key-points' else '盘前'}预判与观察清单"

    advice = evidence.meta.get("portfolio_advice_sections") or {}
    lines.append(next_heading)
    _append_bullets_or_default(
        lines,
        advice.get("watchlist", []),
        "观察指数强弱、成交额变化、主线板块持续性和炸板率变化。",
    )
    lines.append("")
    _append_market_fact_sections(lines, evidence.meta.get("facts") or {})
    lines.append("")
    lines.append("## 风险提示")
    _append_bullets(lines, _risk_and_catalyst_lines(m3, m4, m6, {}))
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")
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
        "module_diagnostics": {},
        "committee_deep_analysis": {
            "m1": ((adjusted.get("M1") or {}).get("committee_deep_analysis") or {}),
            "m6": ((adjusted.get("M6") or {}).get("committee_deep_analysis") or {}),
        },
        "debate_or_synthesis_notes": lens_context.debate_or_synthesis_notes,
        "lens_adjustments": (adjusted.get("_meta") or {}).get("lens_weight_adjustments", {}),
    }
    if fallback:
        metadata["fallback"] = fallback
    return metadata


def _m7_quality_score(sentiment: dict[str, Any]) -> int:
    if sentiment.get("status") != "ok":
        return 0
    confidence = str(sentiment.get("confidence") or "").lower()
    if confidence == "high":
        return 10
    if confidence == "medium":
        return 8
    return 4


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


def _change_pct_value(row: dict[str, Any]) -> float | None:
    value = row.get("change_pct")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_trend_narrative(m1: dict[str, Any], m3: dict[str, Any], m4: dict[str, Any]) -> str:
    a_values = [
        value
        for row in m1.get("a_indices", [])
        if (value := _change_pct_value(row)) is not None
    ]
    growth_values = [
        value
        for row in m1.get("a_indices", [])
        if row.get("name") in {"创业板指", "科创50"} and (value := _change_pct_value(row)) is not None
    ]
    blowup = float((m4.get("pool_stats") or {}).get("blowup_ratio") or 0)
    zt_count = int((m3.get("pool_stats") or {}).get("zt_count") or m3.get("zt_count") or 0)
    parts: list[str] = []
    if a_values:
        positives = sum(1 for value in a_values if value > 0)
        negatives = sum(1 for value in a_values if value < 0)
        a_avg = sum(a_values) / len(a_values)
        if positives and negatives:
            parts.append("A股指数分化，权重端与成长端走势不一致")
        elif growth_values and sum(growth_values) / len(growth_values) < 0 and a_avg > 0:
            parts.append("A股指数分化，权重端与成长端走势不一致")
        elif a_avg >= 0.3:
            parts.append("A股主要指数均值偏强")
        elif a_avg <= -0.3:
            parts.append("A股主要指数均值偏弱")
        else:
            parts.append("A股主要指数窄幅波动")
    if blowup >= 0.25:
        parts.append(f"短线炸板率约 {blowup:.1%}，高位接力容错率偏低")
    elif zt_count >= 80:
        parts.append(f"涨停样本 {zt_count} 家，短线活跃度较高")
    if not parts:
        return str(m1.get("cross_market_comment") or "市场以结构性轮动为主，建议结合成交额与主线持续性确认。")
    return "；".join(parts) + "。"


def _missing_module_notice(quality: EvidenceQuality) -> str | None:
    if not quality.missing_modules:
        return None
    labels = "、".join(MODULE_LABELS.get(module, module) for module in quality.missing_modules)
    return f"> 本报告缺失模块：{labels}。相关判断已降级，并尽量标注数据来源。"


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
        f"当前采用 {_mode_label(context.mode, default_committee=False)} 模式，结论已按专家框架权重调和。"
    )


def _format_m1_committee_analysis(m1: dict[str, Any]) -> str:
    analysis = m1.get("committee_deep_analysis") or {}
    trend = analysis.get("trend_consistency") or {}
    cross = analysis.get("cross_validation") or {}
    anomalies = analysis.get("anomalies") or []
    return (
        "m1 综合深度分析："
        f"{cross.get('lens_count', 0)} 位专家交叉验证；"
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
        community_count = int((source_breakdown.get("community") or {}).get("sample_count") or 0)
        if 0 < community_count < 3:
            lines.append("- 社区有效样本少于 3 条，情绪结论仅作低置信度参考。")
    return lines


def _append_evidence_appendix(
    lines: list[str],
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    lens_context: LensContext,
    sentiment: dict[str, Any],
) -> None:
    meta = evidence.meta or {}
    adjusted = lens_context.adjusted_evidence
    module_names = [module for module in MODULE_LABELS if module in evidence.modules]
    diagnostics = meta.get("module_diagnostics") or {}
    source_events = meta.get("source_events") or []
    lines.append(
        "- m1–m6 原始数据及本次报告调整记录："
        f"模块={', '.join(module_names)}；质量分={quality.total_score}；"
        f"缺失={quality.missing_modules or '无'}；诊断={diagnostics}；"
        f"来源事件数={len(source_events)}。"
    )
    lines.append(
        "- 各 lens 证据权重调整明细："
        f"{(adjusted.get('_meta') or {}).get('lens_weight_adjustments', {})}。"
    )
    lines.append(
        "- 主要交叉验证与分歧调和记录："
        f"M1={((adjusted.get('M1') or {}).get('committee_deep_analysis') or {}).get('anomalies', [])}；"
        f"M6={((adjusted.get('M6') or {}).get('committee_deep_analysis') or {}).get('conflict_reconciliation', [])}。"
    )
    lines.append(
        "- 免责声明与数据来源："
        "行情和新闻来自公开市场数据与已注册中文财经来源；"
        "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
    )


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
    """Backward-compatible alias; all reports use the committee structure."""
    return render_report_with_metadata(
        trade_date=trade_date,
        session_label=session_label,
        evidence=evidence,
        quality=quality,
        portfolio_snapshot=portfolio_snapshot,
        report_format=report_format,
    ).markdown


def _render_classic_report_legacy(
    *,
    trade_date: str,
    session_label: str,
    evidence: EvidenceBundle,
    quality: EvidenceQuality,
    portfolio_snapshot: dict[str, Any],
    report_format: str,
) -> str:
    lines: list[str] = [f"# 全球市场复盘研报（{trade_date} {session_label}）", ""]
    notice = _missing_module_notice(quality)
    if notice:
        lines.extend([notice, ""])
    if quality.degrade_mode == "simplified":
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
        lines.append(_market_trend_narrative(m1, m3, m4))
        lines.append("")

        lines.append("### 2. 集中度分析")
        sector_rows = m2.get("industry_top20") or m2.get("concept_top20") or []
        if not sector_rows:
            lines.append("> 行业/概念板块榜暂缺；以下集中度来自涨跌停主题统计。")
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
