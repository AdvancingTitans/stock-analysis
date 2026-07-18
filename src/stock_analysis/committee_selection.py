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


def select_committee(research_question: str | None, *, asset_type: str = "company") -> tuple[str, ...]:
    question = (research_question or DEFAULT_RESEARCH_QUESTION).lower()
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
