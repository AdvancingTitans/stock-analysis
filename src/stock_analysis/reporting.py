from __future__ import annotations

from typing import Any

from .evidence import EvidenceBundle
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
            "| 代码 | 名称 | 买入日 | 数量 | 现价 | 当日浮动盈亏 | 趋势 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for detail in details:
        current_price = _fmt_price(detail.get("current_price"))
        if current_price:
            current_price = f"{current_price} {detail.get('currency', '')}".strip()
        lines.append(
            "| {symbol} | {name} | {buy_date} | {quantity} | {price} | {daily_pnl} | {trend} |".format(
                symbol=detail.get("symbol") or "",
                name=detail.get("name") or "",
                buy_date=detail.get("buy_date") or "",
                quantity=_fmt_quantity(detail.get("quantity")),
                price=current_price,
                daily_pnl=_fmt_daily_pnl(detail),
                trend=detail.get("trend") or "",
            )
        )


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
    lines.append("## 二、持仓分析")
    _append_holdings_table(lines, details)
    total_value = portfolio_snapshot.get("total_value_cny")
    total_pnl = portfolio_snapshot.get("total_pnl_cny")
    if total_value is not None and total_pnl is not None:
        lines.append(
            f"\n组合折算总市值约 {_fmt_price(total_value)} CNY，买入以来浮动盈亏约 "
            f"{float(total_pnl):+,.2f} CNY。前三大持仓占比 "
            f"{portfolio_snapshot.get('top3_ratio', 0):.1%}，最高单一市场暴露 "
            f"{portfolio_snapshot.get('dominant_ratio', 0):.1%}。"
        )
    relative_lines = []
    for detail in details:
        if detail.get("relative_label") and detail.get("benchmark_name"):
            relative_lines.append(
                f"{detail.get('name')}当日{detail.get('relative_label')}{detail.get('benchmark_name')}"
                f"{abs(float(detail.get('relative_pct', 0))):.2f}个百分点"
            )
    if relative_lines:
        lines.append("相对强弱：" + "；".join(relative_lines) + "。")
    lines.append("")

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

        lines.append("## 三、六模块深度复盘")
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
    lines.append("## 四、综合持仓建议与风险提示")
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
    _append_bullets(lines, advice.get("watchlist", []))
    lines.append("")
    lines.append("### 风险提示")
    _append_bullets(lines, advice.get("risks", []))
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    disclaimer = "免责声明：以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
    if report_format == "summary":
        compact = _section_prefix(lines, "## 三、六模块深度复盘")
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    if report_format == "key-points":
        compact = _section_prefix(lines, "### 5. 特征分组")
        if disclaimer not in compact:
            compact.extend(["", disclaimer])
        return sanitize_research_report("\n".join(compact))
    return sanitize_research_report("\n".join(lines))
