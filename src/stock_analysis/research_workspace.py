"""Recoverable company-research workspace over a Company Evidence Pack."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .committee_selection import DEFAULT_RESEARCH_QUESTION
from .company_evidence import COMPANY_MODULES
from .company_lens import (
    build_company_lens_opinions,
    freeze_company_evidence,
    synthesize_company_committee,
)
from .research_claims import build_claim_audit_artifacts
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


def _claim_lines(claims: list[dict[str, Any]]) -> list[str]:
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


def _claims_by_section(claims: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    section_by_scope = {
        "C1": 2,
        "C2": 3,
        "C3": 3,
        "C4": 2,
        "C5": 4,
        "C6": 5,
        "C7": 7,
        "C8": 7,
        "business_quality": 2,
        "financial_quality": 3,
        "growth_quality": 3,
        "governance": 4,
        "capital_allocation": 4,
        "valuation": 5,
        "risk": 7,
        "catalyst": 7,
    }
    grouped = {section: [] for section in range(2, 8)}
    for claim in claims:
        section = section_by_scope.get(str(claim.get("scope") or ""), 6)
        grouped[section].append(claim)
    return grouped


def _institutional_report(
    pack: dict[str, Any],
    changes: list[str],
    opinions: dict[str, dict[str, Any]],
    committee: dict[str, Any],
) -> str:
    """Render only committee-published claims as required by plan sections 3-5."""

    del changes
    publication_status = str(committee.get("publication_status") or "publish")
    title = f"# {pack['name']}（{pack['symbol']}）个股深度研究报告 · 投委会"
    if publication_status == "block_report":
        reasons = [
            str(issue["reason"])
            for issue in (committee.get("safety_gate") or {}).get("issues") or []
            if issue.get("decision") == "block_report"
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
    grouped = _claims_by_section(claims)
    committee_names = "、".join(str(opinion["lens_name"]) for opinion in opinions.values())
    lines = [
        title,
        "",
        f"**报告日期**：{pack['trade_date']}  ",
        f"**研究问题**：{committee.get('research_question') or DEFAULT_RESEARCH_QUESTION}  ",
        f"**分析模式**：动态投委会（{committee_names}）",
        "",
        "## 一、执行摘要",
        "",
    ]
    directional_claims = [claim for claim in claims if claim.get("direction") != "neutral"]
    lines.extend(_claim_lines(directional_claims or claims[:3]))
    sections = {
        2: "## 二、行情、商业质量与核心矛盾",
        3: "## 三、财务质量、增长与现金流",
        4: "## 四、治理与资本配置",
        5: "## 五、估值与情景分析",
        6: "## 六、投委会审议",
        7: "## 七、风险、催化剂与跟踪指标",
    }
    for section, heading in sections.items():
        lines.extend([heading, ""])
        lines.extend(_claim_lines(grouped[section]))
    lines.extend(["## 八、投委会结论与条件化动作", ""])
    if publication_status == "block_action":
        action_reasons = [
            str(issue["reason"])
            for issue in (committee.get("safety_gate") or {}).get("issues") or []
            if issue.get("decision") == "block_action"
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
    audit_artifacts = build_claim_audit_artifacts(snapshot, opinions, committee)
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
        "status": {
            "block_report": "blocked_report",
            "block_action": "action_blocked",
        }.get(committee["publication_status"], "ready_for_analysis"),
        "publication_status": committee["publication_status"],
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
