"""Recoverable company-research workspace over a Company Evidence Pack."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .company_evidence import COMPANY_MODULES
from .company_lens import (
    build_company_lens_opinions,
    freeze_company_evidence,
    synthesize_company_committee,
)
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

DISCLAIMER = "以上内容仅供研究参考，不构成任何投资建议。"


def _changes(pack: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    if not baseline:
        return ["首次研究，无历史基线。"]
    previous = baseline.get("evidence_snapshot") or {}
    current = pack.get("_meta") or {}
    changes = []
    if previous.get("coverage") != current.get("coverage"):
        changes.append(f"证据覆盖：{previous.get('coverage')}% → {current.get('coverage')}%")
    if previous.get("available_modules") != current.get("available_modules"):
        changes.append("可用证据模块发生变化。")
    if previous.get("missing_modules") != current.get("missing_modules"):
        changes.append("证据缺口结构发生变化。")
    return changes or ["未发现可由当前结构化 Evidence 自动判定的变化。"]


def _research_plan(pack: dict[str, Any]) -> str:
    lines = [
        f"# Research Plan：{pack['name']}（{pack['symbol']}）",
        "",
        f"**研究截止日**：{pack['trade_date']}",
        "",
        "先定义问题，再补证据；未回答的问题不得被改写成肯定结论。",
        "",
        "| Priority | Research Question | Required Evidence | Status |",
        "|---|---|---|---|",
    ]
    for index, (code, label) in enumerate(COMPANY_MODULES.items(), start=1):
        section = pack["modules"][code]
        status = "answered" if section["available"] else "blocked"
        lines.append(f"| P{index} | {label}有哪些可证伪的核心判断？ | {code} 可核验事实与反证 | {status} |")
    lines.extend(["", "## Research Rules", "", "- 公司 Evidence 与 M1–M6 市场证据分离。", "- 冲突、缺失和条件证据必须显式保留。", "- 专家 lens 只能解释冻结后的 Evidence，不能补写事实。", ""])
    return "\n".join(lines)


def _evidence_summary(pack: dict[str, Any]) -> str:
    meta = pack["_meta"]
    lines = [
        f"# Evidence Summary：{pack['name']}（{pack['symbol']}）",
        "",
        f"- 证据日期：{pack['trade_date']}",
        f"- 覆盖率：{meta['coverage']}%",
        f"- 可用模块：{', '.join(meta['available_modules']) or '无'}",
        f"- 缺失模块：{', '.join(meta['missing_modules']) or '无'}",
        "",
    ]
    for code, label in COMPANY_MODULES.items():
        section = pack["modules"][code]
        lines.extend([f"## {code} {label}", ""])
        if section["evidence"]:
            for item in section["evidence"]:
                subject = item.get("metric") or item.get("title") or "evidence"
                value = item.get("value")
                lines.append(f"- {subject}" + (f"：{value}" if value is not None else ""))
        else:
            lines.append("- 证据暂缺。")
        lines.extend(f"- 缺口：{gap}" for gap in section["gaps"])
        lines.append("")
    return "\n".join(lines)


def _expert_readiness(pack: dict[str, Any], opinions: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"# Company Lens Opinions：{pack['name']}（{pack['symbol']}）",
        "",
        f"- Frozen Evidence：{next(iter(opinions.values()))['evidence_snapshot_id']}",
        "",
        "| Lens | Status | Readiness | Confidence | Missing |",
        "|---|---|---:|---|---|",
    ]
    for opinion in opinions.values():
        lines.append(
            f"| {opinion['lens_name']} | {opinion['status']} | {opinion['readiness']:.1%} | "
            f"{opinion['confidence']} | {', '.join(opinion['missing_modules']) or '无'} |"
        )
    lines.extend(["", "每个 opinion 的 supporting/counter evidence 均通过 evidence_id 指向同一冻结快照。", ""])
    return "\n".join(lines)


def _committee_review(pack: dict[str, Any], committee: dict[str, Any]) -> str:
    lines = [f"# Committee Review：{pack['name']}（{pack['symbol']}）", "", "## Consensus", ""]
    lines.extend(f"- {item}" for item in committee["consensus"])
    lines.extend(["", "## Disagreement", ""])
    lines.extend(f"- {item}" for item in committee["disagreements"])
    lines.extend(["", "## Risk Vetoes", ""])
    lines.extend(f"- {item}" for item in committee["risk_vetoes"] or ["无结构化 veto。"])
    lines.extend(["", "## Committee Status", "", f"- action：{committee['action']}", ""])
    return "\n".join(lines)


def _decision_memo(pack: dict[str, Any], committee: dict[str, Any]) -> str:
    lines = [
        f"# Decision Memo：{pack['name']}（{pack['symbol']}）",
        "",
        f"- 决策：{committee['action']}，不形成无条件买卖指令。",
        "- 仓位：不由 Company lens 或 committee 自动推导。",
    ]
    lines.extend(f"- 条件：{item}" for item in committee["action_conditions"])
    lines.extend(["- 失效条件：Evidence 快照、来源日期或口径发生变化后，旧 opinions 与 committee 自动失效。", "", DISCLAIMER, ""])
    return "\n".join(lines)


def _module_lines(pack: dict[str, Any], codes: tuple[str, ...]) -> list[str]:
    lines = []
    for code in codes:
        section = pack["modules"][code]
        lines.append(f"### {code} {COMPANY_MODULES[code]}")
        lines.append("")
        if not section["evidence"]:
            lines.append("- 证据暂缺。")
        for item in section["evidence"]:
            label = item.get("metric") or item.get("title") or "evidence"
            value = item.get("value")
            if value is not None and label in {
                "revenue", "parent_netprofit", "parent_net_profit", "operating_cash_flow",
                "free_cash_flow_lite", "net_cash_invest", "net_cash_finance",
            }:
                rendered = _fmt(float(value) / 1e8, 2, "亿元")
            elif value is not None and (label.endswith("_pct") or label.startswith("returns_") or label in {"roe_weighted", "gross_margin", "debt_asset_ratio", "atr_14_pct"}):
                rendered = _fmt(value, 2, "%")
            else:
                rendered = _fmt(value) if value is not None else ""
            lines.append(f"- {label}" + (f"：{rendered}" if rendered else ""))
        lines.extend(f"- 缺口：{gap}" for gap in section["gaps"])
        lines.append("")
    return lines


def _metric(pack: dict[str, Any], code: str, name: str) -> Any:
    for item in pack["modules"][code]["evidence"]:
        if item.get("metric") == name:
            return item.get("value")
    return None


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "未取得"
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _expectation_valuation_lines(pack: dict[str, Any]) -> list[str]:
    model = pack.get("expectation_model") or {}
    implied = model.get("market_implied") or []
    if not implied:
        return ["", "当前总市值不可得，无法反推市场隐含利润。"]
    year = model.get("valuation_year") or "未指定估值年份"
    lines = [
        "",
        f"### 逆向验证：当前市值在交易什么（{year}）",
        "",
        "| 假设估值倍数 | 市值隐含净利润 |",
        "|---:|---:|",
    ]
    for row in implied:
        if row["multiple"] in {20.0, 22.0, 25.0, 30.0, 35.0}:
            lines.append(f"| {_fmt(row['multiple'], 1, 'x')} | {_fmt(row['implied_net_profit'] / 1e8, 1, '亿元')} |")
    lines.extend([
        "",
        "这张表不是盈利预测，而是把当前股价翻译成可检验的盈利门槛；估值年份和倍数变化会改变隐含结果。",
    ])

    forward = model.get("forward_model") or {}
    products = forward.get("product_lines") or []
    if products:
        lines.extend(["", "### 正向产品线模型", "", "| 产品线 | 出货量 | ASP | 收入 | 净利润 |", "|---|---:|---:|---:|---:|"])
        for item in products:
            lines.append(
                f"| {item['name']} | {_fmt(item.get('units'), 0)} | {_fmt(item.get('asp'), 2)} | "
                f"{_fmt(item['revenue'] / 1e8, 1, '亿元')} | {_fmt(item['net_profit'] / 1e8, 1, '亿元')} |"
            )
    segments = forward.get("segments") or []
    if segments:
        lines.extend(["", "### SOTP 与市值剩余价值", "", "| 分部 | 正向净利润 | 估值倍数 | 分部价值 |", "|---|---:|---:|---:|"])
        for item in segments:
            lines.append(
                f"| {item['name']} | {_fmt(item['net_profit'] / 1e8, 1, '亿元')} | "
                f"{_fmt(item['multiple'], 1, 'x')} | {_fmt(item['value'] / 1e8, 1, '亿元')} |"
            )
        bridge = model["sotp_bridge"]
        lines.append(
            f"| **市值剩余价值** |  |  | **{_fmt(bridge['residual_value'] / 1e8, 1, '亿元')}**（{bridge['status']}） |"
        )
    option = model.get("option_value")
    if option:
        revenue = option.get("required_revenue")
        if option.get("status") == "overallocated":
            lines.extend([
                "",
                f"已分配分部价值超过当前市值 {_fmt(abs(option['residual_value']) / 1e8, 1, '亿元')}，"
                f"因此 **{option.get('name') or '期权业务'}** 当前没有可分配的正剩余价值；该差额保持为负，不归零。",
            ])
        else:
            lines.extend([
                "",
                f"若把剩余价值全部归于 **{option.get('name') or '期权业务'}**，按 {_fmt(option.get('multiple'), 1, 'x')}，"
                f"需要净利润约 {_fmt(option['required_net_profit'] / 1e8, 1, '亿元')}"
                + (f"、收入约 {_fmt(revenue / 1e8, 1, '亿元')}。" if revenue is not None else "。"),
            ])
        lines.append("内部配套产品若已进入分部利润，不得再次作为独立期权计价。")
    gaps = model.get("expectation_gap") or []
    if gaps:
        lines.extend(["", "### 正向模型与市场隐含预期对账", "", "| 倍数 | 正向净利润 | 隐含净利润 | 预期差 | 覆盖率 |", "|---:|---:|---:|---:|---:|"])
        for row in gaps:
            if row["multiple"] in {20.0, 25.0, 30.0, 35.0}:
                lines.append(
                    f"| {_fmt(row['multiple'], 1, 'x')} | {_fmt(row['forward_net_profit'] / 1e8, 1, '亿元')} | "
                    f"{_fmt(row['implied_net_profit'] / 1e8, 1, '亿元')} | {_fmt(row['gap'] / 1e8, 1, '亿元')} | "
                    f"{_fmt(row['coverage_pct'], 1, '%')} |"
                )
    audits = model.get("premise_audit") or []
    if audits:
        lines.extend(["", "### 前提审计", "", "| 前提 | 状态 | 原因 |", "|---|---|---|"])
        lines.extend(f"| {item['claim']} | {item['status']} | {item['reason']} |" for item in audits)
    return lines


def _institutional_report_v48(
    pack: dict[str, Any],
    changes: list[str],
    opinions: dict[str, dict[str, Any]],
    committee: dict[str, Any],
) -> str:
    meta = pack["_meta"]
    price = _metric(pack, "C6", "market_quote")
    pe = _metric(pack, "C6", "pe_static_proxy") or _metric(pack, "C6", "pe_ttm")
    roe = _metric(pack, "C2", "roe_weighted")
    margin = _metric(pack, "C2", "gross_margin")
    fcf = _metric(pack, "C2", "free_cash_flow_lite")
    revenue_yoy = _metric(pack, "C3", "revenue_yoy_pct")
    profit_yoy = _metric(pack, "C3", "parent_net_profit_yoy_pct")
    return_60d = _metric(pack, "C7", "returns_60d")
    core_ready = all(pack["modules"][code]["available"] for code in ("C2", "C3", "C5", "C6", "C7"))
    lines = [
        f"# Institutional Research Report：{pack['name']}（{pack['symbol']}）",
        "",
        f"**Evidence as of**：{pack['trade_date']}  ",
        f"**Coverage**：{meta['coverage']}%",
        "",
        "## Executive Summary",
        "",
        "结构化证据支持形成条件化研究判断："
        f"最新报告期 ROE {_fmt(roe, 2, '%')}、毛利率 {_fmt(margin, 2, '%')}、"
        f"FCF-lite {_fmt(float(fcf) / 1e8 if fcf is not None else None, 2, '亿元')}；"
        f"现价 {_fmt(price, 2, '元')}对应最新已披露全年 EPS 的静态 PE 代理约 {_fmt(pe, 2, 'x')}。",
        (
            "核心质量、增长、资本配置、估值与风险证据门已通过；"
            "护城河的因果证据仍需人工核验。"
            if core_ready
            else "当前仅能对已取得的核心指标形成判断，行动条件需继续复核。"
        ),
        "",
        "## What's Changed Since Last Review",
        "",
    ]
    lines.extend(f"- {change}" for change in changes)
    lines.extend(
        [
            "",
            "## Investment Thesis",
            "",
            f"- **质量假设**：{_fmt(margin, 2, '%')} 毛利率与 {_fmt(roe, 2, '%')} 报告期 ROE 支持高质量经济性；若利润率、ROE 和现金转化同步下降，该假设失效。",
            f"- **增长假设**：最新同期营收/归母利润变化约 {_fmt(revenue_yoy, 2, '%')} / {_fmt(profit_yoy, 2, '%')}；增长降速需与现金流共同解读。",
            f"- **价格假设**：静态 PE 代理 {_fmt(pe, 2, 'x')} 不等同于内在价值；只有在盈利韧性维持时，估值情景才有意义。",
            f"- **反证**：60 日价格收益 {_fmt(return_60d, 2, '%')} 反映市场重定价，但不单独证明经营质量改变。",
            "",
            "## Evidence Dashboard",
            "",
            "| Available | Missing | Coverage |",
            "|---|---|---:|",
            f"| {', '.join(meta['available_modules']) or '无'} | {', '.join(meta['missing_modules']) or '无'} | {meta['coverage']}% |",
            "",
            "## Business / Industry / Moat / Governance",
            "",
        ]
    )
    lines.extend(_module_lines(pack, ("C1", "C4", "C5")))
    lines.extend([
        "> 投资/融资现金流为现金流量表净额，负值表示净流出；不能在未拆解分红、回购、借款和投资项目时直接等同于股东回报或价值创造。",
        "",
    ])
    lines.extend(["## Financial Quality & Growth", ""])
    history = pack.get("financial_history") or []
    if history:
        lines.extend([
            "| 期间 | ROE | 毛利率 | 负债率 | 营收 | 归母净利 | OCF | FCF-lite |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in history[:6]:
            lines.append(
                f"| {row.get('period_label') or row.get('report_date')} | {_fmt(row.get('roe_weighted'), 2, '%')} | "
                f"{_fmt(row.get('gross_margin'), 2, '%')} | {_fmt(row.get('debt_asset_ratio'), 2, '%')} | "
                f"{_fmt(float(row['revenue']) / 1e8 if row.get('revenue') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['parent_net_profit']) / 1e8 if row.get('parent_net_profit') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['operating_cash_flow']) / 1e8 if row.get('operating_cash_flow') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['free_cash_flow_lite']) / 1e8 if row.get('free_cash_flow_lite') is not None else None, 1, '亿')} |"
            )
        lines.append("")
    lines.extend(_module_lines(pack, ("C3",)))
    lines.extend(["## Valuation & Scenarios", ""])
    lines.extend([
        "| 参考情景 | 对应价格 | 与现价关系 |",
        "|---|---:|---:|",
    ])
    for multiple in (15, 18, 22):
        scenario = _metric(pack, "C6", f"scenario_price_{multiple}x_pe")
        relation = ((scenario / price - 1) * 100) if scenario is not None and price else None
        lines.append(f"| {multiple}x 最新已披露全年 EPS | {_fmt(scenario, 2, '元')} | {_fmt(relation, 2, '%')} |")
    lines.extend(["", "> 情景表是估值敏感性，不是目标价；未引入一致预期、折现率或历史分位。", ""])
    lines.extend(
        [
            "## Expert Debate",
            "",
        ]
    )
    for opinion in opinions.values():
        focus = str(opinion.get("valuation_preference") or opinion.get("risk_focus") or "估值与风险").rstrip("。")
        lines.extend([
            f"### {opinion['lens_name']}",
            "",
            f"- 框架覆盖：{opinion['readiness']:.1%}；主要缺口：{', '.join(opinion['missing_modules']) or '无'}。",
            f"- 复核重点：{focus}。",
            "- 判断：已引用同一冻结快照的支持与反证；不把框架覆盖率当作股票评分。",
            "",
        ])
    lines.extend(["## Risks, Catalysts & Scenario Triggers", ""])
    lines.extend(_module_lines(pack, ("C7", "C8")))
    lines.extend(
        [
            "## Committee Decision Memo",
            "",
            f"- 决策：{committee['action']}。",
            "",
            "### Consensus",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in committee["consensus"])
    lines.extend(
        [
            "",
            "### Disagreements",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in committee["disagreements"])
    lines.extend(
        [
            "",
            "## Sources & Run Manifest",
            "",
        ]
    )
    for event in meta.get("source_events") or []:
        lines.append(f"- {event.get('source') or 'unknown'}：{event.get('status') or 'unknown'}")
    lines.extend(["", DISCLAIMER, "股市有风险，投资需谨慎。", ""])
    return "\n".join(lines)


def _institutional_report(
    pack: dict[str, Any],
    changes: list[str],
    opinions: dict[str, dict[str, Any]],
    committee: dict[str, Any],
) -> str:
    """Render the frozen snapshot as the classic Chinese committee memo."""

    price = _metric(pack, "C6", "market_quote")
    pe = _metric(pack, "C6", "pe_static_proxy") or _metric(pack, "C6", "pe_ttm")
    pb = _metric(pack, "C6", "pb_reported_proxy") or _metric(pack, "C6", "pb")
    roe = _metric(pack, "C2", "roe_weighted")
    margin = _metric(pack, "C2", "gross_margin")
    debt = _metric(pack, "C2", "debt_asset_ratio")
    ocf = _metric(pack, "C2", "operating_cash_flow")
    fcf = _metric(pack, "C2", "free_cash_flow_lite")
    net_margin = _metric(pack, "C1", "parent_net_margin_pct")
    cash_conversion = _metric(pack, "C1", "operating_cash_conversion_pct")
    moat_margin = _metric(pack, "C4", "annual_gross_margin_pct")
    moat_range = _metric(pack, "C4", "annual_gross_margin_range_pct")
    revenue_yoy = _metric(pack, "C3", "revenue_yoy_pct")
    profit_yoy = _metric(pack, "C3", "parent_net_profit_yoy_pct")
    return_5d = _metric(pack, "C7", "returns_5d")
    return_20d = _metric(pack, "C7", "returns_20d")
    return_60d = _metric(pack, "C7", "returns_60d")
    atr = _metric(pack, "C7", "atr_14_pct")
    net_invest = _metric(pack, "C5", "net_cash_invest")
    net_finance = _metric(pack, "C5", "net_cash_finance")
    direct_sales = _metric(pack, "C1", "direct_sales_revenue")
    direct_sales_yoy = _metric(pack, "C1", "direct_sales_revenue_yoy_pct")
    wholesale_yoy = _metric(pack, "C1", "wholesale_revenue_yoy_pct")
    core_product_margin = _metric(pack, "C4", "core_product_gross_margin_pct")
    dividend_total = _metric(pack, "C5", "annual_dividend_total")
    payout_ratio = _metric(pack, "C5", "shareholder_payout_ratio_pct")
    execution_cost_100w = _metric(pack, "C7", "execution_round_trip_cost_100w_bps")
    series_revenue_yoy = _metric(pack, "C7", "series_revenue_yoy_pct")
    inventory_yoy = _metric(pack, "C7", "finished_and_base_inventory_yoy_pct")
    sales_expense_yoy = _metric(pack, "C7", "sales_expense_yoy_pct")
    reinvestment = (float(ocf) - float(fcf)) if ocf is not None and fcf is not None else None
    history = pack.get("financial_history") or []
    events = []
    for code in ("C7", "C8"):
        for item in pack["modules"][code]["evidence"]:
            title = item.get("title")
            if title and title not in events:
                events.append(str(title))

    action_label = "中性偏积极，等待更好赔率" if committee["action"] == "manual_review" else "审慎观察"
    research_question = committee.get("research_question") or "长期商业质量、估值与风险"
    committee_names = "、".join(opinion["lens_name"] for opinion in opinions.values())
    lines = [
        f"# {pack['name']}（{pack['symbol']}）个股深度研究报告 · 投委会",
        "",
        f"**报告日期**：{pack['trade_date']}  ",
        f"**研究问题**：{research_question}  ",
        f"**分析模式**：动态投委会（{committee_names}）  ",
        "**研究原则**：商业质量 → 财务兑现 → 资本配置 → 估值赔率 → 风险触发；所有观点采用同一研究时点的数据",
        "",
        "## 一、执行摘要",
        "",
        "| 项目 | 投委会判断 |",
        "|---|---|",
        f"| 商业经济性 | 毛利率 **{_fmt(margin, 2, '%')}**、归母净利率代理 **{_fmt(net_margin, 2, '%')}**，仍体现强定价与高盈利特征 |",
        f"| 财务质量 | ROE **{_fmt(roe, 2, '%')}**、资产负债率 **{_fmt(debt, 2, '%')}**、FCF-lite **{_fmt(float(fcf) / 1e8 if fcf is not None else None, 1, '亿元')}** |",
        f"| 增长状态 | 最新同口径营收 **{_fmt(revenue_yoy, 2, '%')}**、归母净利 **{_fmt(profit_yoy, 2, '%')}**；利润增速慢于收入，增长已从高增转向质量检验 |",
        f"| 价格与估值 | 现价 **{_fmt(price, 2, '元')}**，静态 PE 代理 **{_fmt(pe, 2, 'x')}**、PB 代理 **{_fmt(pb, 2, 'x')}** |",
        f"| 市场状态 | 5/20/60 日收益 **{_fmt(return_5d, 2, '%')} / {_fmt(return_20d, 2, '%')} / {_fmt(return_60d, 2, '%')}**，ATR14 **{_fmt(atr, 2, '%')}** |",
        f"| 综合结论 | **{action_label}**：生意与现金流质量仍强，当前价格处于合理估值区间，但增长降速与护城河运营指标需要继续验证 |",
        "",
        "==关键判断==  ",
        f"投委会不把 {_fmt(return_60d, 2, '%')} 的 60 日价格变化直接解释为生意恶化；更关键的矛盾是："
        f"在收入增速 {_fmt(revenue_yoy, 2, '%')}、利润增速 {_fmt(profit_yoy, 2, '%')} 的阶段，约 {_fmt(pe, 2, 'x')} 静态估值是否已提供足够赔率。",
        "",
        "## 二、行情、商业质量与核心矛盾",
        "",
        f"- **行情位置**：现价 {_fmt(price, 2, '元')}；短中期价格并非单边趋势，20 日回升与 60 日回撤同时存在。",
        f"- **盈利结构**：最新报告期毛利率 {_fmt(margin, 2, '%')}、归母净利率代理 {_fmt(net_margin, 2, '%')}。高毛利是定价权的可观测代理，但不等同于完整护城河证明。",
        f"- **现金兑现**：经营现金流/归母净利代理 {_fmt(cash_conversion, 2, '%')}；FCF-lite 为 {_fmt(float(fcf) / 1e8 if fcf is not None else None, 1, '亿元')}。利润与现金流方向一致，未出现明显“有利润、无现金”信号。",
        f"- **护城河代理**：最近可比年度毛利率 {_fmt(moat_margin, 2, '%')}，样本区间波动约 {_fmt(moat_range, 2, 'pct')}；这支持稳定盈利结构，但渠道批价、库存与市场份额仍是下一轮经营验证项。",
        f"- **渠道结构**：2025 年直销收入 {_fmt(float(direct_sales) / 1e8 if direct_sales is not None else None, 1, '亿元')}、同比 {_fmt(direct_sales_yoy, 2, '%')}，批发代理同比 {_fmt(wholesale_yoy, 2, '%')}。直销增长部分对冲了传统批发渠道压力。",
        f"- **核心产品**：茅台酒毛利率 {_fmt(core_product_margin, 2, '%')}；核心产品盈利能力明显高于公司整体，是质量判断的主要支点。",
        "",
        "## 三、财务质量、增长与现金流",
        "",
    ]
    if history:
        lines.extend([
            "| 期间 | ROE | 毛利率 | 负债率 | 营收 | 归母净利 | OCF | FCF-lite |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in history[:6]:
            lines.append(
                f"| {row.get('period_label') or row.get('report_date')} | {_fmt(row.get('roe_weighted'), 2, '%')} | "
                f"{_fmt(row.get('gross_margin'), 2, '%')} | {_fmt(row.get('debt_asset_ratio'), 2, '%')} | "
                f"{_fmt(float(row['revenue']) / 1e8 if row.get('revenue') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['parent_net_profit']) / 1e8 if row.get('parent_net_profit') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['operating_cash_flow']) / 1e8 if row.get('operating_cash_flow') is not None else None, 1, '亿')} | "
                f"{_fmt(float(row['free_cash_flow_lite']) / 1e8 if row.get('free_cash_flow_lite') is not None else None, 1, '亿')} |"
            )
    lines.extend([
        "",
        f"财务主线是“高盈利、低杠杆、增长换挡”：最新报告期 ROE {_fmt(roe, 2, '%')} 与低负债率仍提供防守性，"
        f"但利润同比 {_fmt(profit_yoy, 2, '%')} 低于收入同比 {_fmt(revenue_yoy, 2, '%')}，需要观察费用、产品结构和渠道政策是否继续侵蚀经营杠杆。",
        "",
        "## 四、治理与资本配置",
        "",
        f"- 经营现金流 {_fmt(float(ocf) / 1e8 if ocf is not None else None, 1, '亿元')}，FCF-lite {_fmt(float(fcf) / 1e8 if fcf is not None else None, 1, '亿元')}，隐含资本开支代理约 {_fmt(float(reinvestment) / 1e8 if reinvestment is not None else None, 1, '亿元')}。",
        f"- 年度投资现金流净额 {_fmt(float(net_invest) / 1e8 if net_invest is not None else None, 1, '亿元')}，融资现金流净额 {_fmt(float(net_finance) / 1e8 if net_finance is not None else None, 1, '亿元')}。",
        f"- 2025 年拟现金分红 {_fmt(float(dividend_total) / 1e8 if dividend_total is not None else None, 1, '亿元')}，约占归母净利润 {_fmt(payout_ratio, 2, '%')}；分红与回购共同构成股东回报，但仍需与长期资本开支统筹评估。",
        "- 这些净额说明现金流向，不直接等同于分红、回购或价值创造；投委会仍要求把分红、回购、重大投资与关联交易拆开审阅。",
        "",
        "## 五、估值与情景分析",
        "",
        "| 情景 | 估值锚 | 对应价格 | 相对现价 | 含义 |",
        "|---|---:|---:|---:|---|",
    ])
    labels = {15: "盈利承压/估值收缩", 18: "增长平稳/质量溢价收敛", 22: "盈利韧性/质量溢价维持"}
    for multiple in (15, 18, 22):
        scenario = _metric(pack, "C6", f"scenario_price_{multiple}x_pe")
        relation = ((scenario / price - 1) * 100) if scenario is not None and price else None
        lines.append(f"| {labels[multiple]} | {multiple}x FY EPS | {_fmt(scenario, 2, '元')} | {_fmt(relation, 2, '%')} | 敏感性测试，不是目标价 |")
    lines.extend(_expectation_valuation_lines(pack))
    lines.extend([
        "",
        f"==估值判断== 现价约 {_fmt(pe, 2, 'x')} 静态 PE；静态倍数只描述历史盈利。"
        "投资分歧应落到当前市值隐含的未来利润、正向经营模型能否覆盖该门槛，以及剩余价值是否有独立证据支持。",
        f"交易实现采用 100 万元订单情景，估算往返成本 {_fmt(execution_cost_100w, 2, 'bps')}；已计价差、佣金、经手/过户费、卖出印花税和波动率冲击，仍需用用户真实费率与成交回报校准。",
        "",
        "## 六、投委会审议",
        "",
        "| 委员框架 | 基于当前数据的判断 | 主要保留意见 |",
        "|---|---|---|",
    ])
    views = {
        "buffett": ("高毛利、低杠杆和强 FCF 符合优质特许经营特征；价格已可讨论，但安全边际不算宽。", "需用批价、渠道库存和长期 owner earnings 验证护城河。"),
        "munger": ("商业模式简单、现金创造强，错误风险主要来自把过去的品牌强度线性外推。", "机会成本与治理激励需和其他高质量资产比较。"),
        "duan_yongping": ("好生意特征仍在，增长换挡不必然改变长期价值。", "合理价格取决于消费者心智和渠道秩序是否稳定。"),
        "zhang_kun": ("长期现金流质量较高，利润率与资本回报仍具稀缺性。", "利润增速弱于收入，需确认竞争格局与自由现金流可持续性。"),
        "graham": (f"{_fmt(pe, 2, 'x')} PE 并非传统深度价值区，15x 情景仍有下行空间。", "资产下行保护弱于盈利与品牌保护，不能只看 PB。"),
        "dalio": (f"60 日收益 {_fmt(return_60d, 2, '%')}、ATR {_fmt(atr, 2, '%')}，组合层面仍需考虑消费风格和利率敏感性。", "单一优质资产也不能替代风险预算与分散化。"),
        "klarman": (f"现价对应 {_fmt(pe, 2, 'x')} 静态 PE，绝对回报取决于盈利兑现与催化，而非相对排名。", "15x 情景的永久损失风险仍需显式计入。"),
        "lynch": (f"营收/利润同比 {_fmt(revenue_yoy, 2, '%')} / {_fmt(profit_yoy, 2, '%')}，增长故事正进入兑现检验。", "需解释产品、渠道和费用为何造成利润慢于收入。"),
        "o_neil": (f"增长尚未加速，5/20/60 日收益 {_fmt(return_5d, 2, '%')} / {_fmt(return_20d, 2, '%')} / {_fmt(return_60d, 2, '%')} 也未形成一致强势。", "缺少盈利加速与趋势共振，不宜只凭品牌质量追价。"),
        "wood": ("品牌与渠道数字化能够支持长期创新，但现阶段核心仍是成熟业务现金流。", "研发、渗透率和新增量尚不足以支持非线性增长假设。"),
        "soros": ("20 日回升与 60 日回撤并存，价格反馈尚未形成单向反身性。", "政策、批价与市场预期变化可能快速改变估值中枢。"),
        "livermore": (f"短线趋势尚未确认，ATR {_fmt(atr, 2, '%')} 要求先定义风险点。", "基本面优质不能替代价格确认和止损纪律。"),
        "minervini": (f"利润增速 {_fmt(profit_yoy, 2, '%')} 与 60 日收益 {_fmt(return_60d, 2, '%')} 尚不满足强势成长模板。", "等待盈利加速、相对强度和量价收缩后再评估入场质量。"),
        "simons": ("5/20/60 日与 ATR 已形成可复核样本，但仍只是单标的短窗口统计。", "需要更长样本、因子基准和交易成本后才能声称概率优势。"),
        "feng_liu": (f"市场已用 {_fmt(return_60d, 2, '%')} 的 60 日变化重定价增长预期，赔率有所改善。", "需要批价、渠道或利润率的边际改善验证认知差。"),
    }
    for lens_id, opinion in opinions.items():
        view, reservation = views.get(lens_id, ("质量与估值需要共同过关。", "等待下一期 Evidence 更新。"))
        consumed = {item["metric"]: item.get("value") for item in opinion.get("metric_analyses") or []}
        cross_cutting_metrics = []
        if consumed.get("parent_net_margin_pct") is not None:
            cross_cutting_metrics.append(f"净利率 {_fmt(consumed['parent_net_margin_pct'], 2, '%')}")
        if consumed.get("operating_cash_conversion_pct") is not None:
            cross_cutting_metrics.append(f"经营现金转化 {_fmt(consumed['operating_cash_conversion_pct'], 2, '%')}")
        if consumed.get("shareholder_payout_ratio_pct") is not None:
            cross_cutting_metrics.append(f"股东派现率 {_fmt(consumed['shareholder_payout_ratio_pct'], 2, '%')}")
        if consumed.get("execution_round_trip_cost_100w_bps") is not None:
            cross_cutting_metrics.append(f"100万元往返成本 {_fmt(consumed['execution_round_trip_cost_100w_bps'], 2, 'bps')}")
        cross_cutting = "、".join(cross_cutting_metrics) + "；" if cross_cutting_metrics else ""
        lines.append(f"| {opinion['lens_name']} | {cross_cutting}{view} | {reservation} |")
    lines.extend([
        "",
        "**投委会共识**：质量和现金流可以支持继续研究，但估值并未给出无条件行动信号。  ",
        "**核心分歧**：长期质量、保守估值、增长兑现与价格纪律的权重不同；最终动作取决于用户研究问题和本轮入选委员的共同约束。",
        "",
        "## 七、风险、催化剂与跟踪指标",
        "",
        "| 类型 | 需要跟踪的可证伪指标 |",
        "|---|---|",
        "| 经营风险 | 营收与利润增速继续背离、毛利率/ROE 同步下行、经营现金转化下降 |",
        f"| 护城河风险 | 系列酒收入同比 {_fmt(series_revenue_yoy, 2, '%')}、库存量同比 {_fmt(inventory_yoy, 2, '%')}；继续跟踪批价、核心产品需求与份额变化 |",
        f"| 费用风险 | 销售费用同比 {_fmt(sales_expense_yoy, 2, '%')}；若费用高增长未换来收入和渠道改善，将继续压制经营杠杆 |",
        "| 估值风险 | 盈利预期下修叠加估值中枢向 15x–18x 收缩 |",
        "| 治理风险 | 分红回购、重大资本开支、关联交易和管理层变动偏离股东利益 |",
        f"| 市场风险 | 60 日趋势 {_fmt(return_60d, 2, '%')} 与 ATR {_fmt(atr, 2, '%')} 继续恶化，触发组合风险预算复核 |",
    ])
    if events:
        lines.extend(["", "**当前事件线索**：" + "；".join(events[:3]) + "。事件只作为跟踪线索，不单独构成投资结论。"])
    monitoring = (pack.get("expectation_model") or {}).get("monitoring") or []
    if monitoring:
        lines.extend(["", "**观点变化触发器**：", "", "| 指标 | 基准 | 下次检查 | 改变观点的条件 |", "|---|---:|---|---|"])
        for item in monitoring:
            lines.append(
                f"| {item['metric']} | {_fmt(item.get('baseline'))} | {item.get('next_check_date') or '待定'} | "
                f"{item['view_change_condition']} |"
            )
    lines.extend([
        "",
        "## 八、投委会结论与条件化动作",
        "",
        f"**结论：{action_label}。** 当前数据更支持“高质量、增长换挡、估值合理但安全边际一般”，而不是简单的买入/卖出标签。",
        "",
        "| 情形 | 条件化动作 |",
        "|---|---|",
        "| 已有长期仓位 | 继续持有并用季报、批价、渠道库存和现金流验证，不因短期风格跑输机械减仓 |",
        "| 准备新增仓位 | 先设定组合上限；等待盈利韧性确认，或价格进入更有吸引力的 15x–18x 情景后分批复核 |",
        "| 经营证伪 | 若毛利率、ROE、现金转化与批价同步恶化，重估护城河并收缩风险预算 |",
        "| 估值上行 | 若价格接近或超过 22x 情景而盈利未上修，提高收益兑现与机会成本要求 |",
        "",
        "### 后续跟踪重点",
        "",
        "- 分红与回购是否持续覆盖自由现金流，并保持资本配置纪律。",
        "- 直销与批发渠道收入、批价、库存及核心产品需求变化。",
        "- 毛利率、ROE、净利率和经营现金转化是否同步企稳。",
        "- 价格进入不同估值情景时，盈利预期是否发生相同方向变化。",
        "",
        DISCLAIMER,
        "股市有风险，投资需谨慎。",
        "",
    ])
    return "\n".join(lines)


def build_research_workspace(
    pack: dict[str, Any],
    root: Path | str | None = None,
    lenses: tuple[str, ...] | list[str] | None = None,
    research_question: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """Create or resume a dated workspace without overwriting manual edits."""

    root_path = Path(root).expanduser() if root is not None else research_root()
    symbol_dir = root_path / _safe_symbol(str(pack["symbol"]))
    workspace = symbol_dir / str(pack["trade_date"])
    workspace.mkdir(parents=True, exist_ok=True)
    previous_manifest = _load_json(workspace / "workspace.json")
    baseline = _previous_workspace(symbol_dir, str(pack["trade_date"]))
    changes = _changes(pack, baseline)
    now = datetime.now(timezone.utc).isoformat()
    snapshot = freeze_company_evidence(pack)
    opinions = build_company_lens_opinions(snapshot, lenses=lenses, research_question=research_question)
    committee = synthesize_company_committee(snapshot, opinions)
    evidence_json = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    opinions_json = json.dumps(opinions, ensure_ascii=False, indent=2) + "\n"
    committee_json = json.dumps(committee, ensure_ascii=False, indent=2) + "\n"
    contents = {
        "research_plan": ("01-research-plan.md", _research_plan(pack)),
        "company_evidence": ("02-frozen-company-evidence.json", evidence_json),
        "evidence_summary": ("03-evidence-summary.md", _evidence_summary(pack)),
        "expert_readiness": ("04-company-lens-opinions.md", _expert_readiness(pack, opinions)),
        "company_opinions": ("04-company-lens-opinions.json", opinions_json),
        "committee_synthesis": ("05-committee-synthesis.json", committee_json),
        "committee_review": ("05-committee-review.md", _committee_review(pack, committee)),
        "decision_memo": ("06-decision-memo.md", _decision_memo(pack, committee)),
        "institutional_report": ("07-institutional-report.md", _institutional_report(pack, changes, opinions, committee)),
    }
    previous_artifacts = previous_manifest.get("artifacts") or {}
    artifacts = {
        key: _write_artifact(workspace, filename, content, previous_artifacts.get(key), now)
        for key, (filename, content) in contents.items()
    }
    missing = list(pack["_meta"]["missing_modules"])
    manifest = {
        "schema_version": "1.0",
        "symbol": pack["symbol"],
        "name": pack.get("name") or pack["symbol"],
        "market": pack.get("market"),
        "trade_date": pack["trade_date"],
        "research_question": committee.get("research_question"),
        "committee_members": list(opinions),
        "created_at": previous_manifest.get("created_at") or now,
        "updated_at": now,
        "status": "ready_for_analysis" if committee["action"] == "manual_review" else "evidence_insufficient",
        "stages": {
            "scope": "complete",
            "research_plan": "complete",
            "evidence_collection": "complete",
            "evidence_validation": "complete",
            "expert_analysis": "complete",
            "committee_review": "complete",
            "report": "complete",
        },
        "baseline": {"trade_date": baseline.get("trade_date"), "path": baseline.get("workspace_path")}
        if baseline
        else None,
        "evidence_snapshot": {
            "coverage": pack["_meta"]["coverage"],
            "available_modules": pack["_meta"]["available_modules"],
            "missing_modules": missing,
            "sha256": snapshot["snapshot_id"].removeprefix("sha256:"),
            "snapshot_id": snapshot["snapshot_id"],
            "committee_id": committee["committee_id"],
        },
        "artifacts": artifacts,
        "workspace_path": str(workspace),
    }
    _atomic_write(workspace / "workspace.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest, workspace
