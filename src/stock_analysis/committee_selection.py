"""Question-driven committee selection shared by every analysis entry point."""

from __future__ import annotations

DEFAULT_RESEARCH_QUESTION = "长期商业质量、护城河、现金流、资本配置、估值与风险"
LENS_SELECTION_ORDER = (
    "buffett", "munger", "duan_yongping", "zhang_kun", "graham", "klarman",
    "lynch", "o_neil", "wood", "dalio", "soros", "livermore", "minervini",
    "simons", "feng_liu",
)
LENS_TOPICS = {
    "buffett": ("长期", "质量", "护城河", "现金流", "资本配置", "治理", "估值", "分红"),
    "munger": ("长期", "质量", "护城河", "治理", "激励", "风险", "反向"),
    "duan_yongping": ("长期", "质量", "商业模式", "品牌", "消费者", "护城河", "现金流", "治理"),
    "zhang_kun": ("长期", "质量", "现金流", "竞争格局", "治理", "估值", "组合"),
    "graham": ("估值", "安全边际", "低估", "资产负债", "下行", "分红"),
    "klarman": ("估值", "安全边际", "绝对回报", "催化", "错定价", "下行", "风险"),
    "lynch": ("增长", "盈利", "收入", "产品", "用户", "估值", "景气"),
    "o_neil": ("增长", "盈利加速", "行业龙头", "趋势", "量价", "突破", "成交量"),
    "wood": ("创新", "研发", "渗透率", "技术", "增长", "长期", "产业"),
    "dalio": ("宏观", "周期", "利率", "流动性", "风险", "组合", "回撤", "波动"),
    "soros": ("预期差", "反身性", "政策", "趋势", "催化", "景气", "拐点"),
    "livermore": ("短线", "趋势", "量价", "突破", "止损", "交易", "仓位"),
    "minervini": ("短线", "趋势", "量价", "突破", "盈利加速", "强势", "止损"),
    "simons": ("量化", "样本", "因子", "交易成本", "波动", "回撤", "风险", "趋势"),
    "feng_liu": ("预期差", "赔率", "催化", "困境反转", "边际变化", "估值", "趋势"),
}

QUESTION_ALIASES = {
    "margin of safety": "安全边际",
    "capital allocation": "资本配置",
    "trading costs": "交易成本",
    "trading cost": "交易成本",
    "cash conversion": "现金流",
    "cash flow": "现金流",
    "price volume": "量价",
    "downside protection": "下行",
    "corporate governance": "治理",
    "competitive advantage": "护城河",
    "moat": "护城河",
    "valuation": "估值",
    "growth": "增长",
    "innovation": "创新",
    "momentum": "趋势",
    "drawdown": "回撤",
    "volatility": "波动",
    "liquidity": "流动性",
    "macro": "宏观",
    "risk": "风险",
    "business model": "商业模式",
    "market share": "市场份额",
    "pricing power": "定价权",
    "management team": "管理层",
    "buyback": "回购",
    "dividend": "分红",
    "earnings": "盈利",
    "revenue": "收入增长",
    "product mandate": "产品契约",
    "index methodology": "指数契约",
    "holdings": "持仓",
    "performance": "业绩",
    "tracking error": "跟踪",
    "premium discount": "折溢价",
    "management fee": "管理费",
    "catalyst": "催化",
    "现金创造": "现金流",
    "估值保护": "安全边际",
    "公司治理": "治理",
    "成交确认": "量价",
}

COMPANY_RESEARCH_MODULE_TOPICS = {
    "C1": ("商业模式", "生意", "客户", "产品定位", "怎么赚钱"),
    "C2": ("财务", "现金流", "利润", "盈利", "资产负债", "自由现金流", "roe"),
    "C3": ("增长", "景气", "盈利加速", "收入增长", "渗透率", "创新", "产业"),
    "C4": ("护城河", "竞争", "品牌", "市场份额", "定价权", "渠道"),
    "C5": ("管理层", "治理", "资本配置", "分红", "回购", "激励"),
    "C6": ("估值", "安全边际", "低估", "赔率", "市值", "目标价"),
    "C7": ("风险", "下行", "波动", "回撤", "流动性", "交易成本", "止损"),
    "C8": ("催化", "预期差", "反身性", "政策", "跟踪", "拐点"),
}
FUND_RESEARCH_MODULE_TOPICS = {
    "F1": ("产品契约", "产品定位", "指数契约", "复制", "基准"),
    "F2": ("持仓", "成分", "暴露", "集中度", "行业", "组合"),
    "F3": ("业绩", "收益", "趋势", "景气", "增长"),
    "F4": ("跟踪", "折溢价", "交易", "流动性", "交易成本"),
    "F5": ("估值", "安全边际", "低估", "底层"),
    "F6": ("风险", "回撤", "波动", "beta", "压力"),
    "F7": ("治理", "规模", "管理费", "基金经理", "申购", "赎回", "运营"),
    "F8": ("催化", "调仓", "宏观", "周期", "政策", "跟踪条件"),
}


def _normalize_question(question: str) -> str:
    normalized = question.lower()
    matched_topics = [topic for alias, topic in QUESTION_ALIASES.items() if alias in normalized]
    return " ".join((normalized, *matched_topics))


def relevant_research_modules(
    research_question: str | None,
    *,
    asset_type: str,
) -> tuple[str, ...]:
    """Map an explicit research question to modules before lens aggregation."""

    topics = (
        FUND_RESEARCH_MODULE_TOPICS
        if asset_type == "fund"
        else COMPANY_RESEARCH_MODULE_TOPICS
    )
    if not research_question:
        return tuple(topics)
    question = _normalize_question(research_question)
    matched = tuple(
        module
        for module, keywords in topics.items()
        if any(keyword in question for keyword in keywords)
    )
    return matched


def select_committee(research_question: str | None, *, asset_type: str = "company") -> tuple[str, ...]:
    question = _normalize_question(research_question or DEFAULT_RESEARCH_QUESTION)
    if asset_type == "fund" and not research_question:
        question = "指数 行业 景气 估值 波动 回撤 组合 风险 交易成本 趋势"
    scores = {
        lens_id: sum(3 if topic in question else 0 for topic in topics)
        for lens_id, topics in LENS_TOPICS.items()
    }
    boosts = (
        (("短线", "趋势", "量价", "突破", "止损"), ("livermore", "o_neil", "minervini", "simons"), 8),
        (("长期", "护城河", "现金流", "治理", "资本配置"), ("buffett", "munger", "duan_yongping", "zhang_kun"), 8),
        (("估值", "安全边际", "低估", "下行"), ("graham", "klarman"), 7),
        (("增长", "景气", "盈利", "产业", "创新"), ("lynch", "o_neil", "wood", "soros"), 6),
        (("风险", "回撤", "波动", "组合", "宏观"), ("dalio", "simons", "klarman"), 6),
    )
    for tokens, lenses, increment in boosts:
        if any(token in question for token in tokens):
            for lens_id in lenses:
                scores[lens_id] += increment
    ranked = sorted(LENS_SELECTION_ORDER, key=lambda lens_id: (-scores[lens_id], LENS_SELECTION_ORDER.index(lens_id)))
    return tuple(ranked[:6])
