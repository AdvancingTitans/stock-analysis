"""User-facing scenario workflows over deterministic Evidence Packs."""

from __future__ import annotations

from typing import Any

from .company_evidence import COMPANY_MODULES, build_company_evidence


def build_stock_review(symbol: str, trade_date: str) -> dict[str, Any]:
    return build_company_evidence(symbol, trade_date)


def render_stock_review(pack: dict[str, Any], title: str = "公司研究") -> str:
    meta = pack["_meta"]
    lines = [f"# {title}：{pack['name']}（{pack['symbol']}）", "", f"**证据日期**：{pack['trade_date']}", "", "## 结论状态", "", "证据不足，维持观察。该工作流仅整理可核验证据；不会把缺失的公司、治理或估值资料替换成主观评级。", "", "## Evidence Coverage", "", f"- 覆盖率：{meta['coverage']}%", f"- 可用模块：{', '.join(meta['available_modules']) or '无'}", f"- 缺失模块：{', '.join(meta['missing_modules']) or '无'}", ""]
    for code, label in COMPANY_MODULES.items():
        section = pack["modules"][code]
        lines.extend([f"## {code} {label}", ""])
        if section["evidence"]:
            for item in section["evidence"]:
                if item.get("metric"):
                    lines.append(f"- {item['metric']}：{item.get('value')}（{item.get('period') or item.get('source') or '公开数据'}）")
                elif item.get("title"):
                    suffix = f"（{item.get('tone') or '未分类'}）" if item.get("tone") else ""
                    lines.append(f"- {item['title']}{suffix}")
        else:
            lines.append("- 证据暂缺。")
        for gap in section["gaps"]:
            lines.append(f"- 缺口：{gap}")
        lines.append("")
    lines.extend(["## 反证与跟踪", "", "- 任何投资判断均应补充原始财报、监管披露、同业可比和管理层事件后再作出。", "- 当 C2/C3/C6 或 C7 的关键证据发生变化时，运行 `thesis-review` 重新核对。", "", "以上内容仅供研究参考，不构成任何投资建议。"])
    return "\n".join(lines)


def render_price_move(pack: dict[str, Any]) -> str:
    quote = pack.get("quote") or {}
    risk = pack["modules"]["C7"]
    events = pack["modules"]["C8"]
    lines = [f"# 异动归因：{pack['name']}（{pack['symbol']}）", "", f"**证据日期**：{pack['trade_date']}", "", "## 已验证市场事实", "", f"- 最新价：{quote.get('value') if quote.get('value') is not None else '暂缺'} {quote.get('currency') or ''}", f"- 报价来源：{quote.get('source') or '暂缺'}", "", "## 量价与事件证据", ""]
    for item in risk.get("evidence") or []:
        if item.get("metric"):
            lines.append(f"- {item['metric']}：{item.get('value')}")
        elif item.get("title"):
            lines.append(f"- 事件：{item['title']}（{item.get('tone') or '未分类'}）")
    for item in events.get("evidence") or []:
        if item.get("title"):
            lines.append(f"- 新闻脉冲：{item['title']}（{item.get('tone') or '未分类'}）")
    if not (risk.get("evidence") or events.get("evidence")):
        lines.append("- 证据暂缺。")
    lines.extend(["", "## 归因边界", "", "当前证据可确认价格、量价和公开事件样本；未取得指数/同行同步表现和原始公告前，不将事件断言为异动主因。", "", "## 是否触发论文重审", "", "- 是：若 C2/C3/C6/C7 的核心事实或原有证伪条件发生变化。", "- 否：仅凭单日价格波动或未交叉验证新闻不修改投资论文。", "", "以上内容仅供研究参考，不构成任何投资建议。"])
    return "\n".join(lines)


def render_earnings_review(pack: dict[str, Any]) -> str:
    facts = pack.get("financial_facts") or []
    lines = [f"# 财报复核：{pack['name']}（{pack['symbol']}）", "", f"**证据日期**：{pack['trade_date']}", "", "## 已披露结构化财务事实", ""]
    if facts:
        lines.extend(["| 指标 | 期间 | 数值 | 口径 | 来源 |", "|---|---|---:|---|---|"])
        for fact in facts:
            lines.append(f"| {fact['metric']} | {fact['period']} | {fact['value']} | {fact['accounting_basis']} | {fact['source']} |")
    else:
        lines.append("当前市场没有可核验的结构化财务事实；不将行情或新闻当作财报结论。")
    lines.extend(["", "## 需要补充后才能判断", "", "- 原始定期报告及其会计口径；", "- 同比/环比、分部和指引；", "- GAAP/Non-GAAP 调整、现金流与营运资本解释；", "- 市场预期与估值影响。", "", "## 论文影响", "", "运行 `thesis-review` 可把本次事实快照与持久化论文的上一版本对比；没有上述一手资料时，状态维持证据不足。", "", "以上内容仅供研究参考，不构成任何投资建议。"])
    return "\n".join(lines)
