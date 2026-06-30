from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_documents_young_style_entry_contracts():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for text in (skill, readme):
        assert "--market stock --symbol" in text
        assert "--market fund --symbol" in text
        assert "确定性" in text
        assert "浏览器" in text

    assert "M1-M7" in readme


def test_skill_documents_user_triggered_complete_holding_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, output_discipline, portfolio_template):
        assert "用户主动" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text
        assert "只提问一次" in text
        assert "普通市场复盘报告" in text

    assert "没有主动提供持仓信息的用户不会被打扰" in skill
    assert "缺失任意一项，不得进行收益计算" in skill
    assert "没有年份" in skill and "当前年份" in skill
    assert "人民币、港币还是美元" in skill


def test_skill_documents_investment_memory_first_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "投资记忆优先" in text
        assert "~/.young_stock/profile.json" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text

    assert "默认读取投资记忆" in skill
    assert "投资记忆不存在" in skill
    assert "投资记忆有但信息不完整" in skill
    assert "保存到本地投资记忆" in skill
    assert "投资记忆已保存本地" in skill
    assert "如需清空投资记忆请反馈" in skill
    assert "除非用户明确已经清空过投资记忆" in skill

    assert "不得把本地已保存 profile 视为用户本轮主动触发持仓分析" not in skill
    assert "已保存持仓只在用户本轮主动触发持仓分析时使用" not in skill


def test_skill_documents_new_user_holdings_override_saved_memory_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "新提供的信息与之前保存的投资记忆不一致" in text
        assert "优先以用户新提供的信息为准" in text
        assert "覆盖写入投资记忆" in text
        assert "确认信息完整性后" in text

    assert "不完整的新信息不得覆盖已有完整投资记忆" in skill


def test_skill_documents_young_investor_lens_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    expected_lenses = (
        "buffett",
        "munger",
        "graham",
        "klarman",
        "lynch",
        "o_neil",
        "wood",
        "dalio",
        "soros",
        "livermore",
        "minervini",
        "simons",
        "duan_yongping",
        "zhang_kun",
        "feng_liu",
    )
    for lens in expected_lenses:
        assert lens in skill

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "用户明确提出想用哪位投资专家的风格" in text
        assert "完全以相关专家的视角输出报告" in text
        assert "不得只在结尾追加专家点评" in text
        assert "单专家视角不触发 M7" in text
        assert "不得模仿身份声明或虚构专家发言" in text

    assert "15 个 young-stock-cli 投资专家 lens" in skill
    assert "专家名称、英文名、中文名、别名或 lens id" in skill
    assert "## {专家中文名}持仓建议与风险提示" in skill
    assert "交易计划草案" in skill
    assert "组合经理最终意见" in skill
